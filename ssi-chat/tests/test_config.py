from __future__ import annotations

from chat_application.config import Settings, settings


class TestSettings:
    def test_default_values(self) -> None:
        s = Settings()
        assert s.host == "0.0.0.0"
        assert s.port == 8092
        assert s.retrieval_limit == 15
        assert s.rrf_k == 60
        assert s.max_context_hits == 10

    def test_env_override(self, monkeypatch) -> None:
        monkeypatch.setenv("PORT", "9999")
        monkeypatch.setenv("RETRIEVAL_LIMIT", "25")
        s = Settings()
        assert s.port == 9999
        assert s.retrieval_limit == 25

    def test_vertex_defaults(self) -> None:
        s = Settings()
        assert s.gcp_project_id == "rag-demos-501323"
        assert s.vertex_gemini_model == "gemini-2.5-flash"
        assert s.embedding_dimension == 768

    def test_module_level_settings_instance(self) -> None:
        assert isinstance(settings, Settings)
        assert settings.multimodal_vector_index == "multimodal_embedding"
