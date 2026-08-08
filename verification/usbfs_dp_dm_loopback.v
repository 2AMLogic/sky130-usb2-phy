// usbfs_dp_dm_loopback.v -- test-fixture-only wire loopback, NOT PHY RTL.
//
// `klt functional-verification` (like `klt sim`/`klt lvs`) drives cocotb
// against a live simulator, and cocotb has to attach to *something* --
// it cannot drive/monitor pure-Python signals without an HDL toplevel.
// This module is the minimal such target for `request-usbfs-model.json`:
// two wires, nothing else. It exists so `verification/test_usbfs_loopback.py`
// can prove `usbfs.transceiver.IdealTransceiver` (issue #10's Layer 2 BFM)
// drives and monitors DP/DM against a real simulator process, not only
// against itself in a Python unit test.
//
// It contains no PID/NRZI/bit-stuffing/CRC logic and is not the TX-path or
// RX-path RTL -- those are issues #12 and #13's job, not this one's. Same
// spirit as rtl/utmi_stub.v (issue #3): a deliberately trivial toolchain
// fixture, documented as such, kept out of `rtl/` so that directory stays
// reserved for actual PHY digital-layer RTL.

`default_nettype none

module usbfs_dp_dm_loopback (
    input  wire dp_drv,
    input  wire dm_drv,
    output wire dp_sense,
    output wire dm_sense
);

    assign dp_sense = dp_drv;
    assign dm_sense = dm_drv;

endmodule

`default_nettype wire
