"""Archive every VERIFIED template that isn't a hand-rolled commercial one.

Earlier sessions promoted legacy Kazakh inventory forms (Inv 4 / Da 4 /
Inv 10 ...) to VERIFIED so the matcher had SOMETHING to render before the
commercial templates existed. They've now been superseded — keeping them
verified lets the matcher pick "inventarizatsionnaya opis" for a normal
Russian invoice/act request, which the operator team flagged as a real bug.

Heuristic: a template is "commercial" when its name explicitly contains
"коммерческий" / "коммерческая" — the only string our own installer
inserts. Everything else gets ARCHIVED, which makes the matcher ignore it.

Idempotent: re-running is a no-op for already-archived rows.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.db import SessionLocal
from app.db.models import Company, Template


def _is_commercial(name: str) -> bool:
    low = (name or "").lower()
    return "коммерческ" in low


async def cleanup() -> None:
    async with SessionLocal() as session:
        company = (await session.scalars(select(Company).limit(1))).first()
        if not company:
            print("no company found")
            return
        rows = list(await session.scalars(
            select(Template).where(
                Template.company_id == company.id,
                Template.status == "VERIFIED",
            )
        ))
        kept, archived = [], []
        for t in rows:
            if _is_commercial(t.name):
                kept.append(t)
            else:
                t.status = "ARCHIVED"
                archived.append(t)
        await session.commit()
        print(f"company: {company.id}")
        print(f"kept VERIFIED ({len(kept)}):")
        for t in kept:
            print(f"  {t.kind:11s} {t.format:5s} {t.name}")
        print(f"archived ({len(archived)}):")
        for t in archived:
            print(f"  {t.kind:11s} {t.format:5s} {t.name}")


if __name__ == "__main__":
    asyncio.run(cleanup())
