# Harness sharing analysis (issue #119)

Analysis only. Nothing here changes `sim/harness` behavior, `reuse.lock.json`
(no file changes mode, nothing is vendored), or the ratified matrix. Upstream
facts are about `2AMLogic/gf180-usb2-phy` @ `0aab249`; they are source
evidence about that repo's code structure, never a sky130 claim. Every
sky130 result in this repo comes from this repo's own `sim/*/records/`.

Method: upstream files were read at the pin with
`gh api -H "Accept: application/vnd.github.raw" "repos/2AMLogic/gf180-usb2-phy/contents/<path>?ref=0aab249"`
(all nine were readable; none is marked unverified). Line numbers below are
from those blobs. Local line numbers are from this repo at the commit that
adds this note; re-check with the quoted grep if the files move.

Terms: **neutral** = no PDK name, library, section list, temperature or
supply default in the file's logic; **specific** = the file is mostly PDK
facts; **mixed** = reusable mechanics with PDK facts embedded or imported.

## 1. Local modules (`sim/harness/`)

| Module | Lines | Verdict | Evidence (reproduce with grep) |
|---|---|---|---|
| `evidence_lint.py` | 220 | **mixed** (mostly neutral) | Neutral grammars/checks: `RECORD_ID_RE` L34, `FIELD_RE` L35, `NO_SUPERSESSION_RE` L38, `parse_fields` L45, `check_append_only` L58, `sha256_file` L41. Repo-shaped: `EVIDENCE_PATH_RE` L37 hardcodes `sim/[^/]+/(records\|netlist-snapshots\|corners)/`; `CORNER_LOG_RE` L36 hardcodes two-decimal supply (`\d+\.\d\d`) and `[a-z]+` process. PDK-coupled: `from . import matrix as mx, results as rs` L30, and `check_pass_record` L114-146 calls `mx.from_dict`/`mx.check_request`/`rs.evaluate`/`rs.job_id`. `grep -n "mx\.\|rs\." sim/harness/evidence_lint.py` |
| `matrix.py` | 123 | **mixed** | Neutral: `Matrix` dataclass L28, `points()`, `corner_id` L43 (`<process>_<temp>c_<supply>v`), `key` L48 (rounding), `MatrixError`. Specific: `SCHEMA = "sky130-usb2-phy.sim.corners/1"` L17, `SKY130_SECTIONS` L20, "not a sky130 MOS corner section" L73; `check_request` L81 is neutral logic whose wording and gf180-rejection docstring (L84-87) are sky130-flavored. Data (library, sections, temps, supplies) lives in `sim/corners.json`, not in the module. `grep -n "sky130\|SKY130" sim/harness/matrix.py` |
| `results.py` | 175 | **mixed** | Neutral: `corner_key` L54, `evaluate` L63 (bounds, finite checks, spread check), `mx_supply` L161, `job_id` L166. `build_request` L19 is a neutral klt-request builder: `"engine": "ngspice"`, models from `matrix.pdk` (library name comes from the matrix, not a literal). Only coupling is `from . import matrix as mx` L13 and `from . import trim as trimmod` L14 (design-specific hook). |
| `runner.py` | 336 | **mixed** | Neutral: `sha256_*` L29/L33, `_git` L82, `tool_version` L87, `allocate_record_id` L95, `invoke_klt` L103, `write_evidence` L121. PDK-specific: `find_pdk_dir` L37 (search roots `~/.volare`, `~/.ciel`, `/usr/share/pdk`), `lib_sections` L51 (`.lib <section>` scan), `check_env` L60 (reads `SOURCES` for an `open_pdks` pin), `"resolved request is not the sky130 matrix"` L257, `SCHEMA` literal `sky130-usb2-phy.sim.evidence/1` L274. Design-specific: `SMOKE_RECORD_DEFAULTS` L152, `render_record` L171. |
| `trim.py` | 80 | **PDK-neutral, design-specific** | Pure math for the D+ pull-up trim (`r_eff` L26, `analyse` L40); no PDK name, library, or corner constant. Belongs with the block experiment, not in a shared core. `grep -n "sky130\|gf180" sim/harness/trim.py` returns nothing. |
| `__init__.py` | 10 | neutral | `HARNESS_VERSION = "0.1.0"` only. |

## 2. Upstream modules (gf180-usb2-phy @ 0aab249)

