from datetime import datetime

import pytest
from meross_iot.model.credentials import MerossCloudCreds

from meross_cli.session import SessionError, load_cached_creds, load_settings, save_creds


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    for var in ("MEROSS_EMAIL", "MEROSS_PASSWORD", "MEROSS_API_URL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.chdir(tmp_path)  # pas de .env parasite du dossier courant


def test_missing_credentials_explains_where_to_put_them(tmp_path):
    with pytest.raises(SessionError, match=r"\.env"):
        load_settings(tmp_path)


def test_reads_credentials_from_config_dir_env_file(tmp_path):
    (tmp_path / ".env").write_text("MEROSS_EMAIL=moi@example.com\nMEROSS_PASSWORD=secret\n")

    settings = load_settings(tmp_path)

    assert (settings.email, settings.password) == ("moi@example.com", "secret")
    assert settings.api_url == "https://iotx-eu.meross.com"


def test_environment_variable_wins_over_env_file(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("MEROSS_EMAIL=fichier@example.com\nMEROSS_PASSWORD=secret\n")
    monkeypatch.setenv("MEROSS_EMAIL", "env@example.com")

    assert load_settings(tmp_path).email == "env@example.com"


def test_cached_credentials_roundtrip(tmp_path):
    creds = MerossCloudCreds(token="t", key="k", user_id="u", user_email="moi@example.com",
                             issued_on=datetime(2026, 1, 1), domain="https://iotx-eu.meross.com",
                             mqtt_domain="mqtt-eu.meross.com")

    save_creds(tmp_path, creds)

    assert load_cached_creds(tmp_path).token == "t"


def test_corrupted_cache_is_ignored(tmp_path):
    (tmp_path / "credentials.json").write_text("pas du json")

    assert load_cached_creds(tmp_path) is None


def test_no_cache_returns_none(tmp_path):
    assert load_cached_creds(tmp_path) is None
