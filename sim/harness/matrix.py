"""The one canonical PVT matrix: sim/corners.json.

Request generation, `--list`, record lint and the tests all expand the grid
through :func:`points`; there is no second hardcoded grid anywhere.
"""

from __future__ import annotations

import itertools
import json
from dataclasses import dataclass
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SIM_DIR.parent
CORNERS_JSON = SIM_DIR / "corners.json"
SCHEMA = "sky130-usb2-phy.sim.corners/1"

#: The only process sections the matrix may name (open_pdks sky130A MOS corners).
SKY130_SECTIONS = ("tt", "ff", "ss", "fs", "sf")


class MatrixError(ValueError):
    pass


@dataclass(frozen=True)
class Matrix:
    pdk: dict
    process: tuple[str, ...]
    temperature_c: tuple[float, ...]
    supply_v: tuple[float, ...]
    supply_source: str
    expected_points: int

    def points(self) -> list[tuple[str, float, float]]:
        return [
            (p, float(t), float(v))
            for p, t, v in itertools.product(self.process, self.temperature_c, self.supply_v)
        ]


def corner_id(process: str, temp_c: float, vdd: float) -> str:
    """`<process>_<temp>c_<supply>v`, e.g. `ss_-40c_3.00v`."""
    return f"{process}_{temp_c:g}c_{vdd:.2f}v"


def key(process: str, temp_c: float, vdd: float) -> tuple[str, float, float]:
    return (str(process), round(float(temp_c), 6), round(float(vdd), 6))


def from_dict(data: dict) -> Matrix:
    if data.get("schema") != SCHEMA:
        raise MatrixError(f"corners.json schema must be {SCHEMA!r}")
    try:
        matrix = Matrix(
            pdk=dict(data["pdk"]),
            process=tuple(data["process"]),
            temperature_c=tuple(float(t) for t in data["temperature_c"]),
            supply_v=tuple(float(v) for v in data["supply_v"]),
            supply_source=str(data["supply_source"]),
            expected_points=int(data["expected_points"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise MatrixError(f"malformed corners.json: {exc!r}") from exc
    pts = matrix.points()
    if len({key(*p) for p in pts}) != len(pts):
        raise MatrixError("corners.json axes contain duplicate values")
    if len(pts) != matrix.expected_points:
        raise MatrixError(f"corners.json expands to {len(pts)} points, expected {matrix.expected_points}")
    bad = [p for p in matrix.process if p not in SKY130_SECTIONS]
    if bad:
        raise MatrixError(f"not a sky130 MOS corner section: {bad}")
    return matrix


def load(path: Path = CORNERS_JSON) -> Matrix:
    return from_dict(json.loads(Path(path).read_text()))


def check_request(request: dict, matrix: Matrix) -> list[str]:
    """Problems with a resolved `klt sim` request relative to the matrix.

    Empty list means: sky130A model library, only matrix corner sections, and
    exactly the matrix's 45 unique (process, temperature, supply) tuples. This
    is what rejects an inherited gf180 request (sm141064, `typical`, 125 C,
    +/-10 % supply).
    """
    problems: list[str] = []
    models = request.get("models") or {}
    if models.get("pdk") != matrix.pdk["name"]:
        problems.append(f"models.pdk is {models.get('pdk')!r}, expected {matrix.pdk['name']!r}")
    if models.get("lib") != matrix.pdk["lib"]:
        problems.append(f"models.lib is {models.get('lib')!r}, expected {matrix.pdk['lib']!r}")
    corners = request.get("corners") or {}
    process = corners.get("process")
    supply = corners.get("supply_v")
    temps = corners.get("temperature_c")
    if not isinstance(process, list) or not all(isinstance(p, str) for p in process):
        problems.append("corners.process must be a list of bare sky130 section names")
        process = []
    if not isinstance(supply, dict) or set(supply) != {matrix.supply_source}:
        problems.append(f"corners.supply_v must sweep exactly {matrix.supply_source!r}")
        supply_values = []
    else:
        supply_values = supply[matrix.supply_source]
    if not isinstance(temps, list):
        problems.append("corners.temperature_c must be a list")
        temps = []
    try:
        got = [key(p, t, v) for p, t, v in itertools.product(process, temps, supply_values)]
    except (TypeError, ValueError):
        problems.append("corners axes must be numeric lists")
        got = []
    want = [key(*p) for p in matrix.points()]
    if len(set(got)) != len(got):
        problems.append("request contains duplicate corner tuples")
    if set(got) != set(want):
        problems.append(
            f"request tuples differ from corners.json: missing {sorted(set(want) - set(got))[:3]}"
            f" extra {sorted(set(got) - set(want))[:3]}"
        )
    return problems
