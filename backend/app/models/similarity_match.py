from uuid import uuid4
from decimal import Decimal
from sqlalchemy import String, Text, Numeric, CheckConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

SNIPPET_STATUSES = ("pending", "verified", "source_verified_text_missing")


class SimilarityMatch(Base):
    __tablename__ = "similarity_matches"
    __table_args__ = (
        CheckConstraint(
            f"snippet_status IN {SNIPPET_STATUSES}",
            name="chk_snippet_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    bill_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("bills.id"), nullable=False)
    matched_bill_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("bills.id"), nullable=False)
    matched_state: Mapped[str | None] = mapped_column(String(2))
    similarity_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    algorithm: Mapped[str] = mapped_column(Text, nullable=False, default="minhash")
    matched_bill_title: Mapped[str | None] = mapped_column(Text)
    matched_bill_url: Mapped[str | None] = mapped_column(Text)
    matched_snippets: Mapped[list | None] = mapped_column(JSONB)
    snippet_status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
