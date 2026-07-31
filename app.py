from __future__ import annotations

import hashlib
import hmac
import html as html_lib
import json
import os
import re
import secrets
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field, field_validator

DATA_DIR = Path(os.getenv("ARTIFACT_DATA_DIR", "/data"))
DB_PATH = DATA_DIR / "artifacts.sqlite3"
PUBLIC_BASE_URL = os.getenv("ARTIFACT_PUBLIC_BASE_URL", "http://localhost:8080").rstrip("/")
PUBLISH_TOKEN = os.getenv("ARTIFACT_PUBLISH_TOKEN", "").strip()
PUBLISH_TOKEN_FILE = os.getenv("ARTIFACT_PUBLISH_TOKEN_FILE", "").strip()
if not PUBLISH_TOKEN and PUBLISH_TOKEN_FILE:
    token_path = Path(PUBLISH_TOKEN_FILE)
    if token_path.is_file():
        PUBLISH_TOKEN = token_path.read_text(encoding="utf-8").strip()
MAX_HTML_BYTES = int(os.getenv("ARTIFACT_MAX_HTML_BYTES", "2000000"))
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+){0,7}$")
RESERVED_NAMES = {"api", "a", "named", "preview", "content", "download", "health", "docs", "redoc", "openapi"}


def validate_name(value: str) -> str:
    name = value.strip().lower()
    if len(name) > 64 or not NAME_RE.fullmatch(name) or name in RESERVED_NAMES:
        raise ValueError("name must be 1-64 lowercase letters/numbers separated by single hyphens")
    return name



@asynccontextmanager
async def lifespan(_: FastAPI):
    if not PUBLISH_TOKEN:
        raise RuntimeError("ARTIFACT_PUBLISH_TOKEN must be configured")
    init_db()
    yield


app = FastAPI(
    title="Artifact Viewer",
    version="1.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)


class ArtifactCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=500)
    html: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list, max_length=20)
    source: str = Field(default="hermes", max_length=100)
    name: str | None = Field(default=None, max_length=64)

    @field_validator("html")
    @classmethod
    def html_size(cls, value: str) -> str:
        if len(value.encode("utf-8")) > MAX_HTML_BYTES:
            raise ValueError(f"HTML exceeds {MAX_HTML_BYTES} bytes")
        return value

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        return validate_name(value) if value is not None else None

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            tag = value.strip().lower()[:40]
            if tag and tag not in cleaned:
                cleaned.append(tag)
        return cleaned


class NameAssignment(BaseModel):
    artifact_id: str = Field(min_length=1, max_length=100)


