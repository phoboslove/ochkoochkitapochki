"""OCR provider abstraction with chaos-handling.

Each provider returns ``{text, blocks, confidence, warnings, rotation}``.
``warnings`` is a list of soft signals (low contrast, partial page, handwriting…)
that the UI surfaces without failing the document.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.core.config import settings


LARGE_FILE_THRESHOLD = 12 * 1024 * 1024  # 12 MB
LOW_CONFIDENCE_THRESHOLD = 0.65


class OCRProvider(ABC):
    @abstractmethod
    async def extract(self, *, content: bytes, mime: str) -> dict[str, Any]: ...


class MockOCR(OCRProvider):
    async def extract(self, *, content: bytes, mime: str) -> dict[str, Any]:
        warnings: list[str] = []
        if len(content) > LARGE_FILE_THRESHOLD:
            warnings.append("Large file — only the first pages were sampled.")
        if mime.startswith("image/"):
            warnings.append("Image input — confidence may be reduced for handwriting or low-contrast scans.")
        if mime == "application/pdf" and not content.startswith(b"%PDF"):
            warnings.append("Malformed PDF header — extracted text may be incomplete.")
        if len(content) < 200:
            warnings.append("Very small payload — likely a partial upload.")
        confidence = 0.99 if not warnings else max(0.45, 0.99 - 0.15 * len(warnings))
        return {
            "text": "[mock OCR]\nInvoice #INV-2025-001\nTotal: 125,000 KZT",
            "blocks": [], "confidence": round(confidence, 2),
            "warnings": warnings, "rotation": 0,
        }


class AzureDocIntelOCR(OCRProvider):
    """Azure AI Document Intelligence (prebuilt-read model).

    Required env:
      AZURE_DOC_INTEL_ENDPOINT — https://<resource>.cognitiveservices.azure.com
      AZURE_DOC_INTEL_KEY     — subscription key
    """
    async def extract(self, *, content: bytes, mime: str) -> dict[str, Any]:
        import asyncio, httpx
        ep = (settings.azure_doc_intel_endpoint or "").rstrip("/")
        key = settings.azure_doc_intel_key
        if not ep or not key:
            raise RuntimeError("Azure Document Intelligence not configured "
                               "(set AZURE_DOC_INTEL_ENDPOINT and AZURE_DOC_INTEL_KEY)")
        url = f"{ep}/formrecognizer/documentModels/prebuilt-read:analyze?api-version=2023-07-31"
        headers = {"Ocp-Apim-Subscription-Key": key,
                   "Content-Type": mime or "application/octet-stream"}
        warnings: list[str] = []

        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(url, content=content, headers=headers)
            if r.status_code != 202:
                raise RuntimeError(f"Azure submit {r.status_code}: {r.text[:200]}")
            op = r.headers.get("Operation-Location")
            if not op:
                raise RuntimeError("Azure: missing Operation-Location header")
            for _ in range(30):
                await asyncio.sleep(1)
                poll = await c.get(op, headers={"Ocp-Apim-Subscription-Key": key})
                if poll.status_code != 200:
                    raise RuntimeError(f"Azure poll {poll.status_code}: {poll.text[:200]}")
                data = poll.json()
                if data.get("status") == "succeeded":
                    break
                if data.get("status") == "failed":
                    raise RuntimeError(f"Azure failed: {data.get('error')}")
            else:
                raise RuntimeError("Azure analysis timed out (30s)")

        result = (data or {}).get("analyzeResult") or {}
        pages  = result.get("pages") or []
        lines: list[str] = []
        confs: list[float] = []
        for p in pages:
            for line in (p.get("lines") or []):
                if (t := (line.get("content") or "").strip()): lines.append(t)
            for w in (p.get("words") or []):
                if (c := w.get("confidence")) is not None: confs.append(float(c))

        text = "\n".join(lines)
        confidence = (sum(confs) / len(confs)) if confs else 0.95
        if len(pages) > 5:
            warnings.append(f"{len(pages)}-page document — verify table extraction manually.")
        if confidence < 0.7:
            warnings.append(f"Low confidence {round(confidence*100)}%; review extracted fields.")

        return {"text": text, "blocks": [], "confidence": round(confidence, 3),
                "warnings": warnings, "rotation": 0, "pages": len(pages)}


class OCRSpaceOCR(OCRProvider):
    """OCR.Space (https://ocr.space) — free MVP-grade provider.

    Pros:  no infra setup, supports PDF + images + multipage out of the box,
           Russian/Kazakh/English models, JSON over HTTP.
    Cons:  free tier limits (1 MB file / 3-page PDF / 25k req/month),
           per-line confidence not exposed without overlay mode.

    Response is normalized to the same shape as Azure / Mock so the rest of the
    document pipeline (DocumentService._run_ocr, anomaly detection, recovery)
    doesn't care which provider produced it.
    """

    API_URL = "https://api.ocr.space/parse/image"

    async def extract(self, *, content: bytes, mime: str) -> dict[str, Any]:
        import httpx
        api_key = settings.ocr_space_api_key
        if not api_key:
            raise RuntimeError(
                "OCR.Space not configured: set OCR_SPACE_API_KEY in apps/api/.env",
            )
        warnings: list[str] = []

        # Free-tier hard limits — fail early with actionable hint.
        size_mb = len(content) / (1024 * 1024)
        if size_mb > 1:
            warnings.append(
                f"File is {size_mb:.1f} MB; OCR.Space free tier rejects > 1 MB. "
                "Upgrade plan or compress before retry.",
            )

        ext = _ext_for(mime)
        files = {"file": (f"document.{ext}", content, mime or "application/octet-stream")}
        data = {
            "apikey": api_key,
            "language": settings.ocr_space_language,
            "isOverlayRequired": "false",
            "scale": "true",                 # upscale low-res images
            "detectOrientation": "true",
            "OCREngine": "2",                # better Cyrillic accuracy than engine 1
            "isTable": "true",               # preserve table layout when possible
        }
        if mime == "application/pdf":
            data["filetype"] = "PDF"

        try:
            async with httpx.AsyncClient(timeout=120) as c:
                r = await c.post(self.API_URL, data=data, files=files)
        except httpx.HTTPError as exc:
            raise RuntimeError(f"OCR.Space network error: {exc}")
        if r.status_code != 200:
            raise RuntimeError(f"OCR.Space HTTP {r.status_code}: {r.text[:200]}")

        try:
            payload = r.json()
        except Exception:  # noqa: BLE001
            raise RuntimeError("OCR.Space returned non-JSON response")

        if payload.get("IsErroredOnProcessing"):
            err = payload.get("ErrorMessage") or payload.get("ErrorDetails") or "unknown"
            if isinstance(err, list): err = "; ".join(str(x) for x in err)
            raise RuntimeError(f"OCR.Space processing error: {str(err)[:240]}")

        results = payload.get("ParsedResults") or []
        if not results:
            raise RuntimeError("OCR.Space returned no parsed results")

        page_texts: list[str] = []
        page_errors: list[str] = []
        for i, p in enumerate(results, start=1):
            txt = (p.get("ParsedText") or "").strip()
            if txt: page_texts.append(txt)
            exit_code = p.get("FileParseExitCode")
            if exit_code is not None and int(exit_code) != 1:
                msg = p.get("ErrorMessage") or p.get("ErrorDetails") or f"exit code {exit_code}"
                page_errors.append(f"page {i}: {msg}")

        text = "\n\n".join(page_texts)
        pages = len(results)
        proc_ms = int(payload.get("ProcessingTimeInMilliseconds") or 0)

        # OCR.Space free tier doesn't expose per-line confidence. We derive a
        # heuristic: empty text → 0; small text → 0.6; normal/long text → 0.85;
        # error code present → 0.5. Adjusted down by warnings.
        if not text:
            confidence = 0.0
            warnings.append("OCR.Space returned no text — document may be a scan-of-scan or empty page.")
        elif page_errors:
            confidence = 0.5
        elif len(text) < 80:
            confidence = 0.6
        else:
            confidence = 0.85
        confidence = max(0.0, min(1.0, confidence - 0.05 * len([w for w in warnings if w])))

        if pages > 3:
            warnings.append(f"{pages}-page PDF — OCR.Space free tier truncates after 3 pages.")
        if page_errors:
            warnings.extend(page_errors)

        return {
            "text": text, "blocks": [],
            "confidence": round(confidence, 2),
            "warnings": warnings, "rotation": 0,
            "pages": pages,
            "engine": "ocr_space",
            "processing_ms": proc_ms,
        }


def _ext_for(mime: str) -> str:
    if mime == "application/pdf": return "pdf"
    if mime.startswith("image/png"):  return "png"
    if mime.startswith("image/jpeg"): return "jpg"
    if mime.startswith("image/tiff"): return "tif"
    if mime.startswith("image/webp"): return "webp"
    return "bin"


def get_ocr_provider() -> OCRProvider:
    p = settings.ocr_provider.lower()
    if p == "azure":     return AzureDocIntelOCR()
    if p == "ocr_space": return OCRSpaceOCR()
    return MockOCR()
