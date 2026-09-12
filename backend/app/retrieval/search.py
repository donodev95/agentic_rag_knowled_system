"""Database-native owner-scoped pgvector similarity search."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import cast, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.document import Document, DocumentStatus
from backend.app.models.document_chunk import DocumentChunk


@dataclass(frozen=True, slots=True) # frozen=True makes the return data immutable, slots=True makes the return data more memory efficient.
class SearchHit:
    """Internal typed result returned by the vector query."""

    chunk: DocumentChunk
    document_name: str
    score: float


async def search_chunks(
    session: AsyncSession,
    *,
    owner_id: UUID,
    query_vector: list[float],
    top_k: int,
    score_threshold: float,
    thread_id: UUID | None = None,
    include_global: bool = False,
    metadata: dict[str, Any] | None = None,
) -> list[SearchHit]:
    """
    Rank chunks in PostgreSQL after applying tenant and optional scope filters.
    - Among all the chunks that belong to the owner, rank them by their similarity to the query vector.
    Tasks:

    
    """   
    
    distance = DocumentChunk.embedding.cosine_distance(query_vector) # Produces the distance betwee n the query vector and the embedding vector, the smaller the distance, the more similar the vectors are.
    score = (1 - distance).label("similarity_score") # convert distance to similarity score, the larger the score, the more similar the vectors are.
    statement = ( # SQLAlchemy statement to select the chunks that belong to the owner and have a similarity score above the threshold, and sort them by similarity score.
        select(DocumentChunk, Document.display_name, score)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            DocumentChunk.owner_id == owner_id,
            Document.owner_id == owner_id,
            Document.status == DocumentStatus.COMPLETED,
            distance <= 1 - score_threshold,
        )
        .order_by(distance)
        .limit(top_k)
    )
    if thread_id is not None:
        thread_filter = (
            or_(DocumentChunk.thread_id == thread_id, DocumentChunk.thread_id.is_(None))
            if include_global
            else DocumentChunk.thread_id == thread_id
        )
        statement = statement.where(thread_filter)
    if metadata: # Metadata filter: If metadata is provided, filter the chunks by the metadata. This is useful for filtering by chunk type, source, etc. Eg: only return chunks that have year 2025, source from google drive, etc
        metadata_column = (
            cast(DocumentChunk.metadata_json, JSONB)
            if session.bind is not None and session.bind.dialect.name == "postgresql"
            else DocumentChunk.metadata_json
        )
        statement = statement.where(metadata_column.contains(metadata))

    rows = (await session.execute(statement)).all() # executes the full sqlAlchemy statement
    seen: set[UUID] = set()
    hits: list[SearchHit] = []
    for chunk, document_name, similarity_score in rows:
        if chunk.id in seen:
            continue
        seen.add(chunk.id)
        hits.append(
            SearchHit(chunk, str(document_name), max(0.0, min(1.0, float(similarity_score))))
        )
    return hits
