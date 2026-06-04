from datetime import datetime
from typing import Literal
from pydantic import BaseModel


class StateCoverage(BaseModel):
    state: str
    fetchable: int
    with_sig: int
    status: Literal["complete", "in_progress", "not_started"]


class CoverageOut(BaseModel):
    status: Literal["ready", "pending"]
    as_of: datetime | None
    matchable_pct: float | None
    states: list[StateCoverage]
