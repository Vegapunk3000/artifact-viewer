from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from hermes_constants import get_hermes_home

MAX_BYTES = 2_000_000


def _hermes_home() -> Path:
    return Path(get_hermes_home())


def _configured() -> bool:
    return (_hermes_home() / "secrets" / "artifact-viewer.env").is_file()


def _load_config() -> tuple[str, str]:
    path = _hermes_home() / "secrets" / "artifact-viewer.env"
    if not path.is_file():
        raise RuntimeError(f"Artifact Viewer credentials are missing: {path}")
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    url = values.get("ARTIFACT_VIEWER_URL", "").rstrip("/")
    token = values.get("ARTIFACT_VIEWER_TOKEN", "")
    if not url or not token:
        raise RuntimeError("Artifact Viewer URL or token is not configured")
    return url, token


def _request(method: str, path: str, *, payload: dict[str, Any] | None = None) -> Any:
    base_url, token = _load_config()
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        f"{base_url}{path}",
        data=body,
        method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            return json.loads(raw) if raw else {"ok": True}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"Artifact Viewer returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Artifact Viewer is unreachable: {exc.reason}") from exc


def artifact_viewer(args: dict[str, Any], **_: Any) -> str:
    action = args.get("action", "publish")
    if action == "publish":
        raw_path = str(args.get("path", "")).strip()
        if not raw_path:
            raise ValueError("path is required for publish")
        path = Path(raw_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Artifact file not found: {path}")
        if path.suffix.lower() not in {".html", ".htm"}:
            raise ValueError("Only .html and .htm files can be published")
        size = path.stat().st_size
        if size > MAX_BYTES:
            raise ValueError(f"Artifact is {size} bytes; maximum is {MAX_BYTES}")
        html = path.read_text(encoding="utf-8")
        title = str(args.get("title") or path.stem.replace("-", " ").replace("_", " ").title()).strip()
        result = _request(
            "POST",
            "/api/artifacts",
            payload={
                "title": title,
                "description": str(args.get("description", "")).strip(),
                "html": html,
                "tags": args.get("tags") or [],
                "source": str(args.get("source", "hermes")).strip() or "hermes",
                "name": str(args.get("name", "")).strip() or None,
            },
        )
        return json.dumps({"published": True, **result}, ensure_ascii=False)

    if action == "list":
        limit = max(1, min(int(args.get("limit", 20)), 200))
        return json.dumps(_request("GET", f"/api/artifacts?limit={limit}"), ensure_ascii=False)

    if action == "names":
        limit = max(1, min(int(args.get("limit", 200)), 200))
        return json.dumps(_request("GET", f"/api/names?limit={limit}"), ensure_ascii=False)

    if action == "release_name":
        name = str(args.get("name", "")).strip()
        if not name:
            raise ValueError("name is required for release_name")
        _request("DELETE", f"/api/names/{name}")
        return json.dumps({"released": True, "name": name}, ensure_ascii=False)

    if action == "delete":
        artifact_id = str(args.get("artifact_id", "")).strip()
        if not artifact_id:
            raise ValueError("artifact_id is required for delete")
        result = _request("DELETE", f"/api/artifacts/{artifact_id}")
        return json.dumps({"deleted": True, "artifact_id": artifact_id, **result}, ensure_ascii=False)

    raise ValueError(f"Unknown action: {action}")


SCHEMA = {
    "name": "artifact_viewer",
    "description": "Publish a self-contained HTML file to the sandboxed Artifact Viewer and get a shareable HTTPS URL; list or delete prior artifacts.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["publish", "list", "names", "release_name", "delete"], "default": "publish"},
            "path": {"type": "string", "description": "Absolute path to a self-contained .html/.htm file for publish."},
            "title": {"type": "string", "description": "Human-readable artifact title."},
            "description": {"type": "string", "description": "Short description shown above the artifact."},
            "tags": {"type": "array", "items": {"type": "string"}},
            "source": {"type": "string", "description": "Origin such as german-learning or finance."},
            "name": {"type": "string", "description": "Optional stable lowercase name. Republishing with the same name moves that named URL to the new immutable version."},
            "artifact_id": {"type": "string", "description": "Artifact ID for delete."},
            "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 20},
        },
        "required": ["action"],
    },
}


def register(ctx) -> None:
    ctx.register_tool(
        name="artifact_viewer",
        toolset="artifact_viewer",
        schema=SCHEMA,
        handler=artifact_viewer,
        check_fn=_configured,
        description="Publish and manage sandboxed interactive HTML artifacts.",
        emoji="🧩",
    )
