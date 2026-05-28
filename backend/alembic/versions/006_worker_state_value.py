"""add value column to worker_state

Revision ID: 006
Revises: 005
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "worker_state",
        sa.Column("value", sa.Text(), nullable=True),
    )


def downgrade():
    op.drop_column("worker_state", "value")
