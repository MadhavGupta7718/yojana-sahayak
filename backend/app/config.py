from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg2://yojana:yojana_secure_change_me@localhost:5432/yojana_sahayak"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "dev-secret-change-me"
    admin_username: str = "admin"
    admin_password: str = "Admin@ChangeMe123"
    access_token_expire_minutes: int = 480
    cors_origins: str = "http://localhost:3000"

    crawler_user_agent: str = "YojanaSahayakBot/1.0 (+https://localhost; research; respectful crawler)"
    crawl_delay_seconds: float = 1.5
    default_crawl_frequency_minutes: int = 15
    max_partner_radius_km: int = 100
    partner_radius_steps_km: str = "20,40,60,100"

    weight_eligibility: float = 40
    weight_purpose: float = 25
    weight_loan_amount: float = 15
    weight_project_cost: float = 10
    weight_other: float = 10

    freshness_fresh_days: int = 7
    freshness_aging_days: int = 30

    enable_embeddings: bool = False
    embedding_model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    upload_dir: str = "/app/uploads"

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def partner_radius_steps(self) -> List[int]:
        return [int(x.strip()) for x in self.partner_radius_steps_km.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
