"""Toolchain-free tests for the mismatch Monte Carlo harness and its record lint.

No klt, ngspice or PDK: reports and yield documents are synthetic. They prove the grading
and the lint *reject* the ways a Monte Carlo record can be wrong (insufficient samples, an
undetected negative control, a measurement mismatch did not move, an unpinned PDK, a control
deck that is not the nominal deck plus the declared skew, a pairing hash that does not pin its
report); they say nothing about the circuits, which is the recorded campaign.
"""

import copy
import hashlib
import json
import re
import shutil
from pathlib import Path

import pytest

from harness import matrix as mx, mismatch as mm, mismatch_lint as ml

SIM = Path(__file__).resolve().parents[1]
PINS = json.loads((SIM / "pdk-pins.json").read_text())["current"]
EXPERIMENTS = ("diff-receiver-mismatch", "se-receiver-mismatch")


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ---------------------------------------------------------------- committed declarations


@pytest.mark.parametrize("name", EXPERIMENTS)
def test_committed_specs_are_wellformed(name):
    exp = SIM / name
    spec = mm.load_spec(exp)
    mc = spec["monte_carlo"]
    assert mc["vary"] == "mismatch" and isinstance(mc["seed"], int)
    # n must be able to support the declared target yield at the declared confidence with zero failures
    import math
    y = spec["yield"]
    need = math.ceil(math.log((1 - y["confidence"]) / 2) / math.log(y["target_yield"]))
    assert mc["n"] >= need, f"n={mc['n']} cannot support target_yield {y['target_yield']} (needs {need})"
    for c in spec["corners"]:
        assert c["process"].endswith("_mm")
    for rcv in spec["receivers"]:
        assert set(rcv["limits"]) == set(rcv["measure"])
        assert set(rcv["control"]["must_detect"]) <= set(rcv["limits"])
        assert set(rcv["spread_measures"]) <= set(rcv["limits"])
        nominal, control = mm.build_body(exp, rcv, False), mm.build_body(exp, rcv, True)
        assert nominal != control
        # the control differs from the nominal deck by the declared replacements only
        assert len(nominal.splitlines()) == len(control.splitlines())


@pytest.mark.parametrize("name", EXPERIMENTS)
def test_committed_binding_corners_are_the_45_point_extremes(name):
    spec = mm.load_spec(SIM / name)
    binding = next(c for c in spec["corners"] if c["id"] == "binding")
    want = {"diff-receiver-mismatch": ("sf_mm", 100.0, 3.0), "se-receiver-mismatch": ("ff_mm", 100.0, 3.0)}[name]
    assert (binding["process"], binding["temperature_c"], binding["supply_v"]) == want


def test_request_is_batch_staged_mismatch_only():
    spec = mm.load_spec(SIM / "diff-receiver-mismatch")
    rcv, corner = spec["receivers"][0], spec["corners"][1]
    nominal = mm.build_request(spec, rcv, corner, False, "n.spice")
    control = mm.build_request(spec, rcv, corner, True, "c.spice")
    assert nominal["backend"] == "batch" and nominal["options"]["stage_model_inputs"] is True
    assert nominal["monte_carlo"] == {"n": 400, "seed": 166, "vary": "mismatch"}
    assert control["monte_carlo"]["n"] == spec["monte_carlo"]["n_control"]
    assert control["monte_carlo"]["seed"] == nominal["monte_carlo"]["seed"]
    assert nominal["corners"]["process"] == ["sf_mm"]


def test_control_replacement_must_match_exactly_once(tmp_path):
    exp = tmp_path / "e"
    (exp / "testbench").mkdir(parents=True)
    (exp / "testbench/t.spice").write_text("* t\n.param skew_v=0\n.param skew_v=0\n")
    rcv = {"id": "r", "netlist": "t.spice", "control": {"replace": [{"find": ".param skew_v=0\n", "with": "x\n"}]}}
    with pytest.raises(mm.MismatchError):
        mm.build_body(exp, rcv, True)
    (exp / "testbench/t.spice").write_text("* t\n")
    with pytest.raises(mm.MismatchError):
        mm.build_body(exp, rcv, True)


