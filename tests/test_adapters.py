"""Smoke tests for the file adapter and the patch parsing."""

import json
from pathlib import Path

import pytest

from drift_agent.adapters import FileAdapter, PortfolioAdapter
from drift_agent.apply_beacon import DriftPatch, load_patches
from drift_agent.models import Project


def test_file_adapter_satisfies_protocol(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = tmp_path / "projects.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "id": "x",
                    "name": "Test Project",
                    "description": "desc",
                    "outcome": None,
                    "tech_stack": ["Python"],
                    "url": "https://github.com/owner/repo",
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("DRIFT_PROJECTS_FILE", str(fixture))

    adapter = FileAdapter()
    assert isinstance(adapter, PortfolioAdapter)
    projects = adapter.fetch_projects()
    assert len(projects) == 1
    assert isinstance(projects[0], Project)
    assert projects[0].name == "Test Project"
    assert projects[0].tech_stack == ["Python"]


def test_drift_patch_from_dict_validates_required() -> None:
    with pytest.raises(ValueError, match="missing required fields"):
        DriftPatch.from_dict({"name_hint": "x"})  # missing project_id


def test_drift_patch_tech_lists_default_empty() -> None:
    patch = DriftPatch.from_dict({"project_id": "id", "name_hint": "x"})
    assert patch.tech_additions == ()
    assert patch.tech_removals == ()
    assert patch.description is None


def test_load_patches_round_trip(tmp_path: Path) -> None:
    cfg = tmp_path / "p.json"
    cfg.write_text(
        json.dumps(
            {
                "patches": [
                    {
                        "project_id": "id1",
                        "name_hint": "First",
                        "tech_additions": ["Python"],
                        "tech_removals": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    patches = load_patches(cfg)
    assert len(patches) == 1
    assert patches[0].tech_additions == ("Python",)


def test_load_patches_missing_file(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="config not found"):
        load_patches(tmp_path / "missing.json")


def test_load_patches_empty_array(tmp_path: Path) -> None:
    cfg = tmp_path / "p.json"
    cfg.write_text(json.dumps({"patches": []}), encoding="utf-8")
    with pytest.raises(SystemExit, match="'patches' must be a non-empty"):
        load_patches(cfg)
