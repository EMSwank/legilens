"""add dataset_hashes table

Revision ID: 002
Revises: 001
Create Date: 2026-05-15
"""
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE dataset_hashes (
            session_id INTEGER PRIMARY KEY,
            hash VARCHAR(64) NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS dataset_hashes")
