"""Built-in HTML fallback for kinds with no VERIFIED template.

Always produces a readable, printable KZ-style document. Used so the AI
pipeline never returns "couldn't generate" — the user gets *something* real,
just visually generic.

Dispatches on kind: KINDS_WITH_TOTAL_ITEMS_CHECK kinds (invoice/act/
nakladnaya/contract_supply) get the commercial layout — parties, items
table, VAT totals — since that's what those documents actually are. Every
other kind (hr_order, trust_letter, act_reconciliation, contract, ...) gets
a generic field-list layout driven by required_fields.DOCUMENT_SCHEMAS,
in schema order, with each field's own label. Before this split, EVERY
kind got the commercial layout regardless of shape — a приказ о приёме
rendered as a blank invoice ("Заказчик", an empty items table, "Итого к
оплате: 0.00") whenever no VERIFIED template existed for it.

SECURITY: all interpolated user-supplied values pass through ``_e()`` which
HTML-escapes them. The fallback is rendered into an iframe in the preview UI
and exported to PDF via xhtml2pdf; raw user input without escaping would be
a stored XSS vector (e.g. ``client_name="<script>alert(1)</script>"`` reaching
the PDF reader or any operator who opens the preview).
"""
from __future__ import annotations

from html import escape as _html_escape
from typing import Any

from app.services.documents.generation.required_fields import (
    KINDS_WITH_TOTAL_ITEMS_CHECK, fields_for, human_kind_for,
)


def _e(value: Any) -> str:
    """HTML-escape any value (str/int/None) for safe interpolation."""
    return _html_escape("" if value is None else str(value), quote=True)


# xhtml2pdf (ReportLab) has no Cyrillic glyphs in its built-in base-14 fonts
# (Helvetica/Times/Courier) — 'Times New Roman' isn't installed on Linux
# either, so xhtml2pdf silently substitutes a base font and every Cyrillic
# character renders as a .notdef box. Liberation Serif is metrically
# Times-compatible and ships full Cyrillic coverage (fonts-liberation, see
# apps/api/Dockerfile); register it explicitly so xhtml2pdf embeds it
# instead of guessing.
_LIBERATION_SERIF = "/usr/share/fonts/truetype/liberation/LiberationSerif"
_FONT_FACES = f"""
  @font-face {{ font-family: 'DocSerif'; src: url('{_LIBERATION_SERIF}-Regular.ttf'); }}
  @font-face {{ font-family: 'DocSerif'; font-weight: bold; src: url('{_LIBERATION_SERIF}-Bold.ttf'); }}
  @font-face {{ font-family: 'DocSerif'; font-style: italic; src: url('{_LIBERATION_SERIF}-Italic.ttf'); }}
  @font-face {{ font-family: 'DocSerif'; font-weight: bold; font-style: italic; src: url('{_LIBERATION_SERIF}-BoldItalic.ttf'); }}
"""

_BASE_STYLE = f"""
  {_FONT_FACES}
  @page {{ size: A4; margin: 18mm 16mm; }}
  /* xhtml2pdf's CSS parser doesn't extract font-family out of the `font`
     shorthand — it silently falls back to a Cyrillic-less default font.
     Longhand properties only. */
  body {{ font-family: 'DocSerif', 'Liberation Serif', serif; font-size: 12.5px; line-height: 1.5; color:#111; }}
  h1 {{ font-size:18px; margin:0 0 4px; text-align:center; }}
  .meta {{ text-align:center; color:#444; margin-bottom:18px; }}
  .parties {{ display:flex; gap:24px; margin:18px 0; }}
  .parties > div {{ flex:1; border:1px solid #d1d5db; padding:10px 12px; }}
  .parties b {{ font-size:11px; text-transform:uppercase; color:#555; letter-spacing:.04em; }}
  table {{ width:100%; border-collapse:collapse; margin-top:8px; }}
  th, td {{ border:1px solid #d1d5db; padding:6px 8px; vertical-align:top; }}
  th {{ background:#f3f4f6; font-size:11px; text-transform:uppercase; }}
  td.r, th.r {{ text-align:right; font-variant-numeric: tabular-nums; }}
  td.c, th.c {{ text-align:center; }}
  .totals {{ margin-top:14px; margin-left:auto; width:320px; }}
  .totals div {{ display:flex; justify-content:space-between; padding:3px 0; }}
  .totals .grand {{ border-top:2px solid #111; padding-top:6px; font-weight:700; }}
  .sig {{ display:flex; justify-content:space-between; margin-top:48px; }}
  .sig > div {{ width:45%; }}
  .sig .line {{ border-top:1px solid #111; margin-top:36px; padding-top:4px;
                text-align:center; color:#555; font-size:11px; }}
  .muted {{ color:#777; }}
  .words {{ margin-top:10px; font-style:italic; }}
  .fields {{ margin-top:18px; }}
  .fields .row {{ display:flex; gap:12px; padding:5px 0; border-bottom:1px solid #eee; }}
  .fields .row:last-child {{ border-bottom:none; }}
  .fields .label {{ width:220px; flex-shrink:0; color:#555; }}
  .fields .value {{ flex:1; }}
"""


