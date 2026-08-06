"""Built-in HTML fallback for kinds with no VERIFIED template.

Always produces a readable, printable KZ-style document. Used so the AI
pipeline never returns "couldn't generate" — the user gets *something* real,
just visually generic.

SECURITY: all interpolated user-supplied values pass through ``_e()`` which
HTML-escapes them. The fallback is rendered into an iframe in the preview UI
and exported to PDF via xhtml2pdf; raw user input without escaping would be
a stored XSS vector (e.g. ``client_name="<script>alert(1)</script>"`` reaching
the PDF reader or any operator who opens the preview).
"""
from __future__ import annotations

from html import escape as _html_escape
from typing import Any

_HUMAN_TITLE = {
    "invoice":      "Счёт на оплату",
    "act":          "Акт выполненных работ",
    "nakladnaya":   "Товарная накладная",
    "contract":     "Договор",
    "trust_letter": "Доверенность",
}


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


def render_fallback_html(*, kind: str, context: dict[str, Any]) -> str:
    title = _e(_HUMAN_TITLE.get(kind, "Документ"))
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

    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"/>
<title>{title} {_e(context['document_number'])}</title>
<style>
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
</style></head><body>
  <h1>{title} № {_e(context['document_number'])}</h1>
  <div class="meta">от {_e(context['document_date'])}</div>

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
  </div>
</body></html>"""
