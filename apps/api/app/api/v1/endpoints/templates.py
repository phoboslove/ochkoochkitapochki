"""Template endpoints — library, analysis, mapping, render preview, versions."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import CurrentUser, get_current_user, require_admin
from app.db.models import Template
from app.services.audit.logger import AuditLogger
from app.services.storage import get_storage
from app.services.templates.converter import (
    convert_to, find_soffice, is_available, ConverterUnavailable, TARGET_FOR,
)
from app.services.templates.placeholders import CANONICAL, GROUP_ORDER
from app.services.templates.validator import validate as validate_template
from app.services.templates.renderer import (
    build_context_from_template, build_demo_context, render_template,
)
from app.services.templates.service import TemplateService

router = APIRouter()
service = TemplateService()
audit = AuditLogger()


def _summary(t) -> dict:
    return {
        "id": t.id, "name": t.name, "kind": t.kind, "format": t.format,
        "is_default": t.is_default, "status": t.status, "version": t.version,
        "language": t.language, "confidence": t.confidence,
        "original_filename": t.original_filename, "file_hash": t.file_hash,
        "industry": t.industry,
        "validation_score":    t.validation_score,
        "validation_warnings": t.validation_warnings or [],
        "converted_from_id":   t.converted_from_id,
        "updated_at":     t.updated_at.isoformat() if t.updated_at else None,
        "last_render_at": t.last_render_at.isoformat() if t.last_render_at else None,
        "last_error":     t.last_error,
        "parent_template_id": t.parent_template_id,
    }


def _detail(t) -> dict:
    return {
        **_summary(t),
        "detected_fields": t.detected_fields or {},
        "detected_tables": t.detected_tables or [],
        "mappings":        t.mappings or {},
        "body":            t.body if t.format == "html" else None,
        "storage_key":     t.body if t.format != "html" else None,
    }


@router.get("")
async def list_templates(
    kind: str | None = None,
    industry: str | None = None,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    rows = await service.list(session, user.company_id, kind)
    if industry: rows = [r for r in rows if r.industry == industry]
    return [_summary(t) for t in rows]


@router.get("/industry-packs")
async def industry_packs(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    rows = await service.list(session, user.company_id)
    counts: dict[str, int] = {}
    for r in rows:
        counts[r.industry or "general"] = counts.get(r.industry or "general", 0) + 1
    return {"packs": [{"industry": k, "count": v}
                      for k, v in sorted(counts.items(), key=lambda x: -x[1])]}


@router.get("/converter-status")
async def converter_status(_: CurrentUser = Depends(get_current_user)) -> dict:
    return {"available": is_available(), "soffice_path": find_soffice()}


@router.get("/clusters")
async def clusters(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Heuristic corpus clustering — groups by (industry × kind) and finds
    duplicate-suspects by tag overlap. Defined BEFORE /{tpl_id} for routing."""
    rows = await service.list(session, user.company_id)
    by_cluster: dict[str, list[dict]] = {}
    by_tag: dict[str, list[str]] = {}
    for t in rows:
        if t.status == "ARCHIVED": continue
        key = f"{t.industry or 'general'}/{t.kind}"
        by_cluster.setdefault(key, []).append({
            "id": t.id, "name": t.name, "format": t.format, "status": t.status,
            "language": t.language, "verified": t.status == "VERIFIED",
        })
        for tag in ((t.detected_fields or {}).get("semantic", {}).get("tags") or []):
            by_tag.setdefault(tag, []).append(t.id)
    duplicates = [{"tag": tag, "templates": ids}
                  for tag, ids in by_tag.items() if len(ids) >= 4]
    return {
        "clusters": [{"key": k, "count": len(v), "templates": v[:12]}
                     for k, v in sorted(by_cluster.items(), key=lambda kv: -len(kv[1]))],
        "duplicate_suspects": sorted(duplicates, key=lambda d: -len(d["templates"]))[:12],
        "total_active": sum(1 for t in rows if t.status != "ARCHIVED"),
    }


