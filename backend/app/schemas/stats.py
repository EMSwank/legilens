from pydantic import BaseModel


class StatsOut(BaseModel):
    total_co_bills: int
    copycat_alerts: int
    bills_analyzed: int
    related_co_bills: int


class TagCountOut(BaseModel):
    tag_type: str
    count: int
