"""Fixed-value regression tests for the Block 3 tax calculators.

Values are the hand-computed examples the user independently verified
against mybuh.kz/pro1c.kz/tengrinews/the 2026 budget law before approving
implementation — see the plan discussion. If these ever fail, the rates
config or the calculator formula changed; re-verify against a primary
source before updating the expected numbers.
"""
from app.services.tax.calculators import calculate_salary, calculate_turnover_tax


class TestCalculateSalary:
    def test_gross_300000(self):
        r = calculate_salary(300_000)
        assert float(r.opv) == 30_000.00
        assert float(r.vosms) == 6_000.00
        assert float(r.ipn_base) == 134_250.00
        assert float(r.ipn) == 13_425.00
        assert float(r.net) == 250_575.00
        assert float(r.opvr) == 10_500.00
        assert float(r.so) == 13_500.00
        assert float(r.oosms) == 9_000.00
        assert float(r.social_tax) == 15_840.00
        assert float(r.employer_total_cost) == 348_840.00
        assert r.progressive_ipn_applied is False

    def test_gross_500000(self):
        r = calculate_salary(500_000)
        assert float(r.opv) == 50_000.00
        assert float(r.vosms) == 10_000.00
        assert float(r.ipn_base) == 310_250.00
        assert float(r.ipn) == 31_025.00
        assert float(r.net) == 408_975.00
        assert float(r.opvr) == 17_500.00
        assert float(r.so) == 22_500.00
        assert float(r.oosms) == 15_000.00
        assert float(r.social_tax) == 26_400.00
        assert float(r.employer_total_cost) == 581_400.00

    def test_gross_150000_illustrates_30_mrp_deduction(self):
        r = calculate_salary(150_000)
        assert float(r.opv) == 15_000.00
        assert float(r.vosms) == 3_000.00
        assert float(r.ipn_base) == 2_250.00
        assert float(r.ipn) == 225.00
        assert float(r.net) == 131_775.00
        assert float(r.opvr) == 5_250.00
        assert float(r.so) == 6_750.00
        assert float(r.oosms) == 4_500.00
        assert float(r.social_tax) == 7_920.00
        assert float(r.employer_total_cost) == 174_420.00

    def test_negative_gross_rejected(self):
        import pytest
        with pytest.raises(ValueError):
            calculate_salary(-1000)

    def test_high_earner_triggers_progressive_bracket(self):
        # Comfortably above the 8500 МРП / year (~3,063,542 ₸/month) threshold
        # once annualized from the monthly base — sanity check the branch fires.
        r = calculate_salary(5_000_000)
        assert r.progressive_ipn_applied is True
        assert len(r.warnings) >= 1


class TestCalculateTurnoverTax:
    def test_ip_5m_half_year_default_rate(self):
        r = calculate_turnover_tax(5_000_000)
        assert float(r.rate) == 0.04
        assert float(r.tax) == 200_000.00

    def test_custom_regional_rate(self):
        r = calculate_turnover_tax(5_000_000, rate=0.02)
        assert float(r.tax) == 100_000.00

    def test_zero_turnover(self):
        r = calculate_turnover_tax(0)
        assert float(r.tax) == 0.0

    def test_negative_turnover_rejected(self):
        import pytest
        with pytest.raises(ValueError):
            calculate_turnover_tax(-1)
