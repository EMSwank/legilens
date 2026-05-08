from uuid import UUID
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel


class SnippetItem(BaseModel):
    co_context_before: str
    co_match: str
    co_context_after: str
    source_context_before: str
    source_match: str
    source_context_after: str


class GhostMessage(BaseModel):
    message: Literal["Source text unavailable for extraction"]


class MatchOut(BaseModel):
    id: UUID
    matched_bill_title: str | None
    matched_state: str | None
    similarity_score: Decimal
    snippet_status: str
    matched_snippets: list[SnippetItem | GhostMessage] | None

    model_config = {"from_attributes": True}
