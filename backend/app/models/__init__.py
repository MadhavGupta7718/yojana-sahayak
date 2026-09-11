from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class GovernmentSource(Base, TimestampMixin):
    __tablename__ = "government_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    organization: Mapped[str] = mapped_column(String(255), nullable=False)
    base_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_type: Mapped[str] = mapped_column(String(100), nullable=False)  # central, ministry, institution, state, open_data
    authority_level: Mapped[int] = mapped_column(Integer, default=50)  # higher = more authoritative
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    crawl_frequency: Mapped[int] = mapped_column(Integer, default=15)  # minutes
    robots_allowed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    last_checked: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_successful_crawl: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_changed: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="PENDING")  # ACTIVE, MANUAL/RESTRICTED, WARNING, ERROR, PENDING
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    discovery_status: Mapped[str] = mapped_column(String(50), default="approved")  # pending_review, approved, rejected


class UserProfile(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    annual_family_income: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    occupation: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    education_status: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    project_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    project_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    loan_required: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    purpose: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    district: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    existing_loan: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)


class Scheme(Base, TimestampMixin):
    __tablename__ = "schemes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    scheme_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    purpose: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    min_income: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_income: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    min_loan: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_loan: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    interest_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    interest_rate_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    tenure: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # months
    moratorium: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # months
    loan_percentage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    beneficiary_requirements: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    eligible_activities: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    required_documents: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    application_process: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_id: Mapped[Optional[int]] = mapped_column(ForeignKey("government_sources.id"), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    last_verified: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(50), default="active")  # active, discontinued, unavailable
    canonical_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, unique=True)
    raw_fields: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)

    versions = relationship("SchemeVersion", back_populates="scheme")
    eligibility_rules = relationship("SchemeEligibilityRule", back_populates="scheme")


class SchemeVersion(Base):
    __tablename__ = "scheme_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scheme_id: Mapped[int] = mapped_column(ForeignKey("schemes.id"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    data_snapshot: Mapped[Any] = mapped_column(JSONB, nullable=False)
    effective_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    source_id: Mapped[Optional[int]] = mapped_column(ForeignKey("government_sources.id"), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active")

    scheme = relationship("Scheme", back_populates="versions")

    __table_args__ = (UniqueConstraint("scheme_id", "version_number", name="uq_scheme_version"),)


class SchemeEligibilityRule(Base, TimestampMixin):
    __tablename__ = "scheme_eligibility_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scheme_id: Mapped[int] = mapped_column(ForeignKey("schemes.id"), nullable=False, index=True)
    rule_type: Mapped[str] = mapped_column(String(100), nullable=False)  # income, category, age, etc.
    operator: Mapped[str] = mapped_column(String(50), nullable=False)  # eq, lte, gte, in, contains, between
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_id: Mapped[Optional[int]] = mapped_column(ForeignKey("government_sources.id"), nullable=True)
    is_hard: Mapped[bool] = mapped_column(Boolean, default=True)

    scheme = relationship("Scheme", back_populates="eligibility_rules")


class Partner(Base, TimestampMixin):
    __tablename__ = "partners"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    partner_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    organization: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    district: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    source_id: Mapped[Optional[int]] = mapped_column(ForeignKey("government_sources.id"), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    last_verified: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active")
    canonical_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, unique=True)


class PartnerSchemeMapping(Base, TimestampMixin):
    __tablename__ = "partner_scheme_mapping"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    partner_id: Mapped[int] = mapped_column(ForeignKey("partners.id"), nullable=False)
    scheme_id: Mapped[int] = mapped_column(ForeignKey("schemes.id"), nullable=False)
    eligibility_status: Mapped[str] = mapped_column(String(50), default="eligible")
    source_id: Mapped[Optional[int]] = mapped_column(ForeignKey("government_sources.id"), nullable=True)
    last_verified: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (UniqueConstraint("partner_id", "scheme_id", name="uq_partner_scheme"),)


class PartnerStatus(Base, TimestampMixin):
    __tablename__ = "partner_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    partner_id: Mapped[int] = mapped_column(ForeignKey("partners.id"), nullable=False, unique=True)
    fund_utilization: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    npa_status: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    overdue_status: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="unknown")
    source_id: Mapped[Optional[int]] = mapped_column(ForeignKey("government_sources.id"), nullable=True)
    last_verified: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class RawDocument(Base, TimestampMixin):
    __tablename__ = "raw_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("government_sources.id"), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    content_type: Mapped[str] = mapped_column(String(100), default="html")
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    http_etag: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    http_last_modified: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    storage_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    metadata_json: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    scraping_run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("scraping_runs.id"), nullable=True)


class StagingRecord(Base, TimestampMixin):
    __tablename__ = "staging_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("government_sources.id"), nullable=False)
    raw_document_id: Mapped[Optional[int]] = mapped_column(ForeignKey("raw_documents.id"), nullable=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # scheme, partner, guidance, document
    entity_key: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    payload: Mapped[Any] = mapped_column(JSONB, nullable=False)
    original_text: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending, compared, promoted, rejected
    source_url: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)


class DataChange(Base, TimestampMixin):
    __tablename__ = "data_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    entity_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    old_value: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    source_id: Mapped[Optional[int]] = mapped_column(ForeignKey("government_sources.id"), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="detected")
    # detected, pending_review, approved, rejected, auto_approved, conflict
    reviewed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False)
    is_conflict: Mapped[bool] = mapped_column(Boolean, default=False)


class ScrapingRun(Base):
    __tablename__ = "scraping_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[Optional[int]] = mapped_column(ForeignKey("government_sources.id"), nullable=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="running")
    pages_crawled: Mapped[int] = mapped_column(Integer, default=0)
    documents_processed: Mapped[int] = mapped_column(Integer, default=0)
    changes_detected: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class ScrapingError(Base):
    __tablename__ = "scraping_errors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scraping_run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("scraping_runs.id"), nullable=True)
    source_id: Mapped[Optional[int]] = mapped_column(ForeignKey("government_sources.id"), nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    error_type: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SourceCitation(Base, TimestampMixin):
    __tablename__ = "source_citations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    field_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_id: Mapped[Optional[int]] = mapped_column(ForeignKey("government_sources.id"), nullable=True)
    source_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    source_title: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    source_section: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_verified: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class AdminUser(Base, TimestampMixin):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="viewer")  # viewer, reviewer, superadmin
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ApplicationGuidance(Base, TimestampMixin):
    __tablename__ = "application_guidance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scheme_id: Mapped[Optional[int]] = mapped_column(ForeignKey("schemes.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    steps: Mapped[Any] = mapped_column(JSONB, nullable=False)
    disclaimer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_id: Mapped[Optional[int]] = mapped_column(ForeignKey("government_sources.id"), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    last_verified: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    details: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RankingWeights(Base, TimestampMixin):
    __tablename__ = "ranking_weights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, default="default")
    eligibility: Mapped[float] = mapped_column(Float, default=40)
    purpose: Mapped[float] = mapped_column(Float, default=25)
    loan_amount: Mapped[float] = mapped_column(Float, default=15)
    project_cost: Mapped[float] = mapped_column(Float, default=10)
    other: Mapped[float] = mapped_column(Float, default=10)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ApprovalRule(Base, TimestampMixin):
    __tablename__ = "approval_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    field_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_approve: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class SourcePriorityRule(Base, TimestampMixin):
    __tablename__ = "source_priority_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    match_source_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
