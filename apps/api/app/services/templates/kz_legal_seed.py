"""Auto-install the 6 KZ legal/HR templates for a tenant.

Same DOCX bytes ``scripts/install_kz_legal_templates.py`` ships — kept in
one place, same pattern as ``commercial_seed.py``, so the CLI script and the
new-user onboarding hook can't drift apart.
"""
from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Template
from app.services.storage import get_storage


def _builders():
    import importlib.util
    script_path = Path(__file__).resolve().parents[3] / "scripts" / "install_kz_legal_templates.py"
    spec = importlib.util.spec_from_file_location("_kz_legal_templates_builders", script_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod.TEMPLATES, mod.CANONICAL_MAPPING_SETS


def _mappings(canonical_keys: list[str]) -> dict[str, dict[str, Any]]:
    return {
        k: {"source_label": k, "source_kind": "canonical",
            "confidence": 0.95, "confirmed": True}
        for k in canonical_keys
    }


async def install_for_tenant(session: AsyncSession, *, company_id: str) -> int:
    """Install the 6 KZ legal/HR templates for a brand-new company.

    Idempotent: skips any kind that already has a VERIFIED template by name.
    Returns the number of templates inserted.
    """
    storage = get_storage()
    templates, mapping_sets = _builders()
    inserted = 0
    for kind, display_name, builder in templates:
        existing = await session.scalar(
            select(Template).where(
                Template.company_id == company_id,
                Template.name == display_name,
            ),
        )
        if existing:
            continue

        blob = builder()
        file_hash = hashlib.sha256(blob).hexdigest()
        tpl_id = f"tpl_{uuid.uuid4().hex[:10]}"
        storage_key = f"{company_id}/templates/{tpl_id}/{display_name}.docx"
        storage.put(storage_key, blob, content_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ))
        canonical_set = mapping_sets[kind]
        session.add(Template(
            id=tpl_id, company_id=company_id,
            name=display_name, kind=kind, format="docx",
            body=storage_key, is_default=True,
            status="VERIFIED",
            original_filename=f"{display_name}.docx",
            file_hash=file_hash, language="ru", version=1,
            detected_fields={
                "placeholders": list(canonical_set),
                "tables": [],
                "semantic": {"kind": kind, "commercial": True},
                "built_by": "kz_legal_seed.install_for_tenant",
            },
            detected_tables=[],
            mappings=_mappings(canonical_set),
            confidence=0.95,
            validation_score=95, validation_warnings=[],
            industry="general",
        ))
        inserted += 1
    await session.flush()
    return inserted
