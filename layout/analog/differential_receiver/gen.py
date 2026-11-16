#!/usr/bin/env python3
"""Generate layout/analog/differential_receiver/differential_receiver.gds.

Layout for the `differential_receiver` leaf of the analog partition; the drawing itself
lives in `layout/analog/gen_se_receiver.py`, shared with the single-ended receiver
leaves. Every device is re-derived for sky130 from
`design/netlist/differential_receiver.spice` (issue #167); no gf180 geometry is
consumed. The conventions it implements (rails, guard rings, pin labels, routing
layers) are written down in `layout/analog/README.md`.

    python3 layout/analog/differential_receiver/gen.py            # write GDS
    python3 layout/analog/differential_receiver/gen.py --check    # no write,
        # exit 1 if the regenerated stream differs from the committed one
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gen_se_receiver import run  # noqa: E402

if __name__ == "__main__":
    sys.exit(run("differential_receiver", "DP", "RXD", Path(__file__).resolve().parent, "DM", differential=True))
