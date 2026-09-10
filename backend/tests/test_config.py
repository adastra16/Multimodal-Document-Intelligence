"""Settings load from the environment and never from hardcoded secrets."""

from pytest import MonkeyPatch

from app.core.config import Settings, get_settings


def test_settings_read_env_overrides(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    get_settings.cache_clear()
    settings = Settings()
    assert settings.app_env == "test"
    assert settings.llm_model == "test-model"
    assert settings.llm_api_key == ""


def test_cors_origins_parse_csv() -> None:
    settings = Settings(cors_origins="http://a.example, http://b.example")
    assert settings.cors_origin_list == ["http://a.example", "http://b.example"]
