<!-- record-meta
{
  "schema": "usb2phy.flow.record/1",
  "record_kind": "analog-layout",
  "record_id": "20261102-172701-73c0a85-differential_driver",
  "experiment": "analog-layout-differential_driver",
  "block": "differential_driver",
  "created_utc": "2026-11-02T17:27:01Z",
  "git_revision": "73c0a85a9c69bc21d6d71ba3633bf02cf36ba210",
  "supersedes": null,
  "design": {
    "block": "differential_driver",
    "netlist": "design/netlist/differential_driver.spice",
    "gds": "layout/analog/differential_driver/differential_driver.gds",
    "generator": "layout/analog/differential_driver/gen.py",
    "anchors_design_claim": false,
    "claim_note": "One leaf of the analog partition. This record is the differential_driver leaf's evidence for T1 items 2 (layout), 3 (DRC), 4 (LVS) and the supply half of 11; the analog partition's rows stay unmet until every leaf has the same, and nothing here is cited from signoff/block-manifest.json (issue #220, out of scope)."
  },
  "reproducibility": {
    "generator": "layout/analog/differential_driver/gen.py",
    "gds_sha256": "sha256:2ae488493e6ebbd869207710d956e5507f35337927909f099b856f87a83a3bd0",
    "regenerated_identical": true
  },
  "stages": {
    "drc_curated": {
      "status": "clean",
      "violation_count": 0,
      "deck": {
        "name": "sky130",
        "content_hash": "sha256:029ef177c1f4e872c13cc81093f94a02a9bbfe1f51939a88194a83532d60bf7c"
      },
      "coverage": {
        "layers_in_stream_without_rules": [
          "66/13",
          "68/5",
          "70/5"
        ],
        "rules_checked_count": 100,
        "rules_skipped": [
          "areaid_re.ongrid.1",
          "capm2.enclosing.via4.1",
          "capm2.separation.via4.1",
          "capm2.space.1",
          "capm2.width.1",
          "dnwell.angle.1",
          "dnwell.ongrid.1",
          "hvntm.angle.1",
          "hvntm.ongrid.1",
          "hvtp.angle.1",
          "hvtp.ongrid.1",
          "hvtr.angle.1",
          "hvtr.ongrid.1",
          "lvtn.angle.1",
          "lvtn.ongrid.1",
          "met4.enclosing.capm2.1",
          "met4.enclosing.via4.1",
          "met5.angle.1",
          "met5.area.1",
          "met5.enclosing.via4.1",
          "met5.holes_area.1",
          "met5.ongrid.1",
          "met5.space.1",
          "met5.width.1",
          "mf.angle.1",
          "mf.ongrid.1",
          "ncm.angle.1",
          "ncm.ongrid.1",
          "nsm.angle.1",
          "nsm.ongrid.1",
          "pad.angle.1",
          "pad.ongrid.1",
          "pwbm.angle.1",
          "pwbm.ongrid.1",
          "pwde.angle.1",
          "pwde.ongrid.1",
          "pwell_rs.angle.1",
          "pwell_rs.ongrid.1",
          "rpm.angle.1",
          "rpm.ongrid.1",
          "rpm.width.1",
          "tunm.angle.1",
          "tunm.ongrid.1",
          "uhvi.angle.1",
          "uhvi.ongrid.1",
          "vhvi.angle.1",
          "vhvi.ongrid.1",
          "via4.angle.1",
          "via4.ongrid.1",
          "via4.space.1",
          "via4.width.1",
          "vpp.angle.1",
          "vpp.ongrid.1"
        ],
        "deck_scope": [
          "cap2m",
          "capm",
          "ct",
          "difftap",
          "li",
          "licon",
          "m1",
          "m2",
          "m3",
          "m4",
          "m5",
          "npc",
          "nsdm",
          "nwell",
          "poly",
          "psdm",
          "rpm",
          "urpm",
          "via",
          "via2",
          "via3",
          "via4",
          "x"
        ],
        "unmodeled_rules": [
          "MR_licon.SP.1",
          "cap2m.11",
          "cap2m.2b",
          "cap2m.2b_a",
          "cap2m.5",
          "capm.11",
          "capm.2b",
          "capm.2b_a",
          "capm.5",
          "difftap.10",
          "difftap.11",
          "difftap.8",
          "difftap.9",
          "dnwell.2",
          "hvi.1",
          "hvi.2a",
          "hvntm.1",
          "hvntm.2",
          "hvtp.1",
          "hvtp.2",
          "hvtr.1",
          "hvtr.2",
          "hvtr.2_a",
          "ldntm.2",
          "li.7",
          "licon.13",
          "lvtn.2",
          "m1.3ab",
          "m1.5",
          "m2.3ab",
          "m2.5",
          "m3.3ab",
          "m4.5ab",
          "n/psdm.10a",
          "n/psdm.10b",
          "n/psdm.5a",
          "n/psdm.5b",
          "n/psdm.6",
          "n/psdm.7",
          "n/psdm.8",
          "ncm.2a",
          "npc.4",
          "nsm.1",
          "pad.2",
          "poly.3",
          "rdl.1",
          "rdl.2",
          "rpm.2",
          "thkox.2",
          "tunm.2",
          "urpm.2",
          "via.5a",
          "via2.5",
          "via3.5"
        ],
        "voltage_domain_warnings": [
          {
            "marker": "75/20",
            "description": "hvi (75/20) marks sky130's 5V-gate/10.5V-drain thick-oxide voltage domain (see sky130.lvs's ngate_high_voltage/pgate_high_voltage). This curated deck models it for MOS device recognition/model binding (issue #1369: sky130_fd_pr__nfet_g5v0d10v5/pfet_g5v0d10v5 under --pdk) and for one DRC rule (nwell.enclosed.hvi.1, nwell.9, issue #3031); no other DRC rule here reads hvi, so every rule still applies its general-case threshold to geometry drawn inside hvi (e.g. diff.width.1 checks difftap.1's 0.15 um where the real DRM's medium-voltage column, difftap.14, requires 0.29 um -- not transcribed in this deck yet)."
          }
        ]
      }
    },
    "drc_native": {
      "status": "clean",
      "violation_count": 0,
      "engine": "klayout",
      "deck_file": "sky130A/libs.tech/klayout/drc/sky130A_mr.drc",
      "deck_sha256": "sha256:caf4a6b08cb12f78d6bb2d120737424c786b3bae8d6489234b9b269e91107bfc",
      "deck_vars": {
        "feol": "true",
        "beol": "true",
        "offgrid": "true",
        "seal": "false",
        "floating_met": "false",
        "thr": "2"
      },
      "expected_rule_categories": 244,
      "declared_rule_categories": 244
    },
    "lvs": {
      "status": "match",
      "engine": "klayout-runset",
      "counts": {
        "nets": {
          "layout": 47,
          "reference": 47,
          "matched": 47
        },
        "devices": {
          "layout": 80,
          "reference": 80,
          "matched": 80
        },
        "pins": {
          "layout": 8,
          "reference": 8,
          "matched": 8
        }
      },
      "device_census": {
        "layout": {
          "sky130_fd_pr__pfet_g5v0d10v5": 36,
          "sky130_fd_pr__nfet_g5v0d10v5": 37,
          "sky130_fd_pr__res_generic_po": 2,
          "sky130_fd_pr__res_xhigh_po_1p41": 1,
          "sky130_fd_pr__model__cap_mim": 4
        },
        "reference": {
          "SKY130_FD_PR__PFET_G5V0D10V5": 36,
          "SKY130_FD_PR__NFET_G5V0D10V5": 37,
          "SKY130_FD_PR__RES_XHIGH_PO_1P41": 1,
          "SKY130_FD_PR__MODEL__CAP_MIM": 4,
          "SKY130_FD_PR__RES_GENERIC_PO": 2
        }
      },
      "warnings_only_mismatches": [],
      "mismatch_count": 0,
      "body_verification": null,
      "body_verification_note": "null: the klayout-runset engine does not compute it. The bulk terminal is still extracted and compared -- the runset's MOS4 and resistor-with-bulk device classes carry B / W -- so the matched devices include their bulk nets.",
      "power_connectivity": {
        "status": "unchecked",
        "reason": "no subcircuit instance in the runset's extracted netlist declares a power/ground-named pin -- the extraction carries no instance-level power connectivity to check"
      },
      "runset": {
        "name": "sky130.lvs",
        "content_hash": "sha256:5b4ede4bdb4744b60e42c9b29baa93f40bb24430fb8f3a48a276a712a492ac38",
        "deck_vars": {
          "convert_subckts": "true",
          "scale": "true",
          "thr": "2"
        },
        "klayout_application_version": "0.28.16"
      },
      "declared_not_recognized_count": 100
    },
    "erc": {
      "status": "clean_partial",
      "erc_status": "clean",
      "erc_finding_count": 0,
      "supply_islands": {
        "VDD": 1,
        "VSS": 1
      },
      "ties_checked": [
        "erc.missing_tie:[\"nwell_vdd\"]",
        "erc.missing_tie:[\"psub_vss\"]"
      ],
      "ties_skipped": [],
      "ties_checked_by_well_assertion": [
        "erc.missing_tie:[\"psub_vss\"]"
      ],
      "status_note": "the overall status is clean_partial because the antenna table has no met3 limit (antenna coverage.skipped: missing_antenna_limit); item 11 is graded from the supply findings, not from this status."
    }
  },
  "provenance": {
    "klt_version": "0.8.1.dev1080+ge2dd61498b57",
    "klayout_version": "0.30.12",
    "pdk": {
      "name": "sky130A",
      "open_pdks_commit": "f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7"
    },
    "inputs": [
      {
        "path": "layout/analog/differential_driver/differential_driver.gds",
        "content_hash": "sha256:2ae488493e6ebbd869207710d956e5507f35337927909f099b856f87a83a3bd0"
      },
      {
        "path": "layout/analog/differential_driver/gen.py",
        "content_hash": "sha256:8b39ac2fb7730adfef548ad255061487308ec8fa319ac3491e685ae54306068d"
      },
      {
        "path": "layout/analog/gen_common.py",
        "content_hash": "sha256:6a75ec10da0d5aa1e85b7602f322d56d77286cd4acda39ef3fd8628eebac0ba3"
      },
      {
        "path": "design/netlist/differential_driver.spice",
        "content_hash": "sha256:bed3319d65789db0a7d1a14831e113eb957cd1998d3cc58d4dc539dd5ea2fdd0"
      },
      {
        "path": "layout/analog/differential_driver/lvs-reference.spice",
        "content_hash": "sha256:c71adad726f05f6b3bf3ef1c0fd1cb79e7c1e3ab3b248e8ba3afc05ab9270548"
      },
      {
        "path": "layout/analog/differential_driver/erc-supply-spec.json",
        "content_hash": "sha256:81ac35e82a08df31d1f243fb28576776346ec4e4307dbabb76ee8455a5d13243"
      },
      {
        "path": "layout/analog/differential_driver/request-lvs.json",
        "content_hash": "sha256:f1523c0d997d208c8ed7f17a6c6eb509d931677d62f19bc3b4beee083d113be0"
      },
      {
        "path": "sim/pdk-pins.json",
        "content_hash": "sha256:42fda161b11df5fc8611f074fad1913bfca193cd3986f7603c2ff629fe201a28"
      }
    ],
    "artifacts": [
      {
        "path": "flow/analog-layout-differential_driver/artifacts/20261102-172701-73c0a85-differential_driver/drc-report.json",
        "content_hash": "sha256:1904f24ea8939bc9855fac9d68c06f402ed5c542a0d5690a5fbf49cfc4176b66"
      },
      {
        "path": "flow/analog-layout-differential_driver/artifacts/20261102-172701-73c0a85-differential_driver/drc-native-report.json",
        "content_hash": "sha256:e967e222ec09f7369acd31befc6b62ed8fc91f55a48e3be8281bd0743bdcf249"
      },
      {
        "path": "flow/analog-layout-differential_driver/artifacts/20261102-172701-73c0a85-differential_driver/lvs-report.json",
        "content_hash": "sha256:391c9f1cbd2851f80b175eaf0336727fbd065f48ab56ca7aeda873e488a720d5"
      },
      {
        "path": "flow/analog-layout-differential_driver/artifacts/20261102-172701-73c0a85-differential_driver/erc-supply-report.json",
        "content_hash": "sha256:7ad2257158d2570bc5c12a4da93610b82ccfb509f5e6500c6abafac1bf2c4abe"
      }
    ]
  },
  "tool_gaps": [
    "https://github.com/2AMLogic/klayout-tools/issues/3987",
    "https://github.com/2AMLogic/klayout-tools/issues/3988",
    "https://github.com/2AMLogic/klayout-tools/issues/3989",
    "https://github.com/2AMLogic/klayout-tools/issues/2934",
    "https://github.com/2AMLogic/klayout-tools/issues/4519"
  ]
}
-->

