"""Email verification codes — 6 digits, 15-minute expiry, 5 wrong attempts
before the code is dead, resends throttled to once a minute. One row per
user (see EmailVerification model); a resend overwrites it in place."""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.db.models import EmailVerification

CODE_TTL_MIN = 15
RESEND_COOLDOWN_S = 60
MAX_ATTEMPTS = 5


class CodeResendTooSoon(Exception):
    def __init__(self, retry_after_s: int):
        self.retry_after_s = retry_after_s


class CodeInvalid(Exception):
    """Wrong code, expired, or attempts exhausted — message is user-facing."""


def _generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


async def issue_code(session: AsyncSession, user_id: str) -> str:
    """Create or overwrite the verification row for this user, honoring the
    resend cooldown. Returns the plaintext code (caller emails it — never
    persisted in plaintext)."""
    now = datetime.utcnow()
    row = await session.scalar(select(EmailVerification).where(EmailVerification.user_id == user_id))

    if row and (now - row.last_sent_at).total_seconds() < RESEND_COOLDOWN_S:
        remaining = RESEND_COOLDOWN_S - int((now - row.last_sent_at).total_seconds())
        raise CodeResendTooSoon(retry_after_s=max(remaining, 1))

    code = _generate_code()
    if row:
        row.code_hash = hash_password(code)
        row.expires_at = now + timedelta(minutes=CODE_TTL_MIN)
        row.attempts = 0
        row.last_sent_at = now
    else:
        row = EmailVerification(
            id=f"ev_{uuid.uuid4().hex[:12]}", user_id=user_id,
            code_hash=hash_password(code), expires_at=now + timedelta(minutes=CODE_TTL_MIN),
            attempts=0, last_sent_at=now,
        )
        session.add(row)
    await session.flush()
    return code


async def verify_code(session: AsyncSession, user_id: str, code: str) -> None:
    """Raises CodeInvalid with a user-facing message on any failure. Caller
    is responsible for committing (and for setting user.email_verified)."""
    row = await session.scalar(select(EmailVerification).where(EmailVerification.user_id == user_id))
    if not row:
        raise CodeInvalid("Код не найден. Запросите новый.")
    if row.attempts >= MAX_ATTEMPTS:
        raise CodeInvalid("Слишком много попыток. Запросите новый код.")
    if datetime.utcnow() > row.expires_at:
        raise CodeInvalid("Код истёк. Запросите новый.")
    if not verify_password(code, row.code_hash):
        row.attempts += 1
        await session.flush()
        left = MAX_ATTEMPTS - row.attempts
        if left <= 0:
            raise CodeInvalid("Слишком много попыток. Запросите новый код.")
        raise CodeInvalid(f"Неверный код. Осталось попыток: {left}.")
    await session.delete(row)
