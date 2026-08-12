"""CLI entry: pick an adapter, run the audit, write the report."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from drift_agent.adapters import BeaconAdapter, FileAdapter, PortfolioAdapter
from drift_agent.analyzer import DEFAULT_MODEL, analyze
from drift_agent.github import build_client, fetch_snapshot, parse_owner_repo
from drift_agent.models import DriftReport
from drift_agent.report import drift_count, render_markdown

UTC = timezone.utc
DEFAULT_OUT = Path(os.getenv("DRIFT_OUTPUT_DIR", "output"))

ADAPTERS: dict[str, type[PortfolioAdapter]] = {
    "beacon": BeaconAdapter,
    "file": FileAdapter,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit portfolio projects against GitHub.")
    parser.add_argument(
        "--adapter",
        default=os.getenv("DRIFT_ADAPTER", "beacon"),
        choices=sorted(ADAPTERS),
        help="portfolio source backend (default: beacon, override via DRIFT_ADAPTER env)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=int(os.getenv("DRIFT_LIMIT") or "0") or None,
        help="stop after N projects (for smoke tests; default: all)",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Anthropic model id (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUT,
        help="directory for drift_*.md + drift_*.json (default: ./output)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    log = logging.getLogger("drift_agent")

    from anthropic import Anthropic

    if not os.getenv("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY env var not set")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    adapter = ADAPTERS[args.adapter]()
    projects = adapter.fetch_projects()
    if args.limit:
        projects = projects[: args.limit]
        log.info("Limiting to first %d projects (--limit)", args.limit)

    gh = build_client()
    anthropic_client = Anthropic()

    reports: list[DriftReport] = []
    skipped: list[tuple[str, str]] = []

    for i, p in enumerate(projects, 1):
        if not p.url:
            skipped.append((p.name, "no url"))
            continue
        parsed = parse_owner_repo(p.url)
        if not parsed:
            skipped.append((p.name, f"url not github.com ({p.url})"))
            continue
        owner, repo = parsed
        log.info("[%d/%d] %s -> github.com/%s/%s", i, len(projects), p.name, owner, repo)
        snapshot = fetch_snapshot(gh, owner, repo)
        if snapshot is None:
            skipped.append((p.name, f"github fetch failed ({owner}/{repo})"))
            continue
        report = analyze(anthropic_client, p, snapshot, model=args.model)
        reports.append(report)
        log.info(
            "  -> drift=%s stale=%s notes=%r",
            report.has_changes,
            report.is_stale,
            report.notes[:80],
        )

    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M")
    md_path = args.output_dir / f"drift_{args.adapter}_{ts}.md"
    json_path = args.output_dir / f"drift_{args.adapter}_{ts}.json"
    md_path.write_text(render_markdown(args.adapter, reports, skipped), encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(UTC).isoformat(),
                "adapter": args.adapter,
                "model": args.model,
                "reports": [asdict(r) for r in reports],
                "skipped": [{"name": n, "reason": r} for n, r in skipped],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    n_drift = drift_count(reports)
    print()
    print(f"  Adapter: {args.adapter}")
    print(f"  Analyzed: {len(reports)}    Drift: {n_drift}    Skipped: {len(skipped)}")
    print(f"  Report  -> {md_path}")
    print(f"  JSON    -> {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
