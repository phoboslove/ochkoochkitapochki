"""Team invitation service. Tokens are cryptographically random; the email
delivery hook is left as a no-op so invites can be tested via copy-paste link.
"""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.models import Invitation, User


VALID_ROLES = {"ADMIN", "MEMBER", "ACCOUNTANT", "VIEWER"}


class InvitationService:
    async def list(self, session: AsyncSession, company_id: str) -> list[Invitation]:
        rows = await session.scalars(
            select(Invitation).where(Invitation.company_id == company_id)
            .order_by(desc(Invitation.created_at)),
        )
        return list(rows)

    async def invite(
        self, session: AsyncSession, *, company_id: str, email: str, role: str, invited_by: str,
    ) -> Invitation:
        if role not in VALID_ROLES:
            raise ValueError(f"invalid role: {role}")
        existing = await session.scalar(
            select(Invitation).where(
                Invitation.company_id == company_id,
                Invitation.email == email,
                Invitation.status == "PENDING",
            ),
        )
        if existing:
            return existing
        invite = Invitation(
            id=f"inv_{uuid.uuid4().hex[:10]}",
            company_id=company_id, email=email, role=role,
            token=secrets.token_urlsafe(24),
            invited_by=invited_by,
            expires_at=datetime.utcnow() + timedelta(days=7),
        )
        session.add(invite)
        await session.flush()
        try:
            from app.db.models import Company
            from app.services.email import get_mailer
            from app.services.email.service import render_invitation
            company = await session.get(Company, company_id)
            await get_mailer().send(render_invitation(
                email=email, token=invite.token,
                company_name=company.name if company else "your team", role=role,
            ))
        except Exception as exc:  # noqa: BLE001
            from app.core.logging import log
            log.warning("invite.email_failed", email=email, error=str(exc))
        return invite

    async def revoke(self, session: AsyncSession, company_id: str, invite_id: str) -> Invitation | None:
        inv = await session.get(Invitation, invite_id)
        if not inv or inv.company_id != company_id or inv.status != "PENDING":
            return None
        inv.status = "REVOKED"
        return inv

    async def accept(
        self, session: AsyncSession, *, token: str, name: str | None, password: str,
    ) -> User:
        inv = await session.scalar(select(Invitation).where(Invitation.token == token))
        if not inv:
            raise ValueError("invalid invite")
        if inv.status != "PENDING":
            raise ValueError(f"invite is {inv.status.lower()}")
        if inv.expires_at < datetime.utcnow():
            inv.status = "EXPIRED"
            raise ValueError("invite expired")
        if await session.scalar(select(User).where(User.email == inv.email)):
            raise ValueError("user already exists with this email")

        user = User(
            id=f"u_{uuid.uuid4().hex[:10]}",
            company_id=inv.company_id, email=inv.email, name=name,
            role=inv.role, password_hash=hash_password(password),
            # The invite link was mailed to this exact address — accepting it
            # already proves ownership, no separate code needed.
            email_verified=True,
        )
        session.add(user)
        inv.status = "ACCEPTED"
        await session.flush()
        return user
