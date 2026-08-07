"""S3-compatible storage adapter (MinIO/AWS/R2)."""
from __future__ import annotations

import boto3
from botocore.client import Config

from app.core.config import settings
from app.services.storage.base import Storage


def _client_for(endpoint: str):
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=Config(signature_version="s3v4"),
    )


class S3Storage(Storage):
    def __init__(self) -> None:
        # Internal client — actual put/get traffic from the api container
        # stays on the Docker network, never leaves the host.
        self._client = _client_for(settings.s3_endpoint)
        self.bucket = settings.s3_bucket

        # Presigning client — SigV4 signs the request's `host` header, so a
        # URL must be generated against whatever host will actually receive
        # it. If s3_public_endpoint differs from s3_endpoint (internal
        # Docker hostname vs. a public domain proxied to MinIO), presigning
        # needs its own client bound to that public host — swapping the
        # host in an already-signed URL would just invalidate the signature.
        public_endpoint = settings.s3_public_endpoint or settings.s3_endpoint
        self._presign_client = (
            self._client if public_endpoint == settings.s3_endpoint
            else _client_for(public_endpoint)
        )

    def put(self, key: str, body: bytes, *, content_type: str) -> str:
        self._client.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType=content_type)
        return key

    def get(self, key: str) -> bytes:
        return self._client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def presign_get(self, key: str, *, expires_in: int = 600) -> str:
        return self._presign_client.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=expires_in,
        )
