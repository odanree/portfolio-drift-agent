"""URL parsing tests for the GitHub fetcher."""

import pytest

from drift_agent.github import parse_owner_repo


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://github.com/owner/repo", ("owner", "repo")),
        ("https://github.com/owner/repo.git", ("owner", "repo")),
        ("https://github.com/owner/repo/", ("owner", "repo")),
        ("https://github.com/owner/repo#readme", ("owner", "repo")),
        ("git@github.com:owner/repo", None),  # ssh-style not supported — Beacon stores https
        ("https://gitlab.com/owner/repo", None),
        ("https://example.com", None),
    ],
)
def test_parse_owner_repo(url: str, expected: tuple[str, str] | None) -> None:
    assert parse_owner_repo(url) == expected
