from app.core.config import settings
from app.services.storage.base import Storage
from app.services.storage.local import LocalStorage


def get_storage() -> Storage:
    if settings.storage_backend == "s3":
        from app.services.storage.s3 import S3Storage
        return S3Storage()  # type: ignore[return-value]
    return LocalStorage()
