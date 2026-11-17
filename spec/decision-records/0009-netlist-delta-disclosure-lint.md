# 0009: Netlist-delta disclosure lint for superseding records

- **Status**: proposed
- **Date**: 2026-11-17
- **Decided by**: operator ruling (rjwalters, attended `/fleet:decide` round
  20261116-r15, q97: option (a)); rule drafted and recorded by the Builder of
  issue #387. This record follows the usual ratification path — two reviews,
  then the operator — and is **not** self-ratified by the PR that adds it.

## Context

A record that supersedes another can commit different netlist bytes with
nothing in the record saying why. `flow/check_records.py`'s synthesis-only
rules compare a record against itself — its committed netlist against its own
recorded sha256 (skipped for superseded records), its reproduction run
against its own bytes — but nothing compared a record's netlist hash with its
`supersedes` target's. The `utmi-top` chain shows the gap twice:
`20261008-210449-1a11293` → `20261017-193151-1e192d8` changed the hash
(`36d1…744b` → `4444…edd`), and `20261024-000101-85fcd37` →
`20261117-051541-1378c0e` changed it again (`4444…edd` → `2dc5…1b223`); the
latter is the record PR #285 minted and landed on `main` on 2026-11-17
(issue #387 was filed against its branch). Neither record states what changed
in the netlist, which tool version produced it, or whether the new bytes are
logically equivalent to the old — so a reviewer cannot tell a deliberate
re-synthesis from a silent divergence.

## Decision

Option (a) of the operator ruling: **a lint rule in this repo**. Options (b)
pin-the-minting-klt and (c) status quo are declined and are not implemented.

`flow/check_records.py` gains rule 8f (`check_netlist_delta_disclosure`,
run pairwise by `lint_experiment` over one experiment's records): when a
record minted after the cutoff constant

```python
NETLIST_DELTA_DISCLOSURE_CUTOFF = "20261117-051541-1378c0e-tt_025C_1v80"
```

supersedes a record present in the same experiment whose
`stages.synthesize.netlist.sha256` differs, the superseding record must carry
a new record field under `stages.synthesize`:

- **`netlist_delta.prior_klt_version`** / **`netlist_delta.new_klt_version`**
  — the `provenance.klt_version` on each side of the delta, stated explicitly
  even when the two are equal; and
- **`netlist_delta.structural_equivalence`** — what changed in the netlist
  and why it is, or is not, logically equivalent.

An empty or whitespace-only disclosure field is a finding, as is a disclosed
version that disagrees with the two records' own `provenance.klt_version`
values. Same-hash supersessions need no disclosure and no field. The finding
rides the existing `synthesis-only` channel; no new finding class. The field
is deliberately **not** added to `REQUIRED_FIELDS` (or every existing record
would fail); it is required only in the changed-hash case, and the rule is
enforced alongside `flow/README.md`, which remains the authoritative statement
of the convention.

**Non-retroactivity and the cutoff.** Records are append-only (the
MANIFEST.sha256 and base-ref gates enforce it), so the two committed hash
changes cannot be retrofitted with disclosures; editing them is refused. The
rule therefore holds only records whose `record_id` sorts **strictly after**
the cutoff constant — a plain string compare, valid because record ids begin
with their mint date and time. The cutoff is the newest record id on `main`
at the time the rule was written (`20261117-051541-1378c0e-tt_025C_1v80`,
PR #285's record): the last record allowed to change netlist bytes silently.
Naming the constant in this record and in `check_records.py` is what makes
the grandfathering auditable.

**Sequencing.** Issue #387 left the choice to this PR — whether #285 rebases
onto the new rule or the cutoff sits after its record. PR #285 merged
2026-11-17 05:44 UTC before this PR, so its record is on `main` and locked;
the cutoff sits at that record. This PR does not rewrite that record, and no
committed record is edited.

This extends the record conventions documented in `flow/README.md`. It does
not amend `spec/usb2-phy.md` or `spec/architecture.md` — no spec row, limit,
or measurement changes.

## Alternatives considered

- **(b) Pin the minting klt version and refuse records minted under any
  other** — declined by the operator ruling: a pin rejects legitimate
  re-mints under a newer tool and still does not force a statement of what
  changed; the disclosure is strictly more information.
- **(c) Status quo** — declined by the operator ruling: different committed
  netlist bytes with no stated reason is exactly the silence this repo's
  evidence convention exists to prevent.
- **A git-diff-based "was the netlist touched in this PR" check** — rejected
  in curation: it needs a base ref and is weaker than comparing the records'
  own recorded hashes, which works even when the pair straddles branches.
- **A retroactive rule with back-filled disclosures** — impossible without
  violating append-only, which is the point of the evidence chain; rejected.

## Consequences

- A future synthesis re-mint whose netlist bytes differ must write the
  disclosure at mint time; the evidence lint fails the PR otherwise. The
  minting driver (`flow/run_synth_utmi_top.py`) and any manual mint must
  collect the klt versions and the equivalence statement while the run is
  fresh, because the disclosure cannot be added to a record after it lands.
- Existing committed records stay green with no edits, including both
  pre-rule hash changes in `flow/utmi-top/records/`.
- `flow/check_records.py` is hash-pinned by signoff item 10
  (`ci-evidence-lint`), so this change re-pins via
  `python3 signoff/check.py --regen` under the pinned grader.
- A `supersedes` target absent from its experiment directory is not this
  rule's finding (the pairwise comparison needs both sides in hand); the
  existing rules continue to govern that case.

This record introduces no numeric design target, so there is nothing awaiting
testbench verification here — it is a process rule over committed evidence.
