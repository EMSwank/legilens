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

