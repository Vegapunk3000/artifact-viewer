# Artifact Viewer

A small self-hosted service for publishing self-contained interactive HTML artifacts from Hermes and sharing them as browser links in Discord or other chat platforms.

## What it does

- authenticated publish/list/delete API;
- unlisted, high-entropy public links;
- SQLite metadata and content persistence;
- responsive viewer shell;
- iframe sandbox without `allow-same-origin` or top-navigation;
- Content Security Policy for viewer and artifact documents;
- HTML download endpoint;
- Docker health check and HTTPS behind Traefik;
- Hermes plugin tool plus reusable skill.

## Runtime

- Dokploy project: `Artifact Viewer`
- Dokploy application: `Viewer` (`artifact-viewer-onszu6`)
- Source: `https://github.com/Vegapunk3000/artifact-viewer`
- Persistent data: `/srv/artifact-viewer/artifacts.sqlite3`
- Public origin: `https://artifacts.timi.click`
- Hermes credentials: `~/.hermes/secrets/artifact-viewer.env` (`0600`)
- Installed plugin: `~/.hermes/plugins/artifact-viewer`
- Installed skill: `~/.hermes/skills/productivity/artifact-viewer`

## Development

```bash
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt pytest httpx
.venv/bin/python -m pytest -q
docker build -t artifact-viewer:1.0.2 .
```

## API

`POST /api/artifacts` requires `Authorization: Bearer …` and accepts `title`, `description`, `html`, `tags`, and `source`. It returns an immutable artifact ID and viewer URL.

`GET /api/artifacts` and `DELETE /api/artifacts/{id}` require the same bearer token. Viewer links under `/a/{id}` are intentionally unlisted rather than login-gated.

## Security model

The publish API token never enters an artifact or browser. Artifact documents are shown in an iframe sandbox with scripts allowed but no same-origin privilege. Links are bearer-like: anyone with the unlisted URL can view the artifact, so private keys, credentials, raw environment files, and unnecessary personal data must never be published.

A custom `artifacts.timi.click` DNS record can replace the `sslip.io` hostname later without changing the service architecture.
