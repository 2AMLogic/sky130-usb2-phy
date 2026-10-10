"""Toolchain-free tests for resistor-set (sheet-resistance) corner coverage (#126).

No klt, ngspice or PDK: the library text is synthetic and `klt sim` is a stub. They prove the
approved-matrix policy (a self-declared matrix is rejected), the 225-point expansion, the
section -> parameter-set mapping check, variant resolution that cannot relax a bound, and that
the lint validates new 225-point records and legacy 45-point records each against their own
frozen, approved matrix. They say nothing about the circuit; that is the recorded batch run.
"""

import copy
import json
import re
import shutil
from pathlib import Path

import pytest

from harness import evidence_lint as lint, matrix as mx, results as rs, runner

SIM = Path(__file__).resolve().parents[1]
EXP = SIM / "dplus-pullup-tolerance"
TB = json.loads((EXP / "testbench/tb.json").read_text())
LEGACY = mx.load()
RES = mx.load_by_id(mx.RESISTOR_SETS_ID)
VTB = rs.resolve_tb(TB, "resistor-sets")
RL = 15000.0


def test_resistor_matrix_is_225_unique_points_over_25_sections():
    pts = RES.points()
    assert len(pts) == len({mx.key(*p) for p in pts}) == 225 == RES.expected_points
    assert len(set(RES.process)) == 25 and set(RES.process) == set(mx.SECTION_MAP)
    # every MOS corner is crossed with every resistor/capacitor set, plus typical
    assert {(m, r, c) for m, r, c in mx.SECTION_MAP.values()} == {
        (m, *rc) for m in mx.MOS_CORNERS for rc in mx.RC_SETS.values()}
    assert RES.matrix_id == mx.RESISTOR_SETS_ID and LEGACY.matrix_id == mx.LEGACY_ID
    assert set(LEGACY.process) <= set(RES.process) and len(LEGACY.points()) == 45
    assert set(RES.temperature_c) == set(LEGACY.temperature_c) and set(RES.supply_v) == set(LEGACY.supply_v)


def test_bare_suffix_sections_carry_the_tt_mos_corner():
    assert mx.SECTION_MAP["hh"] == ("tt", "high", "high") and mx.SECTION_MAP["ss_hl"] == ("ss", "high", "low")
    assert mx.SECTION_MAP["lh"] == ("tt", "low", "high") and mx.SECTION_MAP["ff"] == ("ff", "typical", "typical")


def _data(matrix_file="corners-resistor-sets.json"):
    return json.loads((SIM / matrix_file).read_text())


@pytest.mark.parametrize("mutate,needle", [
    (lambda d: d["process"].append("tt_xx"), "not an approved"),
    (lambda d: d["process"].remove("hh"), "expands to"),          # omitted resistor set
    (lambda d: d["process"].append("tt"), "duplicate"),          # duplicate tuples
    (lambda d: d.update(matrix_id="self-declared"), "not an approved"),
    (lambda d: d.update(schema="sky130-usb2-phy.sim.corners/9"), "schema"),
    (lambda d: d.update(supply_v=[3.0, 3.6]), "expands to"),
    (lambda d: d.update(temperature_c=[-40.0, 27.0, 125.0]), "approved"),
    (lambda d: d.update(supply_v=[2.97, 3.3, 3.63]), "approved"),
    (lambda d: d["pdk"].update(name="gf180mcuD"), "sky130A"),
    (lambda d: d.update(supply_source="vdd"), "approved"),
])
def test_unapproved_or_incomplete_matrices_are_rejected(mutate, needle):
    d = _data()
    mutate(d)
    with pytest.raises(mx.MatrixError, match=needle):
        mx.from_dict(d)


def test_a_shrunk_matrix_cannot_claim_the_approved_id_even_if_self_consistent():
    d = _data()
    d["process"] = [p for p in d["process"] if p not in ("hh", "sf_hh", "ff_hh", "ss_hh", "fs_hh")]
    d["expected_points"] = len(d["process"]) * 9
    with pytest.raises(mx.MatrixError, match="approved"):
        mx.from_dict(d)


def test_legacy_45_point_schema_stays_valid_and_cannot_smuggle_resistor_sections():
    assert mx.from_dict(_data("corners.json")).matrix_id == mx.LEGACY_ID
    d = _data("corners.json")
    d["process"][0] = "hh"
    with pytest.raises(mx.MatrixError):
        mx.from_dict(d)
    d = _data("corners.json")
    d["process"] += ["ll"]
    d["expected_points"] = 54
    with pytest.raises(mx.MatrixError):
        mx.from_dict(d)


