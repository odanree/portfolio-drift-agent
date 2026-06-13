"""Beacon adapter — reads (and writes) projects via the Beacon REST API."""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass

import httpx

from drift_agent.models import Project

log = logging.getLogger(__name__)


@dataclass
class BeaconAdapter:
    """Portfolio adapter for Beacon job-search-pipeline.

    Auth via JWT issued by the Beacon API (extract from the browser session
    cookie or from a service account). See env vars below.

    Env vars:
        BEACON_API_URL  default: https://beacon.danhle.net
        BEACON_JWT      required
    """

    name: str = "beacon"

    def __post_init__(self) -> None:
        self._base = os.environ.get("BEACON_API_URL", "https://beacon.danhle.net").rstrip("/")
        self._jwt = os.environ.get("BEACON_JWT")
        if not self._jwt:
            sys.exit("BeaconAdapter: BEACON_JWT env var not set")
        self._client = httpx.Client(
            base_url=self._base,
            headers={"Authorization": f"Bearer {self._jwt}"},
            timeout=30.0,
        )

    def fetch_projects(self) -> list[Project]:
        r = self._client.get("/api/profile/projects")
        r.raise_for_status()
        out: list[Project] = []
        for p in r.json():
            out.append(
                Project(
                    id=p["id"],
                    name=p["name"],
                    description=p.get("description"),
                    outcome=p.get("outcome"),
                    tech_stack=p.get("tech_stack") or [],
                    url=p.get("url"),
                    start_date=p.get("start_date"),
                    end_date=p.get("end_date"),
                )
            )
        log.info("BeaconAdapter: pulled %d projects from %s", len(out), self._base)
        return out

    # ── Write-side (used by tools/apply_drift_patches.py) ──────────────────────
    # Beacon's projects API has no PATCH — apply is delete-then-recreate.

    def fetch_one_raw(self, project_id: str) -> dict | None:
        r = self._client.get("/api/profile/projects")
        r.raise_for_status()
        for p in r.json():
            if p["id"] == project_id:
                return p
        return None

    def delete_project(self, project_id: str) -> bool:
        r = self._client.delete(f"/api/profile/projects/{project_id}")
        return r.status_code in (200, 204)

    def create_project(self, payload: dict) -> str | None:
        r = self._client.post("/api/profile/projects", json=payload)
        if r.status_code not in (200, 201):
            log.error("BeaconAdapter: create failed %s — %s", r.status_code, r.text[:200])
            return None
        return r.json().get("id")
