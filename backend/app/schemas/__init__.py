from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ProfileInput(BaseModel):
    age: Optional[int] = Field(None, ge=1, le=120)
    category: Optional[str] = None
    annual_family_income: Optional[float] = Field(None, ge=0)
    occupation: Optional[str] = None
    education_status: Optional[str] = None
    project_type: Optional[str] = None
    project_cost: Optional[float] = Field(None, ge=0)
    loan_required: Optional[float] = Field(None, ge=0)
    purpose: Optional[str] = None
    location: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    existing_loan: Optional[bool] = None
    session_id: Optional[str] = None


class EMIRequest(BaseModel):
    principal: float = Field(..., gt=0)
    annual_rate_percent: Optional[float] = Field(None, ge=0)
    tenure_months: int = Field(..., gt=0)
    moratorium_months: int = Field(0, ge=0)
    repayment_frequency: str = "monthly"
    moratorium_interest_known: bool = False


class PartnerSearchRequest(BaseModel):
    scheme_id: int
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    address: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    pin_code: Optional[str] = None
    max_radius_km: Optional[int] = Field(None, ge=1, le=500)


class NLPParseRequest(BaseModel):
    text: str = Field(..., min_length=2, max_length=2000)


class AdminLogin(BaseModel):
    username: str
    password: str


class SourceCreate(BaseModel):
    source_name: str
    organization: str
    base_url: str
    source_type: str
    authority_level: int = 50
    enabled: bool = False
    crawl_frequency: int = 15
    notes: Optional[str] = None


class SourceUpdate(BaseModel):
    enabled: Optional[bool] = None
    crawl_frequency: Optional[int] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    discovery_status: Optional[str] = None
    authority_level: Optional[int] = None


class ChangeDecision(BaseModel):
    approve: bool
    notes: Optional[str] = None


class SchemeOut(BaseModel):
    id: int
    name: str
    scheme_type: Optional[str] = None
    purpose: Optional[str] = None
    description: Optional[str] = None
    min_income: Optional[float] = None
    max_income: Optional[float] = None
    min_loan: Optional[float] = None
    max_loan: Optional[float] = None
    interest_rate: Optional[float] = None
    tenure: Optional[int] = None
    moratorium: Optional[int] = None
    required_documents: Optional[Any] = None
    application_process: Optional[str] = None
    source_url: Optional[str] = None
    last_verified: Optional[datetime] = None
    freshness: Optional[str] = None
    status: str
    current_version: int

    class Config:
        from_attributes = True
