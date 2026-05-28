"""add text-fetch tracking columns to bills + match_type to similarity_matches

Revision ID: 005
Revises: 004
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "bills",
        sa.Column("text_fetch_status", sa.String(16), nullable=False, server_default="queued"),
    )
    op.add_column(
        "bills",
        sa.Column("text_fetched_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "bills",
        sa.Column("text_fetch_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "bills",
        sa.Column("text_doc_id", sa.Integer(), nullable=True),
    )
    op.execute(
        """
        UPDATE bills SET text_fetch_status='done' WHERE full_text IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX ix_bills_text_fetch_queue
            ON bills (state, legiscan_id)
            WHERE text_fetch_status = 'queued' AND full_text IS NULL AND text_fetch_attempts < 3
        """
    )

    op.add_column(
        "similarity_matches",
        sa.Column("match_type", sa.String(16), nullable=False, server_default="cross_state"),
    )
    op.create_index("ix_similarity_matches_match_type", "similarity_matches", ["match_type"])


def downgrade():
    op.drop_index("ix_similarity_matches_match_type", table_name="similarity_matches")
    op.drop_column("similarity_matches", "match_type")
    op.execute("DROP INDEX IF EXISTS ix_bills_text_fetch_queue")
    op.drop_column("bills", "text_doc_id")
    op.drop_column("bills", "text_fetch_attempts")
    op.drop_column("bills", "text_fetched_at")
    op.drop_column("bills", "text_fetch_status")
