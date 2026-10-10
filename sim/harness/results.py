"""Request construction and result validation (pure functions, no I/O).

Shared by the runner and the toolchain-free record lint, so "what counts as a
complete, successful grid" is defined once. A grid is complete only if every
matrix tuple appears exactly once, simulated successfully, with every expected
measurement finite and inside the testbench's harness-only bounds.
"""

from __future__ import annotations

import math

from . import matrix as mx
from . import trim as trimmod

DEFAULT_TIMEOUT_S = 300


class VariantError(ValueError):
    pass


def tb_matrix_id(tb: dict, variant: str | None = None) -> str:
    """The approved matrix id an experiment (variant) runs on; the 45-point matrix by default."""
    return resolve_tb(tb, variant).get("matrix_id", mx.LEGACY_ID)


def resolve_tb(tb: dict, variant: str | None = None) -> dict:
    """The effective testbench configuration for a named variant (None = the base experiment).

    A variant may override only `matrix_id`, `claim` and (key by key) `record`; the netlist,
    measurements, trim window and checks are shared, so a variant can never relax a bound.
    The result has no `variants` key.
    """
    allowed = {"matrix_id", "claim", "record"}
    out = {k: v for k, v in tb.items() if k != "variants"}
    if variant is None:
        return out
    var = (tb.get("variants") or {}).get(variant)
    if not isinstance(var, dict):
        raise VariantError(f"unknown testbench variant {variant!r}")
    extra = set(var) - allowed
    if extra:
        raise VariantError(f"variant {variant!r} may not override {sorted(extra)}")
    for k, v in var.items():
        out[k] = {**(out.get(k) or {}), **v} if k == "record" else v
    return out


def build_request(
    tb: dict,
    matrix: mx.Matrix,
    *,
    backend: str,
    process=None,
    temperature_c=None,
    supply_v=None,
    netlist: str = "body.spice",
    runner_version_check: str | None = None,
) -> dict:
    """The resolved `klt sim` request. Axes default to the full matrix."""
    request = {
        "netlist": netlist,
        "engine": "ngspice",
        "backend": backend,
        "models": {"pdk": matrix.pdk["name"], "lib": matrix.pdk["lib"]},
        "corners": {
            "process": list(process or matrix.process),
            "supply_v": {matrix.supply_source: list(supply_v or matrix.supply_v)},
            "temperature_c": list(temperature_c or matrix.temperature_c),
        },
        "analysis": {"kind": tb["analysis"]["kind"], "args": tb["analysis"].get("args", "")},
        "measurements": [{"name": n, "spice": m["spice"]} for n, m in tb["measure"].items()],
        "options": {"timeout_s": int(tb.get("timeout_s", DEFAULT_TIMEOUT_S)), "keep_artifacts": True},
    }
    if runner_version_check:
        request["batch"] = {"runner_version_check": runner_version_check}
    return request


