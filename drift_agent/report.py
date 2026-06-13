"""Render a list of DriftReports as a single markdown report."""

from __future__ import annotations

from datetime import datetime, timezone

from drift_agent.models import DriftReport

UTC = timezone.utc


def render_markdown(
    adapter_name: str,
    reports: list[DriftReport],
    skipped: list[tuple[str, str]],
) -> str:
    drift = [r for r in reports if r.has_changes]
    clean = [r for r in reports if not r.has_changes and "(analyzer error" not in r.notes]
    errored = [r for r in reports if "(analyzer error" in r.notes]

    out = [
        f"# Portfolio Drift Report ({adapter_name})",
        "",
        f"Generated {datetime.now(UTC).isoformat()}",
        "",
        f"- **Projects analyzed:** {len(reports)}",
        f"- **Skipped (no github URL):** {len(skipped)}",
        f"- **Clean (no drift):** {len(clean)}",
        f"- **With drift / staleness:** {len(drift)}",
    ]
    if errored:
        out.append(f"- **Analyzer errors:** {len(errored)}")

    if drift:
        out.append("\n---\n## Drift detected\n")
        for r in drift:
            stale_tag = " ⏰ **STALE**" if r.is_stale else ""
            out.append(f"### {r.project_name}{stale_tag}")
            if r.canonical_url:
                out.append(
                    f"- **URL drift:** portfolio points elsewhere; canonical = {r.canonical_url}"
                )
            if r.tech_stack_additions:
                out.append(f"- **Tech to add:** {', '.join(r.tech_stack_additions)}")
            if r.tech_stack_removals:
                out.append(f"- **Tech to remove:** {', '.join(r.tech_stack_removals)}")
            if r.description_suggestion:
                out.append("- **Description suggestion:**")
                out.append(f"  > {r.description_suggestion}")
            if r.outcome_suggestion:
                out.append("- **Outcome suggestion:**")
                out.append(f"  > {r.outcome_suggestion}")
            if r.notes:
                out.append(f"- _Notes: {r.notes}_")
            out.append("")

    if clean:
        out.append("\n---\n## Clean (no changes suggested)\n")
        for r in clean:
            out.append(f"- {r.project_name}")

    if skipped:
        out.append("\n---\n## Skipped\n")
        for name, reason in skipped:
            out.append(f"- {name} — {reason}")

    if errored:
        out.append("\n---\n## Analyzer errors\n")
        for r in errored:
            out.append(f"- {r.project_name} — {r.notes}")

    return "\n".join(out) + "\n"


def drift_count(reports: list[DriftReport]) -> int:
    return sum(1 for r in reports if r.has_changes)
