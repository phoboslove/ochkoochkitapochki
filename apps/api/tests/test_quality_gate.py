"""Kind-aware render-QA regression tests.

Covers the fix for act_reconciliation/hr_order/employment_contract/
trust_letter being auto-blocked by checks that only make sense for
invoice-shaped documents (a single grand total + generic items table).
"""
from io import BytesIO

from docx import Document

from app.services.documents.generation.quality import check_render_quality


def _is_blocked(report) -> bool:
    """Mirrors GenerationPipeline._request_approval()'s actual blocking rule:
    ANY single 'error'-severity issue blocks, independent of the aggregate
    score-based report.status. Asserting on report.status alone would test
    the wrong thing — a lone weight=20 error issue doesn't necessarily drop
    the score below the 60-point 'blocked' threshold by itself."""
    return report.status == "blocked" or any(i.severity == "error" for i in report.issues)


def _valid_docx_bytes(paragraphs: list[str] | None = None) -> bytes:
    doc = Document()
    for p in paragraphs or ["Test document body."]:
        doc.add_paragraph(p)
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _base_canonical(**overrides) -> dict:
    base = {
        "company_name": "TOO Altyn Dala",
        "document_number": "AKS-2026-0001",
    }
    base.update(overrides)
    return base


class TestActReconciliationNotPenalizedForMissingTotal:
    def test_real_data_passes_not_blocked(self):
        canonical = _base_canonical(
            client_name="TOO Romashka",
            operations=[{"date": "10.01.2026", "doc_ref": "N1", "debit_fmt": "200 000.00",
                         "credit_fmt": "", "balance_fmt": "700 000.00"}],
        )
        report = check_render_quality(
            kind="act_reconciliation", canonical=canonical,
            rendered_bytes=_valid_docx_bytes(), rendered_ext="docx",
            pdf_bytes=None, template_format="docx", pipeline_warnings=[],
        )
        codes = [i.code for i in report.issues]
        assert "missing_total_raw" not in codes
        assert "empty_items" not in codes
        assert not _is_blocked(report), f"unexpectedly blocked: {report.issues}"

    def test_missing_operations_blocks(self):
        canonical = _base_canonical(client_name="TOO Romashka", operations=[])
        report = check_render_quality(
            kind="act_reconciliation", canonical=canonical,
            rendered_bytes=_valid_docx_bytes(), rendered_ext="docx",
            pdf_bytes=None, template_format="docx", pipeline_warnings=[],
        )
        codes = [i.code for i in report.issues]
        assert "missing_operations" in codes
        assert _is_blocked(report), f"expected blocked: {report.issues}"


class TestHrOrderRequiredFields:
    def test_real_data_not_blocked(self):
        canonical = _base_canonical(
            employee_name="Ivanov I.I.", employee_position="Manager", hire_date="01.09.2026",
        )
        report = check_render_quality(
            kind="hr_order", canonical=canonical,
            rendered_bytes=_valid_docx_bytes(), rendered_ext="docx",
            pdf_bytes=None, template_format="docx", pipeline_warnings=[],
        )
        assert not _is_blocked(report), f"unexpectedly blocked: {report.issues}"

    def test_missing_position_blocks(self):
        canonical = _base_canonical(employee_name="Ivanov I.I.", employee_position="", hire_date="01.09.2026")
        report = check_render_quality(
            kind="hr_order", canonical=canonical,
            rendered_bytes=_valid_docx_bytes(), rendered_ext="docx",
            pdf_bytes=None, template_format="docx", pipeline_warnings=[],
        )
        codes = [i.code for i in report.issues]
        assert "missing_employee_position" in codes
        assert _is_blocked(report)


class TestEmploymentContractRequiredFields:
    def test_missing_salary_blocks(self):
        canonical = _base_canonical(
            employee_name="Ivanov I.I.", employee_position="Manager", salary="",
        )
        report = check_render_quality(
            kind="employment_contract", canonical=canonical,
            rendered_bytes=_valid_docx_bytes(), rendered_ext="docx",
            pdf_bytes=None, template_format="docx", pipeline_warnings=[],
        )
        codes = [i.code for i in report.issues]
        assert "missing_salary" in codes
        assert _is_blocked(report)


class TestTrustLetterRequiredFields:
    def test_missing_valid_until_blocks(self):
        canonical = _base_canonical(employee_name="Ivanov I.I.", valid_until="")
        report = check_render_quality(
            kind="trust_letter", canonical=canonical,
            rendered_bytes=_valid_docx_bytes(), rendered_ext="docx",
            pdf_bytes=None, template_format="docx", pipeline_warnings=[],
        )
        codes = [i.code for i in report.issues]
        assert "missing_valid_until" in codes
        assert _is_blocked(report)


class TestInvoiceShapedKindsKeepTotalItemsChecks:
    """Regression: act/invoice/nakladnaya/contract_supply must keep the old
    behavior exactly — missing total or empty items still blocks them."""

    def test_invoice_missing_total_and_items_still_blocks(self):
        canonical = _base_canonical(client_name="TOO Romashka", total_raw=None, items=[])
        report = check_render_quality(
            kind="invoice", canonical=canonical,
            rendered_bytes=_valid_docx_bytes(), rendered_ext="docx",
            pdf_bytes=None, template_format="docx", pipeline_warnings=[],
        )
        codes = [i.code for i in report.issues]
        assert "missing_total_raw" in codes
        assert "empty_items" in codes
        assert _is_blocked(report)

    def test_invoice_with_total_and_items_not_blocked(self):
        canonical = _base_canonical(
            client_name="TOO Romashka", total_raw=100000.0,
            items=[{"name": "Widget", "qty": 1, "total": 100000.0}],
            subtotal_raw=100000.0,
        )
        report = check_render_quality(
            kind="invoice", canonical=canonical,
            rendered_bytes=_valid_docx_bytes(), rendered_ext="docx",
            pdf_bytes=None, template_format="docx", pipeline_warnings=[],
        )
        assert not _is_blocked(report), f"unexpectedly blocked: {report.issues}"

    def test_contract_supply_missing_items_still_blocks(self):
        canonical = _base_canonical(client_name="TOO Romashka", total_raw=None, items=[])
        report = check_render_quality(
            kind="contract_supply", canonical=canonical,
            rendered_bytes=_valid_docx_bytes(), rendered_ext="docx",
            pdf_bytes=None, template_format="docx", pipeline_warnings=[],
        )
        codes = [i.code for i in report.issues]
        assert "empty_items" in codes
        assert _is_blocked(report)

    def test_contract_services_not_penalized_for_missing_total_or_items(self):
        """contract_services was explicitly excluded from the total/items
        check set — it has its own required fields (client_name, service_description)."""
        canonical = _base_canonical(
            client_name="TOO Romashka", service_description="Consulting", total_raw=None,
        )
        report = check_render_quality(
            kind="contract_services", canonical=canonical,
            rendered_bytes=_valid_docx_bytes(), rendered_ext="docx",
            pdf_bytes=None, template_format="docx", pipeline_warnings=[],
        )
        codes = [i.code for i in report.issues]
        assert "missing_total_raw" not in codes
        assert "empty_items" not in codes
        assert not _is_blocked(report), f"unexpectedly blocked: {report.issues}"
