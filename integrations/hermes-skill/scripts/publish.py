#!/usr/bin/env python3
"""Publish one self-contained HTML file when the Hermes plugin tool is unavailable."""
from __future__ import annotations

import argparse
import json
import os
import urllib.request
from pathlib import Path

MAX_BYTES = 2_000_000


def config() -> tuple[str, str]:
    home = Path(os.getenv("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
    values: dict[str, str] = {}
    for raw in (home / "secrets" / "artifact-viewer.env").read_text(encoding="utf-8").splitlines():
        if "=" in raw and not raw.lstrip().startswith("#"):
            key, value = raw.split("=", 1)
            values[key.strip()] = value.strip()
    return values["ARTIFACT_VIEWER_URL"].rstrip("/"), values["ARTIFACT_VIEWER_TOKEN"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--title")
    parser.add_argument("--description", default="")
    parser.add_argument("--tag", action="append", default=[])
    parser.add_argument("--source", default="hermes")
    parser.add_argument("--name", help="stable lowercase hyphenated artifact name")
    args = parser.parse_args()
    path = Path(args.path).expanduser().resolve()
    if not path.is_file() or path.suffix.lower() not in {".html", ".htm"}:
        raise SystemExit("path must be an existing .html or .htm file")
    if path.stat().st_size > MAX_BYTES:
        raise SystemExit(f"artifact exceeds {MAX_BYTES} bytes")
    url, token = config()
    payload = json.dumps({
        "title": args.title or path.stem.replace("-", " ").title(),
        "description": args.description,
        "html": path.read_text(encoding="utf-8"),
        "tags": args.tag,
        "source": args.source,
        "name": args.name,
    }).encode("utf-8")
    request = urllib.request.Request(
        url + "/api/artifacts",
        data=payload,
        method="POST",
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)
    print(json.dumps({
        "published": True,
        "immutable_url": result["url"],
        "named_url": (result.get("named_urls") or [None])[0],
        "name": (result.get("names") or [None])[0],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
