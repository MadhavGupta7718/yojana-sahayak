"""Seed admin, sources, ranking weights, and approval rules."""

from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.session import SessionLocal
from app.models import (
    AdminUser,
    ApprovalRule,
    GovernmentSource,
    RankingWeights,
    SourcePriorityRule,
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SENSITIVE_FIELDS = [
    ("interest_rate", True, False, "Interest rate changes require verification"),
    ("max_loan", True, False, "Maximum loan amount"),
    ("min_loan", True, False, "Minimum loan amount"),
    ("max_income", True, False, "Income limit"),
    ("min_income", True, False, "Minimum income"),
    ("tenure", True, False, "Loan tenure"),
    ("moratorium", True, False, "Moratorium period"),
    ("loan_percentage", True, False, "Loan percentage / contribution"),
    ("beneficiary_requirements", True, False, "Eligibility conditions"),
    ("eligible_activities", True, False, "Eligible activities"),
    ("npa_status", True, False, "Partner NPA status"),
    ("overdue_status", True, False, "Partner overdue status"),
    ("fund_utilization", True, False, "Fund utilization"),
    ("phone", False, True, "Contact number"),
    ("email", False, True, "Email address"),
    ("address", False, True, "Address formatting"),
    ("description", False, True, "Minor textual description"),
    ("website", False, True, "Website URL"),
]

SOURCES = [
    {
        "source_name": "NSFDC",
        "organization": "National Scheduled Castes Finance and Development Corporation",
        "base_url": "https://nsfdc.nic.in/",
        "source_type": "institution",
        "authority_level": 90,
        "enabled": True,
        "crawl_frequency": 15,
        "status": "PENDING",
        "notes": "Primary official source for SC concessional finance schemes",
        "discovery_status": "approved",
    },
    {
        "source_name": "MoSJE",
        "organization": "Ministry of Social Justice and Empowerment",
        "base_url": "https://socialjustice.gov.in/",
        "source_type": "ministry",
        "authority_level": 95,
        "enabled": False,
        "crawl_frequency": 60,
        "status": "PENDING",
        "notes": "Enabled after authority/relevance verification and robots check",
        "discovery_status": "approved",
    },
    {
        "source_name": "data.gov.in",
        "organization": "Open Government Data Platform India",
        "base_url": "https://www.data.gov.in/",
        "source_type": "open_data",
        "authority_level": 70,
        "enabled": False,
        "crawl_frequency": 360,
        "status": "PENDING",
        "notes": "Discovery candidate for structured datasets; not auto-enabled",
        "discovery_status": "pending_review",
    },
    {
        "source_name": "SCA Placeholder - Review Required",
        "organization": "State Channelizing Agency (generic placeholder)",
        "base_url": "https://www.india.gov.in/",
        "source_type": "state",
        "authority_level": 60,
        "enabled": False,
        "crawl_frequency": 1440,
        "status": "PENDING",
        "notes": "Replace with specific SCA official URLs after admin review",
        "discovery_status": "pending_review",
    },
]


def seed(db: Session | None = None) -> None:
    own_session = db is None
    if own_session:
        db = SessionLocal()
    settings = get_settings()
    try:
        admin = db.query(AdminUser).filter(AdminUser.username == settings.admin_username).first()
        if not admin:
            db.add(
                AdminUser(
                    username=settings.admin_username,
                    password_hash=pwd_context.hash(settings.admin_password),
                    role="superadmin",
                    is_active=True,
                )
            )

        for src in SOURCES:
            existing = db.query(GovernmentSource).filter(GovernmentSource.source_name == src["source_name"]).first()
            if not existing:
                db.add(GovernmentSource(**src))

        if not db.query(RankingWeights).filter(RankingWeights.name == "default").first():
            db.add(
                RankingWeights(
                    name="default",
                    eligibility=settings.weight_eligibility,
                    purpose=settings.weight_purpose,
                    loan_amount=settings.weight_loan_amount,
                    project_cost=settings.weight_project_cost,
                    other=settings.weight_other,
                    is_active=True,
                )
            )

        for field_name, is_sensitive, auto_approve, desc in SENSITIVE_FIELDS:
            if not db.query(ApprovalRule).filter(ApprovalRule.field_name == field_name).first():
                db.add(
                    ApprovalRule(
                        field_name=field_name,
                        is_sensitive=is_sensitive,
                        auto_approve=auto_approve,
                        description=desc,
                    )
                )

        priorities = [
            ("Specific current scheme notification", 100, "notification"),
            ("Central organization scheme page", 90, "institution"),
            ("Ministry source", 85, "ministry"),
            ("State implementation source", 70, "state"),
            ("Older document / open data", 50, "open_data"),
        ]
        if db.query(SourcePriorityRule).count() == 0:
            for name, priority, match in priorities:
                db.add(SourcePriorityRule(name=name, priority=priority, match_source_type=match))

        db.commit()
        print("Seed completed successfully.")
    except Exception:
        db.rollback()
        raise
    finally:
        if own_session:
            db.close()


if __name__ == "__main__":
    seed()
