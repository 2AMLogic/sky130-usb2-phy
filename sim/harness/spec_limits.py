"""Spec-row `measurements[].limits` for the `klt sim` request (issue #401).

The grader credits a corner row only for a bound `klt sim` itself checked: an
envelope whose request declared no `limits` grades `no_limits_checked` however
the harness's own post-hoc records read. This module puts the ratified spec
bounds into the request, generated from the row table rather than hand-copied
per bench:

- `ROW_BOUNDS` holds each row's numeric bounds once, keyed by row id and a role
  name (one row can carry several bounds: 6-04 has VOH and VOL), each with the
  spec words it is transcribed from. The row table
  `signoff/spec/analog-rows.json` (which pins the spec markdown by content
  hash) is read at apply time: a mapping onto a row the table no longer
  declares fails closed instead of silently emitting stale limits.
- `BENCH_ROWS` maps each bench's measurement names to `(row id, role)`. The
  numbers live only in `ROW_BOUNDS`; a bench references a row, never a value.
- A mapped measurement must carry an equivalent numeric check in tb.json: the
  cross-check (the harness re-derives the verdict post-hoc and the record
  states both) needs the harness bound, and requiring equality keeps the
  request's limits and the tb.json checks from drifting apart. Checks with no
  request equivalent (`per_supply`, `same_as`, `min_spread_pct`) or with
  drifted numbers are refused.

klt applies `min`/`max` inclusively to the **raw** measurement value (before
tb.json `scale`), so bounds are divided by the measurement's scale on emit and
strict tb.json bounds (`gt`/`lt`) become inclusive endpoints: a value exactly
on such an endpoint would pass the envelope and fail the harness cross-check,
and that disagreement is surfaced per corner by the runner, never absorbed.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import matrix as mx, results as rs

#: The ratified analog row table (pins spec/usb2-phy.md section 6 by hash).
ROWS_FILE = mx.REPO_ROOT / "signoff" / "spec" / "analog-rows.json"

#: Request-feature keys a mapped measurement's tb.json check may use.
_CHECK_KEYS = {"min", "max", "gt", "lt"}


class SpecLimitError(ValueError):
    pass


#: Numeric bounds per ratified row, transcribed from the row's requirement text
#: in spec/usb2-phy.md section 6 (as pinned by ROWS_FILE). Units are the
#: tb.json `scale`d (display) units the harness checks; `apply` converts to
#: raw request units. Roles without a unit are pure ratios.
ROW_BOUNDS: dict[str, dict[str, dict]] = {
    # "output voltage swing, static - VOH 2.8-3.6 V (1.5 kOhm pull-up to 3.6 V), VOL 0.0-0.3 V"
    "6-04": {
        "voh": {"min": 2.8, "max": 3.6, "unit": "V"},
        "vol": {"min": 0.0, "max": 0.3, "unit": "V"},
    },
    # "driver output resistance 28-44 Ohm"
    "6-05": {
        "rout": {"min": 28.0, "max": 44.0, "unit": "ohm"},
    },
    # "rise/fall time 4-20 ns (10%-90%), matched to within 10% rise vs. fall"
    "6-06": {
        "tr": {"min": 4.0, "max": 20.0, "unit": "ns"},
        "tr_match": {"min": 0.9, "max": 1.1},
    },
    # "output signal crossover voltage 1.3-2.0 V"
    "6-07": {
        "vcross": {"min": 1.3, "max": 2.0, "unit": "V"},
    },
    # "differential input sensitivity |(D+) - (D-)| > 200 mV": the input-referred
    # differential threshold magnitude must stay below 200 mV
    "6-09": {
        "vth_diff": {"min": -0.2, "max": 0.2, "unit": "V"},
    },
    # "single-ended receiver thresholds VIH > 2.0 V, VIL < 0.8 V": the switching
    # threshold must sit inside the VIL(max)..VIH(min) window (tb.json checks it strictly)
    "6-11": {
        "vth_se": {"min": 0.8, "max": 2.0, "unit": "V"},
    },
    # "FS device D+ pull-up 1.5 kOhm +/-5%": 1.425-1.575 kohm. Two roles for the
    # trim-code existential ("at least one code inside", a different code may be
    # chosen per corner): the smallest per-code effective resistance must reach
    # the window's floor and the largest must reach its ceiling. R_eff is
    # strictly decreasing in V(DP), so these are the resistances at the
    # maximum- and minimum-V(DP) codes respectively.
    "6-14": {
        "r_eff_min": {"min": 1425.0, "unit": "ohm"},
        "r_eff_max": {"max": 1575.0, "unit": "ohm"},
    },
}

#: Bench -> measurement name -> (row id, role). A bench lands here together
#: with its limit-carrying re-run (one bench per PR, issue #401 Part A).
BENCH_ROWS: dict[str, dict[str, tuple[str, str]]] = {
    "driver-static": {
        "voh_dp_v": ("6-04", "voh"),
        "voh15_dp_v": ("6-04", "voh"),
        "voh_dm_v": ("6-04", "voh"),
        "voh15_dm_v": ("6-04", "voh"),
        "vol_dp_v": ("6-04", "vol"),
        "vol_dm_v": ("6-04", "vol"),
        "rout_high_dp_ohm": ("6-05", "rout"),
        "rout_low_dp_ohm": ("6-05", "rout"),
        "rout_high_dm_ohm": ("6-05", "rout"),
        "rout_low_dm_ohm": ("6-05", "rout"),
    },
    # rise/fall per line and edge direction, the four rise/fall matching ratios
    # (same line and cross-line), and the crossover voltage per edge direction
    "driver-signal-quality": {
        "trise_dp_ns": ("6-06", "tr"),
        "tfall_dp_ns": ("6-06", "tr"),
        "trise_dm_ns": ("6-06", "tr"),
        "tfall_dm_ns": ("6-06", "tr"),
        "trf_dp_ratio": ("6-06", "tr_match"),
        "trf_dm_ratio": ("6-06", "tr_match"),
        "trf_x1_ratio": ("6-06", "tr_match"),
        "trf_x2_ratio": ("6-06", "tr_match"),
        "vcross_rise_v": ("6-07", "vcross"),
        "vcross_fall_v": ("6-07", "vcross"),
    },
}


def load_rows(path: str | Path | None = None) -> dict[str, dict]:
    """The ratified row table as {row id: row}. Fails closed on anything else."""
    p = Path(path) if path is not None else ROWS_FILE
    try:
        doc = json.loads(p.read_text())
    except (OSError, ValueError) as exc:
        raise SpecLimitError(f"row table {p} unreadable ({exc})") from exc
    if not isinstance(doc, dict) or doc.get("status") != "ratified":
        raise SpecLimitError(f"row table {p} is not a ratified rows document")
    rows = {r["id"]: r for r in doc.get("rows") or [] if isinstance(r, dict) and r.get("id")}
    if not rows:
        raise SpecLimitError(f"row table {p} declares no rows")
    return rows


def _check_endpoints(name: str, check) -> dict[str, float]:
    """The numeric endpoints of a tb.json check, as {bound: value}.

    `gt`/`lt` are accepted as the strict spelling of `min`/`max`; any other
    check shape (`per_supply`, `same_as`, `min_spread_pct`, ...) has no request
    equivalent and is refused.
    """
    where = f"{name}"
    if not isinstance(check, dict) or not check:
        raise SpecLimitError(f"{where}: no tb.json check; a spec-limit measurement needs "
                             "the equivalent harness bound to cross-check")
    extra = set(check) - _CHECK_KEYS
    if extra:
        raise SpecLimitError(f"{where}: tb.json check uses {sorted(extra)}, which has no "
                             "request equivalent (klt limits are absolute min/max)")
    out: dict[str, float] = {}
    for strict, inclusive in (("gt", "min"), ("lt", "max")):
        if strict in check:
            out[inclusive] = float(check[strict])
    for k in ("min", "max"):
        if k in check:
            out[k] = float(check[k])
    if not out:
        raise SpecLimitError(f"{where}: tb.json check carries no numeric bound")
    return out


def _require_equivalent(name: str, bounds: dict, check) -> None:
    """The tb.json check must carry exactly the row's numbers (scaled units)."""
    got = _check_endpoints(name, check)
    for side in ("min", "max"):
        want = bounds.get(side)
        if want is None:
            if side in got:
                raise SpecLimitError(f"{name}: tb.json check bounds {side}={got[side]:g} but "
                                     f"row role does not (drift between spec row and tb.json)")
        elif side not in got:
            raise SpecLimitError(f"{name}: tb.json check lacks the row's {side} bound {want:g}")
        elif got[side] != float(want):
            raise SpecLimitError(f"{name}: tb.json check {side}={got[side]:g} differs from the "
                                 f"ratified row bound {want:g}; relax neither, reconcile the drift")


