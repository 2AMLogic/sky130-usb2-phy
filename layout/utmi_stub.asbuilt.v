module utmi_stub (RxValid,
    TxReady,
    TxValid,
    clk,
    rst_n,
    DataIn,
    DataOut);
 output RxValid;
 output TxReady;
 input TxValid;
 input clk;
 input rst_n;
 output [7:0] DataIn;
 input [7:0] DataOut;

 wire clknet_0_clk;
 wire clknet_1_0__leaf_clk;
 wire clknet_1_1__leaf_clk;

 sky130_fd_sc_hd__dfrtp_1 _0_ (.CLK(clknet_1_1__leaf_clk),
    .D(TxValid),
    .RESET_B(rst_n),
    .Q(RxValid));
 sky130_fd_sc_hd__dfrtp_1 _1_ (.CLK(clknet_1_0__leaf_clk),
    .D(DataOut[0]),
    .RESET_B(rst_n),
    .Q(DataIn[0]));
 sky130_fd_sc_hd__dfrtp_1 _2_ (.CLK(clknet_1_0__leaf_clk),
    .D(DataOut[1]),
    .RESET_B(rst_n),
    .Q(DataIn[1]));
 sky130_fd_sc_hd__dfrtp_1 _3_ (.CLK(clknet_1_0__leaf_clk),
    .D(DataOut[2]),
    .RESET_B(rst_n),
    .Q(DataIn[2]));
 sky130_fd_sc_hd__dfrtp_1 _4_ (.CLK(clknet_1_1__leaf_clk),
    .D(DataOut[3]),
    .RESET_B(rst_n),
    .Q(DataIn[3]));
 sky130_fd_sc_hd__dfrtp_1 _5_ (.CLK(clknet_1_1__leaf_clk),
    .D(DataOut[4]),
    .RESET_B(rst_n),
    .Q(DataIn[4]));
 sky130_fd_sc_hd__dfrtp_1 _6_ (.CLK(clknet_1_1__leaf_clk),
    .D(DataOut[5]),
    .RESET_B(rst_n),
    .Q(DataIn[5]));
 sky130_fd_sc_hd__dfrtp_1 _7_ (.CLK(clknet_1_0__leaf_clk),
    .D(DataOut[6]),
    .RESET_B(rst_n),
    .Q(DataIn[6]));
 sky130_fd_sc_hd__dfrtp_1 _8_ (.CLK(clknet_1_1__leaf_clk),
    .D(DataOut[7]),
    .RESET_B(rst_n),
    .Q(DataIn[7]));
 sky130_fd_sc_hd__buf_4 clkbuf_0_clk (.A(clk),
    .X(clknet_0_clk));
 sky130_fd_sc_hd__buf_4 clkbuf_1_0__f_clk (.A(clknet_0_clk),
    .X(clknet_1_0__leaf_clk));
 sky130_fd_sc_hd__buf_4 clkbuf_1_1__f_clk (.A(clknet_0_clk),
    .X(clknet_1_1__leaf_clk));
 sky130_fd_sc_hd__inv_1 clkload0 (.A(clknet_1_0__leaf_clk));
 assign TxReady = RxValid;
endmodule
