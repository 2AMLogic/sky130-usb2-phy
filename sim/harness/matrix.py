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
SCHEMA_V2 = "sky130-usb2-phy.sim.corners/2"

#: The MOS-only process sections of the original matrix (open_pdks sky130A). Every one of them
#: loads the typical resistor/capacitor parameter set (`res_typical__cap_typical`).
SKY130_SECTIONS = ("tt", "ff", "ss", "fs", "sf")

#: MOS corner file selected by each of the five MOS corners.
MOS_CORNERS = ("tt", "sf", "ff", "ss", "fs")

#: Resistor/capacitor parameter-set suffixes of the pinned sky130.lib.spice, and the
#: `r+c/res_<R>__cap_<C>.spice` file each loads. The suffixed sections change the resistor
#: sheet resistance AND the capacitor set AND the drawn-width tolerances (tol_* parameters)
#: together; they are not resistor-only. `tt` has no `tt_<suffix>` spelling in the library:
#: its resistor-set sections are the bare `ll`, `hh`, `hl`, `lh`.
RC_SETS = {
    "": ("typical", "typical"),
    "ll": ("low", "low"),
    "hh": ("high", "high"),
    "hl": ("high", "low"),
    "lh": ("low", "high"),
}


def section_name(mos: str, rc: str) -> str:
    """The sky130.lib.spice `.lib` section for a MOS corner and an r+c set suffix."""
    if not rc:
        return mos
    return rc if mos == "tt" else f"{mos}_{rc}"


def _build_section_map() -> dict[str, tuple[str, str, str]]:
    """section -> (mos corner, resistor set, capacitor set) for every approved section."""
    return {section_name(m, rc): (m, *RC_SETS[rc]) for m in MOS_CORNERS for rc in RC_SETS}


#: Every section a matrix may name, with the parameter sets it must load from the pinned
#: library (verified against the library text by runner.check_env).
SECTION_MAP = _build_section_map()

#: The ONLY approved matrix configurations. A corners file (including the copy frozen inside a
#: historical evidence record) is accepted only if it equals one of these exactly, so a
#: self-declared matrix cannot narrow or redefine the coverage a record claims.
LEGACY_ID = "pvt45-mos"
RESISTOR_SETS_ID = "pvt225-mos-rc"
APPROVED_MATRICES = {
    LEGACY_ID: {
        "schema": SCHEMA, "file": "corners.json",
        "process": frozenset(SKY130_SECTIONS), "temperature_c": (-40.0, 27.0, 100.0),
        "supply_v": (3.0, 3.3, 3.6), "expected_points": 45,
    },
    RESISTOR_SETS_ID: {
        "schema": SCHEMA_V2, "file": "corners-resistor-sets.json",
        "process": frozenset(SECTION_MAP), "temperature_c": (-40.0, 27.0, 100.0),
        "supply_v": (3.0, 3.3, 3.6), "expected_points": 225,
    },
}


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
    matrix_id: str = LEGACY_ID

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
    schema = data.get("schema")
    if schema == SCHEMA:
        matrix_id = LEGACY_ID  # schema /1 predates matrix ids; it is exactly the 45-point matrix
    elif schema == SCHEMA_V2:
        matrix_id = data.get("matrix_id")
    else:
        raise MatrixError(f"corners.json schema must be {SCHEMA!r} or {SCHEMA_V2!r}")
    approved = APPROVED_MATRICES.get(matrix_id)
    if approved is None or approved["schema"] != schema:
        raise MatrixError(f"matrix {matrix_id!r} is not an approved configuration {sorted(APPROVED_MATRICES)}")
    try:
        matrix = Matrix(
            pdk=dict(data["pdk"]),
            process=tuple(data["process"]),
            temperature_c=tuple(float(t) for t in data["temperature_c"]),
            supply_v=tuple(float(v) for v in data["supply_v"]),
            supply_source=str(data["supply_source"]),
            expected_points=int(data["expected_points"]),
            matrix_id=matrix_id,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise MatrixError(f"malformed corners.json: {exc!r}") from exc
    bad = [p for p in matrix.process if p not in SECTION_MAP]
    if bad:
        raise MatrixError(f"not an approved sky130 corner section: {bad}")
    pts = matrix.points()
    if len({key(*p) for p in pts}) != len(pts):
        raise MatrixError("corners.json axes contain duplicate values")
    if len(pts) != matrix.expected_points:
        raise MatrixError(f"corners.json expands to {len(pts)} points, expected {matrix.expected_points}")
    if matrix.pdk.get("name") != "sky130A" or matrix.pdk.get("lib") != "libs.tech/ngspice/sky130.lib.spice":
        raise MatrixError("corners.json must name the sky130A libs.tech/ngspice/sky130.lib.spice model library")
    # Exact coverage: the declared axes must be the approved ones (no omitted section, no extra).
    if (set(matrix.process) != approved["process"]
            or sorted(matrix.temperature_c) != list(approved["temperature_c"])
            or sorted(matrix.supply_v) != list(approved["supply_v"])
            or matrix.expected_points != approved["expected_points"]
            or matrix.supply_source != "vsup"):
        raise MatrixError(f"corners.json does not equal the approved {matrix_id!r} configuration "
                          f"(process {sorted(set(matrix.process) ^ approved['process'])} differ)")
    return matrix


def load(path: Path = CORNERS_JSON) -> Matrix:
    """The original 45-point matrix by default; any approved file by path."""
    data = json.loads(Path(path).read_text())
    return from_dict(data)


def load_by_id(matrix_id: str) -> Matrix:
    """The approved matrix with this id, from its file next to sim/corners.json."""
    if matrix_id not in APPROVED_MATRICES:
        raise MatrixError(f"matrix {matrix_id!r} is not approved {sorted(APPROVED_MATRICES)}")
    path = CORNERS_JSON if matrix_id == LEGACY_ID else SIM_DIR / APPROVED_MATRICES[matrix_id]["file"]
    matrix = load(path)
    if matrix.matrix_id != matrix_id:
        raise MatrixError(f"{path.name} declares {matrix.matrix_id!r}, expected {matrix_id!r}")
    return matrix


def check_request(request: dict, matrix: Matrix) -> list[str]:
    """Problems with a resolved `klt sim` request relative to the matrix.

    Empty list means: sky130A model library, only matrix corner sections, and
    exactly the matrix's unique (process, temperature, supply) tuples. This
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