def test_limits_scale_with_the_corner_supply():
    spec = mm.load_spec(SIM / "diff-receiver-mismatch")
    rcv = spec["receivers"][0]
    tt = mm.resolve_limits(spec, rcv, spec["corners"][0])["measurements"]
    binding = mm.resolve_limits(spec, rcv, spec["corners"][1])["measurements"]
    assert tt["rxd_p200_cm1p65_v"]["min"] == pytest.approx(0.9 * 3.3)
    assert binding["rxd_p200_cm1p65_v"]["min"] == pytest.approx(0.9 * 3.0)
    assert binding["rxd_m200_cm1p65_v"]["max"] == pytest.approx(0.1 * 3.0)
    lim = binding["vth_cm2p50_v"]
    assert (lim["min"], lim["max"], lim["exclusive_min"], lim["exclusive_max"]) == (-0.2, 0.2, True, True)
    assert all(v["target_yield"] == spec["yield"]["target_yield"] for v in binding.values())


# ---------------------------------------------------------------- grading


RCV = {"limits": {"vth": {}, "lvl": {}}, "spread_measures": ["vth"],
       "control": {"must_detect": ["vth"]}}


def ymeas(name, **kw):
    m = {"name": name, "status": "pass", "n": 400, "errored": 0, "failed_unmeasurable": 0, "censored": 0,
         "inconclusive": 0, "limits": {"min": -0.2, "max": 0.2},
         "distribution": {"stddev": 0.004, "mean": -0.07, "min": -0.09, "max": -0.05},
         "yield": {"empirical": {"estimate": 1.0, "confidence_interval": {"low": 0.9908, "high": 1.0}}},
         "sample_size": {"verdict": "sufficient"},
         "negative_control": {"verdict": "detected", "yield": {"empirical": {"estimate": 0.0}}}}
    m.update(kw)
    return m


def test_grade_accepts_a_good_report():
    digest, probs = mm.grade(RCV, {"measurements": [ymeas("vth"), ymeas("lvl", negative_control=None)]})
    assert probs == [] and digest["vth"]["negative_control_verdict"] == "detected"


@pytest.mark.parametrize("tamper,needle", [
    ({"status": "fail"}, "yield status"),
    ({"errored": 3}, "errored"),
    ({"failed_unmeasurable": 1}, "failed_unmeasurable"),
    ({"sample_size": {"verdict": "insufficient"}}, "sample_size"),
    ({"negative_control": {"verdict": "not_detected"}}, "negative control"),
    ({"negative_control": None}, "negative control"),
    ({"distribution": {"stddev": 0.0}}, "did not vary"),
])
def test_grade_rejects(tamper, needle):
    _, probs = mm.grade(RCV, {"measurements": [ymeas("vth", **tamper), ymeas("lvl")]})
    assert any(needle in p for p in probs), probs


def test_grade_rejects_a_missing_measurement():
    _, probs = mm.grade(RCV, {"measurements": [ymeas("vth")]})
    assert any("lvl" in p and "missing" in p for p in probs)


def test_pdk_problems_demand_staged_pinned_models():
    pdk = {"open_pdks_commit": PINS["open_pdks_commit"], "lib_sha256": PINS["lib_sha256"]}
    good = {"models_staged": True, "provenance_pdk_version": f"open_pdks {pdk['open_pdks_commit']}",
            "models_lib_sha256": pdk["lib_sha256"], "job_ids": ["klt-sim-1"], "worker_image_pdk_stamps": ["open_pdks old"]}
    assert mm.pdk_problems("s", good, pdk) == []
    assert any("models_staged" in p for p in mm.pdk_problems("s", {**good, "models_staged": False}, pdk))
    assert any("provenance" in p for p in mm.pdk_problems("s", {**good, "provenance_pdk_version": "open_pdks c6d73a3"}, pdk))
    assert any("sha256" in p for p in mm.pdk_problems("s", {**good, "models_lib_sha256": "0" * 64}, pdk))
    assert any("job id" in p for p in mm.pdk_problems("s", {**good, "job_ids": []}, pdk))