| Module | Lines | Verdict | Evidence |
|---|---|---|---|
| `sim/harness/corners.py` | 191 | **PDK-specific** | Docstring L1-4 names gf180mcu and `sm141064.ngspice`; `DEFAULT_TEMPERATURES_C = (-40, 27, 125)` L32; `DEFAULT_SUPPLY_TOLERANCE = 0.10` L33; `DEFAULT_NOMINAL_SUPPLY_V = 3.3  # gf180mcu 3.3 V flavor` L34; `_bundle(mos, bjt, diode, res, moscap, mimcap)` L37 plus the nine-section sets `CORNER_SETS` L103-109 (`res_ff`, `res_ss`, `bjt_ff`, `bjt_ss`). Only `PvtPoint` L151 and `build_grid` L179 are mechanics, and they consume the constants above. |
| `sim/harness/pdk.py` | 181 | **PDK-specific** | `GF180_PDK_PATH` L9/L151, `DEFAULT_VARIANT = "gf180mcuD"` L29, `sm141064.ngspice` L92/L126, install hint L42-60. `repo_relative` L117 is neutral but is imported by `testbench.py` L46 (see below). |
| `sim/harness/klt_backend.py` | 271 | **mixed** | `"models": {"pdk": pdk.variant, "lib": "libs.tech/ngspice/sm141064.ngspice"}` L135 (literal library). Imports `PvtPoint` (corners L33), `Pdk` (pdk L34), `PointResult` (runner L35), `Testbench` (testbench L36). `build_request` L71 and `run_grid_klt` L158 are the neutral klt request/result mechanics; `DEFAULT_SUPPLY_SOURCE = "vsup"` L39 is a convention. |
| `sim/harness/runner.py` | 257 | **mixed** | Neutral: `parse_measurements` L137, `_MEAS_RE` L21, `ngspice_version` L29, `PointResult` L109, `run_grid` L229. gf180-coupled: `compose_deck` L46 emits `* ---- gf180mcu models` L63, `.include pdk.design_include` L64, `.lib pdk.model_lib <section>` L67. Imports corners/pdk/testbench L13-15. This is the local-ngspice path; the sky130 harness is klt-only and has no equivalent. |
| `sim/harness/report.py` | 602 | **mixed** | Neutral: `format_record_id` L102, `allocate_record_id` L112, `git_provenance` L92, `summarize` L133, `render_record` L495, `write_record` L592. Hardcoded gf180 policy text: "full matrix (-40/27/125 C, +-10 % supply ...)" L251 and L430. Imports `HARNESS_VERSION`, corners (L32), `Pdk` (L37), `PointResult` (L38), `Testbench` (L39); `environment(pdk, ...)` L224 and `pdk.provenance()` L242 take a gf180 `Pdk`. |
| `sim/harness/testbench.py` | 355 | **mixed (mostly neutral)** | Neutral: manifest schema `tb.json` L48, forbidden-directive lists L54-82, `load` L203, `validate_dut` L310, `validate_netlist` L330, `discover` L346. Coupling: `from .corners import (` L40 and `from .pdk import repo_relative` L46 pull gf180 modules in for a path helper and corner-name validation. |
| `sim/harness/cli.py` | 457 | **PDK-specific** | "Run a testbench across the gf180mcu PVT corner grid." L52; `--version ... gf180-usb2-phy harness` L174; `# gf180mcu PDK not found` L220; `export GF180_PDK_PATH` / `GF180_MODELS` L229-230. Imports corners, klt_backend, report, runner, testbench, pdk L13-15. Glue; stays per-repo. |
| `sim/harness/evidence_lint.py` | 607 | **mixed** | Neutral: `validate_record_id` L165, `check_experiments` L460, `_check_supersedes` L431, `check_append_only` L500, `NO_SUPPLY` L131. The corner-id grammar L117-130 is deliberately open (process token `^[a-z][a-z0-9]*$`) and supply accepts `nwell2p97v`, but the comment names gf180mcu device-family sections (`bjt_ff`, `res_typical`) L119-122 and the temperature examples are `-40c, 27c, 125c`. Imports from `verification.check_records` L75 (see section 4). |
| `verification/check_records.py` | 484 | **mixed (neutral shared core + digital-flow linter)** | Stdlib-only imports L70-78. Neutral shared core: `RECORD_ID_RE` L89, `parse_fields` L144, `_git` L180, `resolve_base_sha` L197, `git_diff_name_status` L226. Digital-flow-only: `REQUIRED_META_KEYS` L91, `REQUIRED_PROVENANCE_KEYS` L98 (`klt_version`, `pdk`, `deck`, `inputs`), JSON `record-meta` block, `check_hash_freshness` L335. |

