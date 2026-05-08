# Sprint 2: API Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Build the FastAPI read-only API layer that serves bill data, IST scores, and similarity matches to the frontend.

**Architecture:** FastAPI app with GZip + CORS + User-Agent middleware, asyncpg + SQLAlchemy 2.0 async for all DB access, strict Pydantic v2 models, slowapi rate limiting. API is read-only — never triggers LegiScan or worker tasks.

**Prerequisites:** Sprint 1 complete. DB schema exists. Run `alembic upgrade head` before starting.

**Tech Stack:** FastAPI 0.111+, SQLAlchemy 2.0 async, asyncpg, Pydantic v2, slowapi, pytest, httpx (test client)

---

## File Structure

```
backend/
  app/
    main.py                     # FastAPI app, all middleware, router registration
    dependencies.py             # shared deps: db session, user-agent check
    schemas/
      __init__.py
      bill.py                   # BillListItem, BillDetail, ISTScoreOut, FrictionTagOut
      match.py                  # SnippetItem, GhostMessage, MatchOut
      stats.py                  # StatsOut, TagCountOut
    routers/
      __init__.py
      bills.py                  # GET /bills, /bills/search, /bills/{id}
      matches.py                # GET /bills/{id}/matches
      tags.py                   # GET /tags
      stats.py                  # GET /stats
  tests/
    test_api_bills.py
    test_api_matches.py
    test_api_stats.py
```

---

## Task 1: Schemas

**Files:**
- Create: `backend/app/schemas/bill.py`
- Create: `backend/app/schemas/match.py`
- Create: `backend/app/schemas/stats.py`

- [x] **Step 1: Write failing import test**

```python
# backend/tests/test_schemas_import.py
def test_schemas_importable():
    from app.schemas.bill import BillListItem, BillDetail, ISTScoreOut
    from app.schemas.match import MatchOut, SnippetItem, GhostMessage
    from app.schemas.stats import StatsOut, TagCountOut
    assert BillDetail.model_fields["id"]
```

- [x] **Step 2: Run — verify fail**

```bash
cd backend && pytest tests/test_schemas_import.py -v
```

Expected: `ModuleNotFoundError`

- [x] **Step 3: Create schemas/bill.py**

```python
# backend/app/schemas/bill.py
from uuid import UUID
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel

class ISTScoreOut(BaseModel):
    source_authenticity_score: Decimal
    copycat_alert: bool
    analyzed_at: datetime

class FrictionTagOut(BaseModel):
    type: str
    confidence: Decimal | None

class BillListItem(BaseModel):
    id: UUID
    bill_number: str
    title: str
    state: str
    session: str
    status: str | None
    copycat_alert: bool | None

    model_config = {"from_attributes": True}

class BillDetail(BaseModel):
    id: UUID
    bill_number: str
    title: str
    description: str | None
    state: str
    session: str
    status: str | None
    sponsors: list | None
    ist_score: ISTScoreOut | None
    tags: list[FrictionTagOut]

    model_config = {"from_attributes": True}
```

- [x] **Step 4: Create schemas/match.py**

```python
# backend/app/schemas/match.py
from uuid import UUID
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel

class SnippetItem(BaseModel):
    co_context_before: str
    co_match: str
    co_context_after: str
    source_context_before: str
    source_match: str
    source_context_after: str

class GhostMessage(BaseModel):
    message: Literal["Source text unavailable for extraction"]

class MatchOut(BaseModel):
    id: UUID
    matched_bill_title: str | None
    matched_state: str | None
    similarity_score: Decimal
    snippet_status: str
    matched_snippets: list[SnippetItem | GhostMessage] | None

    model_config = {"from_attributes": True}
```

- [x] **Step 5: Create schemas/stats.py**

```python
# backend/app/schemas/stats.py
from pydantic import BaseModel

class StatsOut(BaseModel):
    total_co_bills: int
    copycat_alerts: int
    bills_analyzed: int

class TagCountOut(BaseModel):
    tag_type: str
    count: int
```

