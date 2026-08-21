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

Revision ID: 0006_reference_numbering
Revises: 0005_email_verification
Create Date: 2026-08-20

NOTE: originally shipped as "0006_reference_data_and_numbering" (33 chars)
— alembic_version.version_num is varchar(32) on Postgres, so the very last
step of this migration (stamping the new version) crashed with
StringDataRightTruncation on prod, restart-looping the api container.
Postgres DDL is transactional and this migration runs inside
`context.begin_transaction()` (see alembic/env.py), so the failed stamp
rolled back everything else in the same transaction too — prod was left
cleanly on 0005, not partially migrated. Renamed here to stay well under
32 chars. Also made idempotent (every step checks first) as a defensive
measure, not because that was the actual root cause — a clean rollback
means a straightforward retry after this rename is sufficient, but the
existence checks make a second `alembic upgrade head` safe to run
regardless, if there's ever a reason to.

RULE: every future revision id must stay under 32 characters —
alembic_version.version_num is varchar(32) and does not get widened by
migrations that add unrelated columns elsewhere. Check with:
  python -c "print(len('your_revision_id'))"
before naming a new revision. See infra/README.md.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_reference_numbering"
down_revision = "0005_email_verification"
branch_labels = None
depends_on = None


def _existing_columns(insp, table: str) -> set[str]:
    return {c["name"] for c in insp.get_columns(table)}


def _add_column_if_missing(insp, table: str, column: sa.Column) -> None:
    if column.name not in _existing_columns(insp, table):
        op.add_column(table, column)


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    _add_column_if_missing(insp, "companies", sa.Column("stamp_image_key", sa.String(), nullable=True))
    _add_column_if_missing(insp, "companies", sa.Column("signature_image_key", sa.String(), nullable=True))

    _add_column_if_missing(insp, "clients", sa.Column("address", sa.String(), nullable=True))
    _add_column_if_missing(insp, "clients", sa.Column("signatory_name", sa.String(), nullable=True))
    _add_column_if_missing(insp, "clients", sa.Column("signatory_basis", sa.String(), nullable=True))
    _add_column_if_missing(insp, "clients", sa.Column("bank_name", sa.String(), nullable=True))
    _add_column_if_missing(insp, "clients", sa.Column("bank_bik", sa.String(), nullable=True))
    _add_column_if_missing(insp, "clients", sa.Column("bank_iik", sa.String(), nullable=True))
    _add_column_if_missing(insp, "clients", sa.Column("bank_kbe", sa.String(), nullable=True))
    _add_column_if_missing(insp, "clients", sa.Column(
        "vat_registered", sa.Boolean(), nullable=False, server_default=sa.false(),
    ))
    _add_column_if_missing(insp, "clients", sa.Column("vat_certificate_number", sa.String(), nullable=True))
    _add_column_if_missing(insp, "clients", sa.Column("contact_person", sa.String(), nullable=True))
    # Nullable, no default: SQLite's ALTER TABLE ADD COLUMN rejects a
    # non-constant default like CURRENT_TIMESTAMP outright, and a constant
    # literal would be a meaningless fake timestamp for pre-existing rows.
    # ORM-side default=_now/onupdate=_now populates it for every row this
    # migration doesn't touch, going forward.
    _add_column_if_missing(insp, "clients", sa.Column("updated_at", sa.DateTime(), nullable=True))

    if not insp.has_table("employees"):
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

    if not insp.has_table("document_counters"):
        op.create_table(
            "document_counters",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("company_id", sa.String(), sa.ForeignKey("companies.id"), nullable=False),
            sa.Column("kind", sa.String(), nullable=False),
            sa.Column("year", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("current_value", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            # Inline, not a separate create_unique_constraint call afterward
            # — SQLite has no ALTER-constraint support at all (not even in
            # batch mode's copy-and-move sense for a table this migration
            # itself just created), so the constraint has to be part of the
            # CREATE TABLE.
            sa.UniqueConstraint("company_id", "kind", "year", name="uq_document_counters_company_kind_year"),
        )
        op.create_index("ix_document_counters_company_id", "document_counters", ["company_id"])
        op.create_index("ix_document_counters_kind", "document_counters", ["kind"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if insp.has_table("document_counters"):
        # No separate drop_constraint call: SQLite has no ALTER-constraint
        # support, and dropping the table below removes it anyway.
        existing_indexes = {ix["name"] for ix in insp.get_indexes("document_counters")}
        if "ix_document_counters_kind" in existing_indexes:
            op.drop_index("ix_document_counters_kind", table_name="document_counters")
        if "ix_document_counters_company_id" in existing_indexes:
            op.drop_index("ix_document_counters_company_id", table_name="document_counters")
        op.drop_table("document_counters")

    if insp.has_table("employees"):
        existing_indexes = {ix["name"] for ix in insp.get_indexes("employees")}
        if "ix_employees_full_name" in existing_indexes:
            op.drop_index("ix_employees_full_name", table_name="employees")
        if "ix_employees_company_id" in existing_indexes:
            op.drop_index("ix_employees_company_id", table_name="employees")
        op.drop_table("employees")

    clients_cols = _existing_columns(insp, "clients")
    for col in ("updated_at", "contact_person", "vat_certificate_number", "vat_registered",
                "bank_kbe", "bank_iik", "bank_bik", "bank_name", "signatory_basis",
                "signatory_name", "address"):
        if col in clients_cols:
            op.drop_column("clients", col)

    companies_cols = _existing_columns(insp, "companies")
    for col in ("signature_image_key", "stamp_image_key"):
        if col in companies_cols:
            op.drop_column("companies", col)