## 3. What would move into a neutral core vs. per-PDK config

Candidate neutral core (stdlib + git only; no PDK identifiers):

- **Record id grammar.** `RECORD_ID_RE`. Upstream `check_records.py` L89
  (named groups `date/time/sha`) and local `evidence_lint.py` L34 are the same
  pattern; ship one.
- **Corner-id grammar.** Upstream `evidence_lint.py` L117-130 (open process
  token, signed temperature, optional rail node plus `p`-decimal supply, and
  `nosupply`) and local `matrix.corner_id` L43 / `CORNER_LOG_RE` L36. The two
  repos disagree on supply formatting (upstream accepts one-or-more decimals
  and a node prefix; local requires exactly `\d+\.\d\d`). A neutral grammar
  must pick the superset and let the per-PDK config narrow it.
- **Field parser.** `parse_fields` (upstream `check_records.py` L144, local
  `evidence_lint.py` L45).
- **Evidence manifest + lint.** Evidence-dir checks, supersession chain
  (`NO_SUPERSESSION_RE`, `_check_supersedes`), snapshot/log existence, sha256
  of manifest members (local `check_evidence_dir` L88, upstream
  `check_experiments` L460). The evidence directory names
  (`records`, `netlist-snapshots`, `corners`) become config.
- **Append-only git check.** Local `check_append_only` L58, upstream
  `evidence_lint.check_append_only` L500 and `check_records.check_append_only`
  L370, over `resolve_base_sha`/`git_diff_name_status`.
- **klt request/result validation.** Local `results.build_request` L19,
  `results.evaluate` L63, `results.job_id` L166, `matrix.check_request` L81;
  upstream `klt_backend.build_request` L71 / `run_grid_klt` L158.
  `check_request` becomes "request equals the config's expected tuples".
- **Generic helpers.** `sha256_*`, `allocate_record_id`, `tool_version`,
  `invoke_klt`, `write_evidence`, `parse_measurements`, `git_provenance`.

Stays in per-PDK config (a data file or a small `pdk_config` module, one per
repo):

- model library path and PDK name (`matrix.pdk` in local `sim/corners.json`;
  upstream literal `sm141064.ngspice` at `klt_backend.py` L135, `pdk.py` L92);
- process section list and bundles (local `SKY130_SECTIONS` L20; upstream
  `_bundle`/`CORNER_SETS` L37/L103);
- temperature and supply defaults and tolerance (upstream `corners.py` L32-34;
  local values in `sim/corners.json`);
- PDK discovery (`pdk.py`; local `runner.find_pdk_dir` L37, `lib_sections`
  L51, `check_env` L60);
- schema id strings (`matrix.SCHEMA` L17, `runner.py` L274);
- policy text such as the matrix sentence in upstream `report.py` L251/L430;
- CLI names and env vars (`cli.py` L52, L174, L220, L229-230).

Design-specific, in neither (stay with the block): local `trim.py`,
`SMOKE_RECORD_DEFAULTS` and `render_record` in `runner.py`; upstream
`NO_SUPPLY` use for device testbenches.

## 4. The `verification/check_records.py` dependency

Upstream `sim/harness/evidence_lint.py` L73 does
`sys.path.insert(0, str(Path(__file__).resolve().parents[2]))` and L75 does
`from verification.check_records import (RECORD_ID_RE, _git,
git_diff_name_status, parse_fields, resolve_base_sha)`.

Finding, checked against the blob: at `0aab249` this is **not a Python import
cycle**. `check_records.py` imports only stdlib (L70-78); its only mentions of
`sim/harness` are docstring prose (L47, L62, L87). The real blocker is
directional and structural:

1. A file meant to be stamped byte-identical under `sim/harness/common/`
   imports from a sibling tree (`verification/`) that is not part of the
   stamped set, through a `sys.path` hack that assumes the master's directory
   depth (`parents[2]`). In this repo that import target does not exist and
   `sim/check_records.py` (L10-14) adds `sim/` to the path instead.
2. A documented, circular ownership contract: `check_records.py` L40-66 says
   its stdlib-only shared core exists *for* `sim/harness/evidence_lint.py`,
   while `verification/test_check_records.py` copies only that one file into
   a throwaway repo, so the core cannot be moved out without breaking that
   self-test. Each side constrains the other: neutral code cannot leave
   `check_records.py`, and `evidence_lint.py` cannot be neutral while it
   imports it.
3. `_git` is a private name (leading underscore) imported across modules.

Resolution to propose upstream: extract the shared core into a new
stdlib-only module that both linters import and that the fixture test copies
alongside (or have the test copy two files), then make `evidence_lint.py`
import only from that module and from siblings.

Upstream intra-harness graph (no cycles found, but a dense fan-in):
`klt_backend -> {corners, pdk, runner, testbench}`,
`report -> {corners, pdk, runner, testbench}`,
`runner -> {corners, pdk, testbench}`, `testbench -> {corners, pdk}`,
`cli -> all`. `grep -nE "^\s*from \." sim/harness/*.py` reproduces it.
Because `runner` and `testbench` both import `corners`/`pdk`, no upstream
file in the set except `check_records.py` is vendorable until those imports
are inverted (config passed in, not imported).

## 5. Conclusion for this repo

- Today no upstream file is vendorable as-is (consistent with #109 stamping
  every upstream file `fetched`).
- Local `results.py` and `evidence_lint.py` are the closest to a neutral
  core, but each still imports the local `matrix`. They would need
  `check_request`/`corner_id`/`key` to take the expected-tuple set as an
  argument instead of the `Matrix` module.
- The sharing evidence from block ports is consistent with the proposal:
  the pieces both repos had to write are exactly the grammars, lint, append-only
  check and klt request/result handling; the pieces that differ are the
  data in section 3's per-PDK list.
- Next step is a human or an agent with access to `2AMLogic/gf180-usb2-phy`
  filing the issue below. Recording its number here is the only follow-up
  edit to this note. Filed issue number: **not yet filed**.

## 6. Draft upstream issue text (design-neutral)

Title: `sim harness: split a PDK-neutral core from per-PDK configuration`

> The analog sim harness mixes reusable mechanics with PDK constants and
> intra-package imports, so a second repository on a different PDK cannot
> consume it byte-identically and has re-implemented the mechanics instead.
>
> Observed at `0aab249`:
> - `sim/harness/corners.py` holds the PDK's section bundles and default
>   temperature, supply and tolerance values (L32-34, L37, L103-109).
> - `sim/harness/pdk.py` and `klt_backend.py` embed the model library file
>   name and PDK-specific env var (`pdk.py` L9, L92; `klt_backend.py` L135).
> - `runner.py`, `report.py`, `klt_backend.py` and `testbench.py` import
>   `corners` and `pdk` (e.g. `testbench.py` L40, L46) for helpers and
>   types, so no module outside the config files is import-independent.
> - `report.py` L251/L430 hardcode matrix policy text.
> - `sim/harness/evidence_lint.py` L73-75 reaches into
>   `verification/check_records.py` via a `sys.path` insert and a private
>   name (`_git`); `check_records.py` documents that its shared core exists
>   for the harness while a self-test copies that single file elsewhere.
>
> Proposal:
> 1. Create a stdlib-plus-git-only core containing: record-id grammar,
>    corner-id grammar (superset: open process token, signed temperature,
>    optional rail node, fixed or variable supply decimals configurable),
>    field parser, evidence manifest and lint, supersession checks,
>    append-only git check, klt request building and result validation,
>    and generic helpers (sha256, record-id allocation, tool versions).
> 2. Move the PDK-dependent values behind one per-repo config: PDK name and
>    model library, section list/bundles, temperature and supply defaults,
>    PDK discovery, schema id strings, policy text, CLI naming.
> 3. Make core functions take that config (or expected corner tuples) as an
>    argument rather than importing it.
> 4. Extract the stdlib-only parts of `verification/check_records.py` into a
>    module both linters import, and update its self-test to copy it, so the
>    core no longer imports across `sim/` and `verification/`.
> 5. Publish the core with a stable path so consumers can vendor it
>    byte-identically and stamp it in their reuse lock.
>
> Acceptance: the core contains no PDK identifiers (grep for library file
> names, section names, and default temperature/supply literals returns
> nothing); existing tests pass unchanged with the config supplied; a
> second PDK can supply only a config and its own data files.
>
> Out of scope: changing any recorded result or the existing corner matrix.
