"""Shared base-ref enforcement of the append-only evidence rule.

Both evidence lints in this repo enforce one rule -- "a record, once written,
is never edited and never deleted" -- against the same base ref in the same
`npm run lint` job: `sim/harness/evidence_lint.py` for the analog evidence
under `sim/`, and `flow/check_records.py` for the digital-flow evidence under
`flow/`. This module is the single implementation they both call, so the two
cannot drift into disagreeing about what the rule means (issue #276, where
they had: one diffed the merge base and failed closed, the other walked the
base-ref tip and skipped itself on an unresolvable ref).

Two decisions are deliberate and are the whole reason this module exists:

* **Diff the merge base, not the base-ref tip.** A working tree that is merely
  *behind* the base ref has not deleted the records that landed on the base
  ref after its branch point. Comparing against `merge-base(base_ref, HEAD)`
  asks the only question worth asking -- "what did *this* branch do to the
  evidence?" -- and is the reason `npm run lint` is runnable in a worktree cut
  before the last evidence commit.
* **Fail closed.** An unresolvable base ref, or no merge base with it, is a
  finding, never a skip: a shallow clone must not be able to retire the check
  that guards the evidence trail while still reporting a clean exit.

Each caller resolves the comparison point once with `resolve_merge_base` and
then runs whichever assertions its evidence tree needs, so an unresolvable base
ref is reported once rather than once per assertion. Pure standard library plus
git; messages are returned unprefixed, for the caller to tag with its own check
name.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def _git_bytes(repo: Path, *args: str) -> bytes | None:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True)
    return None if result.returncode != 0 else result.stdout


def resolve_merge_base(repo: Path, base_ref: str) -> tuple[str | None, list[str]]:
    """Resolve `merge-base(base_ref, HEAD)`, or explain why it cannot be resolved.

    Returns `(sha, [])` on success and `(None, [problem])` otherwise -- never
    `(None, [])`, so a caller cannot read an unresolvable base ref as a pass.
    """
    if not base_ref:
        return None, ["no base ref given (set FLOW_LINT_BASE_REF or pass --base-ref)"]
    if _git(repo, "rev-parse", "--verify", "--quiet", f"{base_ref}^{{commit}}").returncode != 0:
        return None, [f"base ref {base_ref!r} is not available in this checkout "
                      "(fetch full history); the required check cannot be skipped"]
    mb = _git(repo, "merge-base", base_ref, "HEAD")
    if mb.returncode != 0 or not mb.stdout.strip():
        return None, [f"no merge base between {base_ref!r} and HEAD (shallow clone?)"]
    return mb.stdout.strip(), []


def check_paths_append_only(
    repo: Path,
    merge_base: str,
    pathspec: Sequence[str],
    is_evidence: Callable[[str], object],
    base_ref: str,
) -> list[str]:
    """Only additions are allowed to the evidence paths `is_evidence` selects.

    `merge_base` is the already-resolved comparison point from
    `resolve_merge_base`; `base_ref` names it in the messages. `pathspec`
    narrows the diff for git's benefit, while `is_evidence` is the authority on
    which of the resulting paths the rule covers: any status other than `A`
    (added) on a covered path is a finding.
    """
    diff = _git(repo, "diff", "--name-status", "--no-renames", merge_base, "--", *pathspec)
    if diff.returncode != 0:
        return [f"git diff failed: {diff.stderr.strip()}"]
    problems = []
    for line in diff.stdout.splitlines():
        status, _, path = line.partition("\t")
        if is_evidence(path) and status != "A":
            problems.append(f"{path} was {'deleted' if status == 'D' else 'modified'}"
                            f" ({status}) relative to {base_ref}; evidence is append-only"
                            " -- mint a new record")
    return problems


def parse_manifest_entries(text: str) -> dict[str, str]:
    """`MANIFEST.sha256` as `{record name: digest}`; comments and junk ignored.

    Deliberately lenient: this is the *base* side of a comparison, so a
    malformed line in a historical manifest must not crash the check. The live
    side's well-formedness is layer 1's business.
    """
    entries: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) == 2:
            entries[parts[1]] = parts[0]
    return entries


def check_manifest_append_only(
    repo: Path, merge_base: str, manifest_rel: str, base_ref: str
) -> list[str]:
    """No `MANIFEST.sha256` line present at the merge base may be removed or rewritten.

    The manifest is the one evidence file that legitimately changes: a new
    record appends a line to it. So it gets this weaker, line-level assertion
    instead of the byte-identity one -- which is also the assertion that closes
    layer 1's hole, an in-place record edit that re-stamps its own manifest
    line. Compared at the merge base, so a worktree behind the base ref is not
    read as having removed the lines it simply has not merged yet.
    """
    base_blob = _git_bytes(repo, "show", f"{merge_base}:{manifest_rel}")
    if base_blob is None:
        return []  # no manifest at the merge base: nothing to preserve
    base_entries = parse_manifest_entries(base_blob.decode("utf-8", errors="replace"))
    live_path = repo / manifest_rel
    live_entries = (
        parse_manifest_entries(live_path.read_text(encoding="utf-8"))
        if live_path.is_file()
        else {}
    )
    problems = []
    for name, digest in sorted(base_entries.items()):
        if name not in live_entries:
            problems.append(
                f"{manifest_rel}: entry for {name} present at merge-base({base_ref}, HEAD) "
                "was removed -- manifest lines are appended, never deleted"
            )
        elif live_entries[name] != digest:
            problems.append(
                f"{manifest_rel}: entry for {name} was rewritten "
                f"({digest} -> {live_entries[name]}) -- a correction mints a new record"
            )
    return problems
