"""Regression test for Alembic migration 005.

Stamps DB to 004, runs upgrade to 005, asserts columns/indexes exist with
expected defaults and backfill, then runs downgrade and asserts clean rollback.
"""
import os
import pytest
from sqlalchemy import create_engine, text
from alembic import command
from alembic.config import Config


@pytest.fixture
def alembic_cfg(tmp_path, monkeypatch):
    db_url = os.environ.get("TEST_DATABASE_URL")
    if not db_url:
        pytest.skip("TEST_DATABASE_URL not set; migration tests require a real Postgres")
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_migration_005_upgrade_adds_columns_and_indexes(alembic_cfg):
    db_url = alembic_cfg.get_main_option("sqlalchemy.url")
    engine = create_engine(db_url)

    # Reset to 004
    command.downgrade(alembic_cfg, "004")

    # Pre-state: insert a bill with text, and one without
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO bills (id, legiscan_id, state, session, bill_number, title, full_text, is_corpus_only) "
            "VALUES (gen_random_uuid(), 99001, 'CO', 'test', 'HB1', 't1', 'body', false)"
        ))
        conn.execute(text(
            "INSERT INTO bills (id, legiscan_id, state, session, bill_number, title, full_text, is_corpus_only) "
            "VALUES (gen_random_uuid(), 99002, 'CO', 'test', 'HB2', 't2', NULL, false)"
        ))

    command.upgrade(alembic_cfg, "005")

    with engine.connect() as conn:
        # Columns exist
        cols = conn.execute(text(
            "SELECT column_name, data_type, is_nullable, column_default "
            "FROM information_schema.columns WHERE table_name='bills' "
            "AND column_name IN ('text_fetch_status','text_fetched_at','text_fetch_attempts','text_doc_id')"
        )).fetchall()
        col_names = {row[0] for row in cols}
        assert col_names == {"text_fetch_status", "text_fetched_at", "text_fetch_attempts", "text_doc_id"}

        # Backfill applied
        statuses = conn.execute(text(
            "SELECT legiscan_id, text_fetch_status FROM bills WHERE legiscan_id IN (99001, 99002) "
            "ORDER BY legiscan_id"
        )).fetchall()
        assert dict(statuses) == {99001: "done", 99002: "queued"}

        # Partial index exists
        idx = conn.execute(text(
            "SELECT indexname FROM pg_indexes WHERE tablename='bills' "
            "AND indexname='ix_bills_text_fetch_queue'"
        )).fetchone()
        assert idx is not None

        # match_type column + index
        mtype = conn.execute(text(
            "SELECT column_default FROM information_schema.columns "
            "WHERE table_name='similarity_matches' AND column_name='match_type'"
        )).fetchone()
        assert mtype is not None
        assert "cross_state" in mtype[0]

    # Cleanup test rows
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM bills WHERE legiscan_id IN (99001, 99002)"))


def test_migration_005_downgrade_reverses_cleanly(alembic_cfg):
    command.upgrade(alembic_cfg, "005")
    command.downgrade(alembic_cfg, "004")

    db_url = alembic_cfg.get_main_option("sqlalchemy.url")
    engine = create_engine(db_url)
    with engine.connect() as conn:
        cols = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='bills' "
            "AND column_name IN ('text_fetch_status','text_fetched_at','text_fetch_attempts','text_doc_id')"
        )).fetchall()
        assert cols == []

        mt = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='similarity_matches' AND column_name='match_type'"
        )).fetchone()
        assert mt is None

    # Restore for subsequent test runs
    command.upgrade(alembic_cfg, "005")
