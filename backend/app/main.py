from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.config import settings
from app.routers import bills, matches, tags, stats, coverage

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

app = FastAPI(title="LegiLens API", version="1.0.0")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(bills.router)
app.include_router(matches.router)
app.include_router(tags.router)
app.include_router(stats.router)
app.include_router(coverage.router)
