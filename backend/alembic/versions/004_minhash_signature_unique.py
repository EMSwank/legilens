"""enforce UNIQUE constraint on minhash_signatures.bill_id

Revision ID: 004
Revises: 003
Create Date: 2026-05-27
"""
from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        DELETE FROM minhash_signatures
        WHERE id NOT IN (
            SELECT DISTINCT ON (bill_id) id
            FROM minhash_signatures
            ORDER BY bill_id, computed_at DESC
        )
    """)
    op.execute("""
        ALTER TABLE minhash_signatures
        ADD CONSTRAINT uq_minhash_signatures_bill_id UNIQUE (bill_id)
    """)


def downgrade():
    op.execute(
        "ALTER TABLE minhash_signatures DROP CONSTRAINT IF EXISTS uq_minhash_signatures_bill_id"
    )
