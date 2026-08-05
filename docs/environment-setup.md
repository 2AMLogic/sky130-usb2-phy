# Environment Setup: cocotb + Icarus + Yosys + sky130A (Ubuntu / apt)

Bootstrap steps for the open-source digital flow described in
[`CLAUDE.md`](../CLAUDE.md): cocotb (verification) + Icarus Verilog
(simulation) + Yosys (synthesis) against the `sky130_fd_sc_hd` standard-cell
library, fetched via [volare](https://github.com/efabless/volare), all
driven through [`klt`](https://github.com/2AMLogic/klayout-tools).

This doc is intended to be followed **verbatim, from a clean shell**, on any
fresh machine or agent session, mirroring the structure of
[`2AMLogic/gf180-bandgap`'s environment-setup doc](https://github.com/2AMLogic/gf180-bandgap/blob/main/docs/environment-setup.md)
(the analog sim-harness's setup doc) for the digital side. Unlike that repo,
`2AMLogic/sky130-modexp` — the digital pattern this repo's harness is copied
from (issue #3) — has **no** `docs/environment-setup.md` of its own (its
harness was migrated wholesale from a `klayout-tools` PR rather than
bootstrapped fresh), so this is the first write-up of the digital-flow setup
steps; treat it as the reference other sky130 digital canary repos can copy.

Recorded on Ubuntu 24.04 LTS (noble), x86_64, with `sudo` access and network
access to `archive.ubuntu.com` / PyPI / GitHub. If you are on a different
OS, the package-manager commands in §1–2 are the parts to substitute; the
rest (klt invocations, PDK fetch, environment variables) is unchanged.

## 1. Versions used to validate this doc (2026-08-05)

| Tool | Version | Source |
|---|---|---|
| `klt` (klayout-tools) | 0.2.0 | `uv tool install klayout-tools` (already present on this machine) |
| Icarus Verilog | **12.0** (stable) | `apt install iverilog` (Ubuntu noble universe) |
| cocotb | **2.0.1** | `uv pip install --python <klt's tool venv> cocotb` (see §3 — **not** a plain distro `pip install`, see the note there) |
| Yosys | **0.67** (git sha1 `2d1509d1b`) | [`yowasp-yosys`](https://pypi.org/project/yowasp-yosys/) `0.67.0.0.post1190` (pip) — **not** the distro `apt install yosys` package; see §4's friction note for why |
| volare | 0.20.6 | already present on this machine (`/tmp/volare-venv/bin/volare`) |
| sky130A PDK | open_pdks commit **`c6d73a35f524070e85faff4a6a9eef49553ebc2b`** | `volare fetch`, already present at `~/.volare/sky130A` on this machine |

The sky130A hash above is the one recorded here for reproducibility; re-check
`volare output --pdk sky130` if a later session shows a different hash and
update this doc rather than silently treating a drifted PDK as equivalent.

## 2. Install Icarus Verilog

```bash
sudo apt-get update
sudo apt-get install -y iverilog
iverilog -V   # expect "Icarus Verilog version 12.0 (stable)"
```

(This doc does **not** recommend `apt install yosys` — see §4.)

## 3. Install cocotb into `klt`'s own tool environment

`klt functional-verification` imports cocotb **in-process**, inside `klt`'s
own environment (it does not shell out to a separate Python for cocotb the
way it shells out to `yosys`/`iverilog` as binaries). If `klt` was installed
with `uv tool install klayout-tools` (as it is on this machine), that
environment is isolated from the system `python3` and from a plain
`pip install --user cocotb` — running `klt functional-verification` without
this step fails with:

```
cocotb is not installed (import failed: No module named 'cocotb_tools') --
install it with `pip install cocotb` (cocotb 2.0 supports Python <= 3.13)
```

Inject cocotb into that same environment with `uv`:

```bash
uv pip install --python "$(uv tool dir)/klayout-tools/bin/python" cocotb
```

Verify:

```bash
"$(uv tool dir)/klayout-tools/bin/python" -c "import cocotb; print(cocotb.__version__)"
# expect: 2.0.1
```

If `klt` was installed a different way (not `uv tool install`), install
cocotb into whichever Python environment `klt`'s own shebang points at
(`head -1 "$(command -v klt)"`), the same way — a plain
`python3 -m pip install cocotb` on Ubuntu 24.04 will itself refuse with
`error: externally-managed-environment` (PEP 668) unless run inside a venv.

## 4. Install a working Yosys via `yowasp-yosys` (not `apt install yosys`)

**Do not rely on Ubuntu noble's `apt install yosys`** — it installs
**Yosys 0.33**, which is missing a `sequential_area` field in `yosys stat
-json` output that `klt synthesize` (0.2.0) unconditionally reads,
**crashing every synthesis run** with:

```
KeyError: 'sequential_area'
```

This reproduces even against `2AMLogic/sky130-modexp`'s own `modexp.v` +
its own `docs/baseline.md` recipe — it is not specific to this repo's RTL.
Filed as a generic tool-gap issue against `2AMLogic/klayout-tools`:
[2AMLogic/klayout-tools#560](https://github.com/2AMLogic/klayout-tools/issues/560),
per `CLAUDE.md`'s friction protocol. `sky130-modexp`'s `docs/baseline.md`
was itself measured against "Yosys 0.67+post" — i.e. this gap was already
latent, just not documented anywhere reproducible until now.

The fix that actually works on this machine: install
[`yowasp-yosys`](https://pypi.org/project/yowasp-yosys/), a pip-distributed,
sandboxed (WASM/`wasmtime`) build of Yosys, at the same 0.67 vintage
`sky130-modexp`'s baseline was measured against, and put it on `PATH` as
`yosys`:

```bash
pip install --user --break-system-packages yowasp-yosys
ln -sf "$(command -v yowasp-yosys)" "$(dirname "$(command -v yowasp-yosys)")/yosys"
yosys --version   # expect: "Yosys 0.67 ..."
```

This works **only** because `~/.local/bin` is first on `PATH` by default on
this machine (`echo $PATH`) — confirm that before relying on the symlink, or
`apt remove yosys` (or otherwise ensure `~/.local/bin` precedes `/usr/bin`)
if it is not.

### A `yowasp-yosys` filesystem gotcha: avoid `/tmp` for synthesis working dirs

`yowasp-yosys` runs Yosys inside a `wasmtime` WASI sandbox that preopens most
top-level host directories by absolute path **except `/tmp`**, which it
remaps to its own private per-invocation temp directory (see
`yowasp_runtime.run_wasm`). A `klt synthesize` request whose working
directory is under `/tmp` therefore fails with a confusing "script file...
No such file or directory" — the file is really there on the host, just not
visible inside the sandbox at that path. **Run `klt synthesize` from a
directory under your home directory (or elsewhere outside `/tmp`)**, not a
`/tmp` scratch dir, when using `yowasp-yosys`.

## 5. Fetch the sky130 PDK via volare

```bash
volare --version                        # expect 0.20.6 (or record whatever is installed)
volare fetch  --pdk sky130 c6d73a35f524070e85faff4a6a9eef49553ebc2b
volare enable --pdk sky130 c6d73a35f524070e85faff4a6a9eef49553ebc2b
volare output --pdk sky130              # confirm: c6d73a35f524070e85faff4a6a9eef49553ebc2b
```

This creates `~/.volare/sky130A` / `sky130B` (symlinks into
`~/.volare/volare/sky130/versions/<hash>/...`) — one directory per sky130
variant. This repo's digital flow uses **`sky130A`** (the standard
open-source variant carrying `sky130_fd_sc_hd`).

## 6. `PDK` / `PDK_ROOT` environment convention

`klt pdk find` (and `klt synthesize`) resolve the PDK via `$PDK`/`$PDK_ROOT`
first, falling back to the volare/ciel stores:

```bash
export PDK_ROOT="$(volare path)"   # -> ~/.volare
export PDK="sky130A"
klt pdk find --format json         # confirm "variant": "sky130A"
```

## 7. Smoke test: `klt functional-verification` against `rtl/utmi_stub.v`

[`rtl/utmi_stub.v`](../rtl/utmi_stub.v) is a trivial registered pass-through
(**not** real UTMI protocol logic — see issue #3) sized only to exercise the
toolchain end-to-end.

```bash
klt functional-verification verification/request-utmi_stub.json --format json
```

Expected (abbreviated): `"status": "pass"`, `"passed_count": 2`,
`"failed_count": 0`.

## 8. Smoke test: `klt synthesize` against `sky130_fd_sc_hd`

Run from a scratch directory **outside `/tmp`** (see §4's gotcha):

```bash
mkdir -p ~/scratch/utmi_stub_synth && cd ~/scratch/utmi_stub_synth
cp /path/to/sky130-usb2-phy/rtl/utmi_stub.v .
cat > req.json <<'JSON'
{ "schema": "klt.synthesize.request/1", "engine": "yosys",
  "sources": ["utmi_stub.v"], "hdl_toplevel": "utmi_stub",
  "pdk": { "cell_library": "sky130_fd_sc_hd", "corner": "tt_025C_1v80" },
  "constraints": { "clock_period_ns": null } }
JSON
PDK=sky130A klt synthesize req.json --format json
```

Expected: `"status": "ok"`, `"instance_count": 9`, all
`sky130_fd_sc_hd__dfrtp_1` (flip-flops only — this stub has no combinational
logic). See [`docs/baseline.md`](baseline.md) for the full recorded result.

## 9. Reproducibility checklist

- [ ] From a **new terminal** (nothing pre-sourced from a prior session),
      confirm `iverilog -V` reports `12.0` and
      `"$(uv tool dir)/klayout-tools/bin/python" -c "import cocotb; print(cocotb.__version__)"`
      reports `2.0.1`.
- [ ] Confirm `yosys --version` resolves to `~/.local/bin/yosys` (the
      `yowasp-yosys` symlink from §4), **not** `/usr/bin/yosys` — `which
      yosys` should print the `~/.local/bin` path.
- [ ] Confirm `klt pdk find --format json` reports `"variant": "sky130A"`
      and the pinned hash from §1/§5, not silently a different install.
- [ ] Run `klt functional-verification verification/request-utmi_stub.json
      --format json` from the repo root and confirm `"status": "pass"`.
- [ ] Run the §8 synthesis smoke test from a non-`/tmp` scratch directory and
      confirm `"status": "ok"` with `"instance_count": 9`.

## 10. Known friction filed against `2AMLogic/klayout-tools`

- [2AMLogic/klayout-tools#560](https://github.com/2AMLogic/klayout-tools/issues/560) —
  `klt synthesize` crashes (`KeyError: 'sequential_area'`) against Yosys
  builds whose `stat -json` output omits the sequential/combinational area
  split (e.g. Ubuntu noble's distro-packaged Yosys 0.33) — see §4. Filed
  generically (no design-specific detail) per `CLAUDE.md`'s friction
  protocol.
