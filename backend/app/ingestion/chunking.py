from dataclasses import dataclass
from typing import Any

import hashlib
import tiktoken

from backend.app.models.document_chunk import DocumentChunk


@dataclass(frozen=True, slots=True)
class PreparedChunk:
    chunk_index: int
    page_number: int | None
    section_title: str | None
    content: str
    normalized_content: str
    content_hash: str
    token_count: int
    metadata: dict[str, Any]


def hash_text(text: str) -> str:
    return str(hashlib.sha256(text.encode("utf-8")).hexdigest())


def get_page_number(chunk) -> int | None:
    page_numbers: list[int] = []

    for item in chunk.meta.doc_items:
        for prov in item.prov:
            page_numbers.append(prov.page_no)

    return min(page_numbers) if page_numbers else None


def get_section_title(chunk) -> str | None:
    headings = chunk.meta.headings or []

    if not headings:
        return None

    return " > ".join(headings)[:500]