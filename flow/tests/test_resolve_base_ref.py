"""The CI base-ref resolver handles every event that can run the lint job.

Direct tests of `.github/scripts/resolve-base-ref.sh` in a hermetic temp git
repo (a bare `origin` plus a full clone): no klt, no PDK, no network. The
merge_group cases are the point -- `github.base_ref` and `github.event.before`
are both empty on a merge-group run, so a push-style fallback would silently
mis-base the append-only lint at the group head's first parent; the resolver
must demand the group's `base_sha` and fail closed when it is missing or
unavailable.
"""

import os
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / ".github" / "scripts" / "resolve-base-ref.sh"

ENV_KEYS = ("EVENT", "BASE_REF", "BEFORE", "MG_BASE", "GITHUB_ENV")


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def _commit(cwd: Path, message: str) -> str:
    result = _git(
        "-c", "user.email=ci@example.invalid",
        "-c", "user.name=CI",
        "commit", "--allow-empty", "-m", message,
        cwd=cwd,
    )
    assert result.returncode == 0, result.stderr
    rev = _git("rev-parse", "HEAD", cwd=cwd)
    assert rev.returncode == 0, rev.stderr
    return rev.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A full clone of a one-commit bare `origin`, on `main`."""
    origin = tmp_path / "origin.git"
    r = _git("init", "--bare", "-b", "main", str(origin), cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    clone = tmp_path / "clone"
    r = _git("clone", str(origin), str(clone), cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    _commit(clone, "base commit on main")
    r = _git("push", "origin", "main", cwd=clone)
    assert r.returncode == 0, r.stderr
    return clone


def run_script(
    repo: Path, tmp_path: Path, **env_extra: str
) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in ENV_KEYS}
    env.update(env_extra)
    return subprocess.run(
        [str(SCRIPT)], cwd=repo, env=env, capture_output=True, text=True
    )


def resolved(result: subprocess.CompletedProcess) -> str:
    assert result.returncode == 0, result.stderr
    match = re.fullmatch(
        r"FLOW_LINT_BASE_REF=(.+)\n", result.stdout
    )
    assert match is not None, f"unexpected stdout: {result.stdout!r}"
    return match.group(1)


def test_pull_request_resolves_the_base_branch(repo, tmp_path):
    result = run_script(repo, tmp_path, EVENT="pull_request", BASE_REF="main")
    assert resolved(result) == "origin/main"


def test_push_uses_before(repo, tmp_path):
    result = run_script(
        repo, tmp_path, EVENT="push", BEFORE="abc1234def"
    )
    assert resolved(result) == "abc1234def"


def test_push_without_before_falls_back_to_head(repo, tmp_path):
    result = run_script(repo, tmp_path, EVENT="push")
    assert resolved(result) == "HEAD~1"


def test_merge_group_uses_the_group_base_sha(repo, tmp_path):
    base = _git("rev-parse", "main", cwd=repo).stdout.strip()
    result = run_script(repo, tmp_path, EVENT="merge_group", MG_BASE=base)
    assert resolved(result) == base


def test_merge_group_without_base_sha_fails(repo, tmp_path):
    result = run_script(repo, tmp_path, EVENT="merge_group", MG_BASE="")
    assert result.returncode != 0
    assert "base_sha" in result.stderr


def test_merge_group_with_unavailable_base_fails(repo, tmp_path):
    result = run_script(
        repo, tmp_path, EVENT="merge_group", MG_BASE="0" * 40
    )
    assert result.returncode != 0
    assert "not available in this checkout" in result.stderr


def test_pull_request_without_base_ref_fails(repo, tmp_path):
    result = run_script(repo, tmp_path, EVENT="pull_request", BASE_REF="")
    assert result.returncode != 0


def test_unsupported_event_fails(repo, tmp_path):
    result = run_script(repo, tmp_path, EVENT="issue_comment")
    assert result.returncode != 0
    assert "unsupported event" in result.stderr


def test_github_env_receives_the_value(repo, tmp_path):
    env_file = tmp_path / "github-env"
    base = _git("rev-parse", "main", cwd=repo).stdout.strip()
    result = run_script(
        repo, tmp_path,
        EVENT="merge_group", MG_BASE=base, GITHUB_ENV=str(env_file),
    )
    assert result.returncode == 0
    assert env_file.read_text() == f"FLOW_LINT_BASE_REF={base}\n"


def test_ci_workflow_declares_merge_group_without_filters():
    text = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text()
    on_block = text.split("\njobs:", 1)[0]
    assert re.search(r"^  merge_group:\s*$", on_block, re.MULTILINE)
    assert "merge_group:" not in re.sub(
        r"^  merge_group:\s*$", "", on_block, flags=re.MULTILINE
    ), "merge_group must be declared once, with no path/branch filters"
