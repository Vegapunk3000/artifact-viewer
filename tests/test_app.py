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

        direct = client.get(f"/a/{artifact_id}")
        assert direct.status_code == 200
        assert direct.text == payload["html"]
        assert "<iframe" not in direct.text
        assert "sandbox allow-scripts allow-forms allow-modals allow-downloads" in direct.headers["content-security-policy"]
        assert "frame-ancestors 'none'" in direct.headers["content-security-policy"]

        preview = client.get(f"/preview/{artifact_id}")
        assert preview.status_code == 200
        assert f"/content/{artifact_id}" in preview.text
        assert 'sandbox="allow-scripts allow-forms allow-modals allow-downloads"' in preview.text
        assert "allow-same-origin" not in preview.text

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


def test_named_artifact_updates_in_place_and_preserves_immutable_versions(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    auth = {"Authorization": "Bearer test-token"}
    with client:
        first = client.post(
            "/api/artifacts",
            headers=auth,
            json={"title": "First", "html": "<h1>first</h1>", "name": "little-helpers"},
        )
        assert first.status_code == 201
        first_data = first.json()
        assert first_data["names"] == ["little-helpers"]
        assert first_data["named_urls"] == ["https://artifacts.example.test/named/little-helpers"]
        first_id = first_data["id"]

        named = client.get("/named/little-helpers")
        assert named.status_code == 200
        assert named.text == "<h1>first</h1>"
        assert named.headers["cache-control"] == "no-cache"

        second = client.post(
            "/api/artifacts",
            headers=auth,
            json={"title": "Second", "html": "<h1>second</h1>", "name": "LITTLE-HELPERS"},
        )
        assert second.status_code == 201
        second_data = second.json()
        assert second_data["id"] != first_id

        assert client.get("/named/little-helpers").text == "<h1>second</h1>"
        assert client.get(f"/a/{first_id}").text == "<h1>first</h1>"

        names = client.get("/api/names", headers=auth)
        assert names.status_code == 200
        assert names.json()["names"][0]["artifact_id"] == second_data["id"]

        assert client.delete("/api/names/little-helpers", headers=auth).status_code == 204
        assert client.get("/named/little-helpers").status_code == 404
        assert client.get(f"/a/{second_data['id']}").status_code == 200


def test_named_artifact_rejects_invalid_or_reserved_names(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    auth = {"Authorization": "Bearer test-token"}
    with client:
        for name in ["Bad Name", "../secret", "api", "a", "-starts-with-dash", "ends-with-dash-"]:
            response = client.post(
                "/api/artifacts",
                headers=auth,
                json={"title": "Invalid", "html": "<p>x</p>", "name": name},
            )
            assert response.status_code == 422, name


def test_deleting_artifact_releases_its_name(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    auth = {"Authorization": "Bearer test-token"}
    with client:
        created = client.post(
            "/api/artifacts",
            headers=auth,
            json={"title": "Named", "html": "<p>x</p>", "name": "temporary"},
        ).json()
        assert client.delete(f"/api/artifacts/{created['id']}", headers=auth).status_code == 204
        assert client.get("/named/temporary").status_code == 404