def test_exec_pdk_reads_every_shard_of_a_sharded_report():
    shard = lambda job, staged: {"job_id": job, "instance_type": "c7i", "lifecycle": "spot",
                                 "worker_environment": {"pdk": {"models_staged": staged, "stamp_text": "open_pdks old"}}}
    base = {"environment": {"models_lib_sha256": "h", "remote": {"fleet": [shard("a", True), shard("b", True)]}},
            "provenance": {"pdk": {"version": "open_pdks x"}}}
    ex = mm.exec_pdk(base)
    assert ex["job_ids"] == ["a", "b"] and ex["models_staged"] is True
    base["environment"]["remote"]["fleet"][1] = shard("b", False)
    assert mm.exec_pdk(base)["models_staged"] is False


# ---------------------------------------------------------------- lint on a synthetic record

RID = "20261020-120000-abcdef0"


def synth_spec():
    return {
        "schema": mm.SCHEMA, "experiment": "x-mismatch", "claim": "c", "spec_rows": ["r"],
        "corners": [{"id": "tt", "process": "tt_mm", "temperature_c": 27.0, "supply_v": 3.3, "basis": "b"}],
        "monte_carlo": {"n": 400, "n_control": 50, "seed": 7, "vary": "mismatch"},
        "yield": {"confidence": 0.95, "target_ci_halfwidth": 0.01, "target_yield": 0.99,
                  "sample_size_justification": "j"},
        "batch": {"capacity_wait_s": 900},
        "receivers": [{
            "id": "r", "netlist": "t.spice", "include": [],
            "analysis": {"kind": "dc", "args": "vin 0 3 0.001"},
            "measure": {"vth": {"spice": ".meas dc vth WHEN v(o)=v(h) RISE=1"},
                        "lvl": {"spice": ".meas dc lvl FIND v(o) AT=1"}},
            "limits": {"vth": {"min": 0.8, "max": 2.0, "exclusive_min": True, "exclusive_max": True},
                       "lvl": {"min_frac_vdd": 0.9}},
            "spread_measures": ["vth"],
            "control": {"description": "skew", "must_detect": ["vth"],
                        "replace": [{"find": "L=14 ", "with": "L=60 "}]}}],
        "record": {"netlist_provenance": "p", "statistical_convention": "s", "method": ["m"], "footer": "f"},
    }


