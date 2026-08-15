"""Register -> unverified -> login blocked -> verify with code -> login works.
Rate limiters are shared global state across the whole pytest session, so
these tests override them to no-ops — rate limiting itself is exercised
live against prod, not here."""
import re
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.endpoints import auth as auth_ep
from app.core.db import get_session
from app.db.models import Plan, User
from app.main import app


@pytest.fixture(autouse=True)
async def override_session(session):
    # register() requires a "trial" plan to exist (create_trial_subscription).
    session.add(Plan(
        id="plan_trial_test", code="trial", name="Trial", price_amount=0,
        price_currency="KZT", billing_period="month",
        limit_documents_per_month=20, limit_users=3, limit_templates=5,
        is_active=True, sort_order=0,
    ))
    await session.commit()

    async def _get_session():
        yield session
    app.dependency_overrides[get_session] = _get_session
    for dep in (auth_ep._register_limit, auth_ep._login_limit, auth_ep._verify_limit, auth_ep._resend_limit):
        app.dependency_overrides[dep] = lambda: None
    yield
    app.dependency_overrides.clear()


def _extract_code(sent_messages: list) -> str:
    text = sent_messages[-1].text
    m = re.search(r"\b(\d{6})\b", text)
    assert m, f"no 6-digit code found in: {text!r}"
    return m.group(1)


@pytest.fixture
def captured_mailer():
    """Swap the real mailer for one that records EmailMessages instead of
    sending them, so tests can pull the plaintext code out."""
    sent: list = []

    class _FakeMailer:
        async def send(self, msg):
            sent.append(msg)
            return {"id": "test", "provider": "fake"}

    with patch("app.services.email.service.get_mailer", return_value=_FakeMailer()):
        yield sent


async def test_register_creates_unverified_user_and_sends_code(session, captured_mailer):
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/api/v1/auth/register", json={
            "company_name": "Verify Co", "email": "newuser@example.com", "password": "SuperSecret123",
        })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body == {"status": "verification_required", "email": "newuser@example.com"}
    assert "access_token" not in body

    from sqlalchemy import select
    user = await session.scalar(select(User).where(User.email == "newuser@example.com"))
    assert user is not None
    assert user.email_verified is False

    assert len(captured_mailer) == 1
    assert captured_mailer[0].to == "newuser@example.com"
    code = _extract_code(captured_mailer)
    assert len(code) == 6


async def test_login_blocked_until_verified_then_works_after_code(session, captured_mailer):
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/v1/auth/register", json={
            "company_name": "Verify Co 2", "email": "blocked@example.com", "password": "SuperSecret123",
        })

        r = await client.post("/api/v1/auth/login", json={"email": "blocked@example.com", "password": "SuperSecret123"})
        assert r.status_code == 403
        assert r.json()["error"] == "email_not_verified"

        code = _extract_code(captured_mailer)
        r = await client.post("/api/v1/auth/verify-email", json={"email": "blocked@example.com", "code": code})
        assert r.status_code == 200, r.text
        assert "access_token" in r.json()

        # now a normal login works
        r = await client.post("/api/v1/auth/login", json={"email": "blocked@example.com", "password": "SuperSecret123"})
        assert r.status_code == 200
        assert "access_token" in r.json()


async def test_wrong_code_decrements_attempts_then_locks(session, captured_mailer):
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/v1/auth/register", json={
            "company_name": "Verify Co 3", "email": "wrongcode@example.com", "password": "SuperSecret123",
        })
        real_code = _extract_code(captured_mailer)
        wrong = "000000" if real_code != "000000" else "111111"

        for expected_left in (4, 3, 2, 1):
            r = await client.post("/api/v1/auth/verify-email", json={"email": "wrongcode@example.com", "code": wrong})
            assert r.status_code == 400
            assert str(expected_left) in r.json()["detail"]

        # 5th wrong attempt exhausts the budget
        r = await client.post("/api/v1/auth/verify-email", json={"email": "wrongcode@example.com", "code": wrong})
        assert r.status_code == 400
        assert "Слишком много попыток" in r.json()["detail"]

        # even the correct code is now rejected — must request a new one
        r = await client.post("/api/v1/auth/verify-email", json={"email": "wrongcode@example.com", "code": real_code})
        assert r.status_code == 400


async def test_resend_cooldown_blocks_immediate_second_send(session, captured_mailer):
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/v1/auth/register", json={
            "company_name": "Verify Co 4", "email": "resend@example.com", "password": "SuperSecret123",
        })
        assert len(captured_mailer) == 1

        r = await client.post("/api/v1/auth/resend-code", json={"email": "resend@example.com"})
        assert r.status_code == 429
        assert "Retry-After" in r.headers