@contextmanager
def db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_db() -> None:
    with db() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS artifacts (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                html TEXT NOT NULL,
                tags TEXT NOT NULL,
                source TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL,
                views INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_artifacts_created_at ON artifacts(created_at DESC)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS artifact_names (
                name TEXT PRIMARY KEY,
                artifact_id TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_artifact_names_artifact_id ON artifact_names(artifact_id)"
        )


def require_token(authorization: Annotated[str | None, Header()] = None) -> None:
    expected = f"Bearer {PUBLISH_TOKEN}"
    if not authorization or not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid publish token")


def get_artifact(artifact_id: str) -> sqlite3.Row:
    with db() as connection:
        row = connection.execute("SELECT * FROM artifacts WHERE id = ?", (artifact_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return row


def names_for_artifact(artifact_id: str) -> list[str]:
    with db() as connection:
        rows = connection.execute(
            "SELECT name FROM artifact_names WHERE artifact_id = ? ORDER BY name",
            (artifact_id,),
        ).fetchall()
    return [row["name"] for row in rows]


def metadata(row: sqlite3.Row) -> dict:
    names = names_for_artifact(row["id"])
    result = {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "tags": json.loads(row["tags"]),
        "source": row["source"],
        "sha256": row["sha256"],
        "created_at": row["created_at"],
        "views": row["views"],
        "url": f"{PUBLIC_BASE_URL}/a/{row['id']}",
        "download_url": f"{PUBLIC_BASE_URL}/download/{row['id']}",
    }
    if names:
        result["names"] = names
        result["named_urls"] = [f"{PUBLIC_BASE_URL}/n/{name}" for name in names]
    return result


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "artifact-viewer", "version": app.version}


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    body = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Artifact Viewer</title><style>
:root{color-scheme:dark;font-family:Inter,ui-sans-serif,system-ui,sans-serif;background:#0a0c10;color:#f3f5f7}*{box-sizing:border-box}body{min-height:100vh;margin:0;display:grid;place-items:center;background:radial-gradient(circle at 20% 15%,#243650 0,transparent 35%),radial-gradient(circle at 82% 80%,#302348 0,transparent 32%),#090b0f}.card{width:min(92vw,680px);padding:clamp(28px,6vw,64px);border:1px solid #ffffff1c;border-radius:28px;background:#11151ccc;box-shadow:0 30px 90px #0009;backdrop-filter:blur(18px)}.mark{display:inline-grid;place-items:center;width:52px;height:52px;border-radius:16px;background:linear-gradient(135deg,#72e2ff,#aa7dff);color:#080a0d;font-weight:900;font-size:25px}h1{font-size:clamp(34px,7vw,64px);line-height:.95;letter-spacing:-.055em;margin:24px 0 18px}p{font-size:18px;line-height:1.65;color:#b8c0cc;margin:0}.status{display:flex;gap:10px;align-items:center;margin-top:28px;color:#7de6ae;font-size:14px}.dot{width:9px;height:9px;border-radius:50%;background:#53e39a;box-shadow:0 0 18px #53e39a}</style></head><body><main class="card"><span class="mark">A</span><h1>Artifact Viewer</h1><p>Secure, sandboxed browser-native artifacts generated by Shaka. Artifact links are unlisted and individually addressable.</p><div class="status"><span class="dot"></span>Service operational</div></main></body></html>"""
    return HTMLResponse(body, headers={"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline';", "X-Content-Type-Options": "nosniff"})


@app.post("/api/artifacts", status_code=201, dependencies=[Depends(require_token)])
def create_artifact(payload: ArtifactCreate) -> JSONResponse:
    artifact_id = secrets.token_urlsafe(16)
    created_at = datetime.now(timezone.utc).isoformat()
    digest = hashlib.sha256(payload.html.encode("utf-8")).hexdigest()
    with db() as connection:
        connection.execute(
            "INSERT INTO artifacts (id,title,description,html,tags,source,sha256,created_at) VALUES (?,?,?,?,?,?,?,?)",
            (artifact_id, payload.title.strip(), payload.description.strip(), payload.html, json.dumps(payload.tags), payload.source.strip(), digest, created_at),
        )
        if payload.name:
            connection.execute(
                "INSERT INTO artifact_names (name,artifact_id,updated_at) VALUES (?,?,?) "
                "ON CONFLICT(name) DO UPDATE SET artifact_id = excluded.artifact_id, updated_at = excluded.updated_at",
                (payload.name, artifact_id, created_at),
            )
        row = connection.execute("SELECT * FROM artifacts WHERE id = ?", (artifact_id,)).fetchone()
    return JSONResponse(metadata(row), status_code=201)


@app.get("/api/artifacts", dependencies=[Depends(require_token)])
def list_artifacts(limit: int = 50) -> dict:
    limit = max(1, min(limit, 200))
    with db() as connection:
        rows = connection.execute("SELECT * FROM artifacts ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return {"artifacts": [metadata(row) for row in rows]}


@app.get("/api/names", dependencies=[Depends(require_token)])
def list_names(limit: int = 200) -> dict:
    limit = max(1, min(limit, 200))
    with db() as connection:
        rows = connection.execute(
            "SELECT n.name, n.updated_at, a.id, a.title, a.sha256 "
            "FROM artifact_names n JOIN artifacts a ON a.id = n.artifact_id "
            "ORDER BY n.name LIMIT ?",
            (limit,),
        ).fetchall()
    return {
        "names": [
            {
                "name": row["name"],
                "title": row["title"],
                "artifact_id": row["id"],
                "sha256": row["sha256"],
                "updated_at": row["updated_at"],
                "url": f"{PUBLIC_BASE_URL}/n/{row['name']}",
                "immutable_url": f"{PUBLIC_BASE_URL}/a/{row['id']}",
            }
            for row in rows
        ]
    }


@app.put("/api/names/{name}", dependencies=[Depends(require_token)])
def assign_name(name: str, payload: NameAssignment) -> JSONResponse:
    try:
        normalized = validate_name(name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    updated_at = datetime.now(timezone.utc).isoformat()
    with db() as connection:
        row = connection.execute("SELECT * FROM artifacts WHERE id = ?", (payload.artifact_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Artifact not found")
        connection.execute(
            "INSERT INTO artifact_names (name,artifact_id,updated_at) VALUES (?,?,?) "
            "ON CONFLICT(name) DO UPDATE SET artifact_id = excluded.artifact_id, updated_at = excluded.updated_at",
            (normalized, payload.artifact_id, updated_at),
        )
    return JSONResponse(metadata(row))


@app.delete("/api/artifacts/{artifact_id}", status_code=204, dependencies=[Depends(require_token)])
def delete_artifact(artifact_id: str) -> Response:
    with db() as connection:
        connection.execute("DELETE FROM artifact_names WHERE artifact_id = ?", (artifact_id,))
        cursor = connection.execute("DELETE FROM artifacts WHERE id = ?", (artifact_id,))
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return Response(status_code=204)


@app.delete("/api/names/{name}", status_code=204, dependencies=[Depends(require_token)])
def release_name(name: str) -> Response:
    try:
        normalized = validate_name(name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    with db() as connection:
        cursor = connection.execute("DELETE FROM artifact_names WHERE name = ?", (normalized,))
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Named artifact not found")
    return Response(status_code=204)


def get_named_artifact(name: str) -> sqlite3.Row:
    try:
        normalized = validate_name(name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Named artifact not found") from exc
    with db() as connection:
        row = connection.execute(
            "SELECT a.* FROM artifact_names n JOIN artifacts a ON a.id = n.artifact_id WHERE n.name = ?",
            (normalized,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Named artifact not found")
    return row


def direct_artifact_response(row: sqlite3.Row, *, cache_control: str = "public, max-age=300") -> Response:
    with db() as connection:
        connection.execute("UPDATE artifacts SET views = views + 1 WHERE id = ?", (row["id"],))
    return Response(
        content=row["html"],
        media_type="text/html",
        headers={
            "Content-Security-Policy": DIRECT_ARTIFACT_CSP,
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": cache_control,
        },
    )


@app.get("/a/{artifact_id}")
def view_artifact(artifact_id: str) -> Response:
    return direct_artifact_response(get_artifact(artifact_id))


@app.get("/n/{name}")
@app.get("/named/{name}", include_in_schema=False)
def view_named_artifact(name: str) -> Response:
    return direct_artifact_response(get_named_artifact(name), cache_control="no-cache")


@app.get("/preview/{artifact_id}", response_class=HTMLResponse)
def preview_artifact(artifact_id: str, request: Request) -> HTMLResponse:
    row = get_artifact(artifact_id)
    with db() as connection:
        connection.execute("UPDATE artifacts SET views = views + 1 WHERE id = ?", (artifact_id,))
    title = html_lib.escape(row["title"])
    description = html_lib.escape(row["description"])
    tags = "".join(f'<span class="tag">{html_lib.escape(tag)}</span>' for tag in json.loads(row["tags"]))
    created = html_lib.escape(row["created_at"][:10])
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} · Artifact Viewer</title><style>
:root{{color-scheme:dark;font-family:Inter,ui-sans-serif,system-ui,sans-serif;background:#0a0c10;color:#f4f6f8}}*{{box-sizing:border-box}}body{{margin:0;background:#0a0c10}}header{{min-height:76px;padding:15px clamp(16px,3vw,34px);display:flex;gap:18px;align-items:center;border-bottom:1px solid #ffffff14;background:#0d1015dd;backdrop-filter:blur(18px);position:sticky;top:0;z-index:2}}.brand{{display:grid;place-items:center;width:40px;height:40px;flex:0 0 auto;border-radius:12px;background:linear-gradient(135deg,#72e2ff,#aa7dff);color:#090b0e;font-weight:900}}.meta{{min-width:0;flex:1}}h1{{font-size:16px;line-height:1.2;margin:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}p{{font-size:13px;color:#9da7b4;margin:5px 0 0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.actions{{display:flex;gap:8px;align-items:center}}a.button{{color:#e8edf3;text-decoration:none;border:1px solid #ffffff1c;background:#171c24;padding:9px 13px;border-radius:10px;font-size:13px}}.tags{{display:flex;gap:6px}}.tag{{padding:5px 8px;border-radius:99px;background:#ffffff0d;color:#aeb7c3;font-size:11px}}main{{height:calc(100vh - 76px);padding:clamp(8px,1.4vw,18px)}}iframe{{display:block;width:100%;height:100%;border:1px solid #ffffff17;border-radius:14px;background:white;box-shadow:0 20px 60px #0008}}@media(max-width:700px){{header{{min-height:68px}}main{{height:calc(100vh - 68px);padding:0}}iframe{{border:0;border-radius:0}}.tags,.description{{display:none}}a.button{{padding:8px 10px}}}}</style></head><body><header><div class="brand">A</div><div class="meta"><h1>{title}</h1><p class="description">{description or 'Interactive HTML artifact'} · {created}</p></div><div class="tags">{tags}</div><div class="actions"><a class="button" href="/download/{artifact_id}">Download</a></div></header><main><iframe title="{title}" src="/content/{artifact_id}" sandbox="allow-scripts allow-forms allow-modals allow-downloads" referrerpolicy="no-referrer"></iframe></main></body></html>"""
    headers = {
        "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; frame-src 'self';",
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "no-store",
    }
    return HTMLResponse(page, headers=headers)


ARTIFACT_CSP = "; ".join([
    "default-src 'none'",
    "script-src 'unsafe-inline' https:",
    "style-src 'unsafe-inline' https:",
    "img-src data: blob: https:",
    "font-src data: https:",
    "connect-src https:",
    "media-src data: blob: https:",
    "frame-src https:",
    "form-action https:",
    "base-uri 'none'",
])

# Direct artifact pages do not have the iframe sandbox to provide the origin boundary.
# Keep equivalent restrictions at the document level and prevent re-embedding.
DIRECT_ARTIFACT_CSP = "; ".join([
    "default-src 'none'",
    "sandbox allow-scripts allow-forms allow-modals allow-downloads",
    "script-src 'unsafe-inline' https:",
    "style-src 'unsafe-inline' https:",
    "img-src data: blob: https:",
    "font-src data: https:",
    "connect-src https:",
    "media-src data: blob: https:",
    "form-action https:",
    "base-uri 'none'",
    "frame-ancestors 'none'",
])


@app.get("/content/{artifact_id}")
def artifact_content(artifact_id: str) -> Response:
    row = get_artifact(artifact_id)
    return Response(
        content=row["html"],
        media_type="text/html",
        headers={
            "Content-Security-Policy": ARTIFACT_CSP,
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "public, max-age=300",
        },
    )


@app.get("/download/{artifact_id}")
def download_artifact(artifact_id: str) -> Response:
    row = get_artifact(artifact_id)
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in row["title"].lower()).strip("-") or "artifact"
    return Response(
        content=row["html"],
        media_type="text/html",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}.html"',
            "X-Content-Type-Options": "nosniff",
        },
    )
