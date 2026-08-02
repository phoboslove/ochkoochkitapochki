"""SQLAlchemy models. SQLite-friendly; Postgres-ready."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, ForeignKey, Numeric, String, Text, DateTime, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _now() -> datetime:
    return datetime.utcnow()


# ─── Tenant ──────────────────────────────────────────────────────────────────

class Company(Base):
    __tablename__ = "companies"
    id:        Mapped[str] = mapped_column(String, primary_key=True)
    name:      Mapped[str] = mapped_column(String)
    bin:       Mapped[str | None] = mapped_column(String, nullable=True)
    tax_mode:  Mapped[str | None] = mapped_column(String, nullable=True)
    country_code: Mapped[str] = mapped_column(String, default="KZ")
    # Company memory — branding, invoice defaults, integrations config snapshots, etc.
    settings:  Mapped[dict] = mapped_column(JSON, default=dict)
    logo_key:  Mapped[str | None] = mapped_column(String, nullable=True)
    # Billing-ready stub (no Stripe yet). Plans gate features via app.services.plans.gate.
    plan:      Mapped[str] = mapped_column(String, default="free")
    onboarded: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at:Mapped[datetime] = mapped_column(DateTime, default=_now)


class User(Base):
    __tablename__ = "users"
    id:           Mapped[str] = mapped_column(String, primary_key=True)
    company_id:   Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    email:        Mapped[str] = mapped_column(String, unique=True, index=True)
    name:         Mapped[str | None] = mapped_column(String, nullable=True)
    role:         Mapped[str] = mapped_column(String, default="MEMBER")  # OWNER|ADMIN|MEMBER|VIEWER
    password_hash:Mapped[str] = mapped_column(String)
    active:       Mapped[bool] = mapped_column(Boolean, default=True)
    telegram_user_id:  Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    telegram_username: Mapped[str | None] = mapped_column(String, nullable=True)
    notify_telegram:   Mapped[bool] = mapped_column(Boolean, default=True)
    notify_email:      Mapped[bool] = mapped_column(Boolean, default=True)
    created_at:   Mapped[datetime] = mapped_column(DateTime, default=_now)


class TelegramLink(Base):
    """One-shot tokens used to bind a Telegram user to an app User."""
    __tablename__ = "telegram_links"
    token:      Mapped[str] = mapped_column(String, primary_key=True)
    user_id:    Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"))
    status:     Mapped[str] = mapped_column(String, default="PENDING")  # PENDING|USED|EXPIRED
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


# ─── CRM ─────────────────────────────────────────────────────────────────────

class Invitation(Base):
    __tablename__ = "invitations"
    id:         Mapped[str] = mapped_column(String, primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    email:      Mapped[str] = mapped_column(String, index=True)
    role:       Mapped[str] = mapped_column(String, default="MEMBER")  # MEMBER|ADMIN|ACCOUNTANT|VIEWER
    token:      Mapped[str] = mapped_column(String, unique=True, index=True)
    status:     Mapped[str] = mapped_column(String, default="PENDING")  # PENDING|ACCEPTED|REVOKED|EXPIRED
    invited_by: Mapped[str | None] = mapped_column(String, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Client(Base):
    __tablename__ = "clients"
    id:         Mapped[str] = mapped_column(String, primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    name:       Mapped[str] = mapped_column(String, index=True)
    bin:        Mapped[str | None] = mapped_column(String, nullable=True)
    phone:      Mapped[str | None] = mapped_column(String, nullable=True)
    email:      Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


# ─── Documents ───────────────────────────────────────────────────────────────

class Document(Base):
    __tablename__ = "documents"
    id:           Mapped[str] = mapped_column(String, primary_key=True)
    company_id:   Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    type:         Mapped[str] = mapped_column(String, default="OTHER")  # INVOICE|ACT|CONTRACT|...
    title:        Mapped[str] = mapped_column(String)
    storage_key:  Mapped[str] = mapped_column(String)
    mime:         Mapped[str] = mapped_column(String)
    size:         Mapped[int] = mapped_column(Integer, default=0)
    checksum:     Mapped[str | None] = mapped_column(String, nullable=True)
    status:       Mapped[str] = mapped_column(String, default="UPLOADED", index=True)  # UPLOADED|OCR_PENDING|OCR_DONE|PARSED|FAILED
    ocr_text:     Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed:       Mapped[dict | None] = mapped_column(JSON, nullable=True)
    meta:         Mapped[dict] = mapped_column(JSON, default=dict)
    created_by:   Mapped[str | None] = mapped_column(String, nullable=True)
    created_at:   Mapped[datetime] = mapped_column(DateTime, default=_now)


# ─── Templates (per-company) ─────────────────────────────────────────────────

class KnowledgeDoc(Base):
    """Per-company knowledge entry — policies, manuals, regulations.

    Body is stored inline for short docs (markdown / plain text). For binary
    docs, ``storage_key`` points at S3-style storage and body holds extracted
    text for keyword retrieval.
    """
    __tablename__ = "knowledge_docs"
    id:         Mapped[str] = mapped_column(String, primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    title:      Mapped[str] = mapped_column(String, index=True)
    tags:       Mapped[list] = mapped_column(JSON, default=list)
    body:       Mapped[str] = mapped_column(Text, default="")
    storage_key:Mapped[str | None] = mapped_column(String, nullable=True)
    mime:       Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Template(Base):
    __tablename__ = "templates"
    id:         Mapped[str] = mapped_column(String, primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    name:       Mapped[str] = mapped_column(String)
    kind:       Mapped[str] = mapped_column(String, index=True)  # invoice|act|nakladnaya|contract|proposal|unknown
    format:     Mapped[str] = mapped_column(String)              # html|docx|xlsx|pdf
    body:       Mapped[str] = mapped_column(Text)                # HTML source OR storage key for docx/xlsx/pdf
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    # ── Template lifecycle (production-grade) ───────────────────────────────
    status:        Mapped[str] = mapped_column(String, default="UPLOADED", index=True)
    # UPLOADED → ANALYZED → MAPPED → VERIFIED | FAILED | ARCHIVED
    original_filename: Mapped[str | None] = mapped_column(String, nullable=True)
    file_hash:         Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    language:          Mapped[str | None] = mapped_column(String, nullable=True)
    version:           Mapped[int]  = mapped_column(Integer, default=1)
    parent_template_id:Mapped[str | None] = mapped_column(ForeignKey("templates.id"), nullable=True)

    # Deterministic analysis output (paragraphs, tables, raw placeholders found).
    detected_fields:   Mapped[dict | None] = mapped_column(JSON, nullable=True)
    detected_tables:   Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Mapping = {placeholder_canonical → {source_label, source_kind, confidence, confirmed}}
    mappings:          Mapped[dict | None] = mapped_column(JSON, nullable=True)
    confidence:        Mapped[float | None] = mapped_column(nullable=True)
    last_render_at:    Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error:        Mapped[str | None] = mapped_column(Text, nullable=True)

    # Validation + industry classification + conversion lineage.
    validation_score:    Mapped[int | None] = mapped_column(Integer, nullable=True)
    validation_warnings: Mapped[list | None] = mapped_column(JSON, nullable=True)
    industry:            Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    converted_from_id:   Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


# ─── Invoicing ───────────────────────────────────────────────────────────────

class Invoice(Base):
    __tablename__ = "invoices"
    id:          Mapped[str] = mapped_column(String, primary_key=True)
    company_id:  Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    client_id:   Mapped[str | None] = mapped_column(ForeignKey("clients.id"), nullable=True)
    number:      Mapped[str] = mapped_column(String, index=True)
    issue_date:  Mapped[datetime] = mapped_column(DateTime, default=_now)
    due_date:    Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    currency:    Mapped[str] = mapped_column(String, default="KZT")
    subtotal:    Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    tax_total:   Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total:       Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    status:      Mapped[str] = mapped_column(String, default="DRAFT")
    items:       Mapped[list] = mapped_column(JSON, default=list)
    pdf_key:     Mapped[str | None] = mapped_column(String, nullable=True)
    notes:       Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at:  Mapped[datetime] = mapped_column(DateTime, default=_now)


# ─── Approvals ───────────────────────────────────────────────────────────────

class Approval(Base):
    __tablename__ = "approvals"
    id:           Mapped[str] = mapped_column(String, primary_key=True)
    company_id:   Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    resource_type:Mapped[str] = mapped_column(String)
    resource_id:  Mapped[str] = mapped_column(String, index=True)
    action:       Mapped[str] = mapped_column(String)
    summary:      Mapped[str] = mapped_column(Text)
    payload:      Mapped[dict] = mapped_column(JSON, default=dict)
    status:       Mapped[str] = mapped_column(String, default="PENDING")
    requested_by: Mapped[str] = mapped_column(String, default="ai")
    decided_by:   Mapped[str | None] = mapped_column(String, nullable=True)
    decided_at:   Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at:   Mapped[datetime] = mapped_column(DateTime, default=_now)


# ─── Integrations ────────────────────────────────────────────────────────────

class Integration(Base):
    __tablename__ = "integrations"
    id:         Mapped[str] = mapped_column(String, primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    provider:   Mapped[str] = mapped_column(String, index=True)
    status:     Mapped[str] = mapped_column(String, default="disconnected")
    config:     Mapped[dict] = mapped_column(JSON, default=dict)
    secrets:    Mapped[dict] = mapped_column(JSON, default=dict)  # encrypt at rest in production
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


# ─── Audit / AI memory ───────────────────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id:         Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    actor_type: Mapped[str] = mapped_column(String)
    actor_id:   Mapped[str | None] = mapped_column(String, nullable=True)
    action:     Mapped[str] = mapped_column(String)
    resource:   Mapped[str | None] = mapped_column(String, nullable=True)
    meta:       Mapped[dict] = mapped_column(JSON, default=dict)
    at:         Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)


class PendingProposal(Base):
    """A document-generation proposal waiting for user confirmation.

    Lifecycle:
      AWAITING_CONFIRMATION → GENERATING → COMPLETED
                            ↘ CANCELLED
                            ↘ EXPIRED (TTL passed, lazily checked)

    The state machine is the operational contract: only one
    AWAITING_CONFIRMATION proposal can exist per (company, user, channel,
    chat_id) tuple at a time; a fresh propose_document call atomically
    expires the prior one. Transitions to GENERATING are atomic
    (UPDATE...WHERE status=AWAITING_CONFIRMATION) so repeated "да"
    messages can only fire generation once.
    """
    __tablename__ = "pending_proposals"
    id:           Mapped[str] = mapped_column(String, primary_key=True)
    company_id:   Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    user_id:      Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    channel:      Mapped[str] = mapped_column(String, default="telegram", index=True)  # telegram|web
    chat_id:      Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    conversation_id: Mapped[str | None] = mapped_column(String, nullable=True)
    kind:         Mapped[str] = mapped_column(String)
    status:       Mapped[str] = mapped_column(
        String, default="AWAITING_CONFIRMATION", index=True,
    )  # AWAITING_CONFIRMATION|GENERATING|COMPLETED|CANCELLED|EXPIRED
    payload:      Mapped[dict] = mapped_column(JSON, default=dict)
    template_id:  Mapped[str | None] = mapped_column(String, nullable=True)
    document_id:  Mapped[str | None] = mapped_column(String, nullable=True)  # filled after generation
    expires_at:   Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at:   Mapped[datetime] = mapped_column(DateTime, default=_now)
    decided_at:   Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Conversation(Base):
    __tablename__ = "conversations"
    id:         Mapped[str] = mapped_column(String, primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    user_id:    Mapped[str | None] = mapped_column(String, nullable=True)
    title:      Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Message(Base):
    __tablename__ = "messages"
    id:              Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    role:            Mapped[str] = mapped_column(String)
    content:         Mapped[str] = mapped_column(Text)
    tool_calls:      Mapped[list | None] = mapped_column(JSON, nullable=True)
    tool_results:    Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at:      Mapped[datetime] = mapped_column(DateTime, default=_now)