def _shell(*, title: str, document_number: str, document_date: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"/>
<title>{title} {_e(document_number)}</title>
<style>{_BASE_STYLE}</style></head><body>
  <h1>{title} № {_e(document_number)}</h1>
  <div class="meta">от {_e(document_date)}</div>
  {body}
</body></html>"""


def render_fallback_html(*, kind: str, context: dict[str, Any]) -> str:
    title = _e(human_kind_for(kind))
    if kind in KINDS_WITH_TOTAL_ITEMS_CHECK:
        body = _render_commercial_body(context)
    else:
        body = _render_generic_body(kind, context)
    return _shell(
        title=title, document_number=context["document_number"],
        document_date=context["document_date"], body=body,
    )


# ── Commercial layout (invoice/act/nakladnaya/contract_supply) ─────────────
# Parties + items table + VAT totals — unchanged from before the kind split.

def _render_commercial_body(context: dict[str, Any]) -> str:
    items_rows = "".join(
        f"<tr><td class='c'>{_e(it.get('idx'))}</td><td>{_e(it.get('name'))}</td>"
        f"<td class='r'>{_e(it.get('qty'))}</td>"
        f"<td class='r'>{_e(it.get('price_fmt'))}</td>"
        f"<td class='r'>{_e(it.get('total_fmt'))}</td></tr>"
        for it in context.get("items") or []
    ) or (
        "<tr><td colspan='5' class='muted c'>— нет позиций —</td></tr>"
    )

    vat_row = (
        f"<div><span>НДС ({_e(context.get('vat_percent') or 0)}%)</span>"
        f"<span>{_e(context.get('vat'))} {_e(context['currency'])}</span></div>"
        if context.get("vat_raw") else ""
    )

    return f"""
  <div class="parties">
    <div>
      <b>Исполнитель</b><br/>
      <b style="font-size:13px">{_e(context['company_name'])}</b><br/>
      БИН {_e(context['company_bin'])}<br/>
      {_e(context['company_address'])}<br/>
      {_e(context['company_bank'])}
    </div>
    <div>
      <b>Заказчик</b><br/>
      <b style="font-size:13px">{_e(context['client_name'])}</b><br/>
      БИН {_e(context['client_bin'])}<br/>
      {_e(context['client_address'])}<br/>
      {_e(context['client_phone'])}
    </div>
  </div>

  <table>
    <thead><tr>
      <th class="c">№</th><th>Наименование</th>
      <th class="r">Кол-во</th><th class="r">Цена</th><th class="r">Сумма</th>
    </tr></thead>
    <tbody>{items_rows}</tbody>
  </table>

  <div class="totals">
    <div><span>Без НДС</span><span>{_e(context['subtotal'])} {_e(context['currency'])}</span></div>
    {vat_row}
    <div class="grand"><span>Итого к оплате</span>
      <span>{_e(context['total'])} {_e(context['currency'])}</span></div>
  </div>
  <div class="words">Сумма прописью: {_e(context['amount_words'])}</div>

  <div class="sig">
    <div>
      <div class="line">Исполнитель / {_e(context['director_name'] or 'Директор')}</div>
    </div>
    <div>
      <div class="line">Заказчик</div>
    </div>
  </div>"""


# ── Generic layout (every other kind) ───────────────────────────────────────
# Company letterhead box (every document needs one) + every field the
# unified schema declares for this kind, in schema order, using the
# field's own label — no parties/items/VAT sections that don't apply.

def _render_generic_body(kind: str, context: dict[str, Any]) -> str:
    company_box = f"""
  <div class="parties">
    <div>
      <b>Исполнитель</b><br/>
      <b style="font-size:13px">{_e(context['company_name'])}</b><br/>
      БИН {_e(context['company_bin'])}<br/>
      {_e(context['company_address'])}<br/>
      {_e(context['company_bank'])}
    </div>
  </div>"""

    rows: list[str] = []
    for field in fields_for(kind):
        if field.source in ("company", "system"):
            continue  # already covered by the header + company box above
        if field.check == "list":
            rows.append(_operations_table(field.label, context))
            continue
        value = context.get(field.key)
        rows.append(
            f'<div class="row"><div class="label">{_e(field.label)}</div>'
            f'<div class="value">{_e(value) or "—"}</div></div>',
        )

    return company_box + f'\n  <div class="fields">{"".join(rows)}</div>'


def _operations_table(label: str, context: dict[str, Any]) -> str:
    ops = context.get("operations") or []
    rows = "".join(
        f"<tr><td class='c'>{_e(op.get('idx'))}</td><td>{_e(op.get('date'))}</td>"
        f"<td>{_e(op.get('doc_ref'))}</td>"
        f"<td class='r'>{_e(op.get('debit_fmt'))}</td>"
        f"<td class='r'>{_e(op.get('credit_fmt'))}</td>"
        f"<td class='r'>{_e(op.get('balance_fmt'))}</td></tr>"
        for op in ops
    ) or "<tr><td colspan='6' class='muted c'>— нет операций —</td></tr>"

    return f"""
  <div class="fields">
    <div class="row"><div class="label">{_e(label)}</div><div class="value"></div></div>
  </div>
  <table>
    <thead><tr>
      <th class="c">№</th><th>Дата</th><th>Документ</th>
      <th class="r">Дебет</th><th class="r">Кредит</th><th class="r">Сальдо</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <div class="totals">
    <div class="grand"><span>Конечное сальдо</span>
      <span>{_e(context.get('closing_balance'))} {_e(context.get('currency'))}</span></div>
  </div>"""
