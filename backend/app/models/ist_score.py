from uuid import uuid4, UUID as PyUUID
from datetime import datetime
from decimal import Decimal
from sqlalchemy import DateTime, Boolean, Numeric, func, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class ISTScore(Base):
    __tablename__ = "ist_scores"

    id: Mapped[PyUUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    bill_id: Mapped[PyUUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("bills.id", ondelete="CASCADE"), nullable=False, index=True)
    source_authenticity_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    copycat_alert: Mapped[bool] = mapped_column(Boolean, nullable=False)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
