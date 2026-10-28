#!/usr/bin/env bash
# Export design/<cell>.sch to design/netlist/<cell>.spice with `klt netlist --block`
# (headless, time-bounded xschem) and the sky130 xschem symbol library from the
# installed open_pdks sky130A.
#
#   design/export_netlist.sh differential_receiver
#
# `--block` turns the commented top-level wrapper (`**.subckt` / `**.ends`) into a
# real `.subckt`. klt writes an absolute `sch_path`; this script makes it
# repo-relative and prepends a provenance header so the committed netlist is
# byte-reproducible from the schematic on any host. Nothing else is edited.
set -euo pipefail
cell="${1:?usage: export_netlist.sh <cell>}"
here="$(cd "$(dirname "$0")" && pwd)"
# Same search order as sim/harness/runner.py: $PDK_ROOT, ~/.ciel, then system roots; the first
# tree holding sky130A wins and must be the open_pdks revision pinned in sim/corners.json.
if [ -z "${XSCHEMRC:-}" ]; then
  pdk=""
  for root in "${PDK_ROOT:-}" "$HOME/.ciel" /usr/share/pdk /usr/local/share/pdk /opt/pdk; do
    if [ -n "$root" ] && [ -f "$root/sky130A/libs.tech/xschem/xschemrc" ]; then pdk="$root/sky130A"; break; fi
  done
  [ -n "$pdk" ] || { echo "export_netlist: sky130A not found (set PDK_ROOT or install it under ~/.ciel; see docs/environment-setup.md)" >&2; exit 2; }
  pin="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["pdk"]["open_pdks_commit"])' "$here/../sim/corners.json")"
  got="$(awk '$1=="open_pdks"{print $2}' "$pdk/SOURCES" 2>/dev/null || true)"
  [ "$got" = "$pin" ] || { echo "export_netlist: $pdk is open_pdks ${got:-unknown}, but this repo pins open_pdks $pin (sim/corners.json)" >&2; exit 2; }
  XSCHEMRC="$pdk/libs.tech/xschem/xschemrc"
fi
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
klt netlist "$here/$cell.sch" --block --rcfile "$XSCHEMRC" -o "$tmp/$cell.spice" >/dev/null
{
  echo "* $cell -- exported by design/export_netlist.sh from design/$cell.sch (xschem, sky130 symbols)"
  echo "* Do not edit: edit the schematic and re-run the export."
  sed -e "s|^\*\* sch_path: .*|** sch_path: design/$cell.sch|" "$tmp/$cell.spice"
} > "$here/netlist/$cell.spice"
