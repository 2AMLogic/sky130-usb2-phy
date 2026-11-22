"""Exact-equality pin on ``gen_common.find_row_x``'s chosen PMOS-row offset, per leaf.

Run: ``python3 -m pytest signoff/tests -v``

Why this pin exists (issue #434): ``find_row_x`` steps its candidate offset with
``start += GRID`` (``layout/analog/gen_common.py``), and for the three receiver
leaves the search runs 2,764 steps, stopping at ``15.810000000001093`` -- *not*
the exactly-rounded ``15.81`` -- carrying +1.09e-12 um of accumulated
floating-point drift. That drift is load-bearing: at the deciding step the
closest pad pair (``LOADDIODE`` / ``RXDP``) sits at ``|dx| =
0.52000000000109026`` against ``make_conflicts``' own ``0.52`` met2-space
threshold, and the predicate is a strict ``<``, so the pair is non-conflicting
only because of the accumulation drift. Replacing ``start += GRID`` with the
algebraically identical ``start0 + k * GRID`` (one multiply) was measured to
flip that single comparison and keep the search stepping, moving the PMOS row
of all three receiver leaves and changing the committed GDS. A ``snap()`` of
``start`` onto the 0.005 grid does the same. ``gen.py --check`` would catch
such a rewrite, but only as an opaque "stream is not byte-identical" with
nothing pointing at the cause; this test is the pointed companion -- it fails
naming the accumulation-order sensitivity and the 1.09e-12 um margin.

``dplus_pullup`` stops at ``k = 0``: its chosen offset is the caller's ``start0
= 0.8 + STRIP_W + 0.9`` as evaluated in floating point, whose drift comes from
that sum rather than the stepping loop. Pinning it to exact equality still
catches a ``snap()``-onto-grid rewrite (``1.99`` != ``1.9900000000000002``),
though not a ``k``-multiply rewrite, which is a no-op at ``k = 0``.

The explanation lives here rather than as a comment in ``gen_common.py``:
that module is a hashed provenance input of every live analog-layout record,
so even a comment-only edit there forces a five-record re-mint plus a signoff
re-pin (Curator guidance on issue #434).

This file needs ``klayout.db`` (the leaf ``build()`` s draw real layouts), so
it runs where that import resolves and skips elsewhere: the signoff CI job
pip-installs the pinned grader wheel ``klayout-tools==0.9.2`` -- the same pin
that re-runs every analog leaf's ``gen.py --check`` in that job -- before
``python3 -m pytest signoff/tests``, so the pin is exercised on every PR; a
grading host running ``npm run check:all`` leg 3 without ``klayout.db`` in its
``python3`` gets a skip, not a failure.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

pytest.importorskip(
    "klayout.db",
    reason="leaf builds draw real layouts; installed with the signoff job's "
    "klayout-tools grader pin (docs/environment-setup.md)",
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ANALOG = REPO_ROOT / "layout" / "analog"

sys.path.insert(0, str(ANALOG))
import gen_se_receiver  # noqa: E402

_dplus_spec = importlib.util.spec_from_file_location(
    "dplus_pullup_gen", ANALOG / "dplus_pullup" / "gen.py"
)
dplus_pullup_gen = importlib.util.module_from_spec(_dplus_spec)
sys.modules["dplus_pullup_gen"] = dplus_pullup_gen
_dplus_spec.loader.exec_module(dplus_pullup_gen)

# The chosen offset per leaf, to exact float equality. Measured 2026-11-22 at
# d8b2b6b6 under the pinned grader wheel klayout-tools==0.9.2, by spying the
# real find_row_x inside the real build() of each leaf (the same values the
# committed, byte-identical GDS was generated with). Hex follows each literal
# so the pinned double is unambiguous.
EXPECTED = {
    "differential_receiver": 15.810000000001093,  # 0x1.f9eb851eb8786p+3
    "dplus_pullup": 1.9900000000000002,  # 0x1.fd70a3d70a3d8p+0
    "se_receiver_dm": 15.810000000001093,  # 0x1.f9eb851eb8786p+3
    "se_receiver_dp": 15.810000000001093,  # 0x1.f9eb851eb8786p+3
}

BUILDS = {
    "se_receiver_dp": lambda: gen_se_receiver.build("se_receiver_dp", "DP", "RXDP"),
    "se_receiver_dm": lambda: gen_se_receiver.build("se_receiver_dm", "DM", "RXDM"),
    "differential_receiver": lambda: gen_se_receiver.build(
        "differential_receiver", "DP", "RXD", "DM", differential=True
    ),
    "dplus_pullup": dplus_pullup_gen.build,
}

_DRIFT_MSG = (
    "find_row_x's chosen PMOS-row offset for {leaf} changed.\n"
    "The `start += GRID` accumulation order is load-bearing (issue #434): at\n"
    "the deciding step the closest pad pair (LOADDIODE/RXDP) clears\n"
    "make_conflicts' 0.52 met2-space threshold by only 1.09e-12 um of\n"
    "accumulation drift, under a strict `<`, so an algebraically 'equivalent'\n"
    "rewrite of the stepping (start0 + k*GRID, snap()) flips the comparison,\n"
    "moves the PMOS row and changes the committed GDS -- surfacing elsewhere\n"
    "as an opaque `gen.py --check` byte mismatch. If the leaf geometry itself\n"
    "changed on purpose, re-measure the offset by spying find_row_x in the\n"
    "real build(), update EXPECTED here -- and expect the five-record analog\n"
    "layout re-mint plus a signoff re-pin, exactly as #432 did.\n"
    "expected: {expected!r}   measured: {got!r}"
)


def _chosen_start(mod, build_fn, monkeypatch):
    """Run ``build_fn()`` with ``mod.find_row_x`` spied; return the chosen offset.

    ``build()`` references ``find_row_x`` as a module global, so the spy sees
    the leaf's real placement geometry and real fixed ports -- no duplicated
    geometry to drift out of sync with the leaf.
    """
    box: dict[str, float] = {}
    real = mod.find_row_x

    def spy(place_fn, fixed_ports, ty_of, start0):
        start = real(place_fn, fixed_ports, ty_of, start0)
        box["start"] = start
        return start

    monkeypatch.setattr(mod, "find_row_x", spy)
    build_fn()
    return box.get("start")


@pytest.mark.parametrize("leaf", sorted(EXPECTED))
def test_pmos_row_offset_is_pinned(leaf, monkeypatch):
    mod = dplus_pullup_gen if leaf == "dplus_pullup" else gen_se_receiver
    got = _chosen_start(mod, BUILDS[leaf], monkeypatch)
    assert got is not None, (
        f"{leaf}'s build() no longer searches its PMOS row through "
        "gen_common.find_row_x -- this pin needs re-pointing at whatever "
        "replaced it (issue #434)"
    )
    assert got == EXPECTED[leaf], _DRIFT_MSG.format(
        leaf=leaf, expected=EXPECTED[leaf], got=got
    )
