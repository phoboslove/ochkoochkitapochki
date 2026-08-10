"""require_platform_admin — 404 (not 403) for non-admins, 200 for admins.

404 specifically because the requirement was that /admin must not reveal
its own existence to anyone who isn't a platform admin.
"""
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.main import app
from app.core.db import get_session


@pytest.fixture(autouse=True)
def override_session(session):
    async def _get_session():
        yield session
    app.dependency_overrides[get_session] = _get_session
    yield
    app.dependency_overrides.pop(get_session, None)


def _token(user_id: str, company_id: str, role: str) -> str:
    return create_access_token(sub=user_id, claims={"company_id": company_id, "role": role})


async def test_non_admin_gets_404(seeded):
    token = _token(seeded["user_id"], seeded["company_id"], "OWNER")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/v1/admin/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404


async def test_platform_admin_gets_200(platform_admin):
    token = _token(platform_admin["user_id"], platform_admin["company_id"], "OWNER")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/v1/admin/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert "companies" in body and "mrr" in body


async def test_no_token_gets_401(seeded):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/v1/admin/dashboard")
    assert r.status_code == 401
