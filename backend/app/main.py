from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import bills, matches, tags, stats

app = FastAPI(title="LegiLens API", version="1.0.0")

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(bills.router)
app.include_router(matches.router)
app.include_router(tags.router)
app.include_router(stats.router)
