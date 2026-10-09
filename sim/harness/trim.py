"""Best-trim-code selection for the D+ pull-up tolerance experiment (pure functions).

The deck measures V(DP) raw for every trim code (host 15 kohm load to ground, pull-up
supply VPU = the swept `vsup`). From those, per corner:

    I_load = V(DP) / R_load                  [A, flowing from DP into the load, i.e. out of the pull-up]
    R_eff  = (VPU - V(DP)) / I_load          [ohm, enable switch + ladder + bypass switches]

A code is *valid* only if its measurement is finite, 0 < V(DP) < VPU (non-zero current, positive
resistance) and R_eff is finite. The corner passes only if EVERY code is valid (the whole code
sweep must be present) and AT LEAST ONE code has R_eff inside the inclusive [lo, hi] window
(existential over codes, evaluated within each corner). The best code is the one with the
smallest |R_eff - target|; ties go to the lowest code number. Choosing a different code per corner
shows trim coverage, not a single calibration code that survives voltage and temperature.
"""

from __future__ import annotations

import math


def _finite(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def r_eff(v_dp, vpu, r_load):
    """Effective pull-up resistance in ohm, or None if it cannot be formed (no/zero current,
    non-finite input, V(DP) not strictly between 0 and VPU)."""
    if not (_finite(v_dp) and _finite(vpu) and _finite(r_load)) or r_load <= 0:
        return None
    if not 0.0 < v_dp < vpu:
        return None
    i_load = v_dp / r_load
    if i_load <= 0.0:
        return None
    r = (vpu - v_dp) / i_load
    return r if _finite(r) and r > 0 else None


def analyse(v_dp: list, vpu: float, cfg: dict) -> tuple[dict, list[str]]:
    """Derived measurements and problems for one corner.

    v_dp: V(DP) per code (None for a missing/non-finite measurement), in code order.
    cfg:  tb.json "trim" block.
    """
    n = int(cfg["codes"])
    lo, hi, target = float(cfg["lo_ohm"]), float(cfg["hi_ohm"]), float(cfg["target_ohm"])
    problems: list[str] = []
    rs: list = [None] * n
    for k in range(n):
        v = v_dp[k] if k < len(v_dp) else None
        rs[k] = r_eff(v, vpu, float(cfg["load_ohm"]))
        if rs[k] is None:
            problems.append(f"code {k}: no finite positive R_eff (V(DP)={v!r}, VPU={vpu:g})")
    derived: dict = {}
    for k, r in enumerate(rs):
        if r is not None:
            derived[f"r_c{k:02d}_ohm"] = r
    good = [k for k in range(n) if rs[k] is not None]
    if good:
        best = good[0]
        for k in good[1:]:
            if abs(rs[k] - target) < abs(rs[best] - target):  # strict: ties keep the lowest code
                best = k
        derived["best_code"] = float(best)
        derived["best_r_ohm"] = rs[best]
        derived["best_err_ohm"] = abs(rs[best] - target)
        derived["n_in_window"] = float(sum(1 for k in good if lo <= rs[k] <= hi))
    if len(good) == n:
        steps = [rs[k - 1] - rs[k] for k in range(1, n)]  # code k-1 -> k, positive = resistance falls
        for k, s in enumerate(steps, start=1):
            derived[f"step_c{k:02d}_ohm"] = s
        derived["step_min_ohm"] = min(steps)
        derived["step_max_ohm"] = max(steps)
        derived["range_ohm"] = rs[0] - rs[n - 1]
        derived["n_nonmonotonic"] = float(sum(1 for s in steps if s <= 0.0))
        if not derived["n_in_window"]:
            b = int(derived["best_code"])
            problems.append(f"no trim code inside [{lo:g}, {hi:g}] ohm (best code {b}: {rs[b]:.6g} ohm)")
    return derived, problems
