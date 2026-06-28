from seq.config import Settings


def test_default_settings() -> None:
    settings = Settings()
    assert settings.port == 8095
    assert settings.mongodb_database == "ssi_sequences"
    assert settings.mongodb_collection == "sequence_counters"
    assert settings.api_prefix == "/api/v1"
