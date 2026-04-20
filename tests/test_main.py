from fastapi.testclient import TestClient

from nagara.main import app

client = TestClient(app)


def test_root_returns_hello_world():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"hello": "world"}
