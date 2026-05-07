# Sprint 1: Data Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Python worker that ingests bills from LegiScan, computes MinHash signatures, finds cross-state matches, and extracts matching snippets into Postgres.

**Architecture:** Three-phase pipeline — Phase 1 ingests all 50-state bills nightly and computes MinHash signatures; Phase 2 runs LSH comparison for CO bills to find candidates; Phase 3 fetches text on-demand and extracts readable snippet pairs via difflib. API never calls LegiScan — worker owns all external calls.

**Tech Stack:** Python 3.11, datasketch, asyncpg, SQLAlchemy 2.0 async, Alembic, Redis (redis-py async), httpx, APScheduler, pytest, pytest-asyncio

---

## File Structure

```
backend/
  pyproject.toml
  .env.example
  alembic.ini
  alembic/
    env.py
    versions/
      001_initial_schema.py
  app/
    __init__.py
    config.py                   # pydantic-settings env loading
    database.py                 # async engine + session factory
    models/
      __init__.py
      base.py                   # DeclarativeBase
      bill.py                   # Bill ORM model
      minhash_signature.py      # MinHashSignature ORM model
      ist_score.py              # ISTScore ORM model
      similarity_match.py       # SimilarityMatch ORM model
      friction_tag.py           # FrictionTag ORM model
    services/
      __init__.py
      legiscan.py               # async LegiScan HTTP client
      minhash.py                # MinHash/LSH computation (num_perm=128)
      redis_cache.py            # zlib-compressed text cache
      snippet_extractor.py      # difflib snippet extraction with context
  worker/
    __init__.py
    scheduler.py                # APScheduler nightly job setup
    tasks/
      __init__.py
      ingest.py                 # Phase 1: fetch + signature
      match.py                  # Phase 2: LSH comparison
      evidence.py               # Phase 3: snippet extraction
  tests/
    conftest.py
    test_minhash.py
    test_snippet_extractor.py
    test_redis_cache.py
    test_ingest.py
    test_match.py
    test_evidence.py
```

---

## Task 1: Project Scaffold

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/.env.example`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
# backend/pyproject.toml
[project]
name = "legilens-backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.111",
    "uvicorn[standard]>=0.29",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.29",
    "alembic>=1.13",
    "pydantic>=2.7",
    "pydantic-settings>=2.2",
    "datasketch>=1.6",
    "redis>=5.0",
    "httpx>=0.27",
    "apscheduler>=3.10",
    "slowapi>=0.1.9",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-mock>=3.14",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 2: Create .env.example**

```bash
# backend/.env.example
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/legilens
REDIS_URL=redis://localhost:6379
LEGISCAN_API_KEY=your_key_here
ALLOWED_ORIGINS=http://localhost:3000
```

- [ ] **Step 3: Create app/config.py**

```python
# backend/app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str
    redis_url: str
    legiscan_api_key: str
    allowed_origins: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
```

- [ ] **Step 4: Install dependencies and verify**

```bash
cd backend
pip install -e ".[dev]"
python -c "from app.config import settings; print('config OK')"
```

Expected: `config OK`

- [ ] **Step 5: Commit**

```bash
git add backend/pyproject.toml backend/.env.example backend/app/__init__.py backend/app/config.py
git commit -m "chore: backend project scaffold and config"
```

---

## Task 2: Database Models

**Files:**
- Create: `backend/app/models/base.py`
- Create: `backend/app/models/bill.py`
- Create: `backend/app/models/minhash_signature.py`
- Create: `backend/app/models/ist_score.py`
- Create: `backend/app/models/similarity_match.py`
- Create: `backend/app/models/friction_tag.py`
- Create: `backend/app/database.py`

- [ ] **Step 1: Write failing import test**

```python
# backend/tests/test_models_import.py
def test_models_importable():
    from app.models.bill import Bill
    from app.models.minhash_signature import MinHashSignature
    from app.models.ist_score import ISTScore
    from app.models.similarity_match import SimilarityMatch
    from app.models.friction_tag import FrictionTag
    assert Bill.__tablename__ == "bills"
    assert MinHashSignature.__tablename__ == "minhash_signatures"
```

- [ ] **Step 2: Run — verify fail**

```bash
cd backend && pytest tests/test_models_import.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create base.py**

```python
# backend/app/models/base.py
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
```

- [ ] **Step 4: Create bill.py**