- [x] **Step 6: Run import test — verify pass**

```bash
cd backend && pytest tests/test_schemas_import.py -v
```

Expected: `PASSED`

- [x] **Step 7: Commit**

```bash
git add backend/app/schemas/
git commit -m "feat: Pydantic v2 response schemas for bills, matches, stats"
```

---

## Task 2: Dependencies

**Files:**
- Create: `backend/app/dependencies.py`
- Test: `backend/tests/test_dependencies.py`

- [x] **Step 1: Write failing tests**

```python
# backend/tests/test_dependencies.py
import pytest
from fastapi import HTTPException
from app.dependencies import require_user_agent

async def test_require_user_agent_passes_with_header():
    result = await require_user_agent(user_agent="Mozilla/5.0")
    assert result is None

async def test_require_user_agent_raises_without_header():
    with pytest.raises(HTTPException) as exc:
        await require_user_agent(user_agent=None)
    assert exc.value.status_code == 400
    assert "User-Agent" in exc.value.detail
```

- [x] **Step 2: Run — verify fail**

```bash
cd backend && pytest tests/test_dependencies.py -v
```

Expected: `ModuleNotFoundError`

- [x] **Step 3: Implement dependencies.py**

```python
# backend/app/dependencies.py
from typing import AsyncGenerator
from fastapi import Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import async_session

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session

async def require_user_agent(user_agent: str | None = Header(default=None)) -> None:
    if not user_agent:
        raise HTTPException(status_code=400, detail="User-Agent header required")
```

- [x] **Step 4: Run — verify pass**

```bash
cd backend && pytest tests/test_dependencies.py -v
```

Expected: both `PASSED`

- [x] **Step 5: Commit**

```bash
git add backend/app/dependencies.py backend/tests/test_dependencies.py
git commit -m "feat: shared FastAPI dependencies — db session, User-Agent guard"
```

---

## Task 3: Bills Router

**Files:**
- Create: `backend/app/routers/bills.py`
- Test: `backend/tests/test_api_bills.py`

- [x] **Step 1: Write failing tests**

```python
# backend/tests/test_api_bills.py
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

@pytest.fixture
async def client():
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

async def test_get_bills_returns_200(client):
    with patch("app.routers.bills.get_db") as mock_db:
        mock_session = AsyncMock()
        mock_session.execute.return_value.scalars.return_value.all.return_value = []
        mock_db.return_value.__aenter__.return_value = mock_session
        resp = await client.get("/bills", headers={"User-Agent": "TestClient/1.0"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

async def test_get_bills_requires_user_agent(client):
    resp = await client.get("/bills")
    assert resp.status_code == 400

async def test_get_bill_detail_404_on_missing(client):
    with patch("app.routers.bills.get_db") as mock_db:
        mock_session = AsyncMock()
        mock_session.get.return_value = None
        mock_db.return_value.__aenter__.return_value = mock_session
        resp = await client.get(f"/bills/{uuid4()}", headers={"User-Agent": "TestClient/1.0"})
    assert resp.status_code == 404
```

- [x] **Step 2: Run — verify fail**

```bash
cd backend && pytest tests/test_api_bills.py -v
```

