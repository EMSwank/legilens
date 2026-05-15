from datetime import datetime
from sqlalchemy import DateTime, func, String
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class DatasetHash(Base):
    __tablename__ = "dataset_hashes"

    session_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
