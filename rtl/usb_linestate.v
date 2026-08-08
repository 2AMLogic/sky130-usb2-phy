// usb_linestate.v -- LineState[1:0] reporting (issue #13, block 6).
//
// Per spec/decision-records/0001-clocking-cdc-jitter-metric-and-pvt-envelope.md
// Decision 4's port table: `LineState[1:0]` is the **raw D-/D+ electrical
// sample** (`LineState[1] = D-`, `LineState[0] = D+`), not a pre-encoded
// J/K/SE0/SE1 value -- deriving J/K is the link controller's job, not
// this PHY's. This module is therefore a pure, continuous format (no
// state, no clock) of usb_bit_sync.v's synchronized dp_sync/dm_sync
// outputs -- kept as its own module purely to give this encoding decision
// one auditable, single-purpose home, per this repo's "one module per
// function" convention (rtl/README.md).
//
// Domain: 144 MHz recovery clock (combinational passthrough of that
// domain's synchronized line levels; usb_rx_cdc.v is what crosses this
// into the 30 MHz UTMI domain as the port-level `LineState[1:0]`).
`default_nettype none

module usb_linestate (
    input  wire dp_sync,
    input  wire dm_sync,
    output wire [1:0] line_state  // {D-, D+}
);

    assign line_state = {dm_sync, dp_sync};

endmodule

`default_nettype wire
