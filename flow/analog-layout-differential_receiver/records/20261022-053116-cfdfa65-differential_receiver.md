<!-- record-meta
{
  "schema": "usb2phy.flow.record/1",
  "record_kind": "analog-layout",
  "record_id": "20261022-053116-cfdfa65-differential_receiver",
  "experiment": "analog-layout-differential_receiver",
  "block": "differential_receiver",
  "created_utc": "2026-10-22T05:31:16Z",
  "git_revision": "cfdfa65e20c87951abd90d483bcf2718c6192f2e",
  "supersedes": "20261020-175729-ca4a45a-differential_receiver",
  "design": {
    "block": "differential_receiver",
    "netlist": "design/netlist/differential_receiver.spice",
    "gds": "layout/analog/differential_receiver/differential_receiver.gds",
    "generator": "layout/analog/differential_receiver/gen.py",
    "anchors_design_claim": false,
    "claim_note": "One leaf of the analog partition. This record is the first analog leaf's evidence for T1 items 2 (layout), 3 (DRC), 4 (LVS) and the supply half of 11; the analog partition's rows stay unmet until every leaf has the same, and nothing here is cited from signoff/block-manifest.json (issue #167, out of scope)."
  },
  "reproducibility": {
    "generator": "layout/analog/differential_receiver/gen.py",
    "gds_sha256": "sha256:3e1055d4eea9ea96d21a834ec8263579879596c09b7cc3a5c4e3798feceba540",
    "regenerated_identical": true
  },
  "stages": {
    "drc_curated": {
      "status": "clean",
      "violation_count": 0,
      "deck": {
        "name": "sky130",
        "content_hash": "sha256:ba0f97887e3d231aec8b54f1f52f2941ded0228f0234b6759712bcaca0e942e6"
      },
      "coverage": {
        "layers_in_stream_without_rules": [
          "66/13",
          "68/5",
          "70/5"
        ],
        "rules_checked_count": 79,
        "rules_skipped": [
          "areaid_re.ongrid.1",
          "capm.enclosing.via3.1",
          "capm.separation.via3.1",
          "capm.space.1",
          "capm.width.1",
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
          "met3.enclosing.capm.1",
          "met3.enclosing.via3.1",
          "met3.enclosing_adjacent.via3.1",
          "met4.angle.1",
          "met4.area.1",
          "met4.enclosing.capm2.1",
          "met4.enclosing.via3.1",
          "met4.enclosing.via4.1",
          "met4.holes_area.1",
          "met4.ongrid.1",
          "met4.space.1",
          "met4.width.1",
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
          "via3.angle.1",
          "via3.ongrid.1",
          "via3.space.1",
          "via3.width.1",
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
          "difftap.10",
          "difftap.11",
          "difftap.8",
          "difftap.9",
          "hvi.1",
          "hvi.2a",
          "hvntm.1",
          "hvntm.2",
          "hvtp.1",
          "hvtp.2",
          "hvtr.1",
          "hvtr.2",
          "hvtr.2_a",
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
          "npc.4",
          "pad.2",
          "rdl.1",
          "rdl.2",
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
          "layout": 10,
          "reference": 10,
          "matched": 10
        },
        "devices": {
          "layout": 11,
          "reference": 11,
          "matched": 11
        },
        "pins": {
          "layout": 5,
          "reference": 5,
          "matched": 5
        }
      },
      "device_census": {
        "layout": {
          "sky130_fd_pr__pfet_g5v0d10v5": 4,
          "sky130_fd_pr__nfet_g5v0d10v5": 6,
          "sky130_fd_pr__res_xhigh_po_1p41": 1
        },
        "reference": {
          "SKY130_FD_PR__RES_XHIGH_PO_1P41": 1,
          "SKY130_FD_PR__NFET_G5V0D10V5": 6,
          "SKY130_FD_PR__PFET_G5V0D10V5": 4
        }
      },
      "warnings_only_mismatches": [],
      "mismatch_count": 0,
      "body_verification": null,
      "body_verification_note": "null: the klayout-runset engine does not compute it. The bulk terminal is still extracted and compared -- the runset's MOS4 and resistor-with-bulk device classes carry B / W -- so the 11 matched devices include their bulk nets.",
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
      "declared_not_recognized_count": 102
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
    "klt_version": "0.7.1.dev2419+ga7dfbc5ce95d",
    "klayout_version": "0.30.12",
    "pdk": {
      "name": "sky130A",
      "open_pdks_commit": "f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7"
    },
    "inputs": [
      {
        "path": "layout/analog/differential_receiver/differential_receiver.gds",
        "content_hash": "sha256:3e1055d4eea9ea96d21a834ec8263579879596c09b7cc3a5c4e3798feceba540"
      },
      {
        "path": "layout/analog/differential_receiver/gen.py",
        "content_hash": "sha256:592de040fa49e1ebd931d973fc6df558eb0d32c08826c169f0a1802938f12be1"
      },
      {
        "path": "design/netlist/differential_receiver.spice",
        "content_hash": "sha256:a4e60f1604ced0bd779dd9c848825d7b7fdaab5bd198307e6c10b38a14d784f1"
      },
      {
        "path": "layout/analog/differential_receiver/erc-supply-spec.json",
        "content_hash": "sha256:67f6d1e60c51aa8e09c1f49ffd84c88e81ffdff23fddbec5d0f68ee944337782"
      },
      {
        "path": "layout/analog/differential_receiver/request-lvs.json",
        "content_hash": "sha256:5f616947da921af3659a3ed64d55225a83a3ac69acb8e644ee10f9f6b0619de1"
      },
      {
        "path": "sim/pdk-pins.json",
        "content_hash": "sha256:42fda161b11df5fc8611f074fad1913bfca193cd3986f7603c2ff629fe201a28"
      }
    ],
    "artifacts": [
      {
        "path": "flow/analog-layout-differential_receiver/artifacts/20261022-053116-cfdfa65-differential_receiver/drc-report.json",
        "content_hash": "sha256:5e97f275c626c37bdc159c65c53b2424bed133c70a8f8e18d5d2893090117ab5"
      },
      {
        "path": "flow/analog-layout-differential_receiver/artifacts/20261022-053116-cfdfa65-differential_receiver/drc-native-report.json",
        "content_hash": "sha256:5bcb663735f3c4502a2f35969ab552cfe43938011dd8253792e5711362b6a494"
      },
      {
        "path": "flow/analog-layout-differential_receiver/artifacts/20261022-053116-cfdfa65-differential_receiver/lvs-report.json",
        "content_hash": "sha256:a5a35e4a10f2e2204a2704a2da48f2c508638bff7191fcae976b216ab9130aef"
      },
      {
        "path": "flow/analog-layout-differential_receiver/artifacts/20261022-053116-cfdfa65-differential_receiver/erc-supply-report.json",
        "content_hash": "sha256:a8637592b6b4a684f99ea6aaf710310bc4226ff7c56166ed7c540d3b8357805c"
      }
    ]
  },
  "tool_gaps": [
    "https://github.com/2AMLogic/klayout-tools/issues/3987",
    "https://github.com/2AMLogic/klayout-tools/issues/3988",
    "https://github.com/2AMLogic/klayout-tools/issues/3989",
    "https://github.com/2AMLogic/klayout-tools/issues/2934"
  ]
}
-->

# 20261022-053116-cfdfa65-differential_receiver

Physical checks of the `differential_receiver` layout leaf (issue #167), generated by
`layout/analog/differential_receiver/run_checks.py` from the committed GDS.
Every `klt` JSON envelope is committed verbatim under
`flow/analog-layout-differential_receiver/artifacts/20261022-053116-cfdfa65-differential_receiver/`.

**Scope.** One leaf of the analog partition. This record is the first analog leaf's evidence for T1 items 2 (layout), 3 (DRC), 4 (LVS) and the supply half of 11; the analog partition's rows stay unmet until every leaf has the same, and nothing here is cited from signoff/block-manifest.json (issue #167, out of scope).

## Layout

`layout/analog/differential_receiver/differential_receiver.gds` (`sha256:3e1055d4eea9ea96d21a834ec8263579879596c09b7cc3a5c4e3798feceba540`) is emitted by
`layout/analog/differential_receiver/gen.py`; regenerating it reproduces that hash byte for byte.
All devices are drawn for sky130 from `design/netlist/differential_receiver.spice`; no gf180 geometry is used.

## DRC

- **Curated deck** (`klt drc --deck sky130`): `status: clean`, 0 violations.
  Deck content hash `sha256:ba0f97887e3d231aec8b54f1f52f2941ded0228f0234b6759712bcaca0e942e6`.
  - `layers_in_stream_without_rules`: 66/13, 68/5, 70/5
  - `rules_skipped`: 71 of the deck's rules (layers absent from the stream), 79 rules checked
  - `deck_scope`: cap2m, capm, ct, difftap, li, licon, m1, m2, m3, m4, m5, npc, nsdm, nwell, poly, psdm, rpm, urpm, via, via2, via3, via4, x
  - `unmodeled_rules` (33): difftap.10, difftap.11, difftap.8, difftap.9, hvi.1, hvi.2a, hvntm.1, hvntm.2, hvtp.1, hvtp.2, hvtr.1, hvtr.2, hvtr.2_a, m1.3ab, m1.5, m2.3ab, m2.5, m3.3ab, m4.5ab, n/psdm.10a, n/psdm.10b, n/psdm.5a, n/psdm.5b, n/psdm.6, n/psdm.7, n/psdm.8, npc.4, pad.2, rdl.1, rdl.2, via.5a, via2.5, via3.5
  - `voltage_domain_warnings`: [{"marker": "75/20", "description": "hvi (75/20) marks sky130's 5V-gate/10.5V-drain thick-oxide voltage domain (see sky130.lvs's ngate_high_voltage/pgate_high_voltage). This curated deck models it for MOS device recognition/model binding (issue #1369: sky130_fd_pr__nfet_g5v0d10v5/pfet_g5v0d10v5 under --pdk) and for one DRC rule (nwell.enclosed.hvi.1, nwell.9, issue #3031); no other DRC rule here reads hvi, so every rule still applies its general-case threshold to geometry drawn inside hvi (e.g. diff.width.1 checks difftap.1's 0.15 um where the real DRM's medium-voltage column, difftap.14, requires 0.29 um -- not transcribed in this deck yet)."}]
- **PDK-native deck** (`klt drc --engine klayout`, `sky130A/libs.tech/klayout/drc/sky130A_mr.drc`, `sha256:caf4a6b08cb12f78d6bb2d120737424c786b3bae8d6489234b9b269e91107bfc`):
  `status: clean`, 0 violations, against
  `--expect-rule-categories 244` (244 declared). This is the
  stronger check: the curated deck cannot see the 5V (`hvi`) rule columns, the native one does.
  It is not a foundry signoff run.

## LVS

`klt lvs` engine `klayout-runset`, runset `sky130.lvs` (`sha256:5b4ede4bdb4744b60e42c9b29baa93f40bb24430fb8f3a48a276a712a492ac38`),
deck vars {"convert_subckts": "true", "scale": "true", "thr": "2"}, standalone klayout 0.28.16.

- `status: match`; devices 11/11, nets 10/10, pins 5/5
- warnings-only mismatches: none
- `body_verification`: null -- null: the klayout-runset engine does not compute it. The bulk terminal is still extracted and compared -- the runset's MOS4 and resistor-with-bulk device classes carry B / W -- so the 11 matched devices include their bulk nets.
- `power_connectivity`: `unchecked` -- no subcircuit instance in the runset's extracted netlist declares a power/ground-named pin -- the extraction carries no instance-level power connectivity to check
- 102 runset device classes are declared but not present in this block (not a gap for this block).

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
