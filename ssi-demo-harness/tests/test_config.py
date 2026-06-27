from __future__ import annotations

from pathlib import Path

from harness.config import Settings


def test_settings_load_service_pat_from_file(tmp_path: Path) -> None:
    pat_file = tmp_path / "login.pat"
    pat_file.write_text("  secret-pat  \n", encoding="utf-8")
    settings = Settings(zitadel_service_pat_file=pat_file)
    assert settings.zitadel_service_pat == "secret-pat"


def test_settings_defaults() -> None:
    settings = Settings()
    assert settings.port == 8091
    assert settings.ilm_api_prefix == "/api/v1"
