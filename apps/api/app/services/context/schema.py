"""Typed business-context schema — single source of truth for company config.

Every module that needs company-aware behavior reads from `BusinessContext`,
not from raw JSON. Mutations go through `ContextService.patch_section`, which
validates against these models and writes an audit entry.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field


# ── Sections ───────────────────────────────────────────────────────────────

class BankDetails(BaseModel):
    bank_name: str | None = None
    iban: str | None = None
    bik: str | None = None
    account: str | None = None
    swift: str | None = None


class CompanyProfile(BaseModel):
    name: str
    legal_name: str | None = None
    bin: str | None = None
    country_code: str = "KZ"
    currency: str = "KZT"
    timezone: str = "Asia/Almaty"
    address: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    website: str | None = None
    director_name: str | None = None
    accountant_name: str | None = None
    bank: BankDetails = Field(default_factory=BankDetails)


class AccountingSettings(BaseModel):
    tax_mode: Literal["simplified", "general", "retail", "custom"] = "simplified"
    vat_enabled: bool = False
    vat_percent: float = 12.0
    payroll_tax_mode: Literal["standard", "none", "custom"] = "standard"
    numbering_format: str = "INV-{year}-{seq:04d}"
    fiscal_year_start_month: int = 1  # 1..12
    overdue_reminder_days: int = 3
    currency_default: str = "KZT"
    due_in_days_default: int = 14
    footer_note: str = "Thank you for your business."


class BrandingSettings(BaseModel):
    primary_color: str = "#0f172a"
    secondary_color: str | None = None
    logo_key: str | None = None
    stamp_key: str | None = None
    signature_key: str | None = None


class ApprovalRules(BaseModel):
    auto_send_invoices: bool = False
    invoice_amount_threshold: float = 0           # 0 = always require approval
    high_value_threshold: float = 1_000_000
    require_admin_above: float = 5_000_000        # OWNER/ADMIN only above this
    approval_required_for: list[str] = Field(
        default_factory=lambda: ["send_invoice", "release_payment"],
    )


class NotificationPrefs(BaseModel):
    org_telegram_enabled: bool = True
    org_email_enabled: bool = True
    notify_on: dict[str, bool] = Field(default_factory=lambda: {
        "approval_request": True,
        "approval_decided": False,
        "overdue":          True,
        "workflow_failed":  True,
        "anomaly":          True,
        "ocr_failed":       True,
    })


class IntegrationsSnapshot(BaseModel):
    """Snapshot of which integrations are connected. Read-only for AI consumers."""
    items: list[dict] = Field(default_factory=list)


# ── Aggregate ──────────────────────────────────────────────────────────────

class BusinessContext(BaseModel):
    company:       CompanyProfile
    accounting:    AccountingSettings
    branding:      BrandingSettings
    approvals:     ApprovalRules
    notifications: NotificationPrefs
    integrations:  IntegrationsSnapshot = Field(default_factory=IntegrationsSnapshot)
    knowledge_doc_count: int = 0
    plan: str = "free"
    onboarded: bool = False

    def to_prompt_block(self) -> str:
        """Compact, AI-friendly view of the context (only stable keys)."""
        c, a, ap = self.company, self.accounting, self.approvals
        return (
            "## Company context\n"
            f"- name: {c.name} (BIN {c.bin}, {c.country_code}, currency {c.currency})\n"
            f"- accounting: tax_mode={a.tax_mode}, VAT={'on '+str(a.vat_percent)+'%' if a.vat_enabled else 'off'}, "
            f"due_in_days={a.due_in_days_default}\n"
            f"- approvals: invoice_threshold={ap.invoice_amount_threshold}, "
            f"high_value={ap.high_value_threshold}, auto_send={ap.auto_send_invoices}\n"
            f"- integrations: " + (", ".join(f"{i.get('provider')}={i.get('status')}"
                                              for i in self.integrations.items) or "none")
            + "\n"
        )


ALL_SECTIONS = {
    "company":       CompanyProfile,
    "accounting":    AccountingSettings,
    "branding":      BrandingSettings,
    "approvals":     ApprovalRules,
    "notifications": NotificationPrefs,
}
