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
    """Synthesized at read time by the router when snippet_status == 'source_verified_text_missing'.

    GhostMessages are never stored in the DB. The evidence worker sets
    matched_snippets=None and snippet_status='source_verified_text_missing'; the
    router converts that state into a GhostMessage for the API response. The
    'kind' field is required for Pydantic v2 discriminated-union serialization.
    """

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
    match_type: Literal["cross_state", "co_internal"]
    matched_bill_id: UUID
    matched_bill_number: str | None

    model_config = {"from_attributes": True}
