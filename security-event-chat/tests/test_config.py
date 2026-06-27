from __future__ import annotations

from pathlib import Path

from chat_application.config import Settings, settings


class TestSettings:
    def test_default_values(self) -> None:
        s = Settings()
        assert s.host == "0.0.0.0"
        assert s.port == 8092
        assert s.retrieval_limit == 15
        assert s.rrf_k == 60
        assert s.max_context_hits == 10

    def test_graph_schema_path(self) -> None:
        s = Settings(graph_model_dir="/tmp/graph-model")
        assert s.graph_schema_path == Path("/tmp/graph-model/relationships.cypher")

    def test_env_override(self, monkeypatch) -> None:
        monkeypatch.setenv("PORT", "9999")
        monkeypatch.setenv("RETRIEVAL_LIMIT", "25")
        s = Settings()
        assert s.port == 9999
        assert s.retrieval_limit == 25

    def test_module_level_settings_instance(self) -> None:
        assert isinstance(settings, Settings)
        assert settings.qdrant_collection == "ssi_search_index"