def measurement_limits(experiment: str, tb: dict, rows: dict | None = None) -> dict[str, dict]:
    """{measurement name: {"row", "role", "limits", "display_limits", "scale",
    ["unit"]}} for a mapped bench.

    `limits` is raw (what `klt sim` grades, pre-scale); `display_limits` is the
    row's own numbers in the tb.json `scale`d unit the `unit` string names.
    `unit` describes `display_limits`, so it may only be emitted beside `limits`
    when raw == display (scale 1.0).

    `{}` for a bench with no mapping (its requests are unchanged). Fails closed
    (`SpecLimitError`) when the mapping references a row the table does not
    declare, a measurement the testbench does not define, or a tb.json check
    that is not the row's own numbers.
    """
    mapping = BENCH_ROWS.get(experiment)
    if not mapping:
        return {}
    if rows is None:
        rows = load_rows()
    measure = tb.get("measure") or {}
    checks = tb.get("checks") or {}
    out: dict[str, dict] = {}
    for name, (row, role) in sorted(mapping.items()):
        if row not in rows:
            raise SpecLimitError(f"{experiment}/{name}: maps to row {row}, which the row "
                                 f"table {ROWS_FILE} does not declare")
        try:
            bounds = ROW_BOUNDS[row][role]
        except KeyError as exc:
            raise SpecLimitError(f"{experiment}/{name}: no role {role!r} under row {row}") from exc
        if name not in measure:
            raise SpecLimitError(f"{experiment}/{name}: not declared in the testbench's "
                                 "`measure`; the mapping is stale")
        _require_equivalent(f"{experiment}/{name}", bounds, checks.get(name))
        scale = float(measure[name].get("scale", 1.0))
        if scale <= 0:
            raise SpecLimitError(f"{experiment}/{name}: non-positive scale {scale}")
        # klt grades the raw (pre-scale) value: convert the row bounds to raw
        # units, keeping the row's own numbers (the display-unit bounds the
        # `unit` string names) for the record's limits column.
        limits = {k: float(v) / scale for k, v in bounds.items() if k in ("min", "max")}
        entry = {"row": row, "role": role, "limits": limits, "scale": scale,
                 "display_limits": {k: float(v) for k, v in bounds.items() if k in ("min", "max")}}
        if bounds.get("unit"):
            entry["unit"] = bounds["unit"]
        out[name] = entry
    return out


