#!/usr/bin/env python3
"""Toolchain-free check of manifests/artifacts/*.manifest.json (stdlib + git only).

    python3 scripts/check_artifact_manifests.py

Fails on a malformed manifest, any `uri` that is not `artifact:<key>`, a storage location or
URL written into a manifest, and stored objects whose bytes are also committed. Rules and the
duplicate match are in sim/harness/artifact_manifest.py. Live checking of the store itself is
`klt artifact verify <manifest>` (needs the broker; not run in CI).
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "sim"))

from harness import artifact_manifest as am  # noqa: E402


def main(argv=None) -> int:
    repo = Path(argv[0]).resolve() if argv else REPO
    problems = am.check_repo(repo)
    for p in problems:
        print(f"FAIL {p}")
    n = len(list((repo / "manifests" / "artifacts").glob("*.manifest.json")))
    print(f"artifact manifests ({n}): " + ("FAILED" if problems else "OK"))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
