"""Markdown rendering tests."""

from drift_agent.models import DriftReport
from drift_agent.report import drift_count, render_markdown


def _report(name: str, *, is_stale: bool = False, **kwargs) -> DriftReport:
    return DriftReport(project_id=name, project_name=name, is_stale=is_stale, **kwargs)


def test_drift_count_counts_only_with_changes() -> None:
    reports = [
        _report("a"),  # no changes
        _report("b", outcome_suggestion="updated"),
        _report("c", tech_stack_additions=["Python"]),
        _report("d", is_stale=True),
    ]
    # b, c, d count — `is_stale=True` flips has_changes True via the dataclass property.
    assert drift_count(reports) == 3


def test_render_markdown_sections() -> None:
    reports = [
        _report("clean_one"),
        _report("drifty", tech_stack_additions=["Qdrant"], notes="caught Qdrant addition"),
    ]
    skipped = [("noprojecturl", "no url")]
    md = render_markdown("beacon", reports, skipped)
    assert "## Drift detected" in md
    assert "drifty" in md
    assert "Qdrant" in md
    assert "## Clean (no changes suggested)" in md
    assert "clean_one" in md
    assert "## Skipped" in md
    assert "noprojecturl" in md
    assert "Generated " in md  # ISO timestamp


def test_render_markdown_when_all_clean() -> None:
    md = render_markdown("file", [_report("ok")], [])
    assert "## Drift detected" not in md
    assert "## Clean (no changes suggested)" in md