def build_tree(tmp_path, tweak=None):
    """A minimal, self-consistent PASS record under tmp_path/sim/x-mismatch."""
    spec = synth_spec()
    exp = tmp_path / "sim" / "x-mismatch"
    (exp / "testbench").mkdir(parents=True)
    cdir = exp / "campaigns" / RID
    cdir.mkdir(parents=True)
    (exp / "records").mkdir()
    (exp / "testbench/mc.json").write_text(json.dumps(spec))
    rcv, corner = spec["receivers"][0], spec["corners"][0]
    pdk = {"name": "sky130A", "open_pdks_commit": PINS["open_pdks_commit"], "lib_sha256": PINS["lib_sha256"],
           "lib": mm.LIB}
    nominal = "* deck\nXR2 a b L=14 mult=1\n"
    files = {"mc.json": json.dumps(spec).encode(), "klt-stderr.txt": b"", "klt-batch-set.json": b"{}"}
    campaigns, reports = [], {}
    for kind in ("nominal", "control"):
        stem = mm.campaign_stem("r", "tt", kind)
        body = nominal if kind == "nominal" else nominal.replace("L=14 ", "L=60 ")
        request = mm.build_request(spec, rcv, corner, kind == "control", f"{stem}.spice")
        n = request["monte_carlo"]["n"]
        report = {"environment": {"netlist_sha256": sha(body.encode()), "monte_carlo": {"seed": 7},
                                  "models_lib_sha256": pdk["lib_sha256"],
                                  "remote": {"job_id": f"klt-sim-{kind}", "instance_type": "c7i", "lifecycle": "spot",
                                             "worker_environment": {"pdk": {"models_staged": True,
                                                                            "stamp_text": "open_pdks old"}}}},
                  "provenance": {"pdk": {"version": f"open_pdks {pdk['open_pdks_commit']}"}},
                  "corners": [{"monte_carlo": {"sample_index": i}} for i in range(n)]}
        rb = json.dumps(report).encode()
        reports[kind] = rb
        files.update({f"{stem}.spice": body.encode(), f"{stem}.request.json": (json.dumps(request, indent=2) + "\n").encode(),
                      f"{stem}.report.json": rb})
        campaigns.append({"receiver": "r", "corner": "tt", "kind": kind, "stem": stem, "job_ids": [f"klt-sim-{kind}"],
                          "report": True, "exec_pdk": mm.exec_pdk(report)})
    limits = mm.resolve_limits(spec, rcv, corner)
    samples = {"derivation": {"nominal": {"content_hash": f"sha256:{sha(reports['nominal'])}"},
                              "negative_control": {"content_hash": f"sha256:{sha(reports['control'])}"}}}
    yld = {"status": "pass", "measurements": [ymeas("vth", n=400), ymeas("lvl", n=400, negative_control=None)]}
    if tweak:
        tweak(spec, files, samples, yld)
    digest, _ = mm.grade(rcv, yld)
    files.update({"r-tt.samples.json": json.dumps(samples).encode(), "r-tt.limits.json": json.dumps(limits).encode(),
                  "r-tt.yield.json": json.dumps(yld).encode()})
    manifest = {"schema": mm.EVIDENCE_SCHEMA, "record_id": RID, "experiment": "x-mismatch", "status": "PASS",
                "problems": [], "pdk": pdk, "monte_carlo": spec["monte_carlo"], "campaigns": campaigns,
                "yields": [{"receiver": "r", "corner": "tt", "yield_status": yld["status"], "samples": "r-tt.samples.json",
                            "limits": "r-tt.limits.json", "yield": "r-tt.yield.json", "measurements": digest}]}
    write_tree(exp, cdir, files, manifest)
    return exp


def write_tree(exp, cdir, files, manifest):
    for n, d in files.items():
        (cdir / n).write_bytes(d)
    manifest["files"] = {n: sha(d) for n, d in sorted(files.items())}
    mbytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    (cdir / "evidence.json").write_bytes(mbytes)
    (exp / "records" / f"{RID}.md").write_text("\n".join([
        f"# x-mismatch -- {RID}", "", f"- **Record ID**: {RID}", f"- **Status**: {manifest['status']}", "- **Claim**: c",
        "- **Netlist provenance**: p", "- **Corners run**: tt", "- **Statistical convention**: s",
        "- **Monte Carlo**: seed 7", "- **Result**: r",
        f"- **Links**: sim/x-mismatch/campaigns/{RID}/ (evidence.json sha256 `{sha(mbytes)}`)",
        "- **Timestamp / author**: t / a", "- **Supersedes**: (none)", ""]))


def lint(exp):
    return ml.lint_experiment(exp)


def test_a_consistent_synthetic_record_passes(tmp_path):
    assert lint(build_tree(tmp_path)) == []


def test_pass_record_with_failing_yield_is_rejected(tmp_path):
    def tw(spec, files, samples, yld):
        yld["status"] = "fail"
        yld["measurements"][0]["status"] = "fail"
    assert any("PASS record has a failing criterion" in p for p in lint(build_tree(tmp_path, tw)))


