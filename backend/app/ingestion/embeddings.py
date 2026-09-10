
from asyncio import Protocol
import asyncio
import math
from typing import Any

from backend.app.core.config import Settings


class EmbeddingProvider(Protocol):
    """Batch embedding interface used by ingestion and retrieval."""

    dimension: int

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed text values in input order."""
        ...


class OllamaEmbeddingProvider:
    """Generate embeddings using Ollama's OpenAI-compatible API."""

    def __init__(
        self,
        model: str,
        dimension: int,
        base_url: str,
    ) -> None:
        from openai import AsyncOpenAI

        self.dimension = dimension
        self.model = model

        self.client: Any = AsyncOpenAI(
            api_key="ollama",  # required by SDK, ignored by Ollama
            base_url=base_url,
            max_retries=3,
            timeout=120,
        )

    async def embed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        """Embed a batch using local Ollama."""

        async with asyncio.timeout(180):
            response = await self.client.embeddings.create(
                model=self.model,
                input=texts,
                dimensions=self.dimension,
            )

        vectors = [
            item.embedding
            for item in sorted(
                response.data,
                key=lambda item: item.index,
            )
        ]

        validate_embeddings(
            vectors,
            len(texts),
            self.dimension,
        )

        return vectors

def validate_embeddings(vectors: list[list[float]], expected_count: int, dimension: int) -> None:
    """Reject missing, non-finite, or incorrectly sized vectors before database writes."""
    if len(vectors) != expected_count:
        raise ValueError("Embedding provider returned the wrong number of vectors")
    if any(len(vector) != dimension for vector in vectors):
        raise ValueError("Embedding provider returned an unexpected dimension")
    if any(not math.isfinite(value) for vector in vectors for value in vector):
        raise ValueError("Embedding provider returned a non-finite value")


def create_embedding_provider(
    settings: Settings,
) -> EmbeddingProvider:
    """Instantiate the configured provider only when needed."""

    if settings.embedding_provider == "ollama":
        if not settings.embedding_model:
            raise ValueError(
                "Ollama embedding model is required"
            )

        return OllamaEmbeddingProvider(
            model=settings.embedding_model,
            dimension=settings.embedding_dimension,
            base_url=(
                settings.embedding_base_url
                or "http://host.docker.internal:11434/v1"
            ),
        )

    raise ValueError(
        f"Unsupported embedding provider: "
        f"{settings.embedding_provider}"
    )
