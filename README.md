# Artifact Viewer

A small self-hosted service for publishing self-contained interactive HTML artifacts from Hermes and sharing them as browser links in Discord or other chat platforms.

## What it does

- authenticated publish/list/delete API;
- unlisted, high-entropy public links;
- SQLite metadata and content persistence;
- responsive viewer shell (kept at `/preview/{id}` for debugging);
- direct browser-native artifact links at `/a/{id}` with document-level CSP sandboxing;
- iframe sandbox compatibility endpoint at `/content/{id}`;
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

`GET /api/artifacts` and `DELETE /api/artifacts/{id}` require the same bearer token. Public artifact links under `/a/{id}` serve the HTML directly with document-level CSP sandboxing. The legacy metadata/iframe shell is available at `/preview/{id}`; `/content/{id}` remains the raw HTML compatibility endpoint. Links are intentionally unlisted rather than login-gated.

## Security model

The publish API token never enters an artifact or browser. Direct artifact documents use a document-level CSP sandbox without same-origin privilege and cannot be embedded because `/a/{id}` sends `frame-ancestors 'none'`. The `/preview/{id}` shell uses the compatibility iframe sandbox. Links are bearer-like: anyone with the unlisted URL can view the artifact, so private keys, credentials, raw environment files, and unnecessary personal data must never be published.

A custom `artifacts.timi.click` DNS record can replace the `sslip.io` hostname later without changing the service architecture.
