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
