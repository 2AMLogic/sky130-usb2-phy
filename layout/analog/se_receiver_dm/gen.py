#!/usr/bin/env python3
"""Generate layout/analog/se_receiver_dm/se_receiver_dm.gds.

Layout for the `se_receiver_dm` leaf of the analog partition; the drawing itself lives
in `layout/analog/gen_se_receiver.py`, shared with its dm/dp twin.

    python3 layout/analog/se_receiver_dm/gen.py            # write GDS
    python3 layout/analog/se_receiver_dm/gen.py --check    # no write,
        # exit 1 if the regenerated stream differs from the committed one
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gen_se_receiver import run  # noqa: E402

if __name__ == "__main__":
    sys.exit(run("se_receiver_dm", "DM", "RXDM", Path(__file__).resolve().parent))
