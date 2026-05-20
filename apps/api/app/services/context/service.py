"""ContextService — load + patch the BusinessContext.

Storage:
  * `Company.settings` JSON holds all sections by name.
  * `Company.name`, `bin`, `country_code`, `tax_mode`, `logo_key` mirror the
    "company" / "branding" sections so existing code that reads scalar columns
    keeps working. ContextService writes both sides on patch.
  * Integrations are joined live from the `integrations` table.
  * Knowledge document count is joined live.

Audit:
  Every section patch writes an audit row `settings.changed` with the section
  name + diff keys (no values, to avoid logging secrets).
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Company, Integration
from app.services.audit.logger import AuditLogger
from app.services.context.schema import (
    ALL_SECTIONS, AccountingSettings, ApprovalRules, BankDetails,
    BrandingSettings, BusinessContext, CompanyProfile, IntegrationsSnapshot,
    NotificationPrefs,
)


class ContextService:
    def __init__(self) -> None:
        self.audit = AuditLogger()

    # ── Read ──────────────────────────────────────────────────────────────

    async def load(self, session: AsyncSession, company_id: str) -> BusinessContext:
        company = await session.get(Company, company_id)
        if not company:
            raise ValueError("company not found")
        settings = company.settings or {}

        # Merge the structured "company" section with the scalar columns
        # (which existed before the typed schema was introduced).
        company_section = settings.get("company") or {}
        company_section.setdefault("name", company.name)
        company_section.setdefault("bin", company.bin)
        company_section.setdefault("country_code", company.country_code)

        accounting_section = settings.get("accounting") or settings.get("invoice") or {}
        if company.tax_mode and "tax_mode" not in accounting_section:
            accounting_section["tax_mode"] = company.tax_mode

        branding_section = settings.get("branding") or {}
        if company.logo_key and not branding_section.get("logo_key"):
            branding_section["logo_key"] = company.logo_key

        # Live joins.
        integrations = list(await session.scalars(
            select(Integration).where(Integration.company_id == company_id),
        ))
        from app.db.models import KnowledgeDoc
        kb_count = (await session.scalar(
            select(func.count(KnowledgeDoc.id)).where(KnowledgeDoc.company_id == company_id),
        )) or 0

        return BusinessContext(
            company=CompanyProfile.model_validate(company_section),
            accounting=AccountingSettings.model_validate(accounting_section),
            branding=BrandingSettings.model_validate(branding_section),
            approvals=ApprovalRules.model_validate(settings.get("approvals") or {}),
            notifications=NotificationPrefs.model_validate(settings.get("notifications") or {}),
            integrations=IntegrationsSnapshot(items=[
                {"provider": i.provider, "status": i.status, "config": i.config}
                for i in integrations
            ]),
            knowledge_doc_count=kb_count,
            plan=company.plan,
            onboarded=company.onboarded,
        )

    # ── Write ─────────────────────────────────────────────────────────────

    async def patch_section(
        self, session: AsyncSession, *,
        company_id: str, section: str, data: dict[str, Any],
        actor_id: str,
    ) -> BusinessContext:
        if section not in ALL_SECTIONS:
            raise ValueError(f"unknown settings section: {section}")
        # Validate against the typed model before persisting (raises on bad input).
        model = ALL_SECTIONS[section]
        merged_input = {**(await self._section_dict(session, company_id, section)), **data}
        validated = model.model_validate(merged_input)
        patch = validated.model_dump()

        company = await session.get(Company, company_id)
        if not company:
            raise ValueError("company not found")
        company.settings = {**(company.settings or {}), section: patch}

        # Mirror to scalar columns where applicable.
        if section == "company":
            if "name" in data and data["name"]: company.name = data["name"]
            if "bin" in data:                   company.bin = data["bin"]
            if "country_code" in data:          company.country_code = data["country_code"] or "KZ"
        elif section == "accounting":
            if "tax_mode" in data:              company.tax_mode = data["tax_mode"]
        elif section == "branding":
            if "logo_key" in data:              company.logo_key = data["logo_key"]

        await self.audit.record(
            session, company_id=company_id, actor_type="user", actor_id=actor_id,
            action="settings.changed",
            meta={"section": section, "keys": sorted(data.keys())},
        )
        await session.flush()
        return await self.load(session, company_id)

    async def _section_dict(self, session: AsyncSession, company_id: str, section: str) -> dict:
        company = await session.get(Company, company_id)
        return ((company.settings or {}).get(section) or {}) if company else {}


# Module-level singleton for code-paths that don't dependency-inject.
_default = ContextService()


async def load_context(session: AsyncSession, company_id: str) -> BusinessContext:
    return await _default.load(session, company_id)
