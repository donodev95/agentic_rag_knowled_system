import asyncio
from pathlib import Path
from uuid import UUID
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from backend.app.core.config import get_settings
from backend.app.ingestion.embeddings import create_embedding_provider
from backend.app.services.document_ingestion import ingest_document

async def main() -> None:
    settings = get_settings()

    engine = create_async_engine(
        settings.database_url,
        echo=True,
    )

    SessionLocal = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    root = Path.cwd()
    # filename = "5.docx"
    # filename = "test_text.txt"
    filename = "WSNZ_Construction_Priority-Plan_v7-FA-web.pdf"

    file_path = root / "data" / filename
    
    
    with file_path.open("rb") as f:
        data = f.read()

    provider = create_embedding_provider(settings)
    async with SessionLocal() as session:
        result = await ingest_document(
            session,
            owner_id=UUID("8212e6f0-dfaf-48ce-a5cd-0ee4d3999eca"),
            thread_id=None,
            filename=filename,
            mime_type="application/pdf",
            data=data,
            settings=settings,
            embedding_provider=provider,  # Replace with your actual embedding provider
        )

    print(f"Document ingested successfully: {result}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())