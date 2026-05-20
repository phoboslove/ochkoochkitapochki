"""Anomaly detector — reads BusinessContext, never acts autonomously."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Client, Invoice
from app.services.context.service import load_context


class AnomalyService:
    async def scan(self, session: AsyncSession, company_id: str) -> list[dict[str, Any]]:
        ctx = await load_context(session, company_id)
        now = datetime.utcnow()
        out: list[dict[str, Any]] = []

        invoices = list(await session.scalars(
            select(Invoice).where(Invoice.company_id == company_id),
        ))

        # Duplicate invoices (same client+total, <= 7 days apart)
        by_key: dict[tuple[str, str], list[Invoice]] = defaultdict(list)
        for i in invoices:
            by_key[(i.client_id or "?", str(i.total))].append(i)
        for group in by_key.values():
            if len(group) < 2: continue
            group.sort(key=lambda x: x.created_at)
            for prev, cur in zip(group, group[1:]):
                if (cur.created_at - prev.created_at) <= timedelta(days=7):
                    out.append({"id": f"dup:{cur.id}", "kind": "duplicate", "severity": "warn",
                                "resource": cur.id,
                                "message": f"{cur.number} duplicates {prev.number} within 7 days."})

        # Amount jump > 3× per-client average
        per_client: dict[str, list[Decimal]] = defaultdict(list)
        for i in sorted(invoices, key=lambda x: x.created_at):
            if not i.client_id: continue
            history = per_client[i.client_id]
            if history:
                avg = sum(history) / len(history)
                if avg > 0 and Decimal(i.total) > avg * 3:
                    out.append({"id": f"jump:{i.id}", "kind": "amount_jump", "severity": "warn",
                                "resource": i.id,
                                "message": f"{i.number}: {i.total} is over 3× client avg ({avg:.0f})."})
            history.append(Decimal(i.total))

        # Long overdue (uses accounting.overdue_reminder_days)
        threshold = ctx.accounting.overdue_reminder_days
        for i in invoices:
            if i.status == "OVERDUE" and i.due_date and (now - i.due_date).days > threshold:
                out.append({"id": f"od:{i.id}", "kind": "overdue", "severity": "high",
                            "resource": i.id,
                            "message": f"{i.number} overdue by {(now - i.due_date).days} days."})

        # VAT enabled but invoice has zero tax (only flag for non-trivial totals)
        if ctx.accounting.vat_enabled:
            for i in invoices:
                if Decimal(i.total) >= 100_000 and Decimal(i.tax_total) == 0:
                    out.append({"id": f"vat:{i.id}", "kind": "missing_tax", "severity": "warn",
                                "resource": i.id,
                                "message": (f"{i.number}: VAT enabled ({ctx.accounting.vat_percent}%) "
                                            "but tax_total = 0.")})

        # KZ: clients without BIN
        if ctx.company.country_code == "KZ":
            no_bin = [c for c in await session.scalars(
                select(Client).where(Client.company_id == company_id)) if not c.bin]
            if no_bin:
                out.append({"id": "no-bin", "kind": "missing_bin", "severity": "info",
                            "resource": None,
                            "message": f"{len(no_bin)} client(s) without a BIN/IIN on file."})
        return out
