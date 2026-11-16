"""The one implementation of the pinned-PDK root search and open_pdks revision check (#304).

Four copies of this logic lived in `sim/harness/runner.py` (the sim harness),
`flow/run_flow.py` (the digital flow), `design/check_netlist.py` and
`design/export_netlist.sh` (netlist export): the same root search order
(explicit `$PDK_ROOT`, ciel's `~/.ciel`, then the system roots), the same
`SOURCES` `open_pdks` parse, and the same compare against the pin in
`sim/corners.json` -- kept in sync by nothing but a comment. What the copies
deliberately do *not* share is the marker that decides a tree is usable (the
ngspice model-library directory for the sim harness, a bare `sky130A/`
directory for the flow, the xschem rcfile for netlist export), so that
predicate is a parameter of the search here.

`export_netlist.sh` runs this module as a script (`python3
sim/harness/pdk_pin.py`) to get the pinned sky130A xschemrc path instead of
re-implementing the search in bash/awk. The pin itself and the
refusal-on-mismatch are unchanged by #304.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Callable, TypeVar

#: The single pin source for every consumer.
CORNERS_JSON = Path(__file__).resolve().parents[1] / "corners.json"

T = TypeVar("T")


class PdkPinError(RuntimeError):
    """No usable PDK tree was found, or the tree found is not at the pinned open_pdks revision."""


def pdk_roots() -> list[Path]:
    """PDK search roots in order: explicit `$PDK_ROOT`, then ciel's `~/.ciel`, then system paths."""
    roots = [Path(os.environ["PDK_ROOT"])] if os.environ.get("PDK_ROOT") else []
    return roots + [Path("~/.ciel").expanduser(), Path("/usr/share/pdk"),
                    Path("/usr/local/share/pdk"), Path("/opt/pdk")]


def pinned_open_pdks_commit() -> str:
    """The open_pdks revision this repo pins (single source: sim/corners.json)."""
    return json.loads(CORNERS_JSON.read_text())["pdk"]["open_pdks_commit"]


def open_pdks_commit(tree: Path) -> str:
    """The open_pdks revision in the tree's `SOURCES` file, or "unknown" (which never matches a pin)."""
    sources = tree / "SOURCES"
    if sources.is_file():
        for line in sources.read_text().splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0] == "open_pdks":
                return parts[1]
    return "unknown"


def ngspice_tree(tree: Path) -> Path | None:
    """Sim-harness marker: a tree carrying an ngspice model-library directory (returns the tree)."""
    ngspice = tree / "libs.tech" / "ngspice"
    return ngspice if ngspice.is_dir() else None


def xschem_rcfile(tree: Path) -> Path | None:
    """Netlist-export marker: the tree's `libs.tech/xschem/xschemrc` (what `klt netlist --rcfile` wants)."""
    rc = tree / "libs.tech" / "xschem" / "xschemrc"
    return rc if rc.is_file() else None


def search_tree(name: str, marker: Callable[[Path], T | None]) -> tuple[T, Path] | None:
    """The first `<root>/<name>` tree in `pdk_roots()` order that `marker` accepts, or None.

    `marker` is handed each candidate `<root>/<name>` and returns a non-None value when that
    tree is usable; the first hit wins, so `$PDK_ROOT` can shadow an otherwise identical
    system tree.
    """
    for root in pdk_roots():
        tree = root / name
        found = marker(tree)
        if found is not None:
            return found, tree
    return None


def check_pin(
    tree: Path, *, name: str = "sky130A", pin: str | None = None, error: type[Exception] = PdkPinError
) -> tuple[str, str]:
    """Refuse a tree whose `SOURCES` open_pdks revision is not the pin; return (commit, pin).

    The refusal names both revisions: a stale tree accepted by one tool while another
    rejects it is exactly the drift this module exists to prevent.
    """
    pin = pinned_open_pdks_commit() if pin is None else pin
    commit = open_pdks_commit(tree)
    if commit != pin:
        raise error(
            f"PDK {name} under {tree.parent} is open_pdks {commit}, but sim/corners.json pins "
            f"open_pdks {pin}; install the pinned revision under ~/.ciel or point PDK_ROOT at it "
            "(see docs/environment-setup.md)"
        )
    return commit, pin


def resolve_pinned_tree(
    name: str,
    marker: Callable[[Path], T | None],
    *,
    pin: str | None = None,
    error: type[Exception] = PdkPinError,
) -> tuple[T, Path, str, str]:
    """`search_tree` then `check_pin` in one call: the pinned-PDK lookup every tool makes.

    Returns `(marker_value, tree, commit, pin)`; raises `error` when no root holds a tree the
    marker accepts, and when the tree found is not at the pinned revision.
    """
    hit = search_tree(name, marker)
    if hit is None:
        raise error(f"{name} not found (set PDK_ROOT or install it under ~/.ciel; see docs/environment-setup.md)")
    found, tree = hit
    commit, pin = check_pin(tree, name=name, pin=pin, error=error)
    return found, tree, commit, pin


if __name__ == "__main__":
    # The `design/export_netlist.sh` shim: print the pinned sky130A xschemrc path.
    try:
        print(resolve_pinned_tree("sky130A", xschem_rcfile)[0])
    except PdkPinError as exc:
        sys.exit(str(exc))