# 20261102-172701-73c0a85-differential_driver

Physical checks of the `differential_driver` layout leaf (issue #220), generated by
`layout/analog/differential_driver/run_checks.py` from the committed GDS.
Every `klt` JSON envelope is committed verbatim under
`flow/analog-layout-differential_driver/artifacts/20261102-172701-73c0a85-differential_driver/`.

**Scope.** One leaf of the analog partition. This record is the differential_driver leaf's evidence for T1 items 2 (layout), 3 (DRC), 4 (LVS) and the supply half of 11; the analog partition's rows stay unmet until every leaf has the same, and nothing here is cited from signoff/block-manifest.json (issue #220, out of scope).

## Layout

`layout/analog/differential_driver/differential_driver.gds` (`sha256:2ae488493e6ebbd869207710d956e5507f35337927909f099b856f87a83a3bd0`) is emitted by
`layout/analog/differential_driver/gen.py`; regenerating it reproduces that hash byte for byte.
All devices are drawn for sky130 from `design/netlist/differential_driver.spice`; no gf180 geometry is used.

## DRC

- **Curated deck** (`klt drc --deck sky130`): `status: clean`, 0 violations.
  Deck content hash `sha256:029ef177c1f4e872c13cc81093f94a02a9bbfe1f51939a88194a83532d60bf7c`.
  - `layers_in_stream_without_rules`: 66/13, 68/5, 70/5
  - `rules_skipped`: 53 of the deck's rules (layers absent from the stream), 100 rules checked
  - `deck_scope`: cap2m, capm, ct, difftap, li, licon, m1, m2, m3, m4, m5, npc, nsdm, nwell, poly, psdm, rpm, urpm, via, via2, via3, via4, x
  - `unmodeled_rules` (54): MR_licon.SP.1, cap2m.11, cap2m.2b, cap2m.2b_a, cap2m.5, capm.11, capm.2b, capm.2b_a, capm.5, difftap.10, difftap.11, difftap.8, difftap.9, dnwell.2, hvi.1, hvi.2a, hvntm.1, hvntm.2, hvtp.1, hvtp.2, hvtr.1, hvtr.2, hvtr.2_a, ldntm.2, li.7, licon.13, lvtn.2, m1.3ab, m1.5, m2.3ab, m2.5, m3.3ab, m4.5ab, n/psdm.10a, n/psdm.10b, n/psdm.5a, n/psdm.5b, n/psdm.6, n/psdm.7, n/psdm.8, ncm.2a, npc.4, nsm.1, pad.2, poly.3, rdl.1, rdl.2, rpm.2, thkox.2, tunm.2, urpm.2, via.5a, via2.5, via3.5
  - `voltage_domain_warnings`: [{"marker": "75/20", "description": "hvi (75/20) marks sky130's 5V-gate/10.5V-drain thick-oxide voltage domain (see sky130.lvs's ngate_high_voltage/pgate_high_voltage). This curated deck models it for MOS device recognition/model binding (issue #1369: sky130_fd_pr__nfet_g5v0d10v5/pfet_g5v0d10v5 under --pdk) and for one DRC rule (nwell.enclosed.hvi.1, nwell.9, issue #3031); no other DRC rule here reads hvi, so every rule still applies its general-case threshold to geometry drawn inside hvi (e.g. diff.width.1 checks difftap.1's 0.15 um where the real DRM's medium-voltage column, difftap.14, requires 0.29 um -- not transcribed in this deck yet)."}]
- **PDK-native deck** (`klt drc --engine klayout`, `sky130A/libs.tech/klayout/drc/sky130A_mr.drc`, `sha256:caf4a6b08cb12f78d6bb2d120737424c786b3bae8d6489234b9b269e91107bfc`):
  `status: clean`, 0 violations, against
  `--expect-rule-categories 244` (244 declared). This is the
  stronger check: the curated deck cannot see the 5V (`hvi`) rule columns, the native one does.
  It is not a foundry signoff run.

## LVS

`klt lvs` engine `klayout-runset`, runset `sky130.lvs` (`sha256:5b4ede4bdb4744b60e42c9b29baa93f40bb24430fb8f3a48a276a712a492ac38`),
deck vars {"convert_subckts": "true", "scale": "true", "thr": "2"}, standalone klayout 0.28.16.

- `status: match`; devices 80/80, nets 47/47, pins 8/8
- warnings-only mismatches: none
- `body_verification`: null -- null: the klayout-runset engine does not compute it. The bulk terminal is still extracted and compared -- the runset's MOS4 and resistor-with-bulk device classes carry B / W -- so the matched devices include their bulk nets.
- `power_connectivity`: `unchecked` -- no subcircuit instance in the runset's extracted netlist declares a power/ground-named pin -- the extraction carries no instance-level power connectivity to check
- 100 runset device classes are declared but not present in this block (not a gap for this block).

## ERC (supply, T1 item 11)

`klt erc` overall `status: clean_partial`, `erc_status: clean`, 0 findings.
the overall status is clean_partial because the antenna table has no met3 limit (antenna coverage.skipped: missing_antenna_limit); item 11 is graded from the supply findings, not from this status.

- supply islands: {"VDD": 1, "VSS": 1} (`VDD` and `VSS` one island each)
- `erc.missing_tie` checked: erc.missing_tie:["nwell_vdd"], erc.missing_tie:["psub_vss"]; skipped: none
- the substrate tie is graded by the region assertion `well_complement_of: [nwell]`
  (`checked_by_well_assertion`: ["erc.missing_tie:[\"psub_vss\"]"]), not by a drawn well layer.

## Tool gaps filed while producing this record

- https://github.com/2AMLogic/klayout-tools/issues/3987
- https://github.com/2AMLogic/klayout-tools/issues/3988
- https://github.com/2AMLogic/klayout-tools/issues/3989
- https://github.com/2AMLogic/klayout-tools/issues/2934
- https://github.com/2AMLogic/klayout-tools/issues/4519
