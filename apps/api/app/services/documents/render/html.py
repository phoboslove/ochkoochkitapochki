"""HTML renderer — Jinja2-style placeholders without the dependency.

Sufficient for invoices/acts where the template is HTML with ``{{ var }}`` and
basic ``{% for x in xs %}…{% endfor %}`` loops. Swap for full Jinja2 by
installing it and replacing the body of `_render`.
"""
from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.services.documents.render import Renderer


def _money(v: Any) -> str:
    return f"{Decimal(str(v)):,.0f}".replace(",", " ")


def _lookup(context: dict, dotted: str) -> Any:
    cur: Any = context
    for part in dotted.split("."):
        if cur is None:
            return ""
        cur = cur.get(part) if isinstance(cur, dict) else getattr(cur, part, "")
    return cur


_VAR_RE  = re.compile(r"\{\{\s*([\w\.]+)(?:\s*\|\s*money)?\s*\}\}")
_LOOP_RE = re.compile(r"\{% for (\w+) in ([\w\.]+) %\}(.*?)\{% endfor %\}", re.DOTALL)


def _render(body: str, context: dict) -> str:
    def loop_sub(m: re.Match) -> str:
        var, src, inner = m.group(1), m.group(2), m.group(3)
        items = _lookup(context, src) or []
        return "".join(_render(inner, {**context, var: it}) for it in items)
    body = _LOOP_RE.sub(loop_sub, body)

    def var_sub(m: re.Match) -> str:
        path = m.group(1)
        val = _lookup(context, path)
        if "| money" in m.group(0) or "|money" in m.group(0):
            return _money(val)
        return "" if val is None else str(val)
    return _VAR_RE.sub(var_sub, body)


