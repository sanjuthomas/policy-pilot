from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8095
    api_prefix: str = "/api/v1"

    mongodb_uri: str = "mongodb://localhost:27017/?replicaSet=rs0"
    mongodb_database: str = "ssi_sequences"
    mongodb_collection: str = "sequence_counters"


settings = Settings()
