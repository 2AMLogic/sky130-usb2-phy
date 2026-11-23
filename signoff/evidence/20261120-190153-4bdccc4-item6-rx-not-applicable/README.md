# Item 6 receiver re-derivation: `not_applicable` negative controls — 20261120-190153-4bdccc4

- **Record ID**: 20261120-190153-4bdccc4-item6-rx-not-applicable
- **Status**: PASS (all six reports `pass`, zero undetected controls)
- **Why this exists**: issue #402, branch (b). The October 2026 receiver
  mismatch campaigns seed a deterministic negative control that, on ten
  measurement instances, cannot degrade the measurement by construction. The
  then-pinned grader (klt 0.9.1) refused all six cited reports with
  `negative_control_not_detected`; klayout-tools#4523 (shipped 2026-10-28)
  gave `klt yield` the per-measurement
  `{"not_applicable": true, "reason": "..."}` declaration for exactly this
  case. This directory re-derives the six reports with that declaration.
  **No new simulation was run** — the nominal and control samples are the
  committed October bytes, unchanged.
- **Derived from (append-only, untouched)**:
  - [`sim/diff-receiver-mismatch/records/20261020-202512-a78d2ac.md`](../../../sim/diff-receiver-mismatch/records/20261020-202512-a78d2ac.md)
    (campaign [`sim/diff-receiver-mismatch/campaigns/20261020-202512-a78d2ac/`](../../../sim/diff-receiver-mismatch/campaigns/20261020-202512-a78d2ac/)) — rows 6-09
  - [`sim/se-receiver-mismatch/records/20261020-202608-a78d2ac.md`](../../../sim/se-receiver-mismatch/records/20261020-202608-a78d2ac.md)
    (campaign [`sim/se-receiver-mismatch/campaigns/20261020-202608-a78d2ac/`](../../../sim/se-receiver-mismatch/campaigns/20261020-202608-a78d2ac/)) — rows 6-11
- **Tool**: `klt yield` of the registry wheel `klayout-tools[yield]==0.9.1`
  (the grader pin at the time of derivation). The manifest is graded by the
  currently pinned `0.9.2` (`signoff/toolchain.json`), which reads the
  declaration; producer and grader are pinned separately.

## Transformation

[`derive.py`](derive.py) copies each of the six committed `*.samples.json`
documents and replaces **only** the affected measurement's input
`negative_control` object (which carried the control's 50 samples) with the
declaration. Everything else — nominal sample arrays, the `derivation`
hashes, every detected control — is carried over unchanged; the originals
round-trip byte-identically through `json.dumps(indent=2)`, so a diff of a
derived sample set against its October source shows exactly the replaced
control objects (3 hunks per differential file, 1 per single-ended file).

| Derived samples | Undeclared → declared `not_applicable` | Reason (checkable against the campaign record's Method section) |
|---|---|---|
| `diff-tt.samples.json`, `diff-binding.samples.json` | `rxd_p200_cm0p80_v`, `rxd_p200_cm1p65_v`, `rxd_p200_cm2p50_v` | one-sided defect: the control's fixed +0.25 V differential input offset (`skew_v`) adds to the +200 mV stimulus and only raises RXD at VDIFF = +200 mV |
| `dp-{tt,binding}.samples.json`, `dm-{tt,binding}.samples.json` | `rxd_low_max_v` | one-sided defect: the control's divider skew (R2 length 14 → 60) raises VREF past VIH, which only keeps RXD low over the 0–0.8 V sweep |

Commands (run from this directory, pinned grader on `PATH`):

```bash
python3 derive.py
klt yield diff-tt.samples.json      --limits ../../../sim/diff-receiver-mismatch/campaigns/20261020-202512-a78d2ac/diff-tt.limits.json      --format json > diff-tt.yield.json
klt yield diff-binding.samples.json --limits ../../../sim/diff-receiver-mismatch/campaigns/20261020-202512-a78d2ac/diff-binding.limits.json --format json > diff-binding.yield.json
klt yield dp-tt.samples.json        --limits ../../../sim/se-receiver-mismatch/campaigns/20261020-202608-a78d2ac/dp-tt.limits.json        --format json > dp-tt.yield.json
klt yield dp-binding.samples.json   --limits ../../../sim/se-receiver-mismatch/campaigns/20261020-202608-a78d2ac/dp-binding.limits.json   --format json > dp-binding.yield.json
klt yield dm-tt.samples.json        --limits ../../../sim/se-receiver-mismatch/campaigns/20261020-202608-a78d2ac/dm-tt.limits.json        --format json > dm-tt.yield.json
klt yield dm-binding.samples.json   --limits ../../../sim/se-receiver-mismatch/campaigns/20261020-202608-a78d2ac/dm-binding.limits.json   --format json > dm-binding.yield.json
```

The limits paths are relative to this directory and point back at the
original, append-only campaign limits — no limit was copied or edited.

## Observed (per report)

| Report | `not_applicable` | `detected` | status | warnings |
|---|---|---|---|---|
| `diff-tt.yield.json` | 3 | 6 | pass | 0 |
| `diff-binding.yield.json` | 3 | 6 | pass | 0 |
| `dp-tt.yield.json` | 1 | 2 | pass | 0 |
| `dp-binding.yield.json` | 1 | 2 | pass | 0 |
| `dm-tt.yield.json` | 1 | 2 | pass | 0 |
| `dm-binding.yield.json` | 1 | 2 | pass | 0 |

The nominal statistics are unchanged from the October reports: every
measurement keeps its n (400), errored count (0), limits, empirical
(Clopper-Pearson) yield and CI, and `sufficient` sample-size verdict, and
every previously-`detected` control is still `detected` with the same
empirical yield. The only moved numbers are renderings of **degenerate**
(zero-variance) populations, where the 0.9.1 producer reports
`normality.verdict: "degenerate"` (statistic `null`, stddev `0.0`) and
omits the meaningless parametric `normal` estimate that the 0.7.1 producer
of the October reports printed (the per-measurement warning text moves with
it: the Anderson-Darling non-normality warning gives way to the
bounded-from-below one) — the October reports were produced by klt
0.7.1; these are produced by the 0.9.1 wheel (graded by the pinned 0.9.2).

## Citation

`signoff/block-manifest.json` `evidence."6.analog"` cites the six
`*.yield.json` reports here (diff against `6-09`, single-ended against
`6-11`), each pinned by the `content_hash` of the derived samples document
the report names. Rows 6-06 and 6-14 remain uncovered (#331).