_DEFAULT_INVOICE_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"/>
<title>Invoice {{ invoice.number }}</title>
<style>
 /* Designed for BOTH WeasyPrint (full @page support) and xhtml2pdf
    (ReportLab). xhtml2pdf supports a subset, so we avoid CSS vars and
    flexbox where they matter most. */
 /* xhtml2pdf supports the @page block but stumbles on nested @bottom-center
    page counters. We keep the page size + margins; WeasyPrint also accepts. */
 @page { size: A4; margin: 18mm 18mm 22mm 18mm; }
 * { box-sizing: border-box; }
 html, body { background:#fff; }
 body { font-family: "Helvetica", "DejaVu Sans", sans-serif; font-size: 11pt;
        line-height: 1.5; color: #0f172a; }
 /* Header / brand */
 .head { width:100%; border-bottom: 2px solid {{ branding.primary_color }};
         padding-bottom: 10px; margin-bottom: 14px; }
 .head td { vertical-align: top; }
 .head .right { text-align: right; }
 .brand-name { font-size: 14pt; font-weight: bold; }
 .brand-meta { color: #6b7280; font-size: 9pt; }
 .doc-title { font-size: 20pt; font-weight: bold; margin: 0; }
 .doc-title .num { color: {{ branding.primary_color }}; }
 .doc-title small { display:block; color: #6b7280; font-size: 9pt;
                    text-transform: uppercase; letter-spacing: .06em; margin-top: 4px; }
 /* Bill-to / From */
 table.meta { width:100%; margin: 6px 0 14px 0; }
 table.meta td { vertical-align: top; width: 50%; padding-right: 8px; }
 table.meta .label { font-size: 8.5pt; text-transform: uppercase; letter-spacing: .08em;
                     color: #6b7280; padding-bottom: 3px; }
 table.meta .name  { font-weight: bold; }
 table.meta .sub   { color: #6b7280; font-size: 9.5pt; }
 /* Items */
 table.items { width: 100%; border-collapse: collapse; margin-top: 8px; }
 .items thead { display: table-header-group; }   /* repeat header on each page */
 .items th { font-size: 8.5pt; text-transform: uppercase; letter-spacing: .06em;
             color: #6b7280; text-align: left; padding: 8px 6px;
             border-bottom: 1.5pt solid #0f172a; font-weight: bold; background: #f8f8f8; }
 .items td { padding: 7px 6px; border-bottom: 0.5pt solid #e5e7eb; vertical-align: top; }
 .items td.r, .items th.r { text-align: right; }
 .items tr { page-break-inside: avoid; }         /* never split a row mid-page */
 /* Totals — table for xhtml2pdf compatibility */
 table.totals { width: 280px; margin-left: auto; margin-top: 14px;
                page-break-inside: avoid; }
 table.totals td { padding: 4px 0; font-size: 11pt; }
 table.totals td.r { text-align: right; }
 table.totals .grand td { border-top: 1.5pt solid #0f172a; padding-top: 8px;
                          font-weight: bold; font-size: 13pt; }
 /* Footer */
 .footer { margin-top: 28px; padding-top: 10px; border-top: 0.5pt dashed #e5e7eb;
           color: #6b7280; font-size: 9pt; }
 .sig { margin-top: 28px; page-break-inside: avoid; }
 .sig td { width: 50%; padding-top: 30px;
           border-top: 0.5pt solid #6b7280; font-size: 9.5pt; }
</style></head><body>

<table class="head">
  <tr>
    <td>
      <div class="brand-name">{{ company.name }}</div>
      <div class="brand-meta">BIN {{ company.bin }}</div>
    </td>
    <td class="right">
      <div class="doc-title">Invoice <span class="num">{{ invoice.number }}</span></div>
      <small>Issued {{ invoice.issue_date }} · Due {{ invoice.due_date }}</small>
    </td>
  </tr>
</table>

<table class="meta">
  <tr>
    <td>
      <div class="label">From</div>
      <div class="name">{{ company.name }}</div>
      <div class="sub">BIN {{ company.bin }}</div>
    </td>
    <td>
      <div class="label">Bill to</div>
      <div class="name">{{ client.name }}</div>
      <div class="sub">BIN {{ client.bin }}</div>
      <div class="sub">{{ client.phone }}</div>
    </td>
  </tr>
</table>

<table class="items">
  <thead><tr><th>Item</th><th class="r">Qty</th><th class="r">Price</th><th class="r">Total</th></tr></thead>
  <tbody>
    {% for it in invoice.items %}
    <tr><td>{{ it.name }}</td><td class="r">{{ it.qty }}</td>
        <td class="r">{{ it.price | money }}</td><td class="r">{{ it.total | money }}</td></tr>
    {% endfor %}
  </tbody>
</table>

<table class="totals">
  <tr><td>Subtotal</td><td class="r">{{ invoice.subtotal | money }} {{ invoice.currency }}</td></tr>
  <tr><td>Tax</td><td class="r">{{ invoice.tax_total | money }} {{ invoice.currency }}</td></tr>
  <tr class="grand"><td>Total</td><td class="r">{{ invoice.total | money }} {{ invoice.currency }}</td></tr>
</table>

<table class="sig">
  <tr>
    <td>Signature, {{ company.name }}</td>
    <td>Signature, {{ client.name }}</td>
  </tr>
</table>

<p class="footer">{{ invoice.footer_note }}</p>
</body></html>"""


class HTMLRenderer(Renderer):
    format = "html"

    def render(self, *, body: str, context: dict[str, Any]) -> tuple[bytes, str, str]:
        # Project items so template loops can use ``it.total`` directly.
        if "invoice" in context and "items" in context["invoice"]:
            items = []
            for it in context["invoice"]["items"]:
                qty = Decimal(str(it.get("qty", 1)))
                price = Decimal(str(it["price"]))
                items.append({**it, "total": qty * price})
            context = {**context, "invoice": {**context["invoice"], "items": items}}
        rendered = _render(body or _DEFAULT_INVOICE_HTML, context)
        return rendered.encode("utf-8"), "text/html", "html"
