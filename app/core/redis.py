from redis.asyncio import Redis

from .config import settings

JTI_EXPIRY = 3600

token_blocklist = Redis.from_url(settings.REDIS_URL, decode_responses=True)


async def add_jti_to_blocklist(jti: str) -> None:
    await token_blocklist.set(name=jti, value="", ex=JTI_EXPIRY)


async def token_in_blocklist(jti: str) -> bool:
    return await token_blocklist.get(jti) is not None
