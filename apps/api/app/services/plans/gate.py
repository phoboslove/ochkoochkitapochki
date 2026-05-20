"""Plan gating — keyed by Company.plan. No billing yet; this is the seam.

Returns booleans + numeric quotas. Callers raise ``PermissionError`` (HTTP 402)
when a gated feature is exercised on a plan that doesn't include it.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlanLimits:
    name: str
    invoices_per_month: int
    documents_per_month: int
    seats: int
    integrations: tuple[str, ...]
    ai_chat: bool
    custom_templates: bool
    semantic_search: bool


PLANS: dict[str, PlanLimits] = {
    "free": PlanLimits(
        name="Free", invoices_per_month=20, documents_per_month=50, seats=2,
        integrations=("whatsapp", "telegram"),
        ai_chat=True, custom_templates=False, semantic_search=False,
    ),
    "starter": PlanLimits(
        name="Starter", invoices_per_month=200, documents_per_month=500, seats=5,
        integrations=("whatsapp", "telegram", "bitrix", "amocrm"),
        ai_chat=True, custom_templates=True, semantic_search=False,
    ),
    "growth": PlanLimits(
        name="Growth", invoices_per_month=2000, documents_per_month=5000, seats=20,
        integrations=("whatsapp", "telegram", "bitrix", "amocrm", "kaspi", "ozon", "gsheets", "gmail"),
        ai_chat=True, custom_templates=True, semantic_search=True,
    ),
    "business": PlanLimits(
        name="Business", invoices_per_month=10**9, documents_per_month=10**9, seats=10**9,
        integrations=("whatsapp", "telegram", "bitrix", "amocrm", "kaspi", "ozon",
                      "gsheets", "gmail", "gdrive", "1c"),
        ai_chat=True, custom_templates=True, semantic_search=True,
    ),
}


def limits_for(plan: str) -> PlanLimits:
    return PLANS.get(plan, PLANS["free"])


def feature_enabled(plan: str, feature: str) -> bool:
    p = limits_for(plan)
    return bool(getattr(p, feature, False))


def integration_allowed(plan: str, provider: str) -> bool:
    return provider in limits_for(plan).integrations