```python
# backend/app/models/bill.py
from uuid import uuid4
from datetime import datetime
from sqlalchemy import String, Boolean, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

class Bill(Base):
    __tablename__ = "bills"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    legiscan_id: Mapped[int] = mapped_column(unique=True, nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    session: Mapped[str] = mapped_column(Text, nullable=False)
    bill_number: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    full_text: Mapped[str | None] = mapped_column(Text)
    sponsors: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str | None] = mapped_column(Text)
    is_corpus_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

- [ ] **Step 5: Create minhash_signature.py**

Note: spec says `INTEGER[]` but datasketch hashvalues are uint32. `BIGINT[]` (signed int64) safely holds all uint32 values.

```python
# backend/app/models/minhash_signature.py
from uuid import uuid4
from datetime import datetime
from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID, ARRAY, BIGINT
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey
from app.models.base import Base

class MinHashSignature(Base):
    __tablename__ = "minhash_signatures"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    bill_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("bills.id"), nullable=False)
    signature: Mapped[list[int]] = mapped_column(ARRAY(BIGINT), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 6: Create ist_score.py**

```python
# backend/app/models/ist_score.py
from uuid import uuid4
from datetime import datetime
from decimal import Decimal
from sqlalchemy import DateTime, Boolean, Numeric, func, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

class ISTScore(Base):
    __tablename__ = "ist_scores"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    bill_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("bills.id"), nullable=False)
    source_authenticity_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    copycat_alert: Mapped[bool] = mapped_column(Boolean, nullable=False)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 7: Create similarity_match.py**

```python
# backend/app/models/similarity_match.py
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
```

- [ ] **Step 8: Create friction_tag.py**

```python
# backend/app/models/friction_tag.py
from uuid import uuid4
from decimal import Decimal
from sqlalchemy import Text, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

class FrictionTag(Base):
    __tablename__ = "friction_tags"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    bill_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("bills.id"), nullable=False)
    tag_type: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    evidence: Mapped[str | None] = mapped_column(Text)
```

- [ ] **Step 9: Create database.py**

```python
# backend/app/database.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings

engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
```

- [ ] **Step 10: Run import test — verify pass**

```bash
cd backend && pytest tests/test_models_import.py -v
```

Expected: `PASSED`

- [ ] **Step 11: Commit**

```bash
git add backend/app/models/ backend/app/database.py
git commit -m "feat: add SQLAlchemy ORM models and async database setup"
```

---

## Task 3: Alembic Migration

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/001_initial_schema.py`

- [ ] **Step 1: Initialize Alembic**

```bash
cd backend && alembic init alembic
```

- [ ] **Step 2: Replace alembic/env.py**

