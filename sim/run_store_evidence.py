#!/usr/bin/env python3
"""Store a staged campaign directory in the artifact store (stdlib only). See sim/README.md.

    python3 sim/run_store_evidence.py diff-receiver-mismatch sim/.work/diff-receiver-mismatch/<id>

Every file under the staged directory is `klt artifact put` into the store; git gets
`manifests/artifacts/<bench>-<run-id>.manifest.json` and `sim/<bench>/campaigns/<run-id>.md`
(a Stored-evidence table). The staged directory must be git-ignored scratch (or outside the
repo), never a tracked path. Fails closed (exit 4, nothing written) if the store is unusable.
"""

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import evidence_store as es, matrix as mx  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bench")
    ap.add_argument("staged", type=Path)
    ap.add_argument("--run-id", default=None, help="default: the staged directory's name")
    ap.add_argument("--note", default="", help="one line describing the campaign, for the summary")
    args = ap.parse_args(argv)
    staged = args.staged.resolve()
    rid = args.run_id or staged.name
    exp = mx.SIM_DIR / args.bench
    try:
        if not (exp / "testbench").is_dir():
            raise ValueError(f"no experiment {args.bench!r}")
        if not staged.is_dir():
            raise ValueError(f"{staged} is not a directory")
        if staged.is_relative_to(mx.REPO_ROOT):
            rel = str(staged.relative_to(mx.REPO_ROOT))
            if subprocess.run(["git", "-C", str(mx.REPO_ROOT), "check-ignore", "-q", rel + "/x"]).returncode != 0:
                raise ValueError(f"{rel} is inside the tracked tree; stage under sim/.work/ (git-ignored)")
        summary = exp / "campaigns" / f"{rid}.md"
        if summary.exists():
            raise ValueError(f"{summary} exists; evidence is append-only")
        files = {f"{args.bench}/{rid}/{p.relative_to(staged).as_posix()}": p
                 for p in sorted(staged.rglob("*")) if p.is_file()}
        if not files:
            raise ValueError("nothing to store")
        es.preflight()
        rows = es.store_files(args.bench, rid, files, staged.parent / f"{rid}.manifest.json")
    except es.StoreUnavailable as exc:
        print(f"error: artifact store unavailable, nothing was recorded: {exc}", file=sys.stderr)
        return 4
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    import hashlib

    msha = hashlib.sha256(es.manifest_path(args.bench, rid).read_bytes()).hexdigest()
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text("\n".join([
        f"# {args.bench} -- {rid} (stored evidence)", "", args.note or "Campaign outputs stored in the fleet artifact store.", "",
        f"- **Manifest**: {es.manifest_rel(args.bench, rid)} (manifest sha256 `{msha}`)", ""]
        + es.stored_table(rows) + [""]))
    print(f"stored {len(rows)} object(s); summary {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
