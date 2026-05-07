from uuid import uuid4
from datetime import datetime
from sqlalchemy import DateTime, func, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ARRAY, BIGINT
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class MinHashSignature(Base):
    __tablename__ = "minhash_signatures"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    bill_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("bills.id"), nullable=False)
    signature: Mapped[list[int]] = mapped_column(ARRAY(BIGINT), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
