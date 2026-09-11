"""Initial schema for YojanaSahayak.

Revision ID: 001_initial
Revises:
Create Date: 2026-09-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "government_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_name", sa.String(255), nullable=False, unique=True),
        sa.Column("organization", sa.String(255), nullable=False),
        sa.Column("base_url", sa.String(1000), nullable=False),
        sa.Column("source_type", sa.String(100), nullable=False),
        sa.Column("authority_level", sa.Integer(), server_default="50"),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("crawl_frequency", sa.Integer(), server_default="15"),
        sa.Column("robots_allowed", sa.Boolean(), nullable=True),
        sa.Column("last_checked", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_successful_crawl", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_changed", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(50), server_default="PENDING"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("discovery_status", sa.String(50), server_default="approved"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "admin_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(100), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), server_default="viewer"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "scraping_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("government_sources.id"), nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(50), server_default="running"),
        sa.Column("pages_crawled", sa.Integer(), server_default="0"),
        sa.Column("documents_processed", sa.Integer(), server_default="0"),
        sa.Column("changes_detected", sa.Integer(), server_default="0"),
        sa.Column("error_count", sa.Integer(), server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("annual_family_income", sa.Float(), nullable=True),
        sa.Column("occupation", sa.String(255), nullable=True),
        sa.Column("education_status", sa.String(255), nullable=True),
        sa.Column("project_type", sa.String(255), nullable=True),
        sa.Column("project_cost", sa.Float(), nullable=True),
        sa.Column("loan_required", sa.Float(), nullable=True),
        sa.Column("purpose", sa.String(100), nullable=True),
        sa.Column("location", sa.String(500), nullable=True),
        sa.Column("state", sa.String(100), nullable=True),
        sa.Column("district", sa.String(100), nullable=True),
        sa.Column("existing_loan", sa.Boolean(), nullable=True),
        sa.Column("session_id", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_users_session_id", "users", ["session_id"])

    op.create_table(
        "schemes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("scheme_type", sa.String(100), nullable=True),
        sa.Column("purpose", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("min_income", sa.Float(), nullable=True),
        sa.Column("max_income", sa.Float(), nullable=True),
        sa.Column("min_loan", sa.Float(), nullable=True),
        sa.Column("max_loan", sa.Float(), nullable=True),
        sa.Column("interest_rate", sa.Float(), nullable=True),
        sa.Column("interest_rate_type", sa.String(50), nullable=True),
        sa.Column("tenure", sa.Integer(), nullable=True),
        sa.Column("moratorium", sa.Integer(), nullable=True),
        sa.Column("loan_percentage", sa.Float(), nullable=True),
        sa.Column("beneficiary_requirements", postgresql.JSONB(), nullable=True),
        sa.Column("eligible_activities", postgresql.JSONB(), nullable=True),
        sa.Column("required_documents", postgresql.JSONB(), nullable=True),
        sa.Column("application_process", sa.Text(), nullable=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("government_sources.id"), nullable=True),
        sa.Column("source_url", sa.String(1000), nullable=True),
        sa.Column("last_verified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_version", sa.Integer(), server_default="1"),
        sa.Column("status", sa.String(50), server_default="active"),
        sa.Column("canonical_key", sa.String(500), nullable=True, unique=True),
        sa.Column("raw_fields", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_schemes_name", "schemes", ["name"])

    op.create_table(
        "scheme_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scheme_id", sa.Integer(), sa.ForeignKey("schemes.id"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("data_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("government_sources.id"), nullable=True),
        sa.Column("source_url", sa.String(1000), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(50), server_default="active"),
        sa.UniqueConstraint("scheme_id", "version_number", name="uq_scheme_version"),
    )
    op.create_index("ix_scheme_versions_scheme_id", "scheme_versions", ["scheme_id"])

    op.create_table(
        "scheme_eligibility_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scheme_id", sa.Integer(), sa.ForeignKey("schemes.id"), nullable=False),
        sa.Column("rule_type", sa.String(100), nullable=False),
        sa.Column("operator", sa.String(50), nullable=False),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("government_sources.id"), nullable=True),
        sa.Column("is_hard", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_scheme_eligibility_rules_scheme_id", "scheme_eligibility_rules", ["scheme_id"])

    op.create_table(
        "partners",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("partner_type", sa.String(100), nullable=True),
        sa.Column("organization", sa.String(500), nullable=True),
        sa.Column("state", sa.String(100), nullable=True),
        sa.Column("district", sa.String(100), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("phone", sa.String(100), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("website", sa.String(1000), nullable=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("government_sources.id"), nullable=True),
        sa.Column("source_url", sa.String(1000), nullable=True),
        sa.Column("last_verified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(50), server_default="active"),
        sa.Column("canonical_key", sa.String(500), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_partners_name", "partners", ["name"])
    op.create_index("ix_partners_state", "partners", ["state"])

    op.create_table(
        "partner_scheme_mapping",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("partner_id", sa.Integer(), sa.ForeignKey("partners.id"), nullable=False),
        sa.Column("scheme_id", sa.Integer(), sa.ForeignKey("schemes.id"), nullable=False),
        sa.Column("eligibility_status", sa.String(50), server_default="eligible"),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("government_sources.id"), nullable=True),
        sa.Column("last_verified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("partner_id", "scheme_id", name="uq_partner_scheme"),
    )

    op.create_table(
        "partner_status",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("partner_id", sa.Integer(), sa.ForeignKey("partners.id"), nullable=False, unique=True),
        sa.Column("fund_utilization", sa.String(255), nullable=True),
        sa.Column("npa_status", sa.String(255), nullable=True),
        sa.Column("overdue_status", sa.String(255), nullable=True),
        sa.Column("status", sa.String(50), server_default="unknown"),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("government_sources.id"), nullable=True),
        sa.Column("last_verified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "raw_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("government_sources.id"), nullable=False),
        sa.Column("url", sa.String(2000), nullable=False),
        sa.Column("title", sa.String(1000), nullable=True),
        sa.Column("content_type", sa.String(100), server_default="html"),
        sa.Column("content_hash", sa.String(128), nullable=False),
        sa.Column("http_etag", sa.String(255), nullable=True),
        sa.Column("http_last_modified", sa.String(255), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("storage_path", sa.String(1000), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.Column("scraping_run_id", sa.Integer(), sa.ForeignKey("scraping_runs.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_raw_documents_source_id", "raw_documents", ["source_id"])
    op.create_index("ix_raw_documents_content_hash", "raw_documents", ["content_hash"])

    op.create_table(
        "staging_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("government_sources.id"), nullable=False),
        sa.Column("raw_document_id", sa.Integer(), sa.ForeignKey("raw_documents.id"), nullable=True),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_key", sa.String(500), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("original_text", postgresql.JSONB(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("status", sa.String(50), server_default="pending"),
        sa.Column("source_url", sa.String(2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_staging_records_entity_key", "staging_records", ["entity_key"])

    op.create_table(
        "data_changes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("entity_key", sa.String(500), nullable=True),
        sa.Column("field_name", sa.String(100), nullable=False),
        sa.Column("old_value", postgresql.JSONB(), nullable=True),
        sa.Column("new_value", postgresql.JSONB(), nullable=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("government_sources.id"), nullable=True),
        sa.Column("source_url", sa.String(2000), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("status", sa.String(50), server_default="detected"),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("admin_users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_sensitive", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("is_conflict", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "scraping_errors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scraping_run_id", sa.Integer(), sa.ForeignKey("scraping_runs.id"), nullable=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("government_sources.id"), nullable=True),
        sa.Column("url", sa.String(2000), nullable=True),
        sa.Column("error_type", sa.String(100), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "source_citations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("field_name", sa.String(100), nullable=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("government_sources.id"), nullable=True),
        sa.Column("source_url", sa.String(2000), nullable=False),
        sa.Column("source_title", sa.String(1000), nullable=True),
        sa.Column("source_section", sa.String(500), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("last_verified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_source_citations_entity_id", "source_citations", ["entity_id"])

    op.create_table(
        "application_guidance",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scheme_id", sa.Integer(), sa.ForeignKey("schemes.id"), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("steps", postgresql.JSONB(), nullable=False),
        sa.Column("disclaimer", sa.Text(), nullable=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("government_sources.id"), nullable=True),
        sa.Column("source_url", sa.String(2000), nullable=True),
        sa.Column("last_verified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("admin_user_id", sa.Integer(), sa.ForeignKey("admin_users.id"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "ranking_weights",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), unique=True, server_default="default"),
        sa.Column("eligibility", sa.Float(), server_default="40"),
        sa.Column("purpose", sa.Float(), server_default="25"),
        sa.Column("loan_amount", sa.Float(), server_default="15"),
        sa.Column("project_cost", sa.Float(), server_default="10"),
        sa.Column("other", sa.Float(), server_default="10"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "approval_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("field_name", sa.String(100), unique=True, nullable=False),
        sa.Column("is_sensitive", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("auto_approve", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "source_priority_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("match_source_type", sa.String(100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )


def downgrade() -> None:
    for table in [
        "source_priority_rules",
        "approval_rules",
        "ranking_weights",
        "audit_logs",
        "application_guidance",
        "source_citations",
        "scraping_errors",
        "data_changes",
        "staging_records",
        "raw_documents",
        "partner_status",
        "partner_scheme_mapping",
        "partners",
        "scheme_eligibility_rules",
        "scheme_versions",
        "schemes",
        "users",
        "scraping_runs",
        "admin_users",
        "government_sources",
    ]:
        op.drop_table(table)