def apply(request: dict, experiment: str, tb: dict, rows: dict | None = None) -> dict[str, dict]:
    """Write `limits` (and `unit`) into a built request's measurements, in place.

    Returns the mapping `measurement_limits` produced (empty for an unmapped
    bench, whose request is left untouched).

    `unit` names the display (scaled) unit, so it is only written when raw ==
    display (scale 1.0); beside non-unity-scale raw `limits` it would misstate
    the numbers by the scale factor, and no raw-unit name is derivable from
    tb.json or the request builder (measurements carry `spice` and `scale`
    only) -- so the measurement's own `unit`, if any, is left untouched.
    """
    mapping = measurement_limits(experiment, tb, rows)
    if not mapping:
        return {}
    have = {m.get("name"): m for m in request.get("measurements") or []}
    for name, entry in mapping.items():
        m = have.get(name)
        if m is None:
            raise SpecLimitError(f"{experiment}/{name}: not in the built request's measurements")
        m["limits"] = dict(entry["limits"])
        if entry.get("unit") and entry["scale"] == 1.0:
            m.setdefault("unit", entry["unit"])
    return mapping


def _harness_verdict(check, value: float) -> bool | None:
    """The tb.json check re-applied to one scaled value (mirrors rs.evaluate)."""
    if value is None or not isinstance(check, dict):
        return None
    if "min" in check and not value >= check["min"]:
        return False
    if "max" in check and not value <= check["max"]:
        return False
    if "gt" in check and not value > check["gt"]:
        return False
    if "lt" in check and not value < check["lt"]:
        return False
    return True