Expected: `ModuleNotFoundError` (app.main doesn't exist yet)

- [x] **Step 3: Create routers/bills.py**

```python
# backend/app/routers/bills.py
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db, require_user_agent
from app.models.bill import Bill
from app.models.ist_score import ISTScore
from app.models.friction_tag import FrictionTag
from app.schemas.bill import BillListItem, BillDetail, ISTScoreOut, FrictionTagOut

router = APIRouter(prefix="/bills", dependencies=[Depends(require_user_agent)])

@router.get("", response_model=list[BillListItem])
async def list_bills(
    session: str | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    q = select(Bill).where(Bill.is_corpus_only.is_(False))
    if session:
        q = q.where(Bill.session == session)
    if status:
        q = q.where(Bill.status == status)
    q = q.offset((page - 1) * size).limit(size)
    result = await db.execute(q)
    bills = result.scalars().all()
    return [BillListItem(
        id=b.id, bill_number=b.bill_number, title=b.title,
        state=b.state, session=b.session, status=b.status,
        copycat_alert=None,
    ) for b in bills]

@router.get("/search", response_model=list[BillListItem])
async def search_bills(
    q: str = Query(..., min_length=2),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Bill)
        .where(Bill.is_corpus_only.is_(False))
        .where(func.similarity(Bill.full_text, q) > 0.1)
        .order_by(func.similarity(Bill.full_text, q).desc())
        .limit(20)
    )
    bills = result.scalars().all()
    return [BillListItem(
        id=b.id, bill_number=b.bill_number, title=b.title,
        state=b.state, session=b.session, status=b.status,
        copycat_alert=None,
    ) for b in bills]

@router.get("/{bill_id}", response_model=BillDetail)
async def get_bill(bill_id: UUID, db: AsyncSession = Depends(get_db)):
    bill = await db.get(Bill, bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    score_result = await db.execute(select(ISTScore).where(ISTScore.bill_id == bill_id))
    score = score_result.scalar_one_or_none()

    tags_result = await db.execute(select(FrictionTag).where(FrictionTag.bill_id == bill_id))
    tags = tags_result.scalars().all()

    return BillDetail(
        id=bill.id,
        bill_number=bill.bill_number,
        title=bill.title,
        description=bill.description,
        state=bill.state,
        session=bill.session,
        status=bill.status,
        sponsors=bill.sponsors,
        ist_score=ISTScoreOut(
            source_authenticity_score=score.source_authenticity_score,
            copycat_alert=score.copycat_alert,
            analyzed_at=score.analyzed_at,
        ) if score else None,
        tags=[FrictionTagOut(type=t.tag_type, confidence=t.confidence) for t in tags],
    )
```

- [x] **Step 4: Create app/main.py (minimal, enough to run tests)**

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import bills, matches, tags, stats

app = FastAPI(title="LegiLens API", version="1.0.0")

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins.split(","),
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(bills.router)
app.include_router(matches.router)
app.include_router(tags.router)
app.include_router(stats.router)
```

- [x] **Step 5: Create stub routers for matches, tags, stats (so main.py imports don't fail)**

```python
# backend/app/routers/matches.py
from fastapi import APIRouter
router = APIRouter()

# backend/app/routers/tags.py
from fastapi import APIRouter
router = APIRouter()

# backend/app/routers/stats.py
from fastapi import APIRouter
router = APIRouter()
```

- [x] **Step 6: Create routers/__init__.py**

```bash
touch backend/app/routers/__init__.py backend/app/schemas/__init__.py
```

- [x] **Step 7: Run bills tests — verify pass**

```bash
cd backend && pytest tests/test_api_bills.py -v
```

Expected: all 3 `PASSED`

- [x] **Step 8: Commit**

```bash
git add backend/app/main.py backend/app/routers/ backend/app/schemas/
git commit -m "feat: bills router — list, search, detail endpoints"
```

---

## Task 4: Matches Router

**Files:**
- Modify: `backend/app/routers/matches.py`
- Test: `backend/tests/test_api_matches.py`

- [x] **Step 1: Write failing tests**

```python
# backend/tests/test_api_matches.py
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from decimal import Decimal

@pytest.fixture
async def client():
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

async def test_get_matches_returns_list(client):
    mock_match = MagicMock()
    mock_match.id = uuid4()
    mock_match.matched_bill_title = "HB-22-1001"
    mock_match.matched_state = "TX"
    mock_match.similarity_score = Decimal("87.42")
    mock_match.snippet_status = "verified"
    mock_match.matched_snippets = [{
        "co_context_before": "Intro.",
        "co_match": "The commission shall establish fees.",
        "co_context_after": "End.",
        "source_context_before": "Preamble.",
        "source_match": "The commission shall establish fees.",
        "source_context_after": "Close.",
    }]

    with patch("app.routers.matches.get_db") as mock_db:
        mock_session = AsyncMock()
        mock_session.execute.return_value.scalars.return_value.all.return_value = [mock_match]
        mock_db.return_value.__aenter__.return_value = mock_session
        resp = await client.get(
            f"/bills/{uuid4()}/matches",
            headers={"User-Agent": "TestClient/1.0"}
        )

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert data[0]["snippet_status"] == "verified"

async def test_ghost_match_returns_message(client):
    mock_match = MagicMock()
    mock_match.id = uuid4()
    mock_match.matched_bill_title = "SB-21-0042"
    mock_match.matched_state = "FL"
    mock_match.similarity_score = Decimal("74.11")
    mock_match.snippet_status = "source_verified_text_missing"
    mock_match.matched_snippets = None

    with patch("app.routers.matches.get_db") as mock_db:
        mock_session = AsyncMock()
        mock_session.execute.return_value.scalars.return_value.all.return_value = [mock_match]
        mock_db.return_value.__aenter__.return_value = mock_session
        resp = await client.get(
            f"/bills/{uuid4()}/matches",
            headers={"User-Agent": "TestClient/1.0"}
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["matched_snippets"][0]["message"] == "Source text unavailable for extraction"
```

- [x] **Step 2: Run — verify fail**

```bash
cd backend && pytest tests/test_api_matches.py -v
```

Expected: `FAILED` (stub router returns nothing)

- [x] **Step 3: Implement matches.py**

```python
# backend/app/routers/matches.py
from uuid import UUID
from pydantic import TypeAdapter
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db, require_user_agent
from app.models.similarity_match import SimilarityMatch
from app.schemas.match import MatchOut, SnippetItem, GhostMessage

router = APIRouter(prefix="/bills", dependencies=[Depends(require_user_agent)])

MatchList = TypeAdapter(list[SnippetItem | GhostMessage])

@router.get("/{bill_id}/matches", response_model=list[MatchOut])
async def get_matches(bill_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SimilarityMatch).where(SimilarityMatch.bill_id == bill_id)
    )
    matches = result.scalars().all()

    out = []
    for m in matches:
        if m.snippet_status == "source_verified_text_missing":
            snippets = [GhostMessage(message="Source text unavailable for extraction")]
        elif m.matched_snippets:
            snippets = MatchList.validate_python(m.matched_snippets)
        else:
            snippets = None

        out.append(MatchOut(
            id=m.id,
            matched_bill_title=m.matched_bill_title,
            matched_state=m.matched_state,
            similarity_score=m.similarity_score,
            snippet_status=m.snippet_status,
            matched_snippets=snippets,
        ))
    return out
```

- [x] **Step 4: Run — verify pass**

```bash
cd backend && pytest tests/test_api_matches.py -v
```

Expected: both `PASSED`

- [x] **Step 5: Commit**

```bash
git add backend/app/routers/matches.py backend/tests/test_api_matches.py
git commit -m "feat: matches router with ghost state and TypeAdapter validation"
```

---

## Task 5: Tags and Stats Routers

**Files:**
- Modify: `backend/app/routers/tags.py`
- Modify: `backend/app/routers/stats.py`
- Test: `backend/tests/test_api_stats.py`

- [x] **Step 1: Write failing tests**

```python
# backend/tests/test_api_stats.py
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch, MagicMock

@pytest.fixture
async def client():
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

async def test_stats_returns_counts(client):
    with patch("app.routers.stats.get_db") as mock_db:
        mock_session = AsyncMock()
        mock_session.execute.return_value.scalar.return_value = 42
        mock_db.return_value.__aenter__.return_value = mock_session
        resp = await client.get("/stats", headers={"User-Agent": "TestClient/1.0"})
    assert resp.status_code == 200
    data = resp.json()
    assert "total_co_bills" in data
    assert "copycat_alerts" in data

async def test_tags_returns_list(client):
    with patch("app.routers.tags.get_db") as mock_db:
        mock_session = AsyncMock()
        mock_session.execute.return_value.all.return_value = [("source_cloned", 12)]
        mock_db.return_value.__aenter__.return_value = mock_session
        resp = await client.get("/tags", headers={"User-Agent": "TestClient/1.0"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
```

- [x] **Step 2: Run — verify fail**

```bash
cd backend && pytest tests/test_api_stats.py -v
```

Expected: `FAILED`

- [x] **Step 3: Implement stats.py**

```python
# backend/app/routers/stats.py
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db, require_user_agent
from app.models.bill import Bill
from app.models.ist_score import ISTScore
from app.schemas.stats import StatsOut

router = APIRouter(dependencies=[Depends(require_user_agent)])

@router.get("/stats", response_model=StatsOut)
async def get_stats(db: AsyncSession = Depends(get_db)):
    total = await db.execute(select(func.count()).where(Bill.is_corpus_only.is_(False)))
    alerts = await db.execute(
        select(func.count()).select_from(ISTScore).where(ISTScore.copycat_alert.is_(True))
    )
    analyzed = await db.execute(select(func.count()).select_from(ISTScore))
    return StatsOut(
        total_co_bills=total.scalar() or 0,
        copycat_alerts=alerts.scalar() or 0,
        bills_analyzed=analyzed.scalar() or 0,
    )
```

- [x] **Step 4: Implement tags.py**

```python
# backend/app/routers/tags.py
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db, require_user_agent
from app.models.friction_tag import FrictionTag
from app.schemas.stats import TagCountOut

router = APIRouter(dependencies=[Depends(require_user_agent)])

@router.get("/tags", response_model=list[TagCountOut])
async def list_tags(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(FrictionTag.tag_type, func.count().label("count"))
        .group_by(FrictionTag.tag_type)
        .order_by(func.count().desc())
    )
    return [TagCountOut(tag_type=row[0], count=row[1]) for row in result.all()]
```

- [x] **Step 5: Run all API tests**

```bash
cd backend && pytest tests/test_api_bills.py tests/test_api_matches.py tests/test_api_stats.py -v
```

Expected: all `PASSED`

- [x] **Step 6: Commit**

```bash
git add backend/app/routers/tags.py backend/app/routers/stats.py backend/tests/test_api_stats.py
git commit -m "feat: tags and stats routers"
```

---

## Task 6: Rate Limiting

**Files:**
- Modify: `backend/app/main.py`

- [x] **Step 1: Add slowapi rate limiting to main.py**

```python
# backend/app/main.py — add these lines after existing imports
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

- [x] **Step 2: Run full test suite**

```bash
cd backend && pytest tests/ -v
```

Expected: all `PASSED`

- [x] **Step 3: Commit**

```bash
git add backend/app/main.py
git commit -m "feat: slowapi rate limiting (60 req/min per IP)"
```

---

## Task 7: Merge Sprint 2

- [x] **Step 1: Run full backend test suite**

```bash
cd backend && pytest tests/ -v --tb=short
```

Expected: all `PASSED`

- [x] **Step 2: Smoke test locally**

```bash
cd backend && uvicorn app.main:app --reload
# In another terminal:
curl -H "User-Agent: curl/7.0" http://localhost:8000/stats
```

Expected: JSON with `total_co_bills`, `copycat_alerts`, `bills_analyzed`

- [x] **Step 3: Merge to main**

```bash
git checkout main
git merge feat/api-layer --no-ff -m "feat: Sprint 2 — FastAPI layer complete"
git branch -d feat/api-layer
```
