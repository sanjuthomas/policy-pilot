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
    port: int = 8092

    gcp_project_id: str = "rag-demos-501323"
    gcp_region: str = "us-central1"
    vertex_embedding_model: str = "text-embedding-004"
    vertex_gemini_model: str = "gemini-2.5-flash"
    embedding_dimension: int = 768
    vertex_timeout_seconds: float = 120.0

    multimodal_vector_index: str = "multimodal_embedding"

    neo4j_uri: str = "bolt://neo4j:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "devpassword"
    graph_model_dir: str = "/app/neo4j-graph-model"

    retrieval_limit: int = 15
    rrf_k: int = 60
    max_context_hits: int = 10

    authorization_service_url: str = "http://authorization-service:8094"
    payment_service_url: str = "http://payment-service:8093"
    instruction_service_url: str = "http://instruction-service:8000"
    users_file: Path = Path("/app/zitadel-seed/users.yaml")
    zitadel_url: str = "http://zitadel-proxy"
    zitadel_host_header: str = "localhost"
    zitadel_internal_url: str | None = None
    zitadel_service_pat: str | None = None
    zitadel_service_pat_file: Path | None = None
    oidc_issuer_url: str | None = None
    oidc_internal_url: str | None = None
    oidc_audience: str | None = None
    compliance_roles: str = "COMPLIANCE_ANALYST,COMPLIANCE_OFFICER,PLATFORM_ADMIN"
    operational_roles: str = "PAYMENT_CREATOR,FUNDING_APPROVER"
    service_user_id: str = "svc-chat"
    service_user_password: str = "Password1!"

    @property
    def compliance_role_set(self) -> set[str]:
        return {role.strip() for role in self.compliance_roles.split(",") if role.strip()}

    @property
    def operational_role_set(self) -> set[str]:
        return {role.strip() for role in self.operational_roles.split(",") if role.strip()}

    @property
    def chat_role_set(self) -> set[str]:
        return self.compliance_role_set | self.operational_role_set

    @property
    def graph_schema_path(self) -> Path:
        return Path(self.graph_model_dir) / "relationships.cypher"

    @model_validator(mode="after")
    def load_service_pat_from_file(self) -> "Settings":
        if self.zitadel_service_pat or not self.zitadel_service_pat_file:
            return self
        path = self.zitadel_service_pat_file
        if path.is_file():
            self.zitadel_service_pat = path.read_text(encoding="utf-8").strip()
        return self


settings = Settings()
