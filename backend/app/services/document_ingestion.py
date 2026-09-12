from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.config import Settings, get_settings
from backend.app.ingestion.chunking import PreparedChunk, get_page_number, get_section_title, hash_text
from backend.app.ingestion.embeddings import EmbeddingProvider, validate_embeddings
from backend.app.ingestion.converter import convert_document, validate_upload
from backend.app.ingestion.normalization import content_hash, normalize_text
from backend.app.models.document import Document, DocumentStatus
from docling_core.transforms.chunker.tokenizer.openai import OpenAITokenizer
from docling.chunking import HybridChunker
import tiktoken
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.ingestion_job import IngestionJob, IngestionJobStatus
from backend.app.repositories.documents import find_document_by_hash
from backend.app.utils.tools import save_json

@dataclass(frozen=True, slots=True)
class IngestionResult:
    """Document ingestion result including owner-scoped duplicate state."""
    document: Document
    duplicate: bool
    chunks_created: int

class IngestionUnavailableError(ValueError):
    """Raised after an indexing failure has been recorded durably."""

async def ingest_document(
    session: AsyncSession,
    *,
    owner_id: UUID,
    thread_id: UUID,
    filename: str,
    mime_type: str,
    data: bytes,
    settings: Settings | None = None,
    embedding_provider: EmbeddingProvider,
    display_name: str | None = None,
    stored_mime_type: str | None = None,
    source_metadata: dict[str, Any] | None = None,
) -> IngestionResult:
    
    # ----------------- 1. Validate the document ----------------- 
    extension = validate_upload(
        filename,
        mime_type,
        data,
        max_size_bytes=settings.max_upload_size_mb * 1024 * 1024,
    )
    
    # -----------------  2. Convert the Bytes to a DoclingDocument ----------------- 
    docling_document = convert_document(extension, filename, data, settings.enable_ocr)
    
    # ----------------- 3. Deduplicate Document -----------------
    binary_hash = docling_document.export_to_dict().get("origin", {}).get("binary_hash")
    if binary_hash is None:
        raise ValueError("Document origin is missing binary_hash")

    document_hash = str(binary_hash)
    duplicate = await find_document_by_hash(session, owner_id, document_hash)
    if duplicate is not None:
        return IngestionResult(duplicate, duplicate=True, chunks_created=0)
        
    # ----------------- 4. Prepare the Document for Ingestion -----------------
    safe_filename = Path(filename).name[:255]
    
    metadata = dict(source_metadata or {})
    metadata.update({"page_count": len(docling_document.pages), "file_extension": extension})
    
    document = Document(
        owner_id=owner_id,
        thread_id=thread_id,
        original_filename=safe_filename,
        display_name=(display_name or safe_filename)[:255],
        mime_type=(stored_mime_type or mime_type).lower(),
        file_size=len(data),
        content_hash=str(document_hash),
        status=DocumentStatus.PROCESSING,
        metadata_json=metadata,
    )
    session.add(document)
    
    # ----------------- 5. Chunking  ----------------- 
    encoding = tiktoken.encoding_for_model("gpt-4o")
    
    tokenizer = OpenAITokenizer(
        tokenizer=encoding,
        max_tokens=512,
    )
    
    chunker = HybridChunker(tokenizer=tokenizer)
    raw_chunks = list(
        chunker.chunk(dl_doc=docling_document)
    )
    
    prepared_chunks: list[PreparedChunk] = []
    for index, chunk in enumerate(raw_chunks):
        contextualized_text = chunker.contextualize(chunk)
        normalized_text = normalize_text(contextualized_text)
        
        prepared_chunks.append(
            PreparedChunk(
                chunk_index=index,
                page_number=get_page_number(chunk),
                section_title=get_section_title(chunk),
                content=contextualized_text,
                normalized_content=normalized_text,
                content_hash=hash_text(normalized_text),
                token_count=len(
                    encoding.encode(normalized_text)
                ),
                metadata={
                    "headings": chunk.meta.headings or [],
                    "filename": (
                        chunk.meta.origin.filename
                        if chunk.meta.origin
                        else None
                    ),
                    "mimetype": (
                        chunk.meta.origin.mimetype
                        if chunk.meta.origin
                        else None
                    ),
                },
            )
        )
    # # ----------------- 6. Storing Ingestion Job -----------------
    try:
        await session.flush() # sends pending SQL statements to the database without committing the transaction.
        job = IngestionJob(
            document_id=document.id,
            owner_id=owner_id,
            status=IngestionJobStatus.RUNNING,
            details_json={"chunks": len(raw_chunks)},
        )
        session.add(job) # Put the job into SqlAlchemy's session, but it won't be in the database until we commit.
        await session.commit() # the ingestion_job row is now durably stored in the database with status RUNNING.
    except IntegrityError:
        await session.rollback()
        duplicate = await find_document_by_hash(session, owner_id, document_hash)
        if duplicate is not None: # Race condition: another ingestion job for the same document hash was created after we checked for duplicates but before we committed our own ingestion job.
            return IngestionResult(duplicate, duplicate=True, chunks_created=0)
        raise
    
    # # ----------------- 6. Embedding and storing prepared chunks -----------------
    try:
        # Embed all chunks in one batch
        vectors = await embedding_provider.embed_documents(
            [
                chunk.normalized_content
                for chunk in prepared_chunks
            ]
        )

        validate_embeddings(
            vectors,
            len(prepared_chunks),
            settings.embedding_dimension,
        )

        # Build ORM objects
        db_chunks = [
            DocumentChunk(
                document_id=document.id,
                owner_id=owner_id,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                section_title=chunk.section_title,
                content=chunk.content,
                normalized_content=chunk.normalized_content,
                content_hash=chunk.content_hash,
                token_count=chunk.token_count,
                embedding=vector,
                metadata_json={
                    **(source_metadata or {}),
                    **chunk.metadata,
                },
            )
            for chunk, vector in zip(
                prepared_chunks,
                vectors,
                strict=True,
            )
        ]

        # Insert all chunks
        session.add_all(db_chunks)

        # Update ingestion status
        document.status = DocumentStatus.COMPLETED
        job.status = IngestionJobStatus.COMPLETED

        await session.commit()

    except Exception as exc:
        await session.rollback()
        failed_document = await session.get(
            Document,
            document.id,
        )
        failed_job = await session.get(
            IngestionJob,
            job.id,
        )
        if failed_document is not None:
            failed_document.status = DocumentStatus.FAILED
        if failed_job is not None:
            failed_job.status = IngestionJobStatus.FAILED
            failed_job.error_message = "Document indexing failed"
        await session.commit()
        raise IngestionUnavailableError(
            "Document indexing failed"
        ) from exc


    await session.refresh(document)

    return IngestionResult(
        document=document,
        duplicate=False,
        chunks_created=len(prepared_chunks),
    )
    
    
    
