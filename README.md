# Portfolio Drift Agent

Audit a portfolio of projects against their actual GitHub repos. Surfaces structured, grounded suggestions for what's changed since the portfolio record was last updated — and refuses to invent metrics.

Designed for HITL: the audit is read-only and produces a markdown + JSON report. Applying suggestions is opt-in (via a per-adapter apply tool) and dry-runs by default.

## Why

If your portfolio (resume, profile site, internal project tracker) records what each project does, that record drifts the moment the underlying repo evolves. A test count changes. A dependency gets removed. A new headline metric ships. Six months later, your resume claims things that aren't backed by the source repo — exactly the failure mode a careful technical screen will catch.

This agent is the inverse of [LLM hallucination detection](https://github.com/odanree/evalkit): instead of catching invented claims going *out* (in generated text), it catches *stale claims* going *in* (in the source data feeding the generator).

## How it works

```
your portfolio backend ──┐
                          ├── per project ──► Claude analyzer ──► DriftReport
GitHub repo metadata     ──┘                       │
+ README + recent commits                          ▼
                                       output/drift_*.md + .json
                                                   │
                                                 operator picks suggestions
                                                   ▼
                                      curated drift_patches.json
                                                   │
                                            drift-apply-beacon
                                                  (dry-run by default)
                                                   │
                                                 --apply
                                                   ▼
                                        portfolio backend mutated
```

Every suggestion the analyzer makes must cite specific evidence (a README line, a commit message, a language byte share). If the existing record already matches reality, the analyzer returns empty suggestions.

## Quick start

```bash
pip install -e .[dev]

# Audit Beacon (default adapter)
export BEACON_API_URL=https://beacon.danhle.net
export BEACON_JWT=...          # extract from your Beacon session
export ANTHROPIC_API_KEY=...
export GITHUB_TOKEN=...        # optional, raises rate limit 60/hr → 5000/hr

drift-agent

# Or audit a flat JSON file (the example, or one of your own)
export DRIFT_PROJECTS_FILE=examples/projects.example.json
drift-agent --adapter file

# Or scope to N projects for a smoke test
drift-agent --limit 3
```

Output lands in `./output/drift_<adapter>_<timestamp>.md` (+ matching `.json`).

## Adapters

Currently shipped:

| Adapter | Module | Direction | Env |
|---|---|---|---|
| `beacon` | `drift_agent.adapters.BeaconAdapter` | read + write | `BEACON_API_URL`, `BEACON_JWT` |
| `file` | `drift_agent.adapters.FileAdapter` | read-only | `DRIFT_PROJECTS_FILE` |

### Writing your own

Implement the `PortfolioAdapter` protocol:

```python
from drift_agent.adapters import PortfolioAdapter
from drift_agent.models import Project

class NotionAdapter:
    name = "notion"

    def __init__(self) -> None:
        # pull credentials from env, init clients, etc.
        ...

    def fetch_projects(self) -> list[Project]:
        # return your records as Project instances
        ...
```

Then register it in `ADAPTERS` in `drift_agent/cli.py` and pass `--adapter notion`.

The protocol is read-only on purpose. Adapters that also support *applying* changes (like Beacon does) expose their own apply method; per-adapter apply tooling sits next to the adapter (see `drift_agent/apply_beacon.py` for the reference pattern).

## Applying drift patches (Beacon adapter)

The Beacon project API has no `PATCH`, so each apply is delete-then-recreate. The companion tool `drift-apply-beacon` reads a JSON patches config and validates before touching anything:

```bash
# Copy the template, edit with the suggestions you accept from the drift report
cp examples/drift_patches.example.json drift_patches.json
$EDITOR drift_patches.json

# Dry-run — prints intent, no API calls
drift-apply-beacon

# Apply for real
drift-apply-beacon --apply

# Then re-backfill any downstream index (e.g. Beacon's Qdrant project_overviews)
```

## Scheduled audit (GitHub Actions)

The default `.github/workflows/schedule.yml` workflow runs weekly (Mondays 09:00 UTC), uploads the drift report as a workflow artifact, and opens a GitHub Issue if drift was found. Requires three repo secrets:

| Secret | What |
|---|---|
| `BEACON_JWT` | a long-lived Beacon JWT |
| `ANTHROPIC_API_KEY` | for the analyzer |
| `GITHUB_TOKEN` | already provided by GH Actions |

Cost: ~$0.40/week against a ~25-project portfolio.

## Cost / scale

Per audit run:

- 1 GitHub call to list projects (free — your portfolio backend)
- 4 GitHub calls per project (repo + languages + readme + commits)
- 1 Anthropic Sonnet call per project (~3K input + ~500 output tokens)

For 25 projects at Sonnet 4.6 pricing: ~75K input + ~12.5K output ≈ $0.40 per run.

## Design notes

- **Procedural, not LangGraph.** The audit is one Claude call per project — no tool-use loop, no multi-agent supervisor, no state machine. LangGraph would add scaffolding without function.
- **Refuses to invent metrics.** The analyzer system prompt requires every suggestion to cite evidence. Outcome suggestions that would add a number not visible in the README are explicitly forbidden.
- **Stale window is configurable.** A project whose last commit is older than `DRIFT_STALE_DAYS` (default 180) is flagged stale even if its record otherwise matches the repo.
- **Read-side protocol minimal on purpose.** The `PortfolioAdapter` protocol only requires `fetch_projects()`. Write-side support is opt-in per adapter, because not every backend supports it (e.g. a file in git is read-only from the agent's perspective; you update it via `git commit`).

## License

MIT — see [LICENSE](LICENSE).