def test_undetected_negative_control_is_rejected(tmp_path):
    def tw(spec, files, samples, yld):
        yld["measurements"][0]["negative_control"] = {"verdict": "not_detected", "yield": {"empirical": {"estimate": 1.0}}}
    assert any("negative control" in p for p in lint(build_tree(tmp_path, tw)))


def test_control_deck_must_be_nominal_plus_declared_skew(tmp_path):
    def tw(spec, files, samples, yld):
        stem = mm.campaign_stem("r", "tt", "control")
        body = b"* deck\nXR2 a b L=99 mult=1\n"
        files[f"{stem}.spice"] = body
        rep = json.loads(files[f"{stem}.report.json"])
        rep["environment"]["netlist_sha256"] = sha(body)
        rb = json.dumps(rep).encode()
        files[f"{stem}.report.json"] = rb
        samples["derivation"]["negative_control"]["content_hash"] = f"sha256:{sha(rb)}"
    assert any("control deck is not the nominal deck plus the declared skew" in p for p in lint(build_tree(tmp_path, tw)))


def test_sample_set_must_pin_the_committed_reports(tmp_path):
    def tw(spec, files, samples, yld):
        samples["derivation"]["nominal"]["content_hash"] = "sha256:" + "0" * 64
    assert any("nominal hash does not pin" in p for p in lint(build_tree(tmp_path, tw)))


def test_retired_pdk_pin_is_rejected_for_a_new_record(tmp_path):
    exp = build_tree(tmp_path)
    cdir = exp / "campaigns" / RID
    m = json.loads((cdir / "evidence.json").read_text())
    m["pdk"]["open_pdks_commit"] = json.loads((SIM / "pdk-pins.json").read_text())["retired"][0]["open_pdks_commit"]
    files = {p.name: p.read_bytes() for p in cdir.iterdir() if p.name != "evidence.json"}
    write_tree(exp, cdir, files, m)
    assert any("retired" in p for p in lint(exp))


def test_unstaged_models_are_rejected(tmp_path):
    def tw(spec, files, samples, yld):
        stem = mm.campaign_stem("r", "tt", "nominal")
        rep = json.loads(files[f"{stem}.report.json"])
        rep["environment"]["remote"]["worker_environment"]["pdk"]["models_staged"] = False
        files[f"{stem}.report.json"] = json.dumps(rep).encode()
        samples["derivation"]["nominal"]["content_hash"] = f"sha256:{sha(files[f'{stem}.report.json'])}"
    probs = lint(build_tree(tmp_path, tw))
    assert any("models_staged" in p for p in probs)


def test_edited_evidence_file_is_rejected(tmp_path):
    exp = build_tree(tmp_path)
    p = exp / "campaigns" / RID / "r-tt.yield.json"
    p.write_bytes(p.read_bytes() + b" ")
    assert any("sha256 mismatch" in x for x in lint(exp))


def test_sample_count_must_match_the_request(tmp_path):
    def tw(spec, files, samples, yld):
        stem = mm.campaign_stem("r", "tt", "nominal")
        rep = json.loads(files[f"{stem}.report.json"])
        rep["corners"] = rep["corners"][:10]
        files[f"{stem}.report.json"] = json.dumps(rep).encode()
        samples["derivation"]["nominal"]["content_hash"] = f"sha256:{sha(files[f'{stem}.report.json'])}"
    assert any("Monte Carlo samples, request asked for" in p for p in lint(build_tree(tmp_path, tw)))


def test_fail_record_must_state_its_problems(tmp_path):
    exp = build_tree(tmp_path)
    cdir = exp / "campaigns" / RID
    m = json.loads((cdir / "evidence.json").read_text())
    m["status"] = "FAIL"
    files = {p.name: p.read_bytes() for p in cdir.iterdir() if p.name != "evidence.json"}
    write_tree(exp, cdir, files, m)
    probs = lint(exp)
    assert any("FAIL record must state its problems" in p for p in probs)


def test_committed_mismatch_records_pass_the_lint():
    assert ml.lint_all(SIM) == []
