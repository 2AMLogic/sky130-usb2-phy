# design

Analog schematics (xschem). Empty until the per-block port issues land: the analog blocks are ported here from `gf180-usb2-phy` (operator ruling 2026-10-08, #40) — see [`docs/porting-plan.md`](../docs/porting-plan.md).

`design/netlist/` holds synthesized gate-level netlists of the digital partition.
`netlist/usb_utmi_top.v` is the Yosys/`sky130_fd_sc_hd` mapping of the real UTMI top
(experiment `utmi-top`, [`flow/README.md`](../flow/README.md)); it is synthesis output
only, not placed, routed or signed off, and the record beside it discloses a combinational
loop found in the RTL.
