"""Admin 'Recheck quality' action — the follow-up to the kind-aware quality
gate fix. A real customer document could someday get falsely blocked by a
required-fields rule change; this is the button that fixes it without
hand-editing the database.
"""
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.core.db import get_session
from app.db.models import Approval, Document
from app.main import app


@pytest.fixture(autouse=True)
def override_session(session):
    async def _get_session():
        yield session
    app.dependency_overrides[get_session] = _get_session
    yield
    app.dependency_overrides.pop(get_session, None)


def _token(user_id: str, company_id: str, role: str) -> str:
    return create_access_token(sub=user_id, claims={"company_id": company_id, "role": role})


async def _make_blocked_doc(session, seeded, *, doc_id: str, kind: str, canonical: dict,
                             old_issue_codes: list[str]) -> None:
    """Seed a Document + BLOCKED Approval as if generated under the OLD
    (pre-fix) quality checker, which flagged missing_total_raw/empty_items
    for every kind indiscriminately."""
    doc = Document(
        id=doc_id, company_id=seeded["company_id"], type="OTHER",
        title=f"Test {kind}", storage_key=f"{doc_id}.docx", mime="application/pdf",
        size=100, status="GENERATED",
        parsed={
            "kind": kind, "document_number": "TST-0001",
            "canonical": canonical,
            "quality": {
                "score": 40, "status": "blocked",
                "issues": [
                    {"code": c, "message": f"{c} is empty in the populated context.",
                     "severity": "error", "weight": 20, "where": None}
                    for c in old_issue_codes
                ],
            },
        },
        meta={},
    )
    approval = Approval(
        id=f"apr_{doc_id}", company_id=seeded["company_id"], resource_type="document",
        resource_id=doc_id, action="send_document",
        summary=f"⛔ BLOCKED — Send {kind} TST-0001",
        payload={"document_id": doc_id, "kind": kind}, status="BLOCKED", requested_by="ai",
    )
    session.add_all([doc, approval])
    await session.commit()


async def test_recheck_unblocks_when_new_rules_satisfied(seeded, platform_admin, session):
    await _make_blocked_doc(
        session, seeded, doc_id="gen_unblock", kind="act_reconciliation",
        canonical={
            "company_name": "TOO Test", "document_number": "TST-0001",
            "client_name": "TOO Client", "operations": [{"date": "01.01.2026", "debit": 100}],
        },
        old_issue_codes=["missing_total_raw", "missing_client_name"],
    )
    token = _token(platform_admin["user_id"], platform_admin["company_id"], "OWNER")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/v1/admin/documents/gen_unblock/recheck-quality",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["approval"]["status"] == "PENDING"
    assert body["quality"]["status"] != "blocked"

    refreshed = await session.get(Approval, "apr_gen_unblock")
    assert refreshed.status == "PENDING"
    assert not refreshed.summary.startswith("⛔")


async def test_recheck_stays_blocked_when_field_genuinely_missing(seeded, platform_admin, session):
    await _make_blocked_doc(
        session, seeded, doc_id="gen_stillblocked", kind="hr_order",
        canonical={
            "company_name": "TOO Test", "document_number": "TST-0001",
            "employee_name": "Ivanov I.I.", "employee_position": "", "hire_date": "",
        },
        old_issue_codes=["missing_total_raw", "missing_client_name"],
    )
    token = _token(platform_admin["user_id"], platform_admin["company_id"], "OWNER")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/v1/admin/documents/gen_stillblocked/recheck-quality",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["approval"]["status"] == "BLOCKED"
    codes = [i["code"] for i in body["quality"]["issues"]]
    assert "missing_employee_position" in codes
    assert "missing_hire_date" in codes
    # The stale generic codes must be gone, replaced by kind-aware ones.
    assert "missing_total_raw" not in codes
    assert "missing_client_name" not in codes


async def test_recheck_422_when_no_stored_canonical(seeded, platform_admin, session):
    doc = Document(
        id="gen_nocanonical", company_id=seeded["company_id"], type="OTHER",
        title="Legacy doc", storage_key="x.docx", mime="application/pdf",
        size=100, status="GENERATED",
        parsed={"kind": "act", "document_number": "OLD-0001"},  # no "canonical" key
        meta={},
    )
    approval = Approval(
        id="apr_nocanonical", company_id=seeded["company_id"], resource_type="document",
        resource_id="gen_nocanonical", action="send_document", summary="⛔ BLOCKED — old",
        payload={}, status="BLOCKED", requested_by="ai",
    )
    session.add_all([doc, approval])
    await session.commit()

    token = _token(platform_admin["user_id"], platform_admin["company_id"], "OWNER")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/v1/admin/documents/gen_nocanonical/recheck-quality",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 422


async def test_recheck_requires_platform_admin(seeded, session):
    await _make_blocked_doc(
        session, seeded, doc_id="gen_noauth", kind="act_reconciliation",
        canonical={"company_name": "X", "document_number": "Y", "client_name": "Z", "operations": []},
        old_issue_codes=[],
    )
    token = _token(seeded["user_id"], seeded["company_id"], "OWNER")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/v1/admin/documents/gen_noauth/recheck-quality",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 404
