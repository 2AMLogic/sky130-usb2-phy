#!/usr/bin/env bash
# Export design/<cell>.sch to design/netlist/<cell>.spice with xschem (>= 3.4.7)
# and the sky130 xschem symbol library from the installed open_pdks sky130A.
#
#   design/export_netlist.sh differential_receiver
#
# xschem writes a commented top-level wrapper (`**.subckt` / `**.ends`) and an
# absolute `sch_path`. This script turns the wrapper into a real `.subckt` and
# makes `sch_path` repo-relative so the committed netlist is byte-reproducible
# from the schematic on any host. Nothing else is edited.
set -euo pipefail
cell="${1:?usage: export_netlist.sh <cell>}"
here="$(cd "$(dirname "$0")" && pwd)"
rc="${XSCHEMRC:-$HOME/.volare/sky130A/libs.tech/xschem/xschemrc}"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
(cd "$here" && XSCHEM_LIBRARY_PATH= xschem --rcfile "$rc" -n -s -q --no_x -o "$tmp" "$cell.sch" >/dev/null 2>&1)
{
  echo "* $cell -- exported by design/export_netlist.sh from design/$cell.sch (xschem, sky130 symbols)"
  echo "* Do not edit: edit the schematic and re-run the export."
  sed -e "s|^\*\* sch_path: .*|** sch_path: design/$cell.sch|" \
      -e 's|^\*\*\.subckt |.subckt |' -e 's|^\*\*\.ends|.ends|' -e '/^\.end$/d' "$tmp/$cell.spice"
} > "$here/netlist/$cell.spice"
