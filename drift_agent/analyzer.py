"""LLM-driven drift analyzer — compares Project record to GitHubSnapshot."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from drift_agent.models import DriftReport, GitHubSnapshot, Project

log = logging.getLogger(__name__)

STALE_DAYS = int(os.getenv("DRIFT_STALE_DAYS", "180"))
DEFAULT_MODEL = os.getenv("DRIFT_MODEL", "claude-sonnet-4-6")

ANALYZER_SYSTEM = (
    "You audit a portfolio project record against its actual GitHub repo and propose "
    "grounded edits. You output strict JSON only — no prose, no markdown fences. Every "
    "suggestion must cite specific evidence (a README line, a commit message, a language "
    "byte share). Refuse to invent metrics. If the existing record already matches reality, "
    "return empty suggestions."
)


def _build_user_prompt(p: Project, gh: GitHubSnapshot) -> str:
    lang_summary = ", ".join(
        f"{k} ({v}B)" for k, v in sorted(gh.languages.items(), key=lambda x: -x[1])[:8]
    )
    return (
        f"PORTFOLIO PROJECT RECORD\n"
        f"  name: {p.name}\n"
        f"  url: {p.url or '(none)'}\n"
        f"  description: {p.description or '(empty)'}\n"
        f"  outcome: {p.outcome or '(empty)'}\n"
        f"  tech_stack: {', '.join(p.tech_stack) or '(empty)'}\n"
        f"  start_date: {p.start_date or '-'}  end_date: {p.end_date or '-'}\n\n"
        f"GITHUB SNAPSHOT (live data)\n"
        f"  canonical_url: {gh.canonical_url}\n"
        f"  repo description: {gh.description or '(none)'}\n"
        f"  topics: {', '.join(gh.topics) or '(none)'}\n"
        f"  primary languages (by bytes): {lang_summary or '(none)'}\n"
        f"  last pushed: {gh.pushed_at or 'unknown'} ({gh.days_since_last_commit} days ago)\n"
        f"  recent commit messages:\n"
        + "\n".join(f"    - {m}" for m in gh.recent_commit_messages[:10])
        + "\n\n"
        f"README EXCERPT (first 4000 chars)\n```\n{gh.readme_excerpt}\n```\n\n"
        "Output strict JSON only, matching this schema:\n"
        "{\n"
        '  "description_suggestion": null | "...replacement description grounded in README/topics...",\n'
        '  "outcome_suggestion": null | "...replacement outcome with citable metric...",\n'
        '  "tech_stack_additions": ["tech the repo clearly uses but record is missing"],\n'
        '  "tech_stack_removals": ["tech in record that the repo no longer uses"],\n'
        '  "canonical_url": null | "url" (only if portfolio url differs from canonical_url above),\n'
        '  "notes": "1-3 sentence summary of why these suggestions"\n'
        "}\n"
        "Rules:\n"
        "- If existing description already accurately reflects the repo, set description_suggestion to null.\n"
        "- Same for outcome — only suggest if README/commits reveal a new headline metric.\n"
        "- Tech stack changes: only add what's clearly in evidence. Only remove what's no longer mentioned anywhere.\n"
        "- NEVER invent metrics. Outcome suggestions must cite a number visible in README or commits.\n"
        "- If everything matches, return all-null with notes='no drift detected'.\n"
    )


def analyze(
    anthropic_client, p: Project, gh: GitHubSnapshot, model: str = DEFAULT_MODEL
) -> DriftReport:
    """Score a single project's drift. Always returns a DriftReport; on error
    the report carries an explanatory note and no suggestions."""
    is_stale = (gh.days_since_last_commit or 0) > STALE_DAYS
    report = DriftReport(project_id=p.id, project_name=p.name, is_stale=is_stale)

    try:
        resp = anthropic_client.messages.create(
            model=model,
            max_tokens=900,
            system=ANALYZER_SYSTEM,
            messages=[{"role": "user", "content": _build_user_prompt(p, gh)}],
        )
        raw = "".join(b.text for b in resp.content if hasattr(b, "text")).strip()
        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data: dict[str, Any] = json.loads(raw)

        report.description_suggestion = data.get("description_suggestion") or None
        report.outcome_suggestion = data.get("outcome_suggestion") or None
        report.tech_stack_additions = list(data.get("tech_stack_additions") or [])
        report.tech_stack_removals = list(data.get("tech_stack_removals") or [])
        report.canonical_url = data.get("canonical_url") or None
        report.notes = (data.get("notes") or "").strip()
    except Exception:
        log.exception("analyzer failed for %s", p.name)
        report.notes = "(analyzer error — see logs)"

    return report
