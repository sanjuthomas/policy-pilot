from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8090

    kafka_enabled: bool = True
    kafka_bootstrap_servers: str = "kafka:9092"
    kafka_security_events_topic: str = "instruction-security-events"
    kafka_consumer_group: str = "security-event-qdrant-etl"
    kafka_instruction_topic: str = "ssi-instructions"
    kafka_instruction_consumer_group: str = "ssi-instruction-etl"
    kafka_payment_security_events_topic: str = "payment-security-events"
    kafka_payment_security_events_consumer_group: str = "payment-security-event-etl"
    kafka_payments_topic: str = "ssi-payments"
    kafka_payments_consumer_group: str = "payment-fact-etl"

    neo4j_uri: str = "bolt://neo4j:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "devpassword"
    graph_model_dir: str = "/app/neo4j-graph-model"

    qdrant_url: str = "http://qdrant:6333"
    qdrant_collection: str = "ssi_search_index"
    qdrant_dense_vector_name: str = "dense"
    qdrant_bm25_vector_name: str = "bm25"
    qdrant_bm25_model: str = "qdrant/bm25"

    ollama_url: str = "http://host.docker.internal:11434"
    ollama_embedding_model: str = "bge-m3:latest"
    ollama_timeout_seconds: float = 300.0
    search_default_limit: int = 10
    chat_service_url: str = "http://security-event-chat:8092"

    @property
    def graph_model_dir_path(self) -> Path:
        return Path(self.graph_model_dir)


settings = Settings()
