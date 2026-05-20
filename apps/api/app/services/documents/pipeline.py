"""Document ingest pipeline: upload → store → OCR → parse → index."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import UploadFile

from app.services.documents.ocr import get_ocr_provider
from app.services.documents.parser import parse
from app.services.storage.s3 import S3Storage


class DocumentPipeline:
    def __init__(self) -> None:
        self.storage = S3Storage()
        self.ocr = get_ocr_provider()
        self._demo: dict[str, dict] = _seed_demo()

    def list_demo(self) -> list[dict]:
        return list(self._demo.values())

    def get(self, doc_id: str) -> dict:
        return self._demo[doc_id]

    async def ingest(self, file: UploadFile) -> dict[str, Any]:
        content = await file.read()
        doc_id = f"doc_{uuid.uuid4().hex[:10]}"
        key = f"documents/{doc_id}/{file.filename}"
        self.storage.put(key, content, content_type=file.content_type or "application/octet-stream")

        ocr = await self.ocr.extract(content=content, mime=file.content_type or "")
        parsed = parse("invoice", ocr["text"])

        doc = {
            "id": doc_id,
            "title": file.filename,
            "type": "INVOICE",
            "status": "PARSED",
            "storage_key": key,
            "ocr_text": ocr["text"],
            "parsed": parsed,
        }
        self._demo[doc_id] = doc
        return doc


def _seed_demo() -> dict[str, dict]:
    return {
        "doc_demo1": {
            "id": "doc_demo1",
            "title": "Contract — TOO ABC.pdf",
            "type": "CONTRACT",
            "status": "PARSED",
            "parsed": {"counterparty": "TOO ABC", "amount": "1,200,000 KZT"},
        },
        "doc_demo2": {
            "id": "doc_demo2",
            "title": "Invoice #INV-2025-014.pdf",
            "type": "INVOICE",
            "status": "PARSED",
            "parsed": {"number": "INV-2025-014", "total": "850000"},
        },
    }
