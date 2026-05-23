"""add worker_state table for Postgres-backed bootstrap debounce

Revision ID: 003
Revises: 002
Create Date: 2026-05-23
"""
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE worker_state (
            key VARCHAR(64) PRIMARY KEY,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS worker_state")
