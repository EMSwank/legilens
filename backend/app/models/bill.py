from uuid import uuid4, UUID as PyUUID
from datetime import datetime
from sqlalchemy import String, Boolean, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID as PgUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class Bill(Base):
    __tablename__ = "bills"

    id: Mapped[PyUUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    legiscan_id: Mapped[int] = mapped_column(unique=True, nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    session: Mapped[str] = mapped_column(Text, nullable=False)
    bill_number: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    full_text: Mapped[str | None] = mapped_column(Text)
    sponsors: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str | None] = mapped_column(Text)
    is_corpus_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    last_updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