def test_request_must_equal_the_selected_matrix():
    req = rs.build_request(VTB, RES, backend="batch")
    assert mx.check_request(req, RES) == []
    assert any("differ" in p for p in mx.check_request(req, LEGACY))  # not the 45-point matrix
    short = copy.deepcopy(req)
    short["corners"]["process"].remove("lh")
    assert any("missing" in p for p in mx.check_request(short, RES))
    dup = copy.deepcopy(req)
    dup["corners"]["process"].append("hh")
    assert any("duplicate" in p for p in mx.check_request(dup, RES))
    base = rs.build_request(rs.resolve_tb(TB), LEGACY, backend="batch")
    assert any("extra" in p or "differ" in p for p in mx.check_request(base, RES))


# ---- section mapping against the (synthetic) library text

def _lib(tmp_path, broken=None):
    lines = []
    for sec, (mos, res, cap) in mx.SECTION_MAP.items():
        inc = runner.expected_includes(sec)
        if sec == broken:
            inc = [i.replace("res_high", "res_typical") for i in inc]
        lines += [f".lib {sec}", ".param mc_mm_switch=0"] + [f'.include "{i}"' for i in inc] + [f".endl {sec}", ""]
    p = tmp_path / "sky130.lib.spice"
    p.write_text("\n".join(lines))
    return p


def test_section_mapping_is_checked_against_the_library(tmp_path):
    ev, bad = runner.section_evidence(_lib(tmp_path), RES.process)
    assert bad == [] and ev["ss_hl"]["includes"][1] == "r+c/res_high__cap_low.spice"
    ev, bad = runner.section_evidence(_lib(tmp_path, broken="hh"), RES.process)
    assert len(bad) == 1 and bad[0].startswith("hh:")
    ev, bad = runner.section_evidence(_lib(tmp_path), ["tt", "zz"] if False else RES.process[:2])
    assert bad == []


def test_a_section_missing_from_the_library_is_a_mismatch(tmp_path):
    lib = _lib(tmp_path)
    lib.write_text(lib.read_text().replace(".lib lh\n", ".lib lh_renamed\n").replace(".endl lh\n", ".endl lh_renamed\n"))
    _, bad = runner.section_evidence(lib, RES.process)
    assert any(b.startswith("lh:") for b in bad)


def test_pinned_library_mapping_if_installed():
    pdk = runner.find_pdk_dir("sky130A")
    if pdk is None:
        pytest.skip("sky130A not installed here")
    lib = pdk / RES.pdk["lib"]
    if runner.sha256_file(lib) != RES.pdk["lib_sha256"]:
        pytest.skip("installed library is not the pinned one")
    assert runner.section_evidence(lib, RES.process)[1] == []


# ---- variants

def test_variant_selects_the_matrix_and_cannot_relax_a_bound():
    assert rs.tb_matrix_id(TB) == mx.LEGACY_ID and rs.tb_matrix_id(TB, "resistor-sets") == mx.RESISTOR_SETS_ID
    for k in ("trim", "checks", "measure", "analysis", "netlist", "include"):
        assert VTB[k] == TB[k]
    assert (VTB["trim"]["lo_ohm"], VTB["trim"]["hi_ohm"], VTB["trim"]["target_ohm"]) == (1425, 1575, 1500)
    assert "variants" not in VTB and "225" in VTB["claim"] and "45-point" not in VTB["claim"]
    assert VTB["record"]["method"][:2] == TB["record"]["method"][:2]
    with pytest.raises(rs.VariantError):
        rs.resolve_tb(TB, "nope")
    bad = copy.deepcopy(TB)
    bad["variants"]["resistor-sets"]["trim"] = {"lo_ohm": 1000}
    with pytest.raises(rs.VariantError, match="may not override"):
        rs.resolve_tb(bad, "resistor-sets")


# ---- mocked batch run of the variant, and the lint

def v_of(r, vpu):
    return vpu * RL / (RL + r)


def fake_report(matrix, tamper=None):
    rep_corners = []
    for p, t, v in matrix.points():
        _, res, _ = mx.SECTION_MAP[p]
        rscale = {"typical": 1.0, "low": 0.9, "high": 1.1}[res] * (1.0 + (t - 27.0) * 0.0009)
        vals = {f"vdp_c{k:02d}_v": v_of((1950.0 - 52.0 * k) * rscale, v) for k in range(16)}
        vals.update({"voff_d1_v": 2e-6, "voff_d0_v": 2e-6, "ioff_d1_na": 0.1, "ioff_d0_na": 0.1,
                     "ioff_dz_na": 0.1, "ioff_dh_na": -0.001, "isup_d1_na": 0.1, "isup_d0_na": 0.1,
                     "isup_dz_na": 0.1, "isup_dh_na": 0.01})
        rep_corners.append({
            "corner_id": f"{p}/{v:.3f}V/{t:g}C", "process": p, "supply_v": {"vsup": v},
            "temperature_c": float(t), "status": "pass",
            "measurements": [{"name": n, "value": x / float(TB["measure"][n].get("scale", 1.0)), "status": "pass"}
                             for n, x in vals.items()],
            "artifacts": {"log": None}})
    rep = {"status": "pass", "corners": rep_corners,
           "environment": {"engine_version": "46", "remote": {"job_id": "klt-sim-test"},
                           "models_lib_sha256": matrix.pdk["lib_sha256"], "netlist_sha256": "x"},
           "provenance": {"pdk": {"version": "open_pdks " + matrix.pdk["open_pdks_commit"]}}}
    if tamper:
        tamper(rep)
    return rep


