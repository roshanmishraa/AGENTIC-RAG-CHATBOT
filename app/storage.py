# app/storage.py

import os
import uuid
import boto3
from botocore.client import Config

from app.settings import settings


def get_storage():
    if settings.STORAGE_BACKEND == "r2":
        return R2Storage()
    return LocalStorage()


# ── Local (development only) ──────────────────────────────
class LocalStorage:
    BASE = "./uploads"

    async def save(self, user_id: str, filename: str, data: bytes) -> str:
        ext = filename.rsplit(".", 1)[-1].lower()
        unique_name = f"{uuid.uuid4()}.{ext}"
        folder = os.path.join(self.BASE, user_id)
        os.makedirs(folder, exist_ok=True)

        path = os.path.join(folder, unique_name)
        with open(path, "wb") as f:
            f.write(data)
        return path  # PostgreSQL mein yahi store hoga

    async def get_url(self, path: str) -> str:
        return f"/uploads/{path}"   # local serve (dev only)

    async def delete(self, path: str):
        if os.path.exists(path):
            os.remove(path)


# ── Cloudflare R2 (production) ────────────────────────────
class R2Storage:
    def __init__(self):
        endpoint = (
            f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
        )
        self.bucket = settings.R2_BUCKET_NAME
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )

    async def save(self, user_id: str, filename: str, data: bytes) -> str:
        ext = filename.rsplit(".", 1)[-1].lower()
        key = f"users/{user_id}/{uuid.uuid4()}.{ext}"
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
        )
        return key  # PostgreSQL mein yahi store hoga

    async def get_url(self, key: str, expires: int = 3600) -> str:
        # Presigned URL — 1 hour valid, directly R2 se serve hoga
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires,
        )

    async def delete(self, key: str):
        self.client.delete_object(Bucket=self.bucket, Key=key)