from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import CurrentUser, get_current_user
from app.services.audit.logger import AuditLogger
from app.services.reference_data import service as ref_service

router = APIRouter()
audit = AuditLogger()


class ClientIn(BaseModel):
    name: str
    bin: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    signatory_name: str | None = None
    signatory_basis: str | None = None
    bank_name: str | None = None
    bank_bik: str | None = None
    bank_iik: str | None = None
    bank_kbe: str | None = None
    vat_registered: bool = False
    vat_certificate_number: str | None = None
    contact_person: str | None = None


class ClientPatch(BaseModel):
    name: str | None = None
    bin: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    signatory_name: str | None = None
    signatory_basis: str | None = None
    bank_name: str | None = None
    bank_bik: str | None = None
    bank_iik: str | None = None
    bank_kbe: str | None = None
    vat_registered: bool | None = None
    vat_certificate_number: str | None = None
    contact_person: str | None = None


def _serialize(c) -> dict:
    return {
        "id": c.id, "name": c.name, "bin": c.bin, "phone": c.phone, "email": c.email,
        "address": c.address, "signatory_name": c.signatory_name, "signatory_basis": c.signatory_basis,
        "bank_name": c.bank_name, "bank_bik": c.bank_bik, "bank_iik": c.bank_iik, "bank_kbe": c.bank_kbe,
        "vat_registered": c.vat_registered, "vat_certificate_number": c.vat_certificate_number,
        "contact_person": c.contact_person, "created_at": c.created_at.isoformat(),
    }


@router.get("")
async def list_clients(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    rows = await ref_service.list_clients(session, user.company_id)
    return [_serialize(c) for c in rows]


@router.get("/{client_id}")
async def get_client(
    client_id: str,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    row = await ref_service.get_client(session, user.company_id, client_id)
    if not row:
        raise HTTPException(404, "client not found")
    return _serialize(row)


@router.post("")
async def create_client(
    body: ClientIn,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        row = await ref_service.create_client(session, user.company_id, **body.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e))
    await audit.record(session, company_id=user.company_id, actor_type="user", actor_id=user.id,
                        action="client.created", resource=row.id, meta={"name": row.name})
    await session.commit()
    return _serialize(row)


@router.patch("/{client_id}")
async def update_client(
    client_id: str, body: ClientPatch,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    row = await ref_service.update_client(
        session, user.company_id, client_id,
        **{k: v for k, v in body.model_dump().items() if v is not None},
    )
    if not row:
        raise HTTPException(404, "client not found")
    await audit.record(session, company_id=user.company_id, actor_type="user", actor_id=user.id,
                        action="client.updated", resource=row.id)
    await session.commit()
    return _serialize(row)


@router.delete("/{client_id}")
async def delete_client(
    client_id: str,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    ok = await ref_service.delete_client(session, user.company_id, client_id)
    if not ok:
        raise HTTPException(404, "client not found")
    await audit.record(session, company_id=user.company_id, actor_type="user", actor_id=user.id,
                        action="client.deleted", resource=client_id)
    await session.commit()
    return {"deleted": True}
