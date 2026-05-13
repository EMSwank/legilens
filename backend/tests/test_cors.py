from httpx import AsyncClient, ASGITransport


async def test_cors_allows_configured_production_origin():
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.options(
            "/stats",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "User-Agent": "TestClient/1.0",
            },
        )
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"


async def test_cors_allows_vercel_preview_via_regex():
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.options(
            "/stats",
            headers={
                "Origin": "https://legilens-abc123-feat-foo.vercel.app",
                "Access-Control-Request-Method": "GET",
                "User-Agent": "TestClient/1.0",
            },
        )
    assert resp.headers.get("access-control-allow-origin") == "https://legilens-abc123-feat-foo.vercel.app"


async def test_cors_rejects_unrelated_origin():
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.options(
            "/stats",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "GET",
                "User-Agent": "TestClient/1.0",
            },
        )
    assert resp.headers.get("access-control-allow-origin") is None
