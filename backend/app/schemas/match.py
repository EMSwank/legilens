from uuid import UUID
from decimal import Decimal
from typing import Literal, Annotated
from pydantic import BaseModel, Field


class SnippetItem(BaseModel):
    kind: Literal["snippet"] = "snippet"
    co_context_before: str
    co_match: str
    co_context_after: str
    source_context_before: str
    source_match: str
    source_context_after: str


class GhostMessage(BaseModel):
    kind: Literal["ghost"] = "ghost"
    message: Literal["Source text unavailable for extraction"]


SnippetOrGhost = Annotated[SnippetItem | GhostMessage, Field(discriminator="kind")]

SnippetStatus = Literal["pending", "verified", "source_verified_text_missing"]


class MatchOut(BaseModel):
    id: UUID
    matched_bill_title: str | None
    matched_state: str | None
    similarity_score: Decimal
    snippet_status: SnippetStatus
    matched_snippets: list[SnippetOrGhost] | None

    model_config = {"from_attributes": True}
