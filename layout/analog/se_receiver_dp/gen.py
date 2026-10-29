#!/usr/bin/env python3
"""Generate layout/analog/se_receiver_dp/se_receiver_dp.gds.

Layout for the `se_receiver_dp` leaf of the analog partition; the drawing itself lives
in `layout/analog/gen_se_receiver.py`, shared with its dm/dp twin.

    python3 layout/analog/se_receiver_dp/gen.py            # write GDS
    python3 layout/analog/se_receiver_dp/gen.py --check    # no write,
        # exit 1 if the regenerated stream differs from the committed one
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gen_se_receiver import run  # noqa: E402

if __name__ == "__main__":
    sys.exit(run("se_receiver_dp", "DP", "RXDP", Path(__file__).resolve().parent))
