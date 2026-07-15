from pathlib import Path
from typing import Self

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8091
    oidc_issuer_url: str | None = None
    oidc_internal_url: str | None = None
    oidc_audience: str | None = None
    zitadel_url: str = "http://localhost:8080"
    zitadel_internal_url: str | None = None
    zitadel_host_header: str = ""
    zitadel_service_pat: str = ""
    zitadel_service_pat_file: Path | None = None
    instruction_service_url: str = Field(
        default="http://localhost:8000",
        validation_alias=AliasChoices("instruction_service_url", "INSTRUCTION_SERVICE_URL"),
    )
    instruction_service_api_prefix: str = Field(
        default="/api/v1",
        validation_alias=AliasChoices(
            "instruction_service_api_prefix",
            "INSTRUCTION_SERVICE_API_PREFIX",
        ),
    )
    default_password: str = "Password1!"
    email_domain: str = "ssi.local"
    security_events_database: str = "security_events"
    security_events_collection: str = "instruction_service"
    payment_service_url: str = "http://localhost:8093"
    payment_service_api_prefix: str = "/api/v1"
    payment_security_events_collection: str = "payment_service"
    mongodb_uri: str = "mongodb://localhost:27017"
    verify_security_events: bool = True

    @model_validator(mode="after")
    def load_service_pat_from_file(self) -> Self:
        if self.zitadel_service_pat or not self.zitadel_service_pat_file:
            return self
        path = self.zitadel_service_pat_file
        if path.is_file():
            self.zitadel_service_pat = path.read_text(encoding="utf-8").strip()
        return self


settings = Settings()
