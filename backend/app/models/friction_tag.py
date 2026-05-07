from uuid import uuid4, UUID as PyUUID
from decimal import Decimal
from sqlalchemy import Text, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class FrictionTag(Base):
    __tablename__ = "friction_tags"

    id: Mapped[PyUUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    bill_id: Mapped[PyUUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("bills.id", ondelete="CASCADE"), nullable=False, index=True)
    tag_type: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    evidence: Mapped[str | None] = mapped_column(Text)