def test_good_225_report_passes_and_missing_resistor_set_fails():
    results, problems = rs.evaluate(fake_report(RES), RES.points(), VTB)
    assert problems == [] and len(results) == 225
    _, problems = rs.evaluate(fake_report(RES, lambda r: r["corners"].__setitem__(
        slice(None), [c for c in r["corners"] if c["process"] != "hh"])), RES.points(), VTB)
    assert sum("missing from report" in p for p in problems) == 9
    # incomplete trim-code data in one resistor-set corner fails closed
    def drop_code(r):
        c = next(c for c in r["corners"] if c["process"] == "sf_lh")
        c["measurements"] = [m for m in c["measurements"] if m["name"] != "vdp_c07_v"]
    _, problems = rs.evaluate(fake_report(RES, drop_code), RES.points(), VTB)
    assert any("vdp_c07_v" in p for p in problems)


def test_no_passing_code_at_a_resistor_corner_is_a_failure_not_relaxed():
    def high_r(r):
        for c in r["corners"]:
            if c["process"] == "hl" and c["temperature_c"] == 100.0 and c["supply_v"]["vsup"] == 3.0:
                for m in c["measurements"]:
                    if m["name"].startswith("vdp_c"):
                        k = int(m["name"][5:7])
                        m["value"] = v_of(1700.0 - k * 3, 3.0)
    _, problems = rs.evaluate(fake_report(RES, high_r), RES.points(), VTB)
    assert any("hl_100c_3.00v" in p and "no trim code inside [1425, 1575]" in p for p in problems)


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    sim = tmp_path / "sim"
    sim.mkdir()
    shutil.copytree(EXP, sim / EXP.name, ignore=shutil.ignore_patterns("records", "corners", "netlist-snapshots", "__pycache__"))
    shutil.copytree(EXP / "records", sim / EXP.name / "records")
    shutil.copytree(EXP / "corners", sim / EXP.name / "corners")
    shutil.copytree(EXP / "netlist-snapshots", sim / EXP.name / "netlist-snapshots")
    (tmp_path / "design/netlist").mkdir(parents=True)
    shutil.copy(SIM.parent / "design/netlist/dplus_pullup.spice", tmp_path / "design/netlist/dplus_pullup.spice")
    for f in ("corners.json", "corners-resistor-sets.json"):
        shutil.copy(SIM / f, sim / f)
    monkeypatch.setattr(mx, "SIM_DIR", sim)
    monkeypatch.setattr(mx, "CORNERS_JSON", sim / "corners.json")
    monkeypatch.setattr(runner, "WORK_DIR", tmp_path / "work")

    def env(m):
        ev, bad = runner.section_evidence(_lib(tmp_path), m.process)
        assert bad == []
        return {"open_pdks_commit": m.pdk["open_pdks_commit"], "lib_sha256": m.pdk["lib_sha256"], "sections": ev}

    monkeypatch.setattr(runner, "check_env", env)

    def fake(request_path, outdir, backend, workdir):
        req = json.loads(Path(request_path).read_text())
        mat = RES if len(req["corners"]["process"]) == 25 else LEGACY
        rep = fake_report(mat)
        for c in rep["corners"]:
            log = tmp_path / f"{c['process']}{c['temperature_c']}{c['supply_v']['vsup']}.log"
            log.write_text("ngspice log\n")
            c["artifacts"] = {"log": str(log)}
        rep["environment"]["netlist_sha256"] = runner.sha256_bytes((workdir / "body.spice").read_bytes())
        return rep, "", 0

    monkeypatch.setattr(runner, "invoke_klt", fake)
    return sim


def _new_rid(sim):
    recs = sorted((sim / EXP.name / "records").glob("*.md"))
    old = {p.stem for p in recs}
    return old


