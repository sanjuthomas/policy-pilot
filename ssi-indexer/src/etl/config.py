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

    # Realtime retry (retryable Neo4j / downstream failures)
    kafka_retry_max_attempts: int = 5
    kafka_retry_base_delay_seconds: float = 0.2
    kafka_retry_max_delay_seconds: float = 30.0

    # Mongo DLQ — dedicated database (scheduler must not touch transactional DBs)
    dlq_mongodb_uri: str = "mongodb://mongodb:27017/?replicaSet=rs0"
    dlq_mongodb_database: str = "ssi_indexer_dlq"
    dlq_mongodb_collection: str = "dead_letters"
    dlq_scheduler_interval_seconds: int = 300
    dlq_scheduler_batch_size: int = 20
    dlq_scheduler_max_attempts: int = 8
    dlq_scheduler_backoff_seconds: float = 30.0
    dlq_scheduler_max_backoff_seconds: float = 3600.0
    dlq_lock_ttl_seconds: int = 300
    dlq_pause_poll_seconds: float = 5.0

    # Chat / health honesty signal
    index_lag_banner_threshold: int = 10

    neo4j_uri: str = "bolt://neo4j:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "devpassword"
    graph_model_dir: str = "/app/neo4j-graph-model"

    multimodal_vector_index: str = "multimodal_embedding"

    gcp_project_id: str = "rag-demos-501323"
    gcp_region: str = "us-central1"
    vertex_embedding_model: str = "text-embedding-004"
    vertex_gemini_model: str = "gemini-2.5-flash"
    embedding_dimension: int = 768

    search_default_limit: int = 10
    search_profiles_dir: str | None = None

    @model_validator(mode="after")
    def load_service_pat_from_file(self) -> "Settings":
        if self.zitadel_service_pat or not self.zitadel_service_pat_file:
            return self
        path = self.zitadel_service_pat_file
        if path.is_file():
            self.zitadel_service_pat = path.read_text(encoding="utf-8").strip()
        return self


settings = Settings()
