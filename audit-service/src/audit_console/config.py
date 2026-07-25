from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongodb_uri: str = "mongodb://localhost:27017/?replicaSet=rs0"
    security_events_database: str = "security_events"
    instruction_events_collection: str = "instruction_service"
    payment_events_collection: str = "payment_service"
    audit_database: str = "ssi_cash_activities"
    audit_collection: str = "audit_executions"

    oidc_issuer_url: str = "http://localhost:8080"
    oidc_internal_url: str | None = None
    zitadel_internal_url: str | None = None
    zitadel_service_pat: str | None = None
    zitadel_service_pat_file: Path | None = None
    required_group: str = "TECH_AUDITORS"
    initial_limit: int = Field(default=200, ge=1, le=1000)

    @model_validator(mode="after")
    def load_service_pat_from_file(self) -> "Settings":
        if self.zitadel_service_pat or not self.zitadel_service_pat_file:
            return self
        if self.zitadel_service_pat_file.is_file():
            self.zitadel_service_pat = self.zitadel_service_pat_file.read_text(
                encoding="utf-8"
            ).strip()
        return self


settings = Settings()
