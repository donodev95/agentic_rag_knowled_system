
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.document import Document

async def find_document_by_hash(
    session: AsyncSession, owner_id: UUID, document_hash: str
) -> Document | None:
    """Find an owner's existing normalized document without crossing tenants."""
    statement = select(Document).where(
        Document.owner_id == owner_id,
        Document.content_hash == document_hash,
    )
    return (await session.execute(statement)).scalar_one_or_none()