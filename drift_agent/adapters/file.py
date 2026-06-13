"""File adapter — read projects from a flat JSON file.

Read-only by design. Updates would conventionally go through git rather than
an API call. Useful as a starting point if your portfolio lives in a static
file, and as a reference implementation for writing your own adapter.

Expected file shape (a list of project records):

    [
      {
        "id": "lumen",
        "name": "Lumen — Semantic Search",
        "description": "...",
        "outcome": "...",
        "tech_stack": ["Python", "FastAPI", "Qdrant"],
        "url": "https://github.com/owner/repo",
        "start_date": "2025-01-01",
        "end_date": null
      },
      ...
    ]
"""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from drift_agent.models import Project

log = logging.getLogger(__name__)


@dataclass
class FileAdapter:
    """Portfolio adapter for a flat JSON file.

    Env vars:
        DRIFT_PROJECTS_FILE   required — path to the JSON file
    """

    name: str = "file"

    def __post_init__(self) -> None:
        path = os.environ.get("DRIFT_PROJECTS_FILE")
        if not path:
            sys.exit("FileAdapter: DRIFT_PROJECTS_FILE env var not set")
        self._path = Path(path)
        if not self._path.exists():
            sys.exit(f"FileAdapter: file not found: {self._path}")

    def fetch_projects(self) -> list[Project]:
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            sys.exit(f"FileAdapter: {self._path} must contain a JSON array")
        out = [
            Project(
                id=p.get("id") or p.get("name", ""),
                name=p["name"],
                description=p.get("description"),
                outcome=p.get("outcome"),
                tech_stack=p.get("tech_stack") or [],
                url=p.get("url"),
                start_date=p.get("start_date"),
                end_date=p.get("end_date"),
            )
            for p in raw
        ]
        log.info("FileAdapter: loaded %d projects from %s", len(out), self._path)
        return out
