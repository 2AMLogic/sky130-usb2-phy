"""sky130-usb2-phy analog simulation harness (klt sim front end).

Mechanics (experiment layout, append-only dated records, one `klt sim`
request per grid, per-corner result validation) follow the pinned
2AMLogic/gf180-usb2-phy harness; every PDK-specific piece (model library,
corner sections, PVT axes) is sky130 configuration read from sim/corners.json.
See sim/README.md.
"""

HARNESS_VERSION = "0.1.0"
