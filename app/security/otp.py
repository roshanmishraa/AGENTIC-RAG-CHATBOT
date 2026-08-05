import random
import redis.asyncio as redis

from app.settings import settings

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

OTP_TTL_SECONDS = 300   # 5 minutes validity
OTP_KEY_PREFIX = "otp:"


def generate_otp() -> str:
    return str(random.randint(100000, 999999))   # 6-digit OTP


async def store_otp(email: str, otp: str):
    await redis_client.set(f"{OTP_KEY_PREFIX}{email}", otp, ex=OTP_TTL_SECONDS)


async def verify_otp(email: str, otp: str) -> bool:
    stored = await redis_client.get(f"{OTP_KEY_PREFIX}{email}")
    if stored and stored == otp:
        await redis_client.delete(f"{OTP_KEY_PREFIX}{email}")   # one-time use, delete after verify
        return True
    return False