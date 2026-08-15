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
    sender = os.environ.get("EMAIL_FROM", "Wagwan <noreply@example.com>")
    provider = os.environ.get("EMAIL_PROVIDER", "console").lower()
    if provider == "resend" and os.environ.get("RESEND_API_KEY"):
        return ResendMailer(os.environ["RESEND_API_KEY"], sender)
    if provider == "postmark" and os.environ.get("POSTMARK_TOKEN"):
        return PostmarkMailer(os.environ["POSTMARK_TOKEN"], sender)
    return ConsoleMailer()


# ── Templated emails ────────────────────────────────────────────────────────

def _base_url() -> str:
    return os.environ.get("APP_BASE_URL", "http://localhost:3000").rstrip("/")


def render_verification_code(*, email: str, code: str, ttl_min: int = 15) -> EmailMessage:
    text = (
        f"Ваш код подтверждения Wagwan: {code}\n\n"
        f"Код действует {ttl_min} минут. Если вы не запрашивали регистрацию — "
        f"просто проигнорируйте это письмо."
    )
    html = f"""\
<!doctype html>
<html>
<body style="margin:0;padding:0;background-color:#f4f1ea;font-family:Georgia,'Times New Roman',serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f1ea;padding:48px 16px;">
    <tr><td align="center">
      <table role="presentation" width="480" cellpadding="0" cellspacing="0" style="max-width:480px;width:100%;background-color:#ffffff;border:1px solid #e5ded0;">
        <tr><td style="padding:40px 40px 24px;text-align:center;">
          <div style="font-size:26px;letter-spacing:8px;color:#1a1a1a;font-weight:400;">W A G W A N</div>
          <div style="margin-top:8px;height:1px;background-color:#e5ded0;"></div>
        </td></tr>
        <tr><td style="padding:8px 40px 0;text-align:center;">
          <p style="font-family:Helvetica,Arial,sans-serif;font-size:15px;line-height:1.6;color:#4a4a4a;margin:0 0 28px;">
            Код подтверждения для входа в Wagwan
          </p>
          <div style="display:inline-block;padding:18px 32px;background-color:#f4f1ea;border:1px solid #e5ded0;
                      font-family:'Courier New',monospace;font-size:34px;letter-spacing:10px;color:#1a1a1a;">
            {code}
          </div>
          <p style="font-family:Helvetica,Arial,sans-serif;font-size:13px;line-height:1.6;color:#8a8578;margin:24px 0 0;">
            Код действует {ttl_min} минут.<br/>
            Если вы не запрашивали регистрацию — просто проигнорируйте это письмо.
          </p>
        </td></tr>
        <tr><td style="padding:32px 40px 40px;text-align:center;">
          <p style="font-family:Helvetica,Arial,sans-serif;font-size:11px;color:#b5b0a0;margin:0;">
            Wagwan · AI Backoffice OS
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""
    return EmailMessage(to=email, subject=f"{code} — код подтверждения Wagwan", text=text, html=html, tag="verification")


def render_invitation(*, email: str, token: str, company_name: str, role: str) -> EmailMessage:
    link = f"{_base_url()}/accept-invite?token={token}"
    text = (f"You've been invited to {company_name} on Wagwan as {role}.\n\n"
            f"Accept here: {link}\n\nThis link expires in 7 days.")
    html = f"""<p>You've been invited to <b>{company_name}</b> on Wagwan as <b>{role}</b>.</p>
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
        text=f"Invoice {number} ({total} {currency}) is past due. Take action in Wagwan.",
        tag="overdue",
    )


def render_recovery_alert(*, email: str, count: int) -> EmailMessage:
    link = f"{_base_url()}/recovery"
    return EmailMessage(
        to=email, subject=f"{count} workflow item(s) need attention",
        text=f"{count} failed steps are waiting in the recovery center: {link}",
        tag="recovery",
    )