@router.get("/registry")
async def field_registry(_: CurrentUser = Depends(get_current_user)) -> dict:
    return {
        "groups": GROUP_ORDER,
        "fields": [
            {"key": f.key, "group": f.group, "label": f.label, "sample": f.sample}
            for f in CANONICAL.values()
        ],
    }


@router.get("/{tpl_id}")
async def get_template(
    tpl_id: str,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    t = await service.get(session, user.company_id, tpl_id)
    if not t: raise HTTPException(404, "template not found")
    return _detail(t)


@router.get("/{tpl_id}/reliability")
async def template_reliability(
    tpl_id: str,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Operational reliability for one template.

    Aggregates the recent render history (last 20) for this template and
    returns the same numbers the matcher consults — render success rate,
    fallback rate, average quality, approval-block rate, and a single
    ``operational_score`` (0–100). Useful for ops UI + debug.
    """
    t = await service.get(session, user.company_id, tpl_id)
    if not t:
        raise HTTPException(404, "template not found")
    from app.services.templates.reliability import compute_reliability
    rel = await compute_reliability(session, template_id=t.id, company_id=user.company_id)
    return {"template_id": t.id, "name": t.name, "kind": t.kind, **rel.as_dict()}


@router.get("/{tpl_id}/versions")
async def template_versions(
    tpl_id: str,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    rows = await service.versions(session, user.company_id, tpl_id)
    return [_summary(t) for t in rows]


class UpsertTemplateIn(BaseModel):
    id: str | None = None
    name: str
    kind: str = "invoice"
    format: str = "html"
    body: str
    is_default: bool = False


@router.put("")
async def upsert_template(
    body: UpsertTemplateIn,
    user: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    t = await service.upsert(session, company_id=user.company_id, **body.model_dump())
    await session.commit()
    return _summary(t)


_EXT_FORMAT = {".docx":"docx",".xlsx":"xlsx",".pdf":"pdf",".rtf":"rtf",".doc":"doc",".xls":"xls"}


def _detect_format(file: UploadFile) -> str:
    name = (file.filename or "").lower()
    for ext, fmt in _EXT_FORMAT.items():
        if name.endswith(ext): return fmt
    ct = file.content_type or ""
    if "wordprocessingml" in ct: return "docx"
    if "spreadsheetml"   in ct: return "xlsx"
    if ct == "application/pdf": return "pdf"
    if "rtf" in ct:             return "rtf"
    raise HTTPException(400, "Unsupported file. Use .docx, .xlsx, .pdf, .rtf, .doc, .xls")


def _mime_of(fmt: str) -> str:
    return {
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pdf":  "application/pdf",
        "rtf":  "application/rtf",
        "doc":  "application/msword",
        "xls":  "application/vnd.ms-excel",
        "html": "text/html",
    }.get(fmt, "application/octet-stream")


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    name: str = Form(...),
    kind: str = Form(""),
    is_default: bool = Form(False),
    user: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    fmt = _detect_format(file)
    content = await file.read()
    if len(content) > 8 * 1024 * 1024:
        raise HTTPException(400, "Max template size is 8 MB")
    storage_key = f"{user.company_id}/templates/{datetime.utcnow():%Y%m%d}/{file.filename}"
    get_storage().put(storage_key, content, content_type=file.content_type or _mime_of(fmt))

    tpl = await service.ingest(
        session, company_id=user.company_id, actor_id=user.id,
        name=name or (file.filename or "Template"), filename=file.filename or "template",
        mime=file.content_type or _mime_of(fmt), storage_key=storage_key, content=content,
        is_default=is_default,
    )
    if kind and kind in {"invoice","act","nakladnaya","contract","proposal","unknown"}:
        tpl.kind = kind
    await session.commit()
    return _detail(tpl)


@router.post("/upload-docx")
async def upload_docx_compat(
    file: UploadFile = File(...),
    name: str = Form(...),
    kind: str = Form("invoice"),
    is_default: bool = Form(False),
    user: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await upload_file(file=file, name=name, kind=kind, is_default=is_default,
                             user=user, session=session)


class MappingIn(BaseModel):
    mappings: dict[str, dict[str, Any]]
    confirm_all: bool = False


@router.patch("/{tpl_id}/mappings")
async def patch_mappings(
    tpl_id: str, body: MappingIn,
    user: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    t = await service.get(session, user.company_id, tpl_id)
    if not t: raise HTTPException(404, "template not found")
    t = await service.update_mappings(
        session, t, mappings=body.mappings, confirm_all=body.confirm_all, actor_id=user.id,
    )
    await session.commit()
    return _detail(t)


@router.post("/{tpl_id}/preview")
async def render_preview(
    tpl_id: str,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    t = await service.get(session, user.company_id, tpl_id)
    if not t: raise HTTPException(404, "template not found")

    if t.format == "html":
        body_bytes = (t.body or "").encode("utf-8")
    else:
        try:
            body_bytes = get_storage().get(t.body)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(404, f"original file missing: {exc}")

    context = build_context_from_template(t.mappings or {}, build_demo_context())
    try:
        rendered, mime_out, ext = render_template(content=body_bytes, format=t.format, context=context)
    except Exception as exc:  # noqa: BLE001
        t.last_error = str(exc)[:500]
        await audit.record(
            session, company_id=user.company_id, actor_type="system",
            action="template.render_failed", resource=t.id, meta={"error": str(exc)[:200]},
        )
        await session.commit()
        raise HTTPException(500, f"render failed: {exc}")

    preview_key = f"{user.company_id}/templates/{t.id}/preview.{ext}"
    storage = get_storage()
    storage.put(preview_key, rendered, content_type=mime_out)
    t.last_render_at = datetime.utcnow()
    t.last_error = None
    await audit.record(
        session, company_id=user.company_id, actor_type="user", actor_id=user.id,
        action="template.rendered", resource=t.id,
        meta={"format": ext, "size": len(rendered)},
    )
    await session.commit()
    return {
        "preview_url": storage.presign_get(preview_key, expires_in=3600),
        "mime": mime_out, "ext": ext, "bytes": len(rendered),
    }


@router.post("/{tpl_id}/archive")
async def archive(
    tpl_id: str,
    user: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    t = await service.get(session, user.company_id, tpl_id)
    if not t: raise HTTPException(404, "template not found")
    t = await service.archive(session, t, actor_id=user.id)
    await session.commit()
    return _summary(t)


@router.post("/{tpl_id}/make-default")
async def make_default(
    tpl_id: str,
    user: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    t = await service.get(session, user.company_id, tpl_id)
    if not t: raise HTTPException(404, "template not found")
    for other in await service.list(session, user.company_id, t.kind):
        if other.id != t.id and other.is_default:
            other.is_default = False
    t.is_default = True
    await audit.record(
        session, company_id=user.company_id, actor_type="user", actor_id=user.id,
        action="template.made_default", resource=t.id, meta={"kind": t.kind},
    )
    await session.commit()
    return _summary(t)


@router.post("/{tpl_id}/convert")
async def convert_legacy(
    tpl_id: str,
    user: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Convert a legacy .doc/.xls/.rtf template to .docx/.xlsx via LibreOffice.
    Creates a new Template row (lineage preserved through `converted_from_id`)
    and re-analyzes it. The original stays in the library as ARCHIVED."""
    src = await service.get(session, user.company_id, tpl_id)
    if not src: raise HTTPException(404, "template not found")
    if src.format not in ("doc", "xls", "rtf"):
        raise HTTPException(400, f"format {src.format!r} does not need conversion")

    target = TARGET_FOR[src.format]
    try:
        original = get_storage().get(src.body)
        out = convert_to(original, source_filename=src.original_filename or "input",
                         target=target)
    except ConverterUnavailable as exc:
        await audit.record(
            session, company_id=user.company_id, actor_type="system",
            action="template.conversion_failed", resource=src.id,
            meta={"reason": "libreoffice_missing"},
        )
        await session.commit()
        raise HTTPException(503, str(exc))
    except Exception as exc:  # noqa: BLE001
        src.last_error = f"convert: {exc}"[:500]
        await audit.record(
            session, company_id=user.company_id, actor_type="system",
            action="template.conversion_failed", resource=src.id,
            meta={"error": str(exc)[:200]},
        )
        await session.commit()
        raise HTTPException(500, f"conversion failed: {exc}")

    # Persist converted file + new Template via the normal ingest pipeline.
    new_name = (src.original_filename or src.name).rsplit(".", 1)[0] + f".{target}"
    storage_key = f"{user.company_id}/templates/converted/{new_name}"
    get_storage().put(storage_key, out,
                      content_type=_mime_of(target))
    new_tpl = await service.ingest(
        session, company_id=user.company_id, actor_id=user.id,
        name=src.name, filename=new_name, mime=_mime_of(target),
        storage_key=storage_key, content=out, is_default=False,
    )
    new_tpl.kind = src.kind                # preserve user-confirmed classification
    new_tpl.converted_from_id = src.id
    new_tpl.industry = src.industry
    # Archive the legacy original.
    src.status = "ARCHIVED"
    src.last_error = None
    await audit.record(
        session, company_id=user.company_id, actor_type="user", actor_id=user.id,
        action="template.converted", resource=new_tpl.id,
        meta={"from": src.id, "src_format": src.format, "to_format": target,
              "size": len(out)},
    )
    await session.commit()
    return _detail(new_tpl)


@router.post("/convert-legacy-all")
async def convert_all_legacy(
    user: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Best-effort: walk every non-archived legacy template and convert it.
    Returns a per-file report. Failures never abort the batch."""
    rows = await service.list(session, user.company_id)
    legacy = [r for r in rows if r.format in ("doc", "xls") and r.status != "ARCHIVED"]
    if not is_available():
        raise HTTPException(503, "LibreOffice is not installed on this host.")

    report = {"total": len(legacy), "converted": 0, "failed": 0, "items": []}
    for src in legacy:
        target = TARGET_FOR[src.format]
        try:
            original = get_storage().get(src.body)
            out = convert_to(original, source_filename=src.original_filename or "input",
                             target=target)
        except Exception as exc:  # noqa: BLE001
            src.last_error = f"convert: {exc}"[:500]
            await audit.record(
                session, company_id=user.company_id, actor_type="system",
                action="template.conversion_failed", resource=src.id,
                meta={"error": str(exc)[:200]},
            )
            report["failed"] += 1
            report["items"].append({"id": src.id, "name": src.name, "status": "failed",
                                     "error": str(exc)[:160]})
            continue
        new_name = (src.original_filename or src.name).rsplit(".", 1)[0] + f".{target}"
        storage_key = f"{user.company_id}/templates/converted/{new_name}"
        get_storage().put(storage_key, out, content_type=_mime_of(target))
        new_tpl = await service.ingest(
            session, company_id=user.company_id, actor_id=user.id,
            name=src.name, filename=new_name, mime=_mime_of(target),
            storage_key=storage_key, content=out, is_default=False,
        )
        new_tpl.kind = src.kind
        new_tpl.converted_from_id = src.id
        new_tpl.industry = src.industry
        src.status = "ARCHIVED"
        src.last_error = None
        await audit.record(
            session, company_id=user.company_id, actor_type="user", actor_id=user.id,
            action="template.converted", resource=new_tpl.id,
            meta={"from": src.id, "to_format": target},
        )
        report["converted"] += 1
        report["items"].append({"id": new_tpl.id, "name": new_tpl.name, "status": "converted"})
    await session.commit()
    return report


class RebuildIn(BaseModel):
    folder: str


@router.post("/rebuild")
async def rebuild_corpus(
    body: RebuildIn,
    user: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """End-to-end corpus rebuild after on-disk conversion.

    1. Re-ingest every .docx/.xlsx/.rtf/.pdf in the folder (dedup by hash).
    2. For every new modern file, find a legacy sibling (.doc/.xls) by basename
       and archive it with `converted_from_id` lineage preserved.
    3. Re-run industry classification + validation across the whole corpus.
    """
    from pathlib import Path
    from sqlalchemy import select
    from app.services.templates.industry import classify_industry

    root = Path(body.folder).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise HTTPException(400, f"folder not found: {root}")

    SUPPORTED = (".docx", ".xlsx", ".pdf", ".rtf")
    ingested = 0; skipped = 0
    new_modern: dict[str, Template] = {}      # basename(stem) → new template

    for path in sorted(root.iterdir()):
        if not path.is_file(): continue
        ext = path.suffix.lower()
        if ext not in SUPPORTED:
            skipped += 1; continue
        fmt = _EXT_FORMAT[ext]
        content = path.read_bytes()
        name = path.stem.replace("_", " ").replace("-", " ").strip().capitalize()
        storage_key = f"{user.company_id}/templates/rebuild/{path.name}"
        get_storage().put(storage_key, content, content_type=_mime_of(fmt))
        tpl = await service.ingest(
            session, company_id=user.company_id, actor_id=user.id,
            name=name, filename=path.name, mime=_mime_of(fmt),
            storage_key=storage_key, content=content, is_default=False,
        )
        if ext in (".docx", ".xlsx") and tpl.status != "ARCHIVED":
            key = _strip_kz(path.stem.lower())
            new_modern[key] = tpl
        ingested += 1

    # Auto-archive legacy with a converted sibling (matched by basename).
    archived = 0
    all_rows = list(await session.scalars(
        select(Template).where(Template.company_id == user.company_id),
    ))
    for t in [x for x in all_rows if x.format in ("doc", "xls") and x.status != "ARCHIVED"]:
        base = _strip_kz(Path(t.original_filename or t.name).stem.lower())
        replacement = new_modern.get(base)
        if replacement:
            t.status = "ARCHIVED"
            t.last_error = None
            replacement.converted_from_id = t.id
            archived += 1
            await audit.record(
                session, company_id=user.company_id, actor_type="user", actor_id=user.id,
                action="template.converted", resource=replacement.id,
                meta={"from": t.id, "linkage": "filename_match"},
            )

    # Reclassify + revalidate.
    by_industry: dict[str, int] = {}
    by_qa: dict[str, int] = {}
    for r in await service.list(session, user.company_id):
        paragraphs = (r.detected_fields or {}).get("paragraphs", []) or []
        r.industry = classify_industry(r.original_filename or r.name, paragraphs)
        score, warnings, qa = validate_template(r)
        r.validation_score = score
        r.validation_warnings = warnings
        if qa == "VERIFIED" and r.status != "ARCHIVED":
            r.status = "VERIFIED"
        elif qa == "BROKEN" and r.status != "ARCHIVED":
            r.status = "FAILED"
        by_industry[r.industry] = by_industry.get(r.industry, 0) + 1
        by_qa[qa] = by_qa.get(qa, 0) + 1

    await audit.record(
        session, company_id=user.company_id, actor_type="user", actor_id=user.id,
        action="template.corpus_rebuild",
        meta={"ingested": ingested, "archived_legacy": archived,
              "by_industry": by_industry, "by_qa": by_qa},
    )
    await session.commit()
    return {
        "folder": str(root),
        "ingested_or_skipped_duplicate": ingested,
        "skipped_unsupported": skipped,
        "archived_legacy": archived,
        "new_modern_count": len(new_modern),
        "by_industry": by_industry, "by_qa": by_qa,
    }


def _strip_kz(stem: str) -> str:
    """`a-2-akt_kz` → `a-2-akt` so RU and KZ variants resolve to same legacy parent."""
    return stem[:-3] if stem.endswith("_kz") else stem


@router.post("/{tpl_id}/summarize")
async def summarize_one(
    tpl_id: str,
    user: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Run AI semantic enrichment on one template — summary, purpose, tags, kind/industry probability."""
    from app.services.templates.semantic import summarize
    t = await service.get(session, user.company_id, tpl_id)
    if not t: raise HTTPException(404, "template not found")
    paragraphs = (t.detected_fields or {}).get("paragraphs") or []
    result = await summarize(paragraphs=paragraphs,
                             filename=t.original_filename or t.name,
                             kind=t.kind, language=t.language)
    df = dict(t.detected_fields or {})
    df["semantic"] = result
    t.detected_fields = df
    if not t.industry or t.industry == "general":
        if result.get("probable_industry"):
            t.industry = result["probable_industry"]
    await audit.record(
        session, company_id=user.company_id, actor_type="user", actor_id=user.id,
        action="template.summarized", resource=t.id,
        meta={"model": result.get("model"), "tags": result.get("tags")},
    )
    await session.commit()
    return {"id": t.id, "semantic": result}


@router.post("/summarize-all")
async def summarize_all(
    user: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    limit: int = 30,
) -> dict:
    """Bulk-summarize the first N non-archived templates that don't have a recent
    `semantic` block yet. Capped to keep OpenAI usage in check."""
    from app.services.templates.semantic import summarize
    rows = await service.list(session, user.company_id)
    todo = [t for t in rows if t.status != "ARCHIVED"
            and not ((t.detected_fields or {}).get("semantic"))][:limit]
    done = 0
    for t in todo:
        paragraphs = (t.detected_fields or {}).get("paragraphs") or []
        result = await summarize(paragraphs=paragraphs,
                                 filename=t.original_filename or t.name,
                                 kind=t.kind, language=t.language)
        df = dict(t.detected_fields or {})
        df["semantic"] = result
        t.detected_fields = df
        if not t.industry or t.industry == "general":
            if result.get("probable_industry"):
                t.industry = result["probable_industry"]
        done += 1
    await audit.record(
        session, company_id=user.company_id, actor_type="user", actor_id=user.id,
        action="template.bulk_summarized", meta={"count": done, "limit": limit},
    )
    await session.commit()
    return {"summarized": done, "remaining": len([t for t in rows if t.status != "ARCHIVED"
                                                    and not ((t.detected_fields or {}).get("semantic"))])}


class TaggingIn(BaseModel):
    tags:  list[str] | None = None
    use_case: str | None = None
    summary:  str | None = None
    business_purpose: str | None = None


@router.patch("/{tpl_id}/tagging")
async def update_tagging(
    tpl_id: str, body: TaggingIn,
    user: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Operator overrides AI tagging (final say)."""
    t = await service.get(session, user.company_id, tpl_id)
    if not t: raise HTTPException(404, "template not found")
    df = dict(t.detected_fields or {})
    sem = dict(df.get("semantic") or {})
    if body.tags is not None:
        sem["tags"] = [s.strip().lower() for s in body.tags if s.strip()][:10]
    if body.use_case is not None:         sem["use_case"]         = body.use_case[:240]
    if body.summary is not None:          sem["summary"]          = body.summary[:240]
    if body.business_purpose is not None: sem["business_purpose"] = body.business_purpose[:240]
    sem["model"] = "manual"
    df["semantic"] = sem
    t.detected_fields = df
    await audit.record(
        session, company_id=user.company_id, actor_type="user", actor_id=user.id,
        action="template.tagging_updated", resource=t.id,
        meta={"keys": [k for k, v in body.model_dump().items() if v is not None]},
    )
    await session.commit()
    return {"id": t.id, "semantic": sem}




@router.post("/auto-confirm-safe")
async def auto_confirm_safe(
    user: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Run conservative bulk auto-confirm across the whole corpus.
    See `services/templates/auto_confirm.py` for the safety rules."""
    from app.services.templates.auto_confirm import auto_confirm_corpus
    report = await auto_confirm_corpus(session, company_id=user.company_id, actor_id=user.id)
    await audit.record(
        session, company_id=user.company_id, actor_type="user", actor_id=user.id,
        action="template.bulk_auto_confirmed",
        meta={"scanned": report.scanned, "affected": report.affected,
              "auto_confirmed_total": report.auto_confirmed_total,
              "status_changes": dict(report.status_changes)},
    )
    await session.commit()
    return report.to_dict()


@router.post("/{tpl_id}/rollback-auto-confirms")
async def rollback_one(
    tpl_id: str,
    user: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from app.services.templates.auto_confirm import rollback_auto_confirms
    result = await rollback_auto_confirms(
        session, company_id=user.company_id, actor_id=user.id, template_id=tpl_id,
    )
    await session.commit()
    return result


@router.post("/rollback-auto-confirms")
async def rollback_all(
    user: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Mass-undo every mapping that was auto-confirmed by the safe pass."""
    from app.services.templates.auto_confirm import rollback_auto_confirms
    result = await rollback_auto_confirms(
        session, company_id=user.company_id, actor_id=user.id,
    )
    await session.commit()
    return result


@router.post("/audit")
async def audit_endpoint(
    user: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    render_check: bool = True, sample: int = 12,
) -> dict:
    """Full production-readiness corpus audit (integrity / mapping quality /
    render verification / recovery / readiness score)."""
    from app.services.templates.audit import audit_corpus
    report = await audit_corpus(session, company_id=user.company_id,
                                 render_check=render_check, render_sample=sample)
    await session.commit()
    return report


@router.post("/reclassify-all")
async def reclassify_all(
    user: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Bulk: re-run industry classifier + validator on every template."""
    from app.services.templates.industry import classify_industry
    rows = await service.list(session, user.company_id)
    by_industry: dict[str, int] = {}
    by_qa: dict[str, int] = {}
    for r in rows:
        paragraphs = (r.detected_fields or {}).get("paragraphs", []) or []
        r.industry = classify_industry(r.original_filename or r.name, paragraphs)
        score, warnings, qa = validate_template(r)
        r.validation_score = score
        r.validation_warnings = warnings
        if qa == "VERIFIED" and r.status != "ARCHIVED":
            r.status = "VERIFIED"
        elif qa == "BROKEN" and r.status != "ARCHIVED":
            r.status = "FAILED"
        by_industry[r.industry] = by_industry.get(r.industry, 0) + 1
        by_qa[qa] = by_qa.get(qa, 0) + 1
    await audit.record(
        session, company_id=user.company_id, actor_type="user", actor_id=user.id,
        action="template.bulk_reclassified",
        meta={"count": len(rows), "by_industry": by_industry, "by_qa": by_qa},
    )
    await session.commit()
    return {"total": len(rows), "by_industry": by_industry, "by_qa": by_qa}


@router.get("/{tpl_id}/validate")
async def validate(
    tpl_id: str,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Run the deterministic QA validator. Persists score + warnings."""
    t = await service.get(session, user.company_id, tpl_id)
    if not t: raise HTTPException(404, "template not found")
    score, warnings, qa = validate_template(t)
    t.validation_score = score
    t.validation_warnings = warnings
    # qa_status is derived; we don't mutate `status` unless verifying.
    if qa == "VERIFIED" and t.status != "ARCHIVED":
        t.status = "VERIFIED"
    elif qa == "BROKEN":
        t.status = "FAILED"
    await audit.record(
        session, company_id=user.company_id, actor_type="user", actor_id=user.id,
        action="template.validated", resource=t.id,
        meta={"score": score, "qa_status": qa, "warnings": len(warnings)},
    )
    await session.commit()
    return {"score": score, "qa_status": qa, "warnings": warnings, "summary": _summary(t)}


class BulkIngestIn(BaseModel):
    folder: str
    dry_run: bool = False


@router.post("/bulk-ingest")
async def bulk_ingest(
    body: BulkIngestIn,
    user: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Walk a server-side folder and ingest every supported template file.

    Safety:
      * admin-only;
      * path is resolved to absolute and forbidden to leave the user-supplied root;
      * legacy .doc/.xls are recorded with status=FAILED + a helpful note instead
        of being silently dropped, so they appear in Recovery Center for triage.
    """
    from pathlib import Path

    root = Path(body.folder).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise HTTPException(400, f"folder not found: {root}")

    summary: dict[str, Any] = {"folder": str(root), "by_kind": {}, "by_format": {},
                                "files": [], "skipped": 0, "ingested": 0,
                                "duplicates": 0, "failed_legacy": 0}

    SUPPORTED = (".docx", ".xlsx", ".pdf", ".rtf", ".doc", ".xls")
    for path in sorted(root.iterdir()):
        if not path.is_file(): continue
        ext = path.suffix.lower()
        if ext not in SUPPORTED:
            summary["skipped"] += 1
            continue
        fmt = _EXT_FORMAT[ext]
        content = path.read_bytes()
        name = path.stem.replace("_", " ").replace("-", " ").strip().capitalize()

        summary["by_format"][fmt] = summary["by_format"].get(fmt, 0) + 1
        entry = {"file": path.name, "format": fmt, "name": name}

        if body.dry_run:
            from app.services.templates.analyzer import analyze
            a = await analyze(content, mime=_mime_of(fmt), filename=path.name)
            entry.update({"kind": a.kind, "language": a.language, "confidence": round(a.confidence, 3),
                          "suggestions": list(a.suggestions.keys())[:6], "notes": a.notes})
            summary["by_kind"][a.kind] = summary["by_kind"].get(a.kind, 0) + 1
            summary["files"].append(entry)
            continue

        try:
            storage_key = f"{user.company_id}/templates/bulk/{path.name}"
            get_storage().put(storage_key, content, content_type=_mime_of(fmt))
            tpl = await service.ingest(
                session, company_id=user.company_id, actor_id=user.id,
                name=name, filename=path.name, mime=_mime_of(fmt),
                storage_key=storage_key, content=content,
            )
            if fmt in ("doc", "xls"):
                tpl.status = "FAILED"
                tpl.last_error = f"Legacy {fmt.upper()} — convert to {'DOCX' if fmt == 'doc' else 'XLSX'} for analysis."
                summary["failed_legacy"] += 1
            elif tpl.created_at != tpl.updated_at:
                summary["duplicates"] += 1
            summary["by_kind"][tpl.kind] = summary["by_kind"].get(tpl.kind, 0) + 1
            entry.update({"id": tpl.id, "kind": tpl.kind, "status": tpl.status,
                          "confidence": tpl.confidence})
            summary["ingested"] += 1
        except Exception as exc:  # noqa: BLE001
            entry["error"] = str(exc)[:160]
            summary["skipped"] += 1
        summary["files"].append(entry)

    if not body.dry_run:
        await audit.record(
            session, company_id=user.company_id, actor_type="user", actor_id=user.id,
            action="template.bulk_ingest",
            meta={"folder": str(root), "ingested": summary["ingested"],
                  "by_kind": summary["by_kind"], "by_format": summary["by_format"]},
        )
        await session.commit()
    return summary


@router.post("/{tpl_id}/version")
async def new_version(
    tpl_id: str,
    file: UploadFile = File(...),
    user: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    parent = await service.get(session, user.company_id, tpl_id)
    if not parent: raise HTTPException(404, "template not found")
    fmt = _detect_format(file)
    content = await file.read()
    storage_key = f"{user.company_id}/templates/{datetime.utcnow():%Y%m%d}/{file.filename}"
    get_storage().put(storage_key, content, content_type=file.content_type or _mime_of(fmt))
    new_tpl = await service.make_version(
        session, parent, actor_id=user.id, storage_key=storage_key,
        content=content, filename=file.filename or "template", mime=file.content_type or _mime_of(fmt),
    )
    await session.commit()
    return _detail(new_tpl)
