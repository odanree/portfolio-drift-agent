"""Portfolio adapter protocol — implement this to plug in your own source."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from drift_agent.models import Project


@runtime_checkable
class PortfolioAdapter(Protocol):
    """Read-side contract: any adapter must yield Project instances.

    Write-side (applying drift patches) is intentionally not in this protocol —
    not every backend supports mutation (e.g. a JSON file checked into git is
    fine to read but you'd update it via git, not an API). Adapters that want
    write support expose their own apply method, called by per-adapter tooling.
    """

    name: str  # e.g. "beacon", "file" — used in logs and CI artifact names

    def fetch_projects(self) -> list[Project]:
        """Return every project in the portfolio."""
        ...
