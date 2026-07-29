import importlib
import os
from pathlib import Path

from fastapi.testclient import TestClient


def make_client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ARTIFACT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ARTIFACT_PUBLIC_BASE_URL", "https://artifacts.example.test")
    monkeypatch.setenv("ARTIFACT_PUBLISH_TOKEN", "test-token")
    import app
    importlib.reload(app)
    return TestClient(app.app), app


def test_publish_requires_token(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    with client:
        response = client.post("/api/artifacts", json={"title": "Nope", "html": "<h1>x</h1>"})
    assert response.status_code == 401


def test_publish_view_sandbox_and_download(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    payload = {
        "title": "Interactive chart",
        "description": "A test artifact",
        "html": "<!doctype html><h1>Hello</h1><script>document.body.dataset.ok='yes'</script>",
        "tags": ["Test", "test", " chart "],
    }
    with client:
        created = client.post("/api/artifacts", headers={"Authorization": "Bearer test-token"}, json=payload)
        assert created.status_code == 201
        data = created.json()
        assert data["url"].startswith("https://artifacts.example.test/a/")
        assert data["tags"] == ["test", "chart"]
        artifact_id = data["id"]

        viewer = client.get(f"/a/{artifact_id}")
        assert viewer.status_code == 200
        assert 'sandbox="allow-scripts allow-forms allow-modals allow-downloads"' in viewer.text
        assert "allow-same-origin" not in viewer.text
        assert payload["html"] not in viewer.text

        content = client.get(f"/content/{artifact_id}")
        assert content.text == payload["html"]
        assert "base-uri 'none'" in content.headers["content-security-policy"]

        download = client.get(f"/download/{artifact_id}")
        assert download.status_code == 200
        assert download.headers["content-disposition"].endswith('interactive-chart.html"')


def test_list_and_delete_are_authenticated(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    auth = {"Authorization": "Bearer test-token"}
    with client:
        artifact_id = client.post("/api/artifacts", headers=auth, json={"title": "One", "html": "<p>one</p>"}).json()["id"]
        listed = client.get("/api/artifacts", headers=auth)
        assert listed.status_code == 200
        assert listed.json()["artifacts"][0]["id"] == artifact_id
        assert client.get("/api/artifacts").status_code == 401
        assert client.delete(f"/api/artifacts/{artifact_id}", headers=auth).status_code == 204
        assert client.get(f"/a/{artifact_id}").status_code == 404