def _finite(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def corner_key(c: dict):
    supply = c.get("supply_v")
    vdd = next(iter(supply.values()), None) if isinstance(supply, dict) else None
    try:
        return mx.key(c.get("process"), c.get("temperature_c"), vdd)
    except (TypeError, ValueError):
        return None


def evaluate(report: dict, expected_points, tb: dict) -> tuple[list[dict], list[str]]:
    """Per-point results (in `expected_points` order) and a list of problems.

    problems is empty only for a complete, successful grid: no missing,
    duplicated, unexpected or failed corners; every declared measurement
    present and finite; every `checks` bound satisfied.
    """
    problems: list[str] = []
    seen: dict = {}
    for c in report.get("corners") or []:
        k = corner_key(c) if isinstance(c, dict) else None
        if k is None:
            problems.append("malformed corner entry in report")
        elif k in seen:
            problems.append(f"duplicate corner in report: {mx.corner_id(*k)}")
        else:
            seen[k] = c
    want = [mx.key(*p) for p in expected_points]
    for k in sorted(set(seen) - set(want)):
        problems.append(f"unexpected corner in report: {mx.corner_id(*k)}")

    # Fail closed: every configured trim input must be a declared measurement, else the
    # existential check could be silently skipped. One problem, not one per input/corner.
    trim_cfg_missing: list[str] = []
    if tb.get("trim"):
        tc = tb["trim"]
        try:
            trim_cfg_missing = [n for n in (f"{tc['measure_prefix']}{i:02d}_v" for i in range(int(tc["codes"])))
                                if n not in tb["measure"]]
            if int(tc["codes"]) < 1:
                trim_cfg_missing = ["<no trim codes configured>"]
        except (KeyError, TypeError, ValueError):
            trim_cfg_missing = ["<malformed trim block: needs measure_prefix and codes>"]
        if trim_cfg_missing:
            problems.append(f"trim block references undeclared measurement(s) {trim_cfg_missing}; "
                            "best-code analysis cannot run")

    results: list[dict] = []
    for k in want:
        cid = mx.corner_id(*k)
        c = seen.get(k)
        if c is None:
            problems.append(f"{cid}: missing from report")
            results.append({"corner_id": cid, "status": "missing", "measurements": {}})
            continue
        meas = {}
        for m in c.get("measurements") or []:
            if isinstance(m, dict) and m.get("name") in tb["measure"] and _finite(m.get("value")):
                meas[m["name"]] = float(m["value"]) * float(tb["measure"][m["name"]].get("scale", 1.0))
        status = "ok"
        if c.get("status") not in ("pass",):
            status = "failed"
            problems.append(f"{cid}: simulation status {c.get('status')!r}")
        absent = [n for n in tb["measure"] if n not in meas]
        if absent:
            status = "failed"
            problems.append(f"{cid}: missing or non-finite measurement(s) {absent}")
        # Optional existential best-trim evaluation (see harness/trim.py): derived per-code
        # resistances, best code, steps; the corner fails unless some code is inside the window.
        if trim_cfg_missing:
            status = "failed"  # reported once above; best_code is not derived
        elif tb.get("trim"):
            tcfg = tb["trim"]
            raw = [meas.get(f"{tcfg['measure_prefix']}{i:02d}_v") for i in range(int(tcfg["codes"]))]
            # Missing/non-finite code measurements were already reported above; do not repeat.
            derived, tprob = trimmod.analyse(raw, k[2], tcfg) if None not in raw else ({}, [])
            meas.update(derived)
            for tp in tprob:
                status = "failed"
                problems.append(f"{cid}: {tp}")
        for name, rule in (tb.get("checks") or {}).items():
            v = meas.get(name)
            if v is None:
                continue
            if rule.get("per_supply"):
                v = v / k[2]
            if "min" in rule and v < rule["min"]:
                status = "failed"
                problems.append(f"{cid}: {name}={v:g} below min {rule['min']}")
            if "max" in rule and v > rule["max"]:
                status = "failed"
                problems.append(f"{cid}: {name}={v:g} above max {rule['max']}")
            # Strict (exclusive) bounds: an endpoint value is not "strictly inside".
            if "gt" in rule and not v > rule["gt"]:
                status = "failed"
                problems.append(f"{cid}: {name}={v:g} not strictly above {rule['gt']}")
            if "lt" in rule and not v < rule["lt"]:
                status = "failed"
                problems.append(f"{cid}: {name}={v:g} not strictly below {rule['lt']}")
            # Agreement with another measurement of the same corner (e.g. first and last
            # threshold crossing coincide only for a single-crossing, monotonic response).
            same = rule.get("same_as")
            if same:
                other = meas.get(same["measure"])
                if other is None or abs(meas[name] - other) > float(same.get("tol", 0.0)):
                    status = "failed"
                    problems.append(f"{cid}: {name}={meas[name]:g} differs from {same['measure']}="
                                    f"{other if other is None else format(other, 'g')} "
                                    f"by more than {same.get('tol', 0.0)}")
        results.append({"corner_id": cid, "status": status, "measurements": meas})

    for name, rule in (tb.get("checks") or {}).items():
        if "min_spread_pct" not in rule:
            continue
        vals = [r["measurements"][name] / (mx_supply(r["corner_id"]) if rule.get("per_supply") else 1.0)
                for r in results if name in r["measurements"]]
        if len(vals) > 1 and max(vals) > 0:
            spread = (max(vals) - min(vals)) / (sum(vals) / len(vals)) * 100.0
            if spread < rule["min_spread_pct"]:
                problems.append(
                    f"{name} spread {spread:.2f}% < {rule['min_spread_pct']}%: "
                    "corner sections / temperature did not take effect"
                )
    return results, problems


def mx_supply(corner_id: str) -> float:
    """Supply (V) parsed back out of a `<process>_<temp>c_<supply>v` id."""
    return float(corner_id.rsplit("_", 1)[1][:-1])


def job_id(report: dict):
    """The batch job id from the report envelope, or None."""
    remote = (report.get("environment") or {}).get("remote")
    if isinstance(remote, dict):
        for k in ("job_id", "jobId", "id", "batch_job_id"):
            if remote.get(k):
                return str(remote[k])
    elif isinstance(remote, str) and remote:
        return remote
    return None