def cross_check(report: dict, results: list[dict], tb: dict, mapping: dict[str, dict]) \
        -> tuple[list[str], dict]:
    """Envelope-vs-harness verdict agreement for every limited measurement.

    For each corner and each mapped measurement: the envelope's own limit
    verdict (the per-measurement `status` `klt sim` graded) must equal the
    harness's post-hoc re-check of the same bound on the scaled value. Any
    disagreement is returned as a problem string (the runner fails the record
    on it); the summary counts per measurement feed the record's cross-check
    table. A per-measurement envelope status other than pass/fail (e.g. an
    error) is itself a problem whatever the harness says -- the check fails
    closed on a status it did not enumerate.
    """
    envelope: dict[str, dict[str, str]] = {}
    for c in report.get("corners") or []:
        if not isinstance(c, dict):
            continue
        # key by the matrix tuple, not the report's own corner_id spelling: the
        # results side carries mx.corner_id(...) ids (tt_27c_3.30v) while a klt
        # report spells them differently (tt/3.300V/27C)
        k = rs.corner_key(c)
        if k is None:
            continue
        envelope[mx.corner_id(*k)] = {m.get("name"): m.get("status")
                                      for m in c.get("measurements") or [] if isinstance(m, dict)}
    checks = tb.get("checks") or {}
    problems: list[str] = []
    summary = {name: {"envelope": {"pass": 0, "fail": 0}, "harness": {"pass": 0, "fail": 0},
                      "disagree": 0} for name in mapping}
    for r in results:
        cid = r["corner_id"]
        for name in mapping:
            klt = envelope.get(cid, {}).get(name)
            har = _harness_verdict(checks.get(name), r["measurements"].get(name))
            if klt in ("pass", "fail"):
                summary[name]["envelope"][klt] += 1
            if har is not None:
                summary[name]["harness"]["pass" if har else "fail"] += 1
            if klt in ("pass", "fail") and har is not None and (klt == "pass") != har:
                summary[name]["disagree"] += 1
                v = r["measurements"].get(name)
                problems.append(f"{cid}: {name}={v if v is None else format(v, 'g')} envelope "
                                f"limit verdict {klt!r} disagrees with the harness cross-check "
                                f"({'inside' if har else 'outside'} tb.json bounds)")
            elif klt is None and har is not None:
                problems.append(f"{cid}: {name} graded by the harness but the envelope reports "
                                "no limit verdict for it")
            elif klt is not None and klt not in ("pass", "fail"):
                problems.append(f"{cid}: {name} envelope limit status {klt!r} is neither "
                                "'pass' nor 'fail'")
    return problems, summary


def render_cross(summary: dict[str, dict], mapping: dict[str, dict]) -> list[str]:
    """The record's cross-check table: per measurement, both verdicts and the disagreement count.

    The limits column prints `display_limits` -- the row's ratified numbers in
    the unit the `unit` string names -- never the raw request `limits` those
    entries carry for grading (which the scale converts).
    """
    lines = ["| measurement | row | limits | envelope pass/fail | harness pass/fail | disagreements |",
             "|---|---|---|---|---|---|"]
    for name in sorted(summary):
        entry = mapping[name]
        b = entry.get("display_limits") or entry["limits"]
        parts = []
        if "min" in b:
            parts.append(f">= {b['min']:g}")
        if "max" in b:
            parts.append(f"<= {b['max']:g}")
        window = " and ".join(parts) + (f" {entry['unit']}" if entry.get("unit") else "")
        s = summary[name]
        lines.append(f"| `{name}` | {entry['row']} | {window or '(none)'} | "
                     f"{s['envelope']['pass']}/{s['envelope']['fail']} | "
                     f"{s['harness']['pass']}/{s['harness']['fail']} | {s['disagree']} |")
    return lines
