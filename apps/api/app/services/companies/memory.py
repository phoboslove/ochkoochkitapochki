"""Company memory — profile + settings, surfaced to the AI before tool runs."""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Company, Integration


class CompanyMemory:
    async def load(self, session: AsyncSession, company_id: str) -> dict[str, Any]:
        company = await session.get(Company, company_id)
        if not company:
            return {}
        from sqlalchemy import select
        integrations = list(await session.scalars(
            select(Integration).where(Integration.company_id == company_id),
        ))
        return {
            "company": {
                "id": company.id, "name": company.name, "bin": company.bin,
                "tax_mode": company.tax_mode, "country_code": company.country_code,
            },
            "branding": (company.settings or {}).get("branding", {}),
            "invoice_defaults": (company.settings or {}).get("invoice", {}),
            "ai_policy": (company.settings or {}).get("ai", {}),
            "integrations": [
                {"provider": i.provider, "status": i.status, "config": i.config}
                for i in integrations
            ],
        }

    def to_system_prompt_block(self, memory: dict[str, Any]) -> str:
        c = memory.get("company", {})
        inv = memory.get("invoice_defaults", {})
        ints = ", ".join(
            f"{i['provider']}={i['status']}" for i in memory.get("integrations", [])
        ) or "none"
        return (
            "## Company context\n"
            f"- name: {c.get('name')} (BIN {c.get('bin')}, {c.get('country_code')}, tax: {c.get('tax_mode')})\n"
            f"- invoice defaults: currency={inv.get('currency_default','KZT')}, "
            f"due_in_days={inv.get('due_in_days_default',14)}\n"
            f"- integrations: {ints}\n"
        )

    async def update_settings(
        self, session: AsyncSession, company_id: str, patch: dict[str, Any],
    ) -> dict[str, Any]:
        company = await session.get(Company, company_id)
        if not company:
            raise ValueError("company not found")
        merged = {**(company.settings or {})}
        for k, v in patch.items():
            if isinstance(v, dict) and isinstance(merged.get(k), dict):
                merged[k] = {**merged[k], **v}
            else:
                merged[k] = v
        company.settings = merged
        return merged
