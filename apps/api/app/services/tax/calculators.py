"""Deterministic tax/payroll calculators — Block 3.

Pure functions, no LLM involved in any arithmetic. Every rate is read from
``tax_rates_kz_2026.json`` via :mod:`app.services.tax.rates`, never
hardcoded here, so a rate change only ever touches one file. The AI tool
layer (``app/services/ai/tools/registry.py``) parses natural language into
the plain numeric arguments these functions take, then formats the returned
breakdown back into prose — arithmetic itself never touches the model.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from app.services.tax.rates import disclaimer, load_rates


def _d(value: float | int | str | Decimal) -> Decimal:
    return Decimal(str(value))


def _round2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ── Salary breakdown ─────────────────────────────────────────────────────────

@dataclass
class SalaryBreakdown:
    gross: Decimal
    opv: Decimal
    vosms: Decimal
    ipn_base: Decimal
    ipn: Decimal
    net: Decimal
    opvr: Decimal
    so: Decimal
    oosms: Decimal
    social_tax: Decimal
    employer_total_cost: Decimal
    progressive_ipn_applied: bool
    rates_effective_date: str
    disclaimer: str
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        d = asdict(self)
        for k, v in d.items():
            if isinstance(v, Decimal):
                d[k] = float(v)
        return d


def calculate_salary(gross: float | Decimal) -> SalaryBreakdown:
    """Full itemized payroll breakdown for a monthly gross ``gross`` (KZT).

    Order of operations (2026 rates, see tax_rates_kz_2026.json for sources):
      1. ОПВ (employee, 10%, base capped at 50×МЗП)
      2. ВОСМС (employee, 2%, base capped at 20×МЗП)
      3. ИПН base = gross - ОПВ - ВОСМС - base_deduction(30 МРП)
      4. ИПН = progressive 10%/15% split at 8500 МРП/year (monthly
         approximation: monthly base × 12, bracket-applied, ÷12 — exact
         calculation requires real cumulative annual income, see warnings)
      5. net = gross - ОПВ - ВОСМС - ИПН
      6. Employer-only additions on top of gross: ОПВР (3.5%), СО (5% of
         gross-ОПВ, clamped to [1×МЗП, 7×МЗП]), ООСМС (3%, capped at
         40×МЗП), социальный налог (6% of gross-ОПВ-ВОСМС, floored at
         14 МРП — NOT netted against СО, per the 2026 code change).
    """
    rates = load_rates()
    p = rates["payroll"]
    mrp = _d(rates["base_values"]["mrp"]["value"])
    mzp = _d(rates["base_values"]["mzp"]["value"])
    gross_d = _d(gross)
    warnings: list[str] = []

    if gross_d < 0:
        raise ValueError("gross salary cannot be negative")

    # ОПВ — employee
    opv_cap = mzp * p["opv"]["base_cap_mzp"]
    opv_base = min(gross_d, opv_cap)
    opv = _round2(opv_base * _d(p["opv"]["rate"]))
    if gross_d > opv_cap:
        warnings.append(f"gross exceeds ОПВ base cap ({opv_cap:,.0f} ₸) — excess is not pension-taxed")

    # ВОСМС — employee
    vosms_cap = mzp * p["vosms"]["base_cap_mzp"]
    vosms_base = min(gross_d, vosms_cap)
    vosms = _round2(vosms_base * _d(p["vosms"]["rate"]))

    # ИПН — progressive, monthly approximation of the annual cumulative rule
    base_deduction = _d(p["ipn"]["base_deduction"]["kzt"])
    ipn_base = max(Decimal("0"), gross_d - opv - vosms - base_deduction)
    annual_base = ipn_base * 12
    threshold = _d(p["ipn"]["progressive_threshold_kzt_annual"])
    rate_std = _d(p["ipn"]["rate_standard"])
    rate_high = _d(p["ipn"]["rate_high"])
    progressive_applied = annual_base > threshold
    if progressive_applied:
        ipn_annual = threshold * rate_std + (annual_base - threshold) * rate_high
        warnings.append(
            "приближённый годовой доход превышает порог 8500 МРП — часть ИПН "
            "рассчитана по повышенной ставке 15%; точный расчёт требует "
            "фактического дохода нарастающим итогом с начала года"
        )
    else:
        ipn_annual = annual_base * rate_std
    ipn = _round2(ipn_annual / 12)

    net = gross_d - opv - vosms - ipn

    # ОПВР — employer, same base cap convention as ОПВ
    opvr = _round2(min(gross_d, opv_cap) * _d(p["opvr"]["rate"]))

    # СО — employer, base = gross - ОПВ, clamped to [1 МЗП, 7 МЗП]
    so_min = mzp * p["so"]["base_min_mzp"]
    so_max = mzp * p["so"]["base_max_mzp"]
    so_base = min(max(gross_d - opv, so_min), so_max)
    so = _round2(so_base * _d(p["so"]["rate"]))

    # ООСМС — employer
    oosms_cap = mzp * p["oosms"]["base_cap_mzp"]
    oosms_base = min(gross_d, oosms_cap)
    oosms = _round2(oosms_base * _d(p["oosms"]["rate"]))

    # Социальный налог — employer, base = gross - ОПВ - ВОСМС, floored at 14 МРП,
    # NOT netted against СО (2026 change).
    st_floor = mrp * p["social_tax"]["floor_mrp"]
    st_base = max(gross_d - opv - vosms, st_floor)
    social_tax = _round2(st_base * _d(p["social_tax"]["rate"]))

    employer_total_cost = gross_d + opvr + so + oosms + social_tax

    return SalaryBreakdown(
        gross=gross_d, opv=opv, vosms=vosms, ipn_base=ipn_base, ipn=ipn, net=net,
        opvr=opvr, so=so, oosms=oosms, social_tax=social_tax,
        employer_total_cost=employer_total_cost,
        progressive_ipn_applied=progressive_applied,
        rates_effective_date=rates["last_verified"],
        disclaimer=disclaimer(),
        warnings=warnings,
    )


# ── Turnover tax (упрощёнка / форма 910) ─────────────────────────────────────

@dataclass
class TurnoverTaxResult:
    turnover: Decimal
    rate: Decimal
    tax: Decimal
    regime_label: str
    rates_effective_date: str
    disclaimer: str
    self_payments_note: str

    def as_dict(self) -> dict:
        d = asdict(self)
        for k, v in d.items():
            if isinstance(v, Decimal):
                d[k] = float(v)
        return d


def calculate_turnover_tax(
    turnover: float | Decimal, *, rate: float | Decimal | None = None,
) -> TurnoverTaxResult:
    """Упрощёнка (форма 910) turnover tax for a given period's oborot.

    ``rate`` overrides the base 4% when the caller knows their maslikhat has
    set a different regional rate (2-6% range) — defaults to the base rate
    otherwise, with a warning-equivalent note baked into the result.
    """
    rates = load_rates()
    regime = rates["regimes"]["simplified_910"]
    turnover_d = _d(turnover)
    if turnover_d < 0:
        raise ValueError("turnover cannot be negative")
    used_rate = _d(rate) if rate is not None else _d(regime["ipn_rate_base"])
    tax = _round2(turnover_d * used_rate)

    return TurnoverTaxResult(
        turnover=turnover_d, rate=used_rate, tax=tax,
        regime_label=regime["label"],
        rates_effective_date=rates["last_verified"],
        disclaimer=disclaimer(),
        self_payments_note=(
            "Указанная сумма — только налог с оборота (форма 910). Отдельно "
            "необходимы социальные платежи «за себя» (ОПВ, СО, ОСМС) — они "
            "считаются от выбранного дохода для исчисления, а не от оборота, "
            "и в этот расчёт не входят."
        ),
    )
