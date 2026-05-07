from uuid import uuid4, UUID as PyUUID
from datetime import datetime
from sqlalchemy import DateTime, func, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PgUUID, ARRAY, BIGINT
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class MinHashSignature(Base):
    __tablename__ = "minhash_signatures"

    id: Mapped[PyUUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    bill_id: Mapped[PyUUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("bills.id", ondelete="CASCADE"), nullable=False, index=True)
    signature: Mapped[list[int]] = mapped_column(ARRAY(BIGINT), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
