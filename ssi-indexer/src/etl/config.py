from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = "0.0.0.0"
    port: int = 8090

    oidc_issuer_url: str | None = None
    oidc_internal_url: str | None = None
    oidc_audience: str | None = None
    zitadel_internal_url: str | None = None
    zitadel_service_pat: str | None = None
    zitadel_service_pat_file: Path | None = None
    auth_mode: str = "auto"

    kafka_enabled: bool = True
    kafka_bootstrap_servers: str = "kafka:9092"
    kafka_instruction_security_events_topic: str = "instruction_security_events"
    kafka_instruction_security_events_consumer_group: str = "instruction-security-event-etl"
    kafka_instruction_topic: str = "instructions"
    kafka_instruction_consumer_group: str = "ssi-instruction-etl"
    kafka_payment_security_events_topic: str = "payment_security_events"
    kafka_payment_security_events_consumer_group: str = "payment-security-event-etl"
    kafka_payments_topic: str = "payments"
    kafka_payments_consumer_group: str = "payment-fact-etl"

    neo4j_uri: str = "bolt://neo4j:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "devpassword"
    graph_model_dir: str = "/app/neo4j-graph-model"

    multimodal_vector_index: str = "multimodal_embedding"
    multimodal_fulltext_index: str = "multimodal_search_text"

    gcp_project_id: str = "rag-demos-501323"
    gcp_region: str = "us-central1"
    vertex_embedding_model: str = "text-embedding-004"
    embedding_dimension: int = 768

    search_default_limit: int = 10
    search_profiles_dir: str | None = None

    @property
    def graph_schema_path(self):
        return self.graph_model_dir_path / "relationships.cypher"

    @model_validator(mode="after")
    def load_service_pat_from_file(self) -> "Settings":
        if self.zitadel_service_pat or not self.zitadel_service_pat_file:
            return self
        path = self.zitadel_service_pat_file
        if path.is_file():
            self.zitadel_service_pat = path.read_text(encoding="utf-8").strip()
        return self

    @property
    def graph_model_dir_path(self) -> Path:
        return Path(self.graph_model_dir)


settings = Settings()
