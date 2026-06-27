from __future__ import annotations

from pathlib import Path

from ps.config import Settings


def test_load_service_pat_from_file(tmp_path: Path) -> None:
    pat_file = tmp_path / "pat.txt"
    pat_file.write_text("  secret-pat-token  ", encoding="utf-8")
    settings = Settings(zitadel_service_pat_file=pat_file)
    assert settings.zitadel_service_pat == "secret-pat-token"


def test_skips_pat_file_when_pat_already_set(tmp_path: Path) -> None:
    pat_file = tmp_path / "pat.txt"
    pat_file.write_text("from-file", encoding="utf-8")
    settings = Settings(zitadel_service_pat="existing", zitadel_service_pat_file=pat_file)
    assert settings.zitadel_service_pat == "existing"


def test_skips_missing_pat_file(tmp_path: Path) -> None:
    settings = Settings(zitadel_service_pat_file=tmp_path / "missing.txt")
    assert settings.zitadel_service_pat is None
