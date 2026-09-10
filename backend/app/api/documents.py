

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Form, UploadFile, status
from fastapi.params import File


from backend.app.core.dependencies import SettingsDep
from backend.app.core.errors import ApplicationError
from backend.app.db.session import SessionDep
from backend.app.ingestion.embeddings import create_embedding_provider
from backend.app.ingestion.converter import DocumentValidationError
from backend.app.schemas.document import DocumentUploadResponse
from backend.app.services.document_ingestion import ingest_document


router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: Annotated[UploadFile, File()],
    # user: CurrentUserDep,
    settings: SettingsDep, 
    # session: SessionDep,
    thread_id: Annotated[UUID | None, Form()] = None,
    ) -> DocumentUploadResponse:
    
    
    data = await file.read(settings.max_upload_size_mb * 1024 * 1024 + 1)
    try:
        pass
        provider = create_embedding_provider(settings)
        result = await ingest_document(
            # session,
            # owner_id=user.id,
            thread_id=thread_id,
            filename=file.filename or "upload",
            mime_type=file.content_type or "application/octet-stream",
            data=data,
            settings=settings,
            embedding_provider=provider,
        )
    # except DocumentValidationError as exc:
    #     raise ApplicationError(422, "invalid_document", str(exc)) from exc
    # except IngestionUnavailableError as exc:
    #     raise ApplicationError(503, "ingestion_unavailable", str(exc)) from exc
    # return DocumentUploadResponse(
    #     document=DocumentPublic.model_validate(result.document),
    #     duplicate=result.duplicate,
    #     chunks_created=result.chunks_created,
    # )
    except DocumentValidationError as exc:
        raise ApplicationError(422, "invalid_document", str(exc)) from exc
    