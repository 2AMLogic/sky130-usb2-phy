#!/usr/bin/env bash
# Export design/<cell>.sch to design/netlist/<cell>.spice with `klt netlist --block`
# (headless, time-bounded xschem) and the sky130 xschem symbol library from the
# installed open_pdks sky130A.
#
#   design/export_netlist.sh differential_receiver
#
# `--block` turns the commented top-level wrapper (`**.subckt` / `**.ends`) into a
# real `.subckt`. klt writes an absolute `sch_path`; this script makes it
# repo-relative and prepends a provenance header. Nothing else is edited. Output is
# byte-reproducible only on a host with the same xschem build (`+` continuation
# wrapping differs across builds); compare across hosts with `design/check_netlist.py`,
# which ignores `+` wrapping.
set -euo pipefail
cell="${1:?usage: export_netlist.sh <cell>}"
here="$(cd "$(dirname "$0")" && pwd)"
# Shared pinned-PDK search + revision check (sim/harness/pdk_pin.py, same order as the sim
# harness: $PDK_ROOT, ~/.ciel, then system roots): prints the pinned sky130A xschemrc, or
# refuses a stale tree naming both open_pdks revisions.
if [ -z "${XSCHEMRC:-}" ]; then
  XSCHEMRC="$(python3 "$here/../sim/harness/pdk_pin.py")" || exit 2
fi
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
klt netlist "$here/$cell.sch" --block --rcfile "$XSCHEMRC" -o "$tmp/$cell.spice" >/dev/null
{
  echo "* $cell -- exported by design/export_netlist.sh from design/$cell.sch (xschem, sky130 symbols)"
  echo "* Do not edit: edit the schematic and re-run the export."
  sed -e "s|^\*\* sch_path: .*|** sch_path: design/$cell.sch|" "$tmp/$cell.spice"
} > "$here/netlist/$cell.spice"
