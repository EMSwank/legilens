from datetime import datetime
from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class WorkerState(Base):
    """Single-row key/value state for the worker, e.g. bootstrap debounce.

    Postgres-backed so it survives Redis restarts; PR #35 made the same move
    for dataset dedup and the bootstrap debounce had the same fragility.
    """

    __tablename__ = "worker_state"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
