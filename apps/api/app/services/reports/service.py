class ReportService:
    def monthly(self, month: str) -> dict:
        return {
            "month": month,
            "revenue": 4_280_000,
            "expenses": 1_120_000,
            "tax_estimate": 128_000,
            "currency": "KZT",
        }

    def monthly_demo(self) -> dict:
        return self.monthly("2026-04")

    def dashboard_demo(self) -> dict:
        return {
            "revenue_mtd": 1_820_000,
            "invoices_open": 7,
            "invoices_overdue": 2,
            "approvals_pending": 2,
            "documents_processed": 38,
            "workflow_failures": 1,
        }
