"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-05-06
"""
from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.execute("""
        CREATE TABLE bills (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            legiscan_id INTEGER UNIQUE NOT NULL,
            state CHAR(2) NOT NULL,
            session TEXT NOT NULL,
            bill_number TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            full_text TEXT,
            sponsors JSONB,
            status TEXT,
            is_corpus_only BOOLEAN NOT NULL DEFAULT FALSE,
            last_updated TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX idx_bills_state_active ON bills (state, is_corpus_only)")
    op.execute("""
        CREATE INDEX ON bills USING GIN (full_text gin_trgm_ops)
        WHERE is_corpus_only = FALSE
    """)

    op.execute("""
        CREATE TABLE minhash_signatures (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            bill_id UUID NOT NULL REFERENCES bills(id) ON DELETE CASCADE,
            signature BIGINT[] NOT NULL,
            computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX idx_minhash_bill_id ON minhash_signatures (bill_id)")

    op.execute("""
        CREATE TABLE ist_scores (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            bill_id UUID NOT NULL REFERENCES bills(id) ON DELETE CASCADE,
            source_authenticity_score DECIMAL(5,2) NOT NULL,
            copycat_alert BOOLEAN NOT NULL,
            analyzed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX idx_ist_scores_bill_id ON ist_scores (bill_id)")

    op.execute("""
        CREATE TABLE similarity_matches (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            bill_id UUID NOT NULL REFERENCES bills(id) ON DELETE CASCADE,
            matched_bill_id UUID NOT NULL REFERENCES bills(id) ON DELETE CASCADE,
            matched_state CHAR(2),
            similarity_score DECIMAL(5,2) NOT NULL,
            algorithm TEXT NOT NULL DEFAULT 'minhash',
            matched_bill_title TEXT,
            matched_bill_url TEXT,
            matched_snippets JSONB,
            snippet_status TEXT NOT NULL DEFAULT 'pending'
                CHECK (snippet_status IN ('pending','verified','source_verified_text_missing'))
        )
    """)
    op.execute("""
        CREATE INDEX idx_matches_bill_status
        ON similarity_matches (bill_id, snippet_status)
    """)
    op.execute("CREATE INDEX idx_matches_matched_bill_id ON similarity_matches (matched_bill_id)")

    op.execute("""
        CREATE TABLE friction_tags (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            bill_id UUID NOT NULL REFERENCES bills(id) ON DELETE CASCADE,
            tag_type TEXT NOT NULL,
            confidence DECIMAL(4,3),
            evidence TEXT
        )
    """)
    op.execute("CREATE INDEX idx_friction_tags_bill_id ON friction_tags (bill_id)")

def downgrade():
    op.execute("DROP TABLE IF EXISTS friction_tags")
    op.execute("DROP TABLE IF EXISTS similarity_matches")
    op.execute("DROP TABLE IF EXISTS ist_scores")
    op.execute("DROP TABLE IF EXISTS minhash_signatures")
    op.execute("DROP TABLE IF EXISTS bills")
