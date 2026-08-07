"""FastAPI dependencies — auth, RBAC, tenant context."""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import decode_token
from app.db.models import User


@dataclass
class CurrentUser:
    id: str
    company_id: str
    role: str
    email: str
    name: str | None = None

    def has_role(self, *allowed: str) -> bool:
        return self.role in allowed


_ROLE_RANK = {"VIEWER": 0, "ACCOUNTANT": 1, "MEMBER": 1, "ADMIN": 2, "OWNER": 3}


async def get_current_user(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> CurrentUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    try:
        payload = decode_token(authorization.removeprefix("Bearer "))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token") from exc

    user = await session.get(User, payload["sub"])
    if not user or not user.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user inactive")
    return CurrentUser(id=user.id, company_id=user.company_id, role=user.role, email=user.email, name=user.name)


def require_role(*allowed: str):
    """Endpoint guard — fails if the user's role is below any allowed role."""
    min_rank = min(_ROLE_RANK[r] for r in allowed)

    async def _dep(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if _ROLE_RANK.get(user.role, -1) < min_rank:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "insufficient role")
        return user

    return _dep


# Convenience aliases
require_member = require_role("MEMBER", "ADMIN", "OWNER")
require_admin  = require_role("ADMIN", "OWNER")
require_owner  = require_role("OWNER")
