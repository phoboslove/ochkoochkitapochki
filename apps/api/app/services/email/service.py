"""Email delivery — provider-agnostic Mailer with Resend / Postmark / Console adapters."""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.logging import log


@dataclass
class EmailMessage:
    to: str
    subject: str
    text: str
    html: str | None = None
    tag: str | None = None  # used for analytics by Resend/Postmark


class Mailer(ABC):
    name: str
    @abstractmethod
    async def send(self, msg: EmailMessage) -> dict[str, Any]: ...


class ConsoleMailer(Mailer):
    """Dev fallback — logs the message and returns a fake id."""
    name = "console"
    async def send(self, msg: EmailMessage) -> dict[str, Any]:
        log.info("email.send.console", to=msg.to, subject=msg.subject, tag=msg.tag,
                 text_preview=msg.text[:200])
        return {"id": "console-mock", "provider": self.name}


class ResendMailer(Mailer):
    name = "resend"
    def __init__(self, api_key: str, sender: str):
        self.api_key = api_key
        self.sender = sender
    async def send(self, msg: EmailMessage) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        body = {"from": self.sender, "to": [msg.to], "subject": msg.subject,
                "text": msg.text, **({"html": msg.html} if msg.html else {}),
                **({"tags": [{"name": "kind", "value": msg.tag}]} if msg.tag else {})}
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post("https://api.resend.com/emails", json=body, headers=headers)
            r.raise_for_status()
            return {"id": r.json().get("id"), "provider": self.name}


class PostmarkMailer(Mailer):
    name = "postmark"
    def __init__(self, token: str, sender: str):
        self.token = token
        self.sender = sender
    async def send(self, msg: EmailMessage) -> dict[str, Any]:
        headers = {"X-Postmark-Server-Token": self.token, "Accept": "application/json"}
        body = {"From": self.sender, "To": msg.to, "Subject": msg.subject,
                "TextBody": msg.text, "HtmlBody": msg.html or msg.text,
                **({"Tag": msg.tag} if msg.tag else {})}
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post("https://api.postmarkapp.com/email", json=body, headers=headers)
            r.raise_for_status()
            return {"id": r.json().get("MessageID"), "provider": self.name}


def get_mailer() -> Mailer:
    sender = os.environ.get("EMAIL_FROM", "Buchuchet <noreply@example.com>")
    provider = os.environ.get("EMAIL_PROVIDER", "console").lower()
    if provider == "resend" and os.environ.get("RESEND_API_KEY"):
        return ResendMailer(os.environ["RESEND_API_KEY"], sender)
    if provider == "postmark" and os.environ.get("POSTMARK_TOKEN"):
        return PostmarkMailer(os.environ["POSTMARK_TOKEN"], sender)
    return ConsoleMailer()


# ── Templated emails ────────────────────────────────────────────────────────

def _base_url() -> str:
    return os.environ.get("APP_BASE_URL", "http://localhost:3000").rstrip("/")


def render_invitation(*, email: str, token: str, company_name: str, role: str) -> EmailMessage:
    link = f"{_base_url()}/accept-invite?token={token}"
    text = (f"You've been invited to {company_name} on Buchuchet as {role}.\n\n"
            f"Accept here: {link}\n\nThis link expires in 7 days.")
    html = f"""<p>You've been invited to <b>{company_name}</b> on Buchuchet as <b>{role}</b>.</p>
<p><a href="{link}">Accept your invite</a> · expires in 7 days.</p>"""
    return EmailMessage(to=email, subject=f"You're invited to {company_name}", text=text, html=html, tag="invitation")


def render_approval_request(*, email: str, summary: str, approval_id: str) -> EmailMessage:
    link = f"{_base_url()}/approvals"
    return EmailMessage(
        to=email, subject="Approval requested",
        text=f"{summary}\n\nReview: {link}\nID: {approval_id}",
        html=f'<p>{summary}</p><p><a href="{link}">Open approvals</a></p>', tag="approval",
    )


def render_overdue(*, email: str, number: str, total: str, currency: str) -> EmailMessage:
    return EmailMessage(
        to=email, subject=f"Invoice {number} is overdue",
        text=f"Invoice {number} ({total} {currency}) is past due. Take action in Buchuchet.",
        tag="overdue",
    )


def render_recovery_alert(*, email: str, count: int) -> EmailMessage:
    link = f"{_base_url()}/recovery"
    return EmailMessage(
        to=email, subject=f"{count} workflow item(s) need attention",
        text=f"{count} failed steps are waiting in the recovery center: {link}",
        tag="recovery",
    )
