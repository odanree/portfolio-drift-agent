"""Core data shapes used across adapters, analyzer, and report."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Project:
    """A portfolio project record. Source of truth varies by adapter
    (Beacon API, JSON file, Notion, etc.) but the shape stays the same."""

    id: str
    name: str
    description: str | None
    outcome: str | None
    tech_stack: list[str] = field(default_factory=list)
    url: str | None = None
    start_date: str | None = None
    end_date: str | None = None


@dataclass
class GitHubSnapshot:
    """Live data pulled from a GitHub repo at audit time."""

    owner: str
    repo: str
    canonical_url: str
    description: str | None
    topics: list[str]
    languages: dict[str, int]
    pushed_at: str | None
    stargazers: int
    readme_excerpt: str
    recent_commit_messages: list[str]
    days_since_last_commit: int | None


@dataclass
class DriftReport:
    """Structured output of the analyzer for a single project."""

    project_id: str
    project_name: str
    is_stale: bool
    description_suggestion: str | None = None
    outcome_suggestion: str | None = None
    tech_stack_additions: list[str] = field(default_factory=list)
    tech_stack_removals: list[str] = field(default_factory=list)
    canonical_url: str | None = None
    notes: str = ""

    @property
    def has_changes(self) -> bool:
        return bool(
            self.description_suggestion
            or self.outcome_suggestion
            or self.tech_stack_additions
            or self.tech_stack_removals
            or self.canonical_url
            or self.is_stale
        )
