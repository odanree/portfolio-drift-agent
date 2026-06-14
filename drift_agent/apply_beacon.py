"""Apply curated drift suggestions to Beacon (the only adapter with mutate support).

Reads a JSON patches config (see examples/drift_patches.example.json), prints
intent in a dry-run by default, applies with --apply. Each apply sends a
PATCH with only the changed fields, so the project id stays stable.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from drift_agent.adapters import BeaconAdapter

log = logging.getLogger("apply_beacon")

DEFAULT_CONFIG = Path("drift_patches.json")


@dataclass
class DriftPatch:
    project_id: str
    name_hint: str
    description: str | None = None
    outcome: str | None = None
    tech_additions: tuple[str, ...] = ()
    tech_removals: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, raw: dict) -> DriftPatch:
        missing = [k for k in ("project_id", "name_hint") if not raw.get(k)]
        if missing:
            raise ValueError(f"patch entry missing required fields {missing}: {raw!r}")
        return cls(
            project_id=raw["project_id"],
            name_hint=raw["name_hint"],
            description=raw.get("description") or None,
            outcome=raw.get("outcome") or None,
            tech_additions=tuple(raw.get("tech_additions") or ()),
            tech_removals=tuple(raw.get("tech_removals") or ()),
        )


def load_patches(config_path: Path) -> list[DriftPatch]:
    if not config_path.exists():
        sys.exit(
            f"config not found: {config_path}\n"
            f"  see examples/drift_patches.example.json for the expected shape."
        )
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    patches_raw = raw.get("patches", [])
    if not isinstance(patches_raw, list) or not patches_raw:
        sys.exit(f"config {config_path}: 'patches' must be a non-empty array")
    return [DriftPatch.from_dict(p) for p in patches_raw]


def _build_payload(existing: dict, patch: DriftPatch) -> dict:
    """Build a PATCH delta — only fields the patch actually changes."""
    payload: dict = {}
    if patch.description is not None:
        payload["description"] = patch.description
    if patch.outcome is not None:
        payload["outcome"] = patch.outcome
    if patch.tech_additions or patch.tech_removals:
        current_tech = list(existing.get("tech_stack") or [])
        new_tech = [t for t in current_tech if t not in patch.tech_removals]
        for add in patch.tech_additions:
            if add not in new_tech:
                new_tech.append(add)
        payload["tech_stack"] = new_tech
    return payload


def _log_intent(patch: DriftPatch) -> None:
    log.info("  %s", patch.name_hint)
    if patch.tech_additions:
        log.info("    +tech: %s", list(patch.tech_additions))
    if patch.tech_removals:
        log.info("    -tech: %s", list(patch.tech_removals))
    if patch.description:
        log.info("    description: rewritten (%d chars)", len(patch.description))
    if patch.outcome:
        log.info("    outcome:     rewritten (%d chars)", len(patch.outcome))


def _apply_one(adapter: BeaconAdapter, patch: DriftPatch) -> bool:
    existing = adapter.fetch_one_raw(patch.project_id)
    if not existing:
        log.error("Project %s (%s) not found on Beacon", patch.project_id, patch.name_hint)
        return False
    payload = _build_payload(existing, patch)
    if not payload:
        log.info("    no-op (patch has no field changes)")
        return True
    if not adapter.patch_project(patch.project_id, payload):
        log.error("Patch failed for %s; payload: %s", patch.project_id, json.dumps(payload)[:300])
        return False
    log.info("    OK: patched id = %s", patch.project_id)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--apply", action="store_true", help="actually apply (default: dry-run)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if not os.getenv("BEACON_JWT"):
        sys.exit("BEACON_JWT env var not set")

    patches = load_patches(args.config)
    log.info("Loaded %d patches from %s", len(patches), args.config)
    log.info("Mode: %s", "APPLY (destructive)" if args.apply else "dry-run (no changes)")
    log.info("Patches to apply:")
    for patch in patches:
        _log_intent(patch)

    if not args.apply:
        print()
        print(f"  Dry-run complete. {len(patches)} patches would be applied.")
        print("  Re-run with --apply to actually execute.")
        return 0

    adapter = BeaconAdapter()
    successes = sum(1 for patch in patches if _apply_one(adapter, patch))
    print()
    print(f"  Applied {successes}/{len(patches)} patches")
    return 0 if successes == len(patches) else 1


if __name__ == "__main__":
    raise SystemExit(main())