def test_variant_run_writes_a_225_point_record_the_lint_accepts(sandbox):
    before = _new_rid(sandbox)
    assert lint.lint_all(sandbox) == []  # legacy 45-point records validate against their own matrix
    assert runner.run("dplus-pullup-tolerance", "batch", True, {}, variant="resistor-sets") == 0
    new = sorted({p.stem for p in (sandbox / EXP.name / "records").glob("*.md")} - before)
    assert len(new) == 1
    rid = new[0]
    rec = (sandbox / EXP.name / "records" / f"{rid}.md").read_text()
    assert "225 points" in rec and "sim/corners-resistor-sets.json" in rec and "pvt225-mos-rc" in rec
    assert "- **Status**: PASS" in rec and "225 unique" not in rec
    assert lint.lint_all(sandbox) == []
    cdir = sandbox / EXP.name / "corners" / rid
    man = json.loads((cdir / "evidence.json").read_text())
    assert man["variant"] == "resistor-sets" and man["matrix_id"] == mx.RESISTOR_SETS_ID
    assert man["sections"]["ss_hl"]["resistor_set"] == "high" and len(man["sections"]) == 25
    assert len([n for n in man["files"] if n.endswith(".log")]) == 225


def _reseal(sim, rid, edit):
    """Apply `edit(cdir)` then re-seal every hash so only the semantic check can catch it."""
    cdir = sim / EXP.name / "corners" / rid
    edit(cdir)
    m = json.loads((cdir / "evidence.json").read_text())
    for name in m["files"]:
        m["files"][name] = lint.sha256_file(cdir / name)
    (cdir / "evidence.json").write_text(json.dumps(m, indent=2, sort_keys=True) + "\n")
    recp = sim / EXP.name / "records" / f"{rid}.md"
    recp.write_text(re.sub(r"evidence\.json sha256 `[0-9a-f]{64}`",
                           f"evidence.json sha256 `{lint.sha256_file(cdir / 'evidence.json')}`", recp.read_text()))


def _variant_rid(sim):
    for p in (sim / EXP.name / "corners").iterdir():
        m = json.loads((p / "evidence.json").read_text())
        if m.get("variant") == "resistor-sets":
            return p.name


def test_lint_rejects_resealed_tampering_of_a_resistor_set_record(sandbox):
    test_variant_run_writes_a_225_point_record_the_lint_accepts(sandbox)
    rid = _variant_rid(sandbox)
    pristine = shutil.copytree(sandbox, sandbox.parent / "pristine")

    def narrow_matrix(cdir):  # self-declare a matrix without the hh sets
        d = json.loads((cdir / "corners.json").read_text())
        d["process"] = [p for p in d["process"] if not p.endswith("hh") and p != "hh"]
        d["expected_points"] = len(d["process"]) * 9
        (cdir / "corners.json").write_text(json.dumps(d, indent=2) + "\n")

    def drop_mapping(cdir):
        m = json.loads((cdir / "evidence.json").read_text())
        m["sections"].pop("hh")
        (cdir / "evidence.json").write_text(json.dumps(m, indent=2, sort_keys=True) + "\n")

    def wrong_mapping(cdir):
        m = json.loads((cdir / "evidence.json").read_text())
        m["sections"]["hh"]["resistor_set"] = "typical"
        (cdir / "evidence.json").write_text(json.dumps(m, indent=2, sort_keys=True) + "\n")

    def legacy_tb(cdir):  # claim the base experiment while using the 225 matrix
        m = json.loads((cdir / "evidence.json").read_text())
        m["variant"] = None
        (cdir / "evidence.json").write_text(json.dumps(m, indent=2, sort_keys=True) + "\n")

    def drop_corner(cdir):
        r = json.loads((cdir / "report.json").read_text())
        r["corners"] = [c for c in r["corners"] if not (c["process"] == "lh" and c["temperature_c"] == -40.0)]
        (cdir / "report.json").write_text(json.dumps(r, indent=2) + "\n")

    for edit, needle in ((narrow_matrix, "approved"), (drop_mapping, "section mapping"),
                         (wrong_mapping, "section mapping"), (legacy_tb, "matrix id"),
                         (drop_corner, "missing from report")):
        sim = sandbox.parent / f"t_{edit.__name__}"
        shutil.copytree(pristine, sim)
        _reseal(sim, rid, edit)
        assert any(needle in p for p in lint.lint_all(sim)), (edit.__name__, lint.lint_all(sim)[:3])


def test_variant_run_still_fails_closed_on_backend_error(sandbox, monkeypatch):
    def boom(*a, **k):
        raise runner.RunError("batch submit failed: no credentials")

    monkeypatch.setattr(runner, "invoke_klt", boom)
    assert runner.run("dplus-pullup-tolerance", "batch", True, {}, variant="resistor-sets") == 2
    assert lint.lint_all(sandbox) == []


def test_full_225_grid_cannot_run_locally_or_be_a_recorded_subset(sandbox):
    with pytest.raises(runner.RunError):
        runner.run("dplus-pullup-tolerance", "local", False, {}, variant="resistor-sets")
    with pytest.raises(runner.RunError):
        runner.run("dplus-pullup-tolerance", "batch", True, {"process": ["hh"]}, variant="resistor-sets")
    with pytest.raises(runner.RunError):
        runner.run("dplus-pullup-tolerance", "batch", True, {}, variant="nope")
