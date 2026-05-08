from uuid import UUID
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel


class ISTScoreOut(BaseModel):
    source_authenticity_score: Decimal
    copycat_alert: bool
    analyzed_at: datetime

    model_config = {"from_attributes": True}


class FrictionTagOut(BaseModel):
    tag_type: str
    confidence: Decimal | None

    model_config = {"from_attributes": True}


class BillListItem(BaseModel):
    id: UUID
    bill_number: str
    title: str
    state: str
    session: str
    status: str | None
    copycat_alert: bool | None

    model_config = {"from_attributes": True}


class BillDetail(BaseModel):
    id: UUID
    bill_number: str
    title: str
    description: str | None
    state: str
    session: str
    status: str | None
    sponsors: dict | None
    ist_score: ISTScoreOut | None
    tags: list[FrictionTagOut]

    model_config = {"from_attributes": True}
