# `ratification/` — installed reviewer-key skills

`ee-key/` and `market-key/` hold the two non-author review keys used on this
repo's spec-ratification PR (installed by #48).

**Both directories are generated output**, copied verbatim from an internal,
private-repo-only generation tool — see each directory's own `MANIFEST.md`,
which says so and says "Do not hand-edit; regenerate instead". They are meant
to stay byte-identical to the same install in every other canary repo, so a
plain

```
diff -rq ratification/ee-key/ <other-canary>/ratification/ee-key/
```

answers "is this copy stale?". Hand-editing a file inside either directory
breaks that check *and* is silently undone by the next regeneration, so fixes
to their content belong in the generator, upstream. This file is deliberately
outside both generated trees for the same reason: adding a file inside
`ee-key/` or `market-key/` would itself break the `diff -rq` parity it
documents.

## Known non-repo-local references (issue #49)

Two relative paths in the generated ee-key text point at locations that live
in the generation tool's own repository and are **not** part of the copied
install payload, so following them from this repo gets a 404. Both were
checked against the generator's source and its input tree on 2026-08-27;
neither is a typo in this repo's content.

### 1. `ratification/canary-variant.md` — fixed at the source, resolved here

`ee-key/MANIFEST.md`'s closing line, as installed by #48, ended:

> — see `ratification/canary-variant.md`'s "Installation file layout" for the
> process this manifest is the output of.

That wording came from an older revision of the generator's `MANIFEST.md`
template. The template has since been changed upstream (tracked and closed on
the tool's own issue tracker) to the phrasing the market-key generator already
used, which promises no repo-local file:

> — see the generation tool's own documentation for the exact install layout
> and for the process this manifest is the output of.

This repo's copy was generated a few hours before that change landed, so the
installed file was a stale artifact rather than correct-as-generated output.
PR #50 replaced only that one line with the current template's text. The
result is **not** a hand-authored approximation: the whole of
`ratification/ee-key/` was verified byte-for-byte against a fresh run of the
generator over its own inputs (`diff -rq` clean, including `MANIFEST.md`,
`SKILL.md` and `rubric.md`) before the change was committed. The same
correction was made for `market-key/MANIFEST.md` in `138aa69`, on the same
byte-for-byte basis.

### 2. `dry-runs/` — intentional, left exactly as generated

`ee-key/SKILL.md`'s "Output format" section contains a relative markdown link
to `dry-runs/`, offering a document there as the place to write up a dry-run
review that has no live PR to post into. (Written as plain code text here on
purpose — this note deliberately does not reproduce the link.)

That directory exists in the generation tool's repository, alongside the
ee-key skill sources, and holds worked dry-run reviews written while the key
was being developed. It is deliberately **not** part of what gets copied into
a canary repo — `ee-key/MANIFEST.md` lists exactly two skill files, `SKILL.md`
and `rubric.md`, which is what was installed.

**This file is left untouched**, because unlike case 1 it *is* current
generator output: editing it would put this repo's copy out of parity with
every other canary's install while changing nothing about how the key is
actually used. The instruction it supports still reads correctly without a
resolvable link — a dry-run write-up is a document rather than a PR review
comment, wherever the reviewer chooses to put it. Whether the generator should
drop the link or ship the directory is a generator-side decision and has been
filed on the tool's own tracker; when that lands, the fix arrives here through
a regeneration, not a hand-edit.

Until then, treat the `dry-runs/` link in `ee-key/SKILL.md` as a
confirmed-intentional forward reference into the generation tool's repository,
not as a broken link in this repo's own documentation.
