"""CRUD + chat-driven patching for the Client/Employee reference-data
entities. Matching/autofill logic lives in matcher.py; this module is the
plain data-access layer both the REST endpoints (Block 5) and the AI tool
below sit on top of.
"""
from __future__ import annotations

import uuid
from typing import Any, Literal

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Client, Employee
from app.services.reference_data.matcher import POSSIBLE_MATCH_THRESHOLD, best_match

EntityType = Literal["counterparty", "employee"]

# Fields a chat-driven patch is allowed to touch — deliberately excludes
# id/company_id/created_at/updated_at (bookkeeping, never user-settable)
# and, for Client, `name`/for Employee `full_name` (renaming an existing
# record is a bigger decision than a one-line patch; that's a real edit
# through the CRUD endpoints, not a chat aside).
_CLIENT_PATCHABLE_FIELDS = frozenset({
    "bin", "phone", "email", "address", "signatory_name", "signatory_basis",
    "bank_name", "bank_bik", "bank_iik", "bank_kbe",
    "vat_registered", "vat_certificate_number", "contact_person",
})
_EMPLOYEE_PATCHABLE_FIELDS = frozenset({
    "iin", "position", "department", "hire_date", "salary", "allowances",
    "probation_period", "work_schedule", "vacation_days", "address",
    "id_doc_number", "id_doc_issued_by", "id_doc_date",
})


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


# ── Client (counterparty) ────────────────────────────────────────────────

async def list_clients(session: AsyncSession, company_id: str) -> list[Client]:
    rows = await session.scalars(
        select(Client).where(Client.company_id == company_id).order_by(desc(Client.created_at)),
    )
    return list(rows)


async def get_client(session: AsyncSession, company_id: str, client_id: str) -> Client | None:
    row = await session.get(Client, client_id)
    return row if row and row.company_id == company_id else None


async def create_client(session: AsyncSession, company_id: str, **fields: Any) -> Client:
    name = (fields.pop("name", "") or "").strip()
    if not name:
        raise ValueError("name is required")
    row = Client(id=_id("cl"), company_id=company_id, name=name,
                 **{k: v for k, v in fields.items() if k in _CLIENT_PATCHABLE_FIELDS})
    session.add(row)
    await session.flush()
    return row


async def update_client(session: AsyncSession, company_id: str, client_id: str, **fields: Any) -> Client | None:
    row = await get_client(session, company_id, client_id)
    if not row:
        return None
    if "name" in fields and fields["name"]:
        row.name = fields["name"]
    for k, v in fields.items():
        if k in _CLIENT_PATCHABLE_FIELDS and v not in (None, ""):
            setattr(row, k, v)
    await session.flush()
    return row


async def delete_client(session: AsyncSession, company_id: str, client_id: str) -> bool:
    row = await get_client(session, company_id, client_id)
    if not row:
        return False
    await session.delete(row)
    await session.flush()
    return True


# ── Employee ──────────────────────────────────────────────────────────────

async def list_employees(session: AsyncSession, company_id: str) -> list[Employee]:
    rows = await session.scalars(
        select(Employee).where(Employee.company_id == company_id).order_by(desc(Employee.created_at)),
    )
    return list(rows)


async def get_employee(session: AsyncSession, company_id: str, employee_id: str) -> Employee | None:
    row = await session.get(Employee, employee_id)
    return row if row and row.company_id == company_id else None


async def create_employee(session: AsyncSession, company_id: str, **fields: Any) -> Employee:
    full_name = (fields.pop("full_name", "") or "").strip()
    if not full_name:
        raise ValueError("full_name is required")
    row = Employee(id=_id("emp"), company_id=company_id, full_name=full_name,
                    **{k: v for k, v in fields.items() if k in _EMPLOYEE_PATCHABLE_FIELDS})
    session.add(row)
    await session.flush()
    return row


async def update_employee(session: AsyncSession, company_id: str, employee_id: str, **fields: Any) -> Employee | None:
    row = await get_employee(session, company_id, employee_id)
    if not row:
        return None
    if "full_name" in fields and fields["full_name"]:
        row.full_name = fields["full_name"]
    for k, v in fields.items():
        if k in _EMPLOYEE_PATCHABLE_FIELDS and v not in (None, ""):
            setattr(row, k, v)
    await session.flush()
    return row


async def delete_employee(session: AsyncSession, company_id: str, employee_id: str) -> bool:
    row = await get_employee(session, company_id, employee_id)
    if not row:
        return False
    await session.delete(row)
    await session.flush()
    return True


# ── Chat-driven one-line patch ───────────────────────────────────────────

async def apply_one_line_update(
    session: AsyncSession, company_id: str, entity_type: EntityType,
    mentioned_name: str, fields: dict[str, Any],
) -> tuple[Client | Employee, list[str]] | None:
    """Find an existing Client/Employee by fuzzy name and patch it.

    Unlike matcher.resolve_*, this never creates a new record — patching a
    name nobody has mentioned before would silently invent a reference-data
    row from a typo. Returns None when no candidate scores high enough to
    be confident it's the entity the operator meant.

    Returns ``(record, rejected_keys)`` — ``rejected_keys`` lists any keys
    in ``fields`` that aren't patchable (typos, or an attempt to rename via
    this path) so the caller can mention them rather than silently drop
    them.
    """
    name = (mentioned_name or "").strip()
    if not name:
        return None

    model = Client if entity_type == "counterparty" else Employee
    name_attr = "name" if entity_type == "counterparty" else "full_name"
    match, score = await best_match(session, model, company_id, name, name_attr)
    if not match or score < POSSIBLE_MATCH_THRESHOLD:
        return None

    patchable = _CLIENT_PATCHABLE_FIELDS if entity_type == "counterparty" else _EMPLOYEE_PATCHABLE_FIELDS
    accepted = {k: v for k, v in fields.items() if k in patchable and v not in (None, "")}
    rejected = [k for k in fields if k not in patchable]
    for k, v in accepted.items():
        setattr(match, k, v)
    await session.flush()
    return match, rejected
