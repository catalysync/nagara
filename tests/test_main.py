import pytest
from fastapi.testclient import TestClient

from nagara.main import app

client = TestClient(app)


def test_root_returns_hello_world():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"hello": "world"}


def test_create_app_refuses_wildcard_cors_with_credentials(monkeypatch):
    """Browsers silently strip Access-Control-Allow-Origin: * when credentials
    are enabled; the boot-time guard prevents shipping a broken config."""
    import nagara.main as main_mod

    monkeypatch.setattr(main_mod.settings, "CORS_ALLOW_CREDENTIALS", True)
    monkeypatch.setattr(main_mod.settings, "CORS_ORIGINS", ["*"])
    with pytest.raises(RuntimeError, match="wildcard"):
        main_mod.create_app()
