"""reference data + numbering — Client extensions, Employee, DocumentCounter,
Company stamp/signature placeholders.

Client gains the counterparty fields the AI document pipeline needs to
autofill from (address, signatory, bank, VAT status, contact person) —
it was previously just name/bin/phone/email, unused by generation at all.
Employee is a new entity for HR-document autofill/matching. DocumentCounter
backs the atomic per-(company, kind, year) numbering counter that replaces
the live COUNT(*) approach. Company gets two nullable placeholder columns
for a future stamp/signature-image render feature — no rendering wired to
them yet.

Revision ID: 0006_reference_data_and_numbering
Revises: 0005_email_verification
Create Date: 2026-08-20
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_reference_data_and_numbering"
down_revision = "0005_email_verification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("stamp_image_key", sa.String(), nullable=True))
    op.add_column("companies", sa.Column("signature_image_key", sa.String(), nullable=True))

    op.add_column("clients", sa.Column("address", sa.String(), nullable=True))
    op.add_column("clients", sa.Column("signatory_name", sa.String(), nullable=True))
    op.add_column("clients", sa.Column("signatory_basis", sa.String(), nullable=True))
    op.add_column("clients", sa.Column("bank_name", sa.String(), nullable=True))
    op.add_column("clients", sa.Column("bank_bik", sa.String(), nullable=True))
    op.add_column("clients", sa.Column("bank_iik", sa.String(), nullable=True))
    op.add_column("clients", sa.Column("bank_kbe", sa.String(), nullable=True))
    op.add_column("clients", sa.Column("vat_registered", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("clients", sa.Column("vat_certificate_number", sa.String(), nullable=True))
    op.add_column("clients", sa.Column("contact_person", sa.String(), nullable=True))
    # Nullable, no default: SQLite's ALTER TABLE ADD COLUMN rejects a
    # non-constant default like CURRENT_TIMESTAMP outright, and a constant
    # literal would be a meaningless fake timestamp for pre-existing rows.
    # ORM-side default=_now/onupdate=_now populates it for every row this
    # migration doesn't touch, going forward.
    op.add_column("clients", sa.Column("updated_at", sa.DateTime(), nullable=True))

    op.create_table(
        "employees",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("company_id", sa.String(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column("iin", sa.String(), nullable=True),
        sa.Column("position", sa.String(), nullable=True),
        sa.Column("department", sa.String(), nullable=True),
        sa.Column("hire_date", sa.DateTime(), nullable=True),
        sa.Column("salary", sa.Numeric(14, 2), nullable=True),
        sa.Column("allowances", sa.Numeric(14, 2), nullable=True),
        sa.Column("probation_period", sa.String(), nullable=True),
        sa.Column("work_schedule", sa.String(), nullable=True),
        sa.Column("vacation_days", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("address", sa.String(), nullable=True),
        sa.Column("id_doc_number", sa.String(), nullable=True),
        sa.Column("id_doc_issued_by", sa.String(), nullable=True),
        sa.Column("id_doc_date", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_employees_company_id", "employees", ["company_id"])
    op.create_index("ix_employees_full_name", "employees", ["full_name"])

    op.create_table(
        "document_counters",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("company_id", sa.String(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_value", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        # Inline, not a separate create_unique_constraint call afterward —
        # SQLite has no ALTER-constraint support at all (not even in batch
        # mode's copy-and-move sense for a table this migration itself just
        # created), so the constraint has to be part of the CREATE TABLE.
        sa.UniqueConstraint("company_id", "kind", "year", name="uq_document_counters_company_kind_year"),
    )
    op.create_index("ix_document_counters_company_id", "document_counters", ["company_id"])
    op.create_index("ix_document_counters_kind", "document_counters", ["kind"])


def downgrade() -> None:
    # No separate drop_constraint call: SQLite has no ALTER-constraint
    # support, and dropping the table below removes it anyway.
    op.drop_index("ix_document_counters_kind", table_name="document_counters")
    op.drop_index("ix_document_counters_company_id", table_name="document_counters")
    op.drop_table("document_counters")

    op.drop_index("ix_employees_full_name", table_name="employees")
    op.drop_index("ix_employees_company_id", table_name="employees")
    op.drop_table("employees")

    op.drop_column("clients", "updated_at")
    op.drop_column("clients", "contact_person")
    op.drop_column("clients", "vat_certificate_number")
    op.drop_column("clients", "vat_registered")
    op.drop_column("clients", "bank_kbe")
    op.drop_column("clients", "bank_iik")
    op.drop_column("clients", "bank_bik")
    op.drop_column("clients", "bank_name")
    op.drop_column("clients", "signatory_basis")
    op.drop_column("clients", "signatory_name")
    op.drop_column("clients", "address")

    op.drop_column("companies", "signature_image_key")
    op.drop_column("companies", "stamp_image_key")
