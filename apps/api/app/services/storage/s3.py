"""S3-compatible storage adapter (MinIO/AWS/R2)."""
from __future__ import annotations

import boto3
from botocore.client import Config

from app.core.config import settings
from app.services.storage.base import Storage


class S3Storage(Storage):
    def __init__(self) -> None:
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            config=Config(signature_version="s3v4"),
        )
        self.bucket = settings.s3_bucket

    def put(self, key: str, body: bytes, *, content_type: str) -> str:
        self._client.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType=content_type)
        return key

    def get(self, key: str) -> bytes:
        return self._client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def presign_get(self, key: str, *, expires_in: int = 600) -> str:
        return self._client.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=expires_in,
        )
