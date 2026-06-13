"""Fetch live data from a GitHub repo to compare against a portfolio record."""

from __future__ import annotations

import base64
import logging
import os
import re
from datetime import datetime, timezone

import httpx

from drift_agent.models import GitHubSnapshot

log = logging.getLogger(__name__)

UTC = timezone.utc
GITHUB_API = "https://api.github.com"
GITHUB_URL_RE = re.compile(r"github\.com/([^/]+)/([^/?#]+)", re.IGNORECASE)
README_EXCERPT_CHARS = 4000


def build_client() -> httpx.Client:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
        log.info("GitHub: authenticated (rate limit 5000/hr)")
    else:
        log.warning("GitHub: unauthenticated (rate limit 60/hr) — set GITHUB_TOKEN for headroom")
    return httpx.Client(base_url=GITHUB_API, headers=headers, timeout=20.0)


def parse_owner_repo(url: str) -> tuple[str, str] | None:
    m = GITHUB_URL_RE.search(url)
    if not m:
        return None
    owner, repo = m.group(1), m.group(2)
    return owner, repo.removesuffix(".git").rstrip("/")


def fetch_snapshot(gh: httpx.Client, owner: str, repo: str) -> GitHubSnapshot | None:
    try:
        meta = gh.get(f"/repos/{owner}/{repo}")
        if meta.status_code == 404:
            log.warning("GitHub 404: %s/%s", owner, repo)
            return None
        meta.raise_for_status()
        m = meta.json()

        languages: dict[str, int] = {}
        lang_resp = gh.get(f"/repos/{owner}/{repo}/languages")
        if lang_resp.status_code == 200:
            languages = lang_resp.json()

        readme_excerpt = ""
        readme_resp = gh.get(f"/repos/{owner}/{repo}/readme")
        if readme_resp.status_code == 200:
            try:
                body = readme_resp.json()
                raw = base64.b64decode(body.get("content", "")).decode("utf-8", errors="replace")
                readme_excerpt = raw[:README_EXCERPT_CHARS]
            except Exception:
                log.exception("readme decode failed for %s/%s", owner, repo)

        commits_resp = gh.get(f"/repos/{owner}/{repo}/commits?per_page=15")
        commit_messages: list[str] = []
        if commits_resp.status_code == 200:
            for c in commits_resp.json():
                msg = (c.get("commit", {}).get("message") or "").split("\n", 1)[0]
                if msg:
                    commit_messages.append(msg[:140])

        pushed_at = m.get("pushed_at")
        days_since = None
        if pushed_at:
            try:
                dt = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
                days_since = (datetime.now(UTC) - dt).days
            except ValueError:
                pass

        return GitHubSnapshot(
            owner=owner,
            repo=repo,
            canonical_url=m.get("html_url") or f"https://github.com/{owner}/{repo}",
            description=m.get("description"),
            topics=list(m.get("topics") or []),
            languages=languages,
            pushed_at=pushed_at,
            stargazers=int(m.get("stargazers_count") or 0),
            readme_excerpt=readme_excerpt,
            recent_commit_messages=commit_messages,
            days_since_last_commit=days_since,
        )
    except httpx.HTTPError:
        log.exception("github fetch failed for %s/%s", owner, repo)
        return None