```python
# backend/alembic/env.py
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
from app.config import settings
from app.models.base import Base
import app.models.bill
import app.models.minhash_signature
import app.models.ist_score
import app.models.similarity_match
import app.models.friction_tag

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)
if config.config_file_name:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata

def run_migrations_offline():
    context.configure(url=settings.database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations():
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

def run_migrations_online():
    asyncio.run(run_async_migrations())

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 3: Create migration file**

```python
# backend/alembic/versions/001_initial_schema.py
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
    op.execute("CREATE INDEX ON bills (state, is_corpus_only)")
    op.execute("""
        CREATE INDEX ON bills USING GIN (full_text gin_trgm_ops)
        WHERE is_corpus_only = FALSE
    """)

    op.execute("""
        CREATE TABLE minhash_signatures (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            bill_id UUID NOT NULL REFERENCES bills(id),
            signature BIGINT[] NOT NULL,
            computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE ist_scores (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            bill_id UUID NOT NULL REFERENCES bills(id),
            source_authenticity_score DECIMAL(5,2) NOT NULL,
            copycat_alert BOOLEAN NOT NULL,
            analyzed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE similarity_matches (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            bill_id UUID NOT NULL REFERENCES bills(id),
            matched_bill_id UUID NOT NULL REFERENCES bills(id),
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

    op.execute("""
        CREATE TABLE friction_tags (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            bill_id UUID NOT NULL REFERENCES bills(id),
            tag_type TEXT NOT NULL,
            confidence DECIMAL(4,3),
            evidence TEXT
        )
    """)

def downgrade():
    op.execute("DROP TABLE IF EXISTS friction_tags")
    op.execute("DROP TABLE IF EXISTS similarity_matches")
    op.execute("DROP TABLE IF EXISTS ist_scores")
    op.execute("DROP TABLE IF EXISTS minhash_signatures")
    op.execute("DROP TABLE IF EXISTS bills")
```

- [ ] **Step 4: Run migration against local Postgres**

Requires local Postgres running with `legilens` DB created.

```bash
cd backend && alembic upgrade head
```

Expected: no errors, all tables created.

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/ backend/alembic.ini
git commit -m "feat: add Alembic migrations for initial schema"
```

---

## Task 4: LegiScan Client

**Files:**
- Create: `backend/app/services/legiscan.py`
- Test: `backend/tests/test_legiscan.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_legiscan.py
import pytest
from unittest.mock import AsyncMock, patch
from app.services.legiscan import LegiScanClient

@pytest.fixture
def client():
    return LegiScanClient(api_key="test_key")

async def test_get_bill_list_returns_bills(client):
    mock_response = {"status": "OK", "bills": [{"bill_id": 1, "number": "SB-1"}]}
    with patch.object(client._http, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json.return_value = mock_response
        mock_get.return_value.raise_for_status = lambda: None
        result = await client.get_bill_list("CO")
    assert result == [{"bill_id": 1, "number": "SB-1"}]

async def test_get_bill_list_empty_on_missing_key(client):
    mock_response = {"status": "OK"}
    with patch.object(client._http, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json.return_value = mock_response
        mock_get.return_value.raise_for_status = lambda: None
        result = await client.get_bill_list("ZZ")
    assert result == []

async def test_get_bill_text_returns_text(client):
    mock_response = {"status": "OK", "bill": {"texts": [{"doc": "The bill text here."}]}}
    with patch.object(client._http, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json.return_value = mock_response
        mock_get.return_value.raise_for_status = lambda: None
        result = await client.get_bill_text(12345)
    assert result == "The bill text here."

async def test_get_bill_text_returns_none_when_no_texts(client):
    mock_response = {"status": "OK", "bill": {"texts": []}}
    with patch.object(client._http, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json.return_value = mock_response
        mock_get.return_value.raise_for_status = lambda: None
        result = await client.get_bill_text(99)
    assert result is None
```

- [ ] **Step 2: Run — verify fail**

```bash
cd backend && pytest tests/test_legiscan.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement legiscan.py**

```python
# backend/app/services/legiscan.py
import httpx

LEGISCAN_BASE = "https://api.legiscan.com/"

class LegiScanClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._http = httpx.AsyncClient(base_url=LEGISCAN_BASE, timeout=30)

    async def get_bill_list(self, state: str) -> list[dict]:
        resp = await self._http.get("/", params={"key": self.api_key, "op": "getBillList", "state": state})
        resp.raise_for_status()
        return resp.json().get("bills", [])

    async def get_bill_text(self, bill_id: int) -> str | None:
        resp = await self._http.get("/", params={"key": self.api_key, "op": "getBill", "id": bill_id})
        resp.raise_for_status()
        texts = resp.json().get("bill", {}).get("texts", [])
        if not texts:
            return None
        return texts[-1].get("doc")

    async def close(self):
        await self._http.aclose()
```

- [ ] **Step 4: Run — verify pass**

```bash
cd backend && pytest tests/test_legiscan.py -v
```

Expected: all 4 `PASSED`

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/legiscan.py backend/tests/test_legiscan.py
git commit -m "feat: add LegiScan async HTTP client"
```

---

## Task 5: Redis Cache Service

**Files:**
- Create: `backend/app/services/redis_cache.py`
- Test: `backend/tests/test_redis_cache.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_redis_cache.py
import pytest
from unittest.mock import AsyncMock, patch
from app.services.redis_cache import RedisCache

@pytest.fixture
def cache():
    return RedisCache(url="redis://localhost:6379")

async def test_set_and_get_bill_text(cache):
    text = "The commission shall establish fees."
    with patch.object(cache._redis, "setex", new_callable=AsyncMock) as mock_set, \
         patch.object(cache._redis, "get", new_callable=AsyncMock) as mock_get:
        import zlib
        mock_get.return_value = zlib.compress(text.encode("utf8"))
        await cache.set_bill_text(12345, text)
        result = await cache.get_bill_text(12345)
    assert result == text

async def test_get_bill_text_returns_none_on_miss(cache):
    with patch.object(cache._redis, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None
        result = await cache.get_bill_text(99999)
    assert result is None

async def test_compression_reduces_size(cache):
    import zlib
    text = "The commission shall establish. " * 200
    compressed = zlib.compress(text.encode("utf8"))
    assert len(compressed) < len(text.encode("utf8"))
```

- [ ] **Step 2: Run — verify fail**

```bash
cd backend && pytest tests/test_redis_cache.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement redis_cache.py**

```python
# backend/app/services/redis_cache.py
import zlib
import redis.asyncio as aioredis

CACHE_TTL = 86400  # 24 hours

class RedisCache:
    def __init__(self, url: str):
        self._redis = aioredis.from_url(url, decode_responses=False)

    async def set_bill_text(self, legiscan_id: int, text: str) -> None:
        key = f"bills:{legiscan_id}:text"
        compressed = zlib.compress(text.encode("utf8"))
        await self._redis.setex(key, CACHE_TTL, compressed)

    async def get_bill_text(self, legiscan_id: int) -> str | None:
        key = f"bills:{legiscan_id}:text"
        data = await self._redis.get(key)
        if data is None:
            return None
        return zlib.decompress(data).decode("utf8")

    async def close(self):
        await self._redis.aclose()
```

- [ ] **Step 4: Run — verify pass**

```bash
cd backend && pytest tests/test_redis_cache.py -v
```

Expected: all 3 `PASSED`

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/redis_cache.py backend/tests/test_redis_cache.py
git commit -m "feat: add zlib-compressed Redis cache service"
```

---

## Task 6: MinHash Service

**Files:**
- Create: `backend/app/services/minhash.py`
- Test: `backend/tests/test_minhash.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_minhash.py
import pytest
from app.services.minhash import compute_minhash, jaccard_estimate, NUM_PERM, LSH_THRESHOLD

def test_compute_minhash_returns_128_bands():
    m = compute_minhash("The commission shall establish fees not to exceed.")
    assert len(m.hashvalues) == NUM_PERM

def test_identical_texts_have_similarity_one():
    text = "The commission shall establish fees."
    m1 = compute_minhash(text)
    m2 = compute_minhash(text)
    assert jaccard_estimate(m1, m2) == pytest.approx(1.0)

def test_unrelated_texts_have_low_similarity():
    m1 = compute_minhash("The quick brown fox jumps over the lazy dog.")
    m2 = compute_minhash("Quantum entanglement is a physical phenomenon.")
    assert jaccard_estimate(m1, m2) < 0.3

def test_similar_texts_exceed_threshold():
    base = "The commission shall establish fees not to exceed one hundred dollars per application."
    similar = "The commission shall establish fees not to exceed one hundred dollars per application submitted."
    m1 = compute_minhash(base)
    m2 = compute_minhash(similar)
    assert jaccard_estimate(m1, m2) >= LSH_THRESHOLD

def test_signature_serializable_as_list():
    m = compute_minhash("Any bill text here.")
    sig = m.hashvalues.tolist()
    assert isinstance(sig, list)
    assert all(isinstance(v, int) for v in sig)
```

- [ ] **Step 2: Run — verify fail**

```bash
cd backend && pytest tests/test_minhash.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement minhash.py**

```python
# backend/app/services/minhash.py
import numpy as np
from datasketch import MinHash, MinHashLSH

NUM_PERM = 128       # fixed — changing invalidates all stored signatures
LSH_THRESHOLD = 0.7  # aligns with copycat_alert (score < 30.00)
SHINGLE_SIZE = 5     # character k-shingles

def compute_minhash(text: str) -> MinHash:
    m = MinHash(num_perm=NUM_PERM)
    text = text.lower()
    for i in range(len(text) - SHINGLE_SIZE + 1):
        shingle = text[i:i + SHINGLE_SIZE]
        m.update(shingle.encode("utf8"))
    return m

def jaccard_estimate(m1: MinHash, m2: MinHash) -> float:
    return m1.jaccard(m2)

def minhash_from_signature(signature: list[int]) -> MinHash:
    """Reconstruct MinHash from stored BIGINT[] signature."""
    m = MinHash(num_perm=NUM_PERM)
    m.hashvalues = np.array(signature, dtype=np.uint64)
    return m

def build_lsh() -> MinHashLSH:
    return MinHashLSH(threshold=LSH_THRESHOLD, num_perm=NUM_PERM)
```

- [ ] **Step 4: Run — verify pass**

```bash
cd backend && pytest tests/test_minhash.py -v
```

Expected: all 5 `PASSED`

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/minhash.py backend/tests/test_minhash.py
git commit -m "feat: add MinHash service (num_perm=128, threshold=0.7)"
```

---

## Task 7: Snippet Extractor Service

**Files:**
- Create: `backend/app/services/snippet_extractor.py`
- Test: `backend/tests/test_snippet_extractor.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_snippet_extractor.py
import pytest
from app.services.snippet_extractor import extract_snippets, MIN_MATCH_LENGTH

def test_identical_text_produces_one_snippet():
    text = "The legislature finds that fees are necessary. The commission shall establish fees not to exceed one hundred dollars. Such fees shall be deposited in the fund."
    snippets = extract_snippets(text, text)
    assert len(snippets) >= 1

def test_snippet_has_required_keys():
    co = "First sentence. The commission shall establish fees not to exceed one hundred dollars. Last sentence."
    src = "Intro line. The commission shall establish fees not to exceed one hundred dollars. Outro line."
    snippets = extract_snippets(co, src)
    assert len(snippets) >= 1
    s = snippets[0]
    assert "co_match" in s
    assert "source_match" in s
    assert "co_context_before" in s
    assert "co_context_after" in s
    assert "source_context_before" in s
    assert "source_context_after" in s

def test_short_matches_excluded():
    co = "The fees. " * 10
    src = "The fees. " * 10 + "Completely different content for the rest of this document."
    snippets = extract_snippets(co, src)
    for s in snippets:
        assert len(s["co_match"]) >= MIN_MATCH_LENGTH

def test_unrelated_texts_produce_no_snippets():
    co = "The quick brown fox jumps over the lazy dog in Colorado."
    src = "Quantum mechanics describes the behavior of particles at subatomic scales."
    snippets = extract_snippets(co, src)
    assert snippets == []

def test_context_before_is_preceding_sentence():
    co = "Intro sentence. The commission shall establish fees not to exceed one hundred dollars per application. Outro sentence."
    src = "Preamble sentence. The commission shall establish fees not to exceed one hundred dollars per application. Closing sentence."
    snippets = extract_snippets(co, src)
    assert len(snippets) >= 1
    assert "Intro sentence" in snippets[0]["co_context_before"] or snippets[0]["co_context_before"] == ""
```

- [ ] **Step 2: Run — verify fail**

```bash
cd backend && pytest tests/test_snippet_extractor.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement snippet_extractor.py**

```python
# backend/app/services/snippet_extractor.py
import difflib
import re

MIN_MATCH_LENGTH = 50

def extract_snippets(co_text: str, source_text: str) -> list[dict]:
    matcher = difflib.SequenceMatcher(None, co_text, source_text, autojunk=False)
    co_sents = _split_sentences(co_text)
    src_sents = _split_sentences(source_text)
    snippets = []

    for a, b, n in matcher.get_matching_blocks():
        if n < MIN_MATCH_LENGTH:
            continue
        co_match = co_text[a:a + n]
        src_match = source_text[b:b + n]
        co_before, co_after = _surrounding_sentence(co_sents, a, a + n)
        src_before, src_after = _surrounding_sentence(src_sents, b, b + n)
        snippets.append({
            "co_context_before": co_before,
            "co_match": co_match,
            "co_context_after": co_after,
            "source_context_before": src_before,
            "source_match": src_match,
            "source_context_after": src_after,
        })

    return snippets

def _split_sentences(text: str) -> list[tuple[int, int, str]]:
    result = []
    for m in re.finditer(r"[^.!?]+[.!?]?", text):
        result.append((m.start(), m.end(), m.group().strip()))
    return result

def _surrounding_sentence(
    sentences: list[tuple[int, int, str]],
    match_start: int,
    match_end: int,
) -> tuple[str, str]:
    before = ""
    after = ""
    for s, e, sent in sentences:
        if e <= match_start:
            before = sent
        if s >= match_end and not after:
            after = sent
            break
    return before, after
```

- [ ] **Step 4: Run — verify pass**

```bash
cd backend && pytest tests/test_snippet_extractor.py -v
```

Expected: all 5 `PASSED`

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/snippet_extractor.py backend/tests/test_snippet_extractor.py
git commit -m "feat: add difflib snippet extractor with sentence context"
```

---

## Task 8: Phase 1 Worker — Ingest

**Files:**
- Create: `backend/worker/tasks/ingest.py`
- Test: `backend/tests/test_ingest.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_ingest.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

async def test_process_bill_stores_signature(tmp_path):
    from worker.tasks.ingest import _process_bill

    mock_session = AsyncMock()
    mock_session.execute.return_value.scalar_one_or_none.return_value = None
    mock_session.flush = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    mock_client = AsyncMock()
    mock_cache = AsyncMock()

    bill_meta = {"bill_id": 42, "number": "SB-1", "title": "Test Bill", "session": "2024A"}
    bill_text = "The commission shall establish fees not to exceed one hundred dollars per application submitted."

    mock_client.get_bill_text.return_value = bill_text

    await _process_bill(mock_session, mock_client, mock_cache, bill_meta, "TX", is_co=False)

    mock_session.add.assert_called()
    mock_cache.set_bill_text.assert_called_once_with(42, bill_text)

async def test_process_bill_skips_when_no_text():
    from worker.tasks.ingest import _process_bill

    mock_session = AsyncMock()
    mock_client = AsyncMock()
    mock_client.get_bill_text.return_value = None
    mock_cache = AsyncMock()

    await _process_bill(mock_session, mock_client, mock_cache, {"bill_id": 1}, "TX", is_co=False)

    mock_session.add.assert_not_called()
```

- [ ] **Step 2: Run — verify fail**

```bash
cd backend && pytest tests/test_ingest.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create worker/__init__.py and tasks/__init__.py**

```bash
touch backend/worker/__init__.py backend/worker/tasks/__init__.py
```

- [ ] **Step 4: Implement ingest.py**

```python
# backend/worker/tasks/ingest.py
import os
from sqlalchemy import select
from app.database import async_session
from app.models.bill import Bill
from app.models.minhash_signature import MinHashSignature
from app.services.legiscan import LegiScanClient
from app.services.minhash import compute_minhash
from app.services.redis_cache import RedisCache
from app.config import settings

ALL_STATES = [
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
    "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
    "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
    "VA","WA","WV","WI","WY",
]

async def ingest_all_states():
    client = LegiScanClient(api_key=settings.legiscan_api_key)
    cache = RedisCache(url=settings.redis_url)
    try:
        async with async_session() as session:
            for state in ALL_STATES:
                bills = await client.get_bill_list(state)
                for bill_meta in bills:
                    await _process_bill(session, client, cache, bill_meta, state, is_co=(state == "CO"))
    finally:
        await client.close()
        await cache.close()

async def _process_bill(session, client, cache, bill_meta, state, is_co: bool):
    legiscan_id = bill_meta["bill_id"]
    text = await client.get_bill_text(legiscan_id)
    if not text:
        return

    existing = await session.execute(select(Bill).where(Bill.legiscan_id == legiscan_id))
    bill = existing.scalar_one_or_none()
    if not bill:
        bill = Bill(
            legiscan_id=legiscan_id,
            state=state,
            session=bill_meta.get("session", ""),
            bill_number=bill_meta.get("number", ""),
            title=bill_meta.get("title", ""),
            is_corpus_only=not is_co,
            full_text=text if is_co else None,
        )
        session.add(bill)
        await session.flush()

    m = compute_minhash(text)
    sig = MinHashSignature(bill_id=bill.id, signature=m.hashvalues.tolist())
    session.add(sig)
    await session.commit()
    await cache.set_bill_text(legiscan_id, text)
```

- [ ] **Step 5: Run — verify pass**

```bash
cd backend && pytest tests/test_ingest.py -v
```

Expected: both `PASSED`

- [ ] **Step 6: Commit**

```bash
git add backend/worker/ backend/tests/test_ingest.py
git commit -m "feat: Phase 1 ingest worker — LegiScan fetch, MinHash, Redis cache"
```

---

## Task 9: Phase 2 Worker — Match

**Files:**
- Create: `backend/worker/tasks/match.py`
- Test: `backend/tests/test_match.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_match.py
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from app.services.minhash import compute_minhash

async def test_match_writes_similarity_match_row():
    from worker.tasks.match import _find_matches_for_bill

    identical_text = "The commission shall establish fees not to exceed one hundred dollars per application submitted to the board."
    co_bill_id = uuid4()
    corpus_bill_id = uuid4()

    co_m = compute_minhash(identical_text)
    corpus_m = compute_minhash(identical_text)

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    corpus_entries = [(corpus_bill_id, "TX", "HB-1", corpus_m)]
    await _find_matches_for_bill(mock_session, co_bill_id, co_m, corpus_entries)

    mock_session.add.assert_called()

async def test_no_match_writes_score_of_100():
    from worker.tasks.match import _find_matches_for_bill

    co_m = compute_minhash("Completely unique Colorado bill text with no parallels anywhere.")
    corpus_entries = []

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    await _find_matches_for_bill(mock_session, uuid4(), co_m, corpus_entries)

    added = [call.args[0] for call in mock_session.add.call_args_list]
    from app.models.ist_score import ISTScore
    scores = [a for a in added if isinstance(a, ISTScore)]
    assert len(scores) == 1
    assert scores[0].source_authenticity_score == Decimal("100.00")
    assert scores[0].copycat_alert is False
```

- [ ] **Step 2: Run — verify fail**

```bash
cd backend && pytest tests/test_match.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement match.py**

```python
# backend/worker/tasks/match.py
from decimal import Decimal
from uuid import UUID
from sqlalchemy import select
from datasketch import MinHash
from app.database import async_session
from app.models.bill import Bill
from app.models.minhash_signature import MinHashSignature
from app.models.similarity_match import SimilarityMatch
from app.models.ist_score import ISTScore
from app.services.minhash import build_lsh, minhash_from_signature, jaccard_estimate, NUM_PERM

async def match_co_bills():
    async with async_session() as session:
        corpus_result = await session.execute(
            select(MinHashSignature, Bill)
            .join(Bill, Bill.id == MinHashSignature.bill_id)
            .where(Bill.is_corpus_only.is_(True))
        )
        corpus_entries = [
            (bill.id, bill.state, bill.bill_number, minhash_from_signature(sig.signature))
            for sig, bill in corpus_result
        ]

        co_result = await session.execute(
            select(MinHashSignature, Bill)
            .join(Bill, Bill.id == MinHashSignature.bill_id)
            .where(Bill.is_corpus_only.is_(False))
        )
        for sig, co_bill in co_result:
            co_m = minhash_from_signature(sig.signature)
            await _find_matches_for_bill(session, co_bill.id, co_m, corpus_entries)

async def _find_matches_for_bill(session, co_bill_id: UUID, co_m, corpus_entries: list):
    if not corpus_entries:
        score = ISTScore(
            bill_id=co_bill_id,
            source_authenticity_score=Decimal("100.00"),
            copycat_alert=False,
        )
        session.add(score)
        await session.commit()
        return

    max_similarity = Decimal("0.00")
    for corpus_bill_id, corpus_state, corpus_bill_number, corpus_m in corpus_entries:
        sim = Decimal(str(round(jaccard_estimate(co_m, corpus_m) * 100, 2)))
        if sim < Decimal("70.00"):
            continue
        match = SimilarityMatch(
            bill_id=co_bill_id,
            matched_bill_id=corpus_bill_id,
            matched_state=corpus_state,
            similarity_score=sim,
            snippet_status="pending",
        )
        session.add(match)
        if sim > max_similarity:
            max_similarity = sim

    authenticity = Decimal("100.00") - max_similarity
    score = ISTScore(
        bill_id=co_bill_id,
        source_authenticity_score=authenticity,
        copycat_alert=authenticity < Decimal("30.00"),
    )
    session.add(score)
    await session.commit()
```

- [ ] **Step 4: Run — verify pass**

```bash
cd backend && pytest tests/test_match.py -v
```

Expected: both `PASSED`

- [ ] **Step 5: Commit**

```bash
git add backend/worker/tasks/match.py backend/tests/test_match.py
git commit -m "feat: Phase 2 match worker — LSH comparison, IST scoring"
```

---

## Task 10: Phase 3 Worker — Evidence

**Files:**
- Create: `backend/worker/tasks/evidence.py`
- Test: `backend/tests/test_evidence.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_evidence.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

async def test_evidence_sets_verified_when_text_available():
    from worker.tasks.evidence import _extract_evidence_for_match

    co_text = "Preamble. The commission shall establish fees not to exceed one hundred dollars. End."
    src_text = "Intro. The commission shall establish fees not to exceed one hundred dollars. Close."

    mock_match = MagicMock()
    mock_match.id = uuid4()
    mock_match.bill_id = uuid4()
    mock_match.matched_bill_id = uuid4()

    mock_co_bill = MagicMock()
    mock_co_bill.legiscan_id = 1
    mock_corpus_bill = MagicMock()
    mock_corpus_bill.legiscan_id = 2

    mock_session = AsyncMock()
    mock_session.get.side_effect = [mock_co_bill, mock_corpus_bill]
    mock_session.commit = AsyncMock()

    mock_cache = AsyncMock()
    mock_cache.get_bill_text.side_effect = [co_text, src_text]
    mock_client = AsyncMock()

    await _extract_evidence_for_match(mock_session, mock_match, mock_cache, mock_client)

    assert mock_match.snippet_status == "verified"
    assert mock_match.matched_snippets is not None
    assert len(mock_match.matched_snippets) >= 1

async def test_evidence_sets_ghost_when_text_unavailable():
    from worker.tasks.evidence import _extract_evidence_for_match

    mock_match = MagicMock()
    mock_match.bill_id = uuid4()
    mock_match.matched_bill_id = uuid4()

    mock_co_bill = MagicMock()
    mock_co_bill.legiscan_id = 1
    mock_corpus_bill = MagicMock()
    mock_corpus_bill.legiscan_id = 2

    mock_session = AsyncMock()
    mock_session.get.side_effect = [mock_co_bill, mock_corpus_bill]
    mock_session.commit = AsyncMock()

    mock_cache = AsyncMock()
    mock_cache.get_bill_text.return_value = None
    mock_client = AsyncMock()
    mock_client.get_bill_text.return_value = None

    await _extract_evidence_for_match(mock_session, mock_match, mock_cache, mock_client)

    assert mock_match.snippet_status == "source_verified_text_missing"
```

- [ ] **Step 2: Run — verify fail**

```bash
cd backend && pytest tests/test_evidence.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement evidence.py**

```python
# backend/worker/tasks/evidence.py
from sqlalchemy import select
from app.database import async_session
from app.models.bill import Bill
from app.models.similarity_match import SimilarityMatch
from app.services.legiscan import LegiScanClient
from app.services.redis_cache import RedisCache
from app.services.snippet_extractor import extract_snippets
from app.config import settings

async def extract_all_pending_evidence():
    client = LegiScanClient(api_key=settings.legiscan_api_key)
    cache = RedisCache(url=settings.redis_url)
    try:
        async with async_session() as session:
            result = await session.execute(
                select(SimilarityMatch).where(SimilarityMatch.snippet_status == "pending")
            )
            for match in result.scalars():
                await _extract_evidence_for_match(session, match, cache, client)
    finally:
        await client.close()
        await cache.close()

async def _extract_evidence_for_match(session, match, cache, client):
    co_bill = await session.get(Bill, match.bill_id)
    corpus_bill = await session.get(Bill, match.matched_bill_id)

    co_text = await cache.get_bill_text(co_bill.legiscan_id)
    if not co_text:
        co_text = await client.get_bill_text(co_bill.legiscan_id)
        if co_text:
            await cache.set_bill_text(co_bill.legiscan_id, co_text)

    src_text = await cache.get_bill_text(corpus_bill.legiscan_id)
    if not src_text:
        src_text = await client.get_bill_text(corpus_bill.legiscan_id)
        if src_text:
            await cache.set_bill_text(corpus_bill.legiscan_id, src_text)

    if not co_text or not src_text:
        match.snippet_status = "source_verified_text_missing"
        await session.commit()
        return

    snippets = extract_snippets(co_text, src_text)
    match.matched_snippets = snippets
    match.snippet_status = "verified"
    await session.commit()
```

- [ ] **Step 4: Run — verify pass**

```bash
cd backend && pytest tests/test_evidence.py -v
```

Expected: both `PASSED`

- [ ] **Step 5: Commit**

```bash
git add backend/worker/tasks/evidence.py backend/tests/test_evidence.py
git commit -m "feat: Phase 3 evidence worker — difflib snippet extraction, ghost state"
```

---

## Task 11: APScheduler Setup

**Files:**
- Create: `backend/worker/scheduler.py`

- [ ] **Step 1: Implement scheduler.py**

```python
# backend/worker/scheduler.py
import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from worker.tasks.ingest import ingest_all_states
from worker.tasks.match import match_co_bills
from worker.tasks.evidence import extract_all_pending_evidence

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_full_pipeline():
    logger.info("Pipeline start: ingesting all states")
    await ingest_all_states()
    logger.info("Ingestion complete. Running match phase.")
    await match_co_bills()
    logger.info("Match phase complete. Extracting evidence.")
    await extract_all_pending_evidence()
    logger.info("Pipeline complete.")

def start():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_full_pipeline, "cron", hour=3, minute=0)  # 3am nightly
    scheduler.start()
    logger.info("Scheduler started. Next run at 03:00.")
    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()

if __name__ == "__main__":
    start()
```

- [ ] **Step 2: Run full test suite**

```bash
cd backend && pytest tests/ -v
```

Expected: all tests `PASSED`

- [ ] **Step 3: Commit**

```bash
git add backend/worker/scheduler.py
git commit -m "feat: APScheduler nightly pipeline (3am UTC)"
```

---

## Task 12: Merge Sprint 1

- [ ] **Step 1: Run full test suite one final time**

```bash
cd backend && pytest tests/ -v --tb=short
```

Expected: all `PASSED`, no failures.

- [ ] **Step 2: Merge to main**

```bash
git checkout main
git merge feat/data-ingestion --no-ff -m "feat: Sprint 1 — data ingestion pipeline complete"
git branch -d feat/data-ingestion
```
