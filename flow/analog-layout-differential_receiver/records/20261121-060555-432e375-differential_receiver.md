<!-- record-meta
{
  "schema": "usb2phy.flow.record/1",
  "record_kind": "analog-layout",
  "record_id": "20261121-060555-432e375-differential_receiver",
  "experiment": "analog-layout-differential_receiver",
  "block": "differential_receiver",
  "created_utc": "2026-11-21T06:05:55Z",
  "git_revision": "432e375dec35eb204f4fba61055655458f747d65",
  "supersedes": "20261120-195744-745d347-differential_receiver",
  "design": {
    "block": "differential_receiver",
    "netlist": "design/netlist/differential_receiver.spice",
    "gds": "layout/analog/differential_receiver/differential_receiver.gds",
    "generator": "layout/analog/differential_receiver/gen.py",
    "anchors_design_claim": false,
    "claim_note": "This record supplies the first analog leaf's physical evidence. The block manifest selects frozen reports for the partition, and the pinned signoff grader evaluates them."
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
        "content_hash": "sha256:f78d2c3c9e92909b5baff6e00ece15a4158a55ca027a3ca20a96a7c6f10c0f42"
      },
      "coverage": {
        "layers_in_stream_without_rules": [
          "66/13",
          "68/5",
          "70/5"
        ],
        "rules_checked_count": 82,
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
          "MR_li.WID.4",
          "MR_licon.SP.1",
          "MR_lvtn.OVL.2",
          "MR_rdl.CON.1",
          "MR_thkox.CON.1",
          "MR_tunm.CON.1",
          "cap2m.11",
          "cap2m.2b",
          "cap2m.2b_a",
          "cap2m.3_a",
          "cap2m.5",
          "capm.10",
          "capm.11",
          "capm.2b",
          "capm.2b_a",
          "capm.5",
          "capm.6",
          "capm.7",
          "capm.8",
          "ct.3",
          "ct.3_a",
          "ct.3_b",
          "ct.4",
          "ct.irdrop.1",
          "ct.irdrop.2",
          "denmos.1",
          "denmos.10",
          "denmos.11",
          "denmos.12",
          "denmos.13",
          "denmos.2",
          "denmos.3",
          "denmos.4",
          "denmos.5",
          "denmos.6",
          "denmos.7",
          "denmos.8",
          "denmos.9a",
          "denmos.9b",
          "depmos.1",
          "depmos.10",
          "depmos.11",
          "depmos.12",
          "depmos.2",
          "depmos.3",
          "depmos.4",
          "depmos.5",
          "depmos.6",
          "depmos.7",
          "depmos.8",
          "depmos.9a",
          "depmos.9b",
          "difftap.10",
          "difftap.11",
          "difftap.1_a",
          "difftap.1_b",
          "difftap.1_c",
          "difftap.2",
          "difftap.4",
          "difftap.5",
          "difftap.6",
          "difftap.7",
          "difftap.8",
          "difftap.9",
          "dnwell.1",
          "dnwell.2",
          "dnwell.3",
          "dnwell.4",
          "dnwell.5",
          "extd.1",
          "extd.2",
          "hv.diff.1",
          "hv.diff.2",
          "hv.diff.3a",
          "hv.nwell.1",
          "hv.poly.2",
          "hv.poly.3",
          "hv.poly.4",
          "hv.poly.6",
          "hvdifftap.14",
          "hvdifftap.14a",
          "hvdifftap.15a",
          "hvdifftap.15b",
          "hvdifftap.16",
          "hvdifftap.17",
          "hvdifftap.18",
          "hvdifftap.19",
          "hvdifftap.20",
          "hvdifftap.21",
          "hvdifftap.22",
          "hvdifftap.23",
          "hvdifftap.24",
          "hvdifftap.25",
          "hvi.1",
          "hvi.2",
          "hvi.2a",
          "hvi.4",
          "hvntm.1",
          "hvntm.2",
          "hvntm.3",
          "hvntm.4",
          "hvntm.5",
          "hvntm.6a",
          "hvntm.9",
          "hvnwel.9",
          "hvnwell.8",
          "hvpoly.13",
          "hvpoly.14",
          "hvtp",
          "hvtp.1",
          "hvtp.2",
          "hvtp.3",
          "hvtp.4",
          "hvtp.5",
          "hvtr.1",
          "hvtr.2",
          "hvtr.2_a",
          "ldntm.1",
          "ldntm.2",
          "li.1a",
          "li.3a",
          "li.5",
          "li.6",
          "li.7",
          "li.8",
          "licon.10",
          "licon.11",
          "licon.11a",
          "licon.11c",
          "licon.12",
          "licon.13",
          "licon.13_a",
          "licon.14",
          "licon.15",
          "licon.16",
          "licon.17",
          "licon.18",
          "licon.1_c",
          "licon.1b/c",
          "licon.2",
          "licon.2b",
          "licon.2c",
          "licon.2d",
          "licon.4",
          "licon.6",
          "licon.7",
          "licon.8a",
          "lvtn.1",
          "lvtn.12",
          "lvtn.13",
          "lvtn.1a",
          "lvtn.2",
          "lvtn.3a",
          "lvtn.3b",
          "lvtn.4b",
          "lvtn.9",
          "m1.11",
          "m1.3ab",
          "m1.4a",
          "m1.4a_a",
          "m1.5",
          "m1.x",
          "m2.11",
          "m2.3ab",
          "m2.4_a",
          "m2.4_b",
          "m2.5",
          "m2.via",
          "m2.x",
          "m3.11",
          "m3.3ab",
          "m3.3cd",
          "m3.4_a",
          "m3.via2",
          "m3.x",
          "m4.11",
          "m4.15",
          "m4.3_a",
          "m4.5ab",
          "m4.via3",
          "m4.x",
          "m5.3_a",
          "m5.via4",
          "m5.x",
          "mf.1",
          "mf.2",
          "mf.3",
          "moduleCut.1",
          "n/psdm.10a",
          "n/psdm.10b",
          "n/psdm.5a",
          "n/psdm.5b",
          "n/psdm.6",
          "n/psdm.7",
          "n/psdm.8",
          "ncm.1",
          "ncm.2",
          "ncm.2a",
          "ncm.3",
          "ncm.5",
          "ncm.6",
          "ncm.7",
          "ncm.x.3",
          "npc.4",
          "nsdm.2",
          "nsdm.3",
          "nsdm.4",
          "nsdm.5",
          "nsdm.6",
          "nsdm.6a",
          "nsdm_psdm_overlap",
          "nsm.1",
          "nsm.2",
          "nsm.3",
          "nsm.4",
          "nwell.4",
          "nwell.5",
          "nwell.6",
          "nwell.7",
          "pad.2",
          "photo.10",
          "photo.2",
          "photo.3",
          "photo.4",
          "photo.5.6",
          "photo.7",
          "photo.8",
          "photo.9",
          "poly.10",
          "poly.11",
          "poly.12",
          "poly.15",
          "poly.1b",
          "poly.3",
          "poly.4",
          "poly.5",
          "poly.6",
          "poly.7",
          "poly.9",
          "psdm.2",
          "psdm.3",
          "psdm.4",
          "psdm.5",
          "psdm.6",
          "psdm.6a",
          "pwbm",
          "pwbm.4",
          "pwde.1",
          "pwde.2",
          "pwdem.3",
          "pwdem.4",
          "pwdem.5",
          "pwres.2",
          "pwres.3",
          "pwres.4",
          "pwres.5",
          "pwres.6",
          "pwres.8",
          "rdl.1",
          "rdl.2",
          "rfdiode.1",
          "rfdiode.2",
          "rpm.10",
          "rpm.2",
          "rpm.3",
          "rpm.4",
          "rpm.5",
          "rpm.6",
          "rpm.7",
          "rpm.8",
          "rpm.9",
          "thkox.1",
          "thkox.2",
          "tunm.1",
          "tunm.2",
          "tunm.3",
          "tunm.4",
          "tunm.5",
          "tunm.6a",
          "tunm.7",
          "uhvi.1",
          "uhvi.2",
          "uhvi.3",
          "uhvi.4",
          "uhvi.5",
          "uhvi.6",
          "uhvi.7",
          "urpm.2",
          "varac.1",
          "varac.2",
          "varac.3",
          "varac.4",
          "varac.5",
          "varac.6",
          "varac.7",
          "vhvi.1",
          "vhvi.2",
          "vhvi.3",
          "vhvi.5",
          "vhvi.7",
          "via.11",
          "via.12",
          "via.1b",
          "via.3",
          "via.3_a",
          "via.3_b",
          "via.4a_a",
          "via.4b",
          "via.4c.5c",
          "via.5a",
          "via1.14",
          "via1.5a",
          "via1.5b",
          "via2",
          "via2.11",
          "via2.12",
          "via2.14",
          "via2.1b",
          "via2.3",
          "via2.3_a",
          "via2.3_b",
          "via2.4_a",
          "via2.4a",
          "via2.5",
          "via3",
          "via3.1",
          "via3.11",
          "via3.12",
          "via3.13",
          "via3.4_a",
          "via3.5",
          "via4",
          "via4.1",
          "via4.3",
          "via4.3_a",
          "via4.3_b",
          "via4.4_a",
          "vpp.1",
          "vpp.13",
          "vpp.3",
          "vpp.4",
          "vpp.5",
          "vpp.5a",
          "vpp.5b",
          "vpp.5c",
          "vpp.8",
          "vpp.9"
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
      "reference": "design/netlist/differential_receiver.spice",
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
        "klayout_application_version": "0.30.12"
      },
      "declared_not_recognized_count": 102
    },
    "lvs_baseline": {
      "engine": "klayout",
      "reference": "design/netlist/differential_receiver.spice",
      "status": "mismatch",
      "counts": {
        "nets": {
          "layout": 10,
          "reference": 10,
          "matched": 7
        },
        "devices": {
          "layout": 21,
          "reference": 20,
          "matched": 19
        },
        "pins": {
          "layout": 5,
          "reference": 5,
          "matched": 5
        }
      },
      "category_error_counts": {
        "device.property": 1,
        "device.unmatched": 1,
        "topology": 2
      }
    },
    "lvs_curated": {
      "engine": "klayout",
      "reference": "design/netlist/differential_receiver.spice",
      "status": "mismatch",
      "counts": {
        "nets": {
          "layout": 10,
          "reference": 10,
          "matched": 7
        },
        "devices": {
          "layout": 11,
          "reference": 11,
          "matched": 10
        },
        "pins": {
          "layout": 5,
          "reference": 5,
          "matched": 5
        }
      },
      "category_error_counts": {
        "device.property": 2,
        "topology": 1
      }
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
    "klt_version": "0.9.3.dev2575+g6bd18bbc8637",
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
        "content_hash": "sha256:1ec2206d653d6c6981878fd1ca70ffc6072fe6e5bc304a4a13d6caa5cdf094d4"
      },
      {
        "path": "layout/analog/gen_common.py",
        "content_hash": "sha256:b07e1c5580699528b9f1fc20624b1f4d23421bda68e74572a87767ebf3b01e8c"
      },
      {
        "path": "layout/analog/gen_se_receiver.py",
        "content_hash": "sha256:3d171b1ed5e6d8535bd04445107dba47cd0efa683d735266e37ce5f487865291"
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
        "path": "layout/analog/differential_receiver/request-lvs-curated.json",
        "content_hash": "sha256:f0b38ea954897d1721ae75d3fbc38e5b3842a3bfba98b96d2203e96fa30d292c"
      },
      {
        "path": "sim/pdk-pins.json",
        "content_hash": "sha256:42fda161b11df5fc8611f074fad1913bfca193cd3986f7603c2ff629fe201a28"
      }
    ],
    "artifacts": [
      {
        "path": "flow/analog-layout-differential_receiver/artifacts/20261121-060555-432e375-differential_receiver/drc-report.json",
        "content_hash": "sha256:ce01f95a424fbe4abfc29e789424503bb6905f7c1030e63dbe9dfd653aba6f9b"
      },
      {
        "path": "flow/analog-layout-differential_receiver/artifacts/20261121-060555-432e375-differential_receiver/drc-native-report.json",
        "content_hash": "sha256:ecc86a73f2ec365b140b4c45a86b0c720d296ff4bb640711e06a7ade851d38d8"
      },
      {
        "path": "flow/analog-layout-differential_receiver/artifacts/20261121-060555-432e375-differential_receiver/lvs-report.json",
        "content_hash": "sha256:2f322d367993f38f54e9a3c6a3d89e2157680379902805f14739f9ac62a2b1b5"
      },
      {
        "path": "flow/analog-layout-differential_receiver/artifacts/20261121-060555-432e375-differential_receiver/lvs-curated-baseline-report.json",
        "content_hash": "sha256:1c0aab09a5f0f0a0dbc804af8ff9ffc82f8e0f7fc35f822e809bf8ad66ab0f4b"
      },
      {
        "path": "flow/analog-layout-differential_receiver/artifacts/20261121-060555-432e375-differential_receiver/lvs-curated-report.json",
        "content_hash": "sha256:4c4d0b9aa6d21f508dac9944ae243b1d534173a828e42838273db68f20345f9c"
      },
      {
        "path": "flow/analog-layout-differential_receiver/artifacts/20261121-060555-432e375-differential_receiver/erc-supply-report.json",
        "content_hash": "sha256:10404bd2f7e8aebd5a03e9e9178e456b4b346db1c857421736beb1034eff9628"
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

# 20261121-060555-432e375-differential_receiver

Physical checks of the `differential_receiver` layout leaf (issue #167), generated by
`layout/analog/differential_receiver/run_checks.py` from the committed GDS.
Every `klt` JSON envelope is committed verbatim under
`flow/analog-layout-differential_receiver/artifacts/20261121-060555-432e375-differential_receiver/`.

**Scope.** This record supplies the first analog leaf's physical evidence. The block manifest selects frozen reports for the partition, and the pinned signoff grader evaluates them.

## Layout

`layout/analog/differential_receiver/differential_receiver.gds` (`sha256:3e1055d4eea9ea96d21a834ec8263579879596c09b7cc3a5c4e3798feceba540`) is emitted by
`layout/analog/differential_receiver/gen.py`; regenerating it reproduces that hash byte for byte.
All devices are drawn for sky130 from `design/netlist/differential_receiver.spice`; no gf180 geometry is used.

## DRC

- **Curated deck** (`klt drc --deck sky130`): `status: clean`, 0 violations.
  Deck content hash `sha256:f78d2c3c9e92909b5baff6e00ece15a4158a55ca027a3ca20a96a7c6f10c0f42`.
  - `layers_in_stream_without_rules`: 66/13, 68/5, 70/5
  - `rules_skipped`: 71 of the deck's rules (layers absent from the stream), 82 rules checked
  - `deck_scope`: cap2m, capm, ct, difftap, li, licon, m1, m2, m3, m4, m5, npc, nsdm, nwell, poly, psdm, rpm, urpm, via, via2, via3, via4, x
  - `unmodeled_rules` (347): MR_li.WID.4, MR_licon.SP.1, MR_lvtn.OVL.2, MR_rdl.CON.1, MR_thkox.CON.1, MR_tunm.CON.1, cap2m.11, cap2m.2b, cap2m.2b_a, cap2m.3_a, cap2m.5, capm.10, capm.11, capm.2b, capm.2b_a, capm.5, capm.6, capm.7, capm.8, ct.3, ct.3_a, ct.3_b, ct.4, ct.irdrop.1, ct.irdrop.2, denmos.1, denmos.10, denmos.11, denmos.12, denmos.13, denmos.2, denmos.3, denmos.4, denmos.5, denmos.6, denmos.7, denmos.8, denmos.9a, denmos.9b, depmos.1, depmos.10, depmos.11, depmos.12, depmos.2, depmos.3, depmos.4, depmos.5, depmos.6, depmos.7, depmos.8, depmos.9a, depmos.9b, difftap.10, difftap.11, difftap.1_a, difftap.1_b, difftap.1_c, difftap.2, difftap.4, difftap.5, difftap.6, difftap.7, difftap.8, difftap.9, dnwell.1, dnwell.2, dnwell.3, dnwell.4, dnwell.5, extd.1, extd.2, hv.diff.1, hv.diff.2, hv.diff.3a, hv.nwell.1, hv.poly.2, hv.poly.3, hv.poly.4, hv.poly.6, hvdifftap.14, hvdifftap.14a, hvdifftap.15a, hvdifftap.15b, hvdifftap.16, hvdifftap.17, hvdifftap.18, hvdifftap.19, hvdifftap.20, hvdifftap.21, hvdifftap.22, hvdifftap.23, hvdifftap.24, hvdifftap.25, hvi.1, hvi.2, hvi.2a, hvi.4, hvntm.1, hvntm.2, hvntm.3, hvntm.4, hvntm.5, hvntm.6a, hvntm.9, hvnwel.9, hvnwell.8, hvpoly.13, hvpoly.14, hvtp, hvtp.1, hvtp.2, hvtp.3, hvtp.4, hvtp.5, hvtr.1, hvtr.2, hvtr.2_a, ldntm.1, ldntm.2, li.1a, li.3a, li.5, li.6, li.7, li.8, licon.10, licon.11, licon.11a, licon.11c, licon.12, licon.13, licon.13_a, licon.14, licon.15, licon.16, licon.17, licon.18, licon.1_c, licon.1b/c, licon.2, licon.2b, licon.2c, licon.2d, licon.4, licon.6, licon.7, licon.8a, lvtn.1, lvtn.12, lvtn.13, lvtn.1a, lvtn.2, lvtn.3a, lvtn.3b, lvtn.4b, lvtn.9, m1.11, m1.3ab, m1.4a, m1.4a_a, m1.5, m1.x, m2.11, m2.3ab, m2.4_a, m2.4_b, m2.5, m2.via, m2.x, m3.11, m3.3ab, m3.3cd, m3.4_a, m3.via2, m3.x, m4.11, m4.15, m4.3_a, m4.5ab, m4.via3, m4.x, m5.3_a, m5.via4, m5.x, mf.1, mf.2, mf.3, moduleCut.1, n/psdm.10a, n/psdm.10b, n/psdm.5a, n/psdm.5b, n/psdm.6, n/psdm.7, n/psdm.8, ncm.1, ncm.2, ncm.2a, ncm.3, ncm.5, ncm.6, ncm.7, ncm.x.3, npc.4, nsdm.2, nsdm.3, nsdm.4, nsdm.5, nsdm.6, nsdm.6a, nsdm_psdm_overlap, nsm.1, nsm.2, nsm.3, nsm.4, nwell.4, nwell.5, nwell.6, nwell.7, pad.2, photo.10, photo.2, photo.3, photo.4, photo.5.6, photo.7, photo.8, photo.9, poly.10, poly.11, poly.12, poly.15, poly.1b, poly.3, poly.4, poly.5, poly.6, poly.7, poly.9, psdm.2, psdm.3, psdm.4, psdm.5, psdm.6, psdm.6a, pwbm, pwbm.4, pwde.1, pwde.2, pwdem.3, pwdem.4, pwdem.5, pwres.2, pwres.3, pwres.4, pwres.5, pwres.6, pwres.8, rdl.1, rdl.2, rfdiode.1, rfdiode.2, rpm.10, rpm.2, rpm.3, rpm.4, rpm.5, rpm.6, rpm.7, rpm.8, rpm.9, thkox.1, thkox.2, tunm.1, tunm.2, tunm.3, tunm.4, tunm.5, tunm.6a, tunm.7, uhvi.1, uhvi.2, uhvi.3, uhvi.4, uhvi.5, uhvi.6, uhvi.7, urpm.2, varac.1, varac.2, varac.3, varac.4, varac.5, varac.6, varac.7, vhvi.1, vhvi.2, vhvi.3, vhvi.5, vhvi.7, via.11, via.12, via.1b, via.3, via.3_a, via.3_b, via.4a_a, via.4b, via.4c.5c, via.5a, via1.14, via1.5a, via1.5b, via2, via2.11, via2.12, via2.14, via2.1b, via2.3, via2.3_a, via2.3_b, via2.4_a, via2.4a, via2.5, via3, via3.1, via3.11, via3.12, via3.13, via3.4_a, via3.5, via4, via4.1, via4.3, via4.3_a, via4.3_b, via4.4_a, vpp.1, vpp.13, vpp.3, vpp.4, vpp.5, vpp.5a, vpp.5b, vpp.5c, vpp.8, vpp.9
  - `voltage_domain_warnings`: [{"marker": "75/20", "description": "hvi (75/20) marks sky130's 5V-gate/10.5V-drain thick-oxide voltage domain (see sky130.lvs's ngate_high_voltage/pgate_high_voltage). This curated deck models it for MOS device recognition/model binding (issue #1369: sky130_fd_pr__nfet_g5v0d10v5/pfet_g5v0d10v5 under --pdk) and for one DRC rule (nwell.enclosed.hvi.1, nwell.9, issue #3031); no other DRC rule here reads hvi, so every rule still applies its general-case threshold to geometry drawn inside hvi (e.g. diff.width.1 checks difftap.1's 0.15 um where the real DRM's medium-voltage column, difftap.14, requires 0.29 um -- not transcribed in this deck yet)."}]
- **PDK-native deck** (`klt drc --engine klayout`, `sky130A/libs.tech/klayout/drc/sky130A_mr.drc`, `sha256:caf4a6b08cb12f78d6bb2d120737424c786b3bae8d6489234b9b269e91107bfc`):
  `status: clean`, 0 violations, against
  `--expect-rule-categories 244` (244 declared). This is the
  stronger check: the curated deck cannot see the 5V (`hvi`) rule columns, the native one does.
  It is not a foundry signoff run.

## LVS

`klt lvs` engine `klayout-runset`, runset `sky130.lvs` (`sha256:5b4ede4bdb4744b60e42c9b29baa93f40bb24430fb8f3a48a276a712a492ac38`),
deck vars {"convert_subckts": "true", "scale": "true", "thr": "2"}, standalone klayout 0.30.12.

- `status: match`; devices 11/11, nets 10/10, pins 5/5
- warnings-only mismatches: none
- `body_verification`: null -- null: the klayout-runset engine does not compute it. The bulk terminal is still extracted and compared -- the runset's MOS4 and resistor-with-bulk device classes carry B / W -- so the 11 matched devices include their bulk nets.
- `power_connectivity`: `unchecked` -- no subcircuit instance in the runset's extracted netlist declares a power/ground-named pin -- the extraction carries no instance-level power connectivity to check
- 102 runset device classes are declared but not present in this block (not a gap for this block).

Curated sky130 LVS reads `design/netlist/differential_receiver.spice` directly. Layout / reference / matched
device counts are reported by each comparison below.

| Curated comparison | Status | Layout | Reference | Matched |
|---|---|---:|---:|---:|
| lvs-curated-baseline-report.json | mismatch | 21 | 20 | 19 |
| lvs-curated-report.json | mismatch | 11 | 11 | 10 |

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
