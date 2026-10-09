v {xschem version=3.4.7 file_version=1.2}
G {}
K {type=subcircuit
format="@name @pinlist @symname"
template="name=x1"}
V {}
S {}
E {}
T {differential_driver -- USB 2.0 FS line driver with drive enable and output enable, sky130 port (issue #112)\nPin contract: differential_driver VDD VSS TXDP TXDM DRVEN OE DP DM. VDD/VSS inout (3.0-3.6 V I/O rail / ground).\nTXDP, TXDM, DRVEN, OE: in, VDD-domain CMOS logic (0 = VSS, 1 = VDD); the 1.8 V core -> VDD level shifter is outside this cell.\nEN = DRVEN AND OE. EN=1: TXDx=1 drives Dx high, TXDx=0 drives Dx low (SE0 when both 0). EN=0: both output devices off, DP/DM high impedance.\nPer line: enable/data gating -> P gate: fast pull-up off switch (MP_POFF), switched mirrored current sink on (MN_PSW/MN_PSRC);\nN gate: pull-down off switch (MN_NOFF), switched mirrored current source on (MP_NSW/MP_NSRC); MIM Miller caps CP/CN gate-to-OUTI\nGate kick (MN_KICK1/2, MP_KICK1N/2N): extra turn-on current until a replica of the output device (MP_KREP / MN_KREPN) conducts,\nset the edge rate (dV/dt = I/C) once the gate reaches threshold; output stage MP_OUT/MN_OUT; series poly resistor RSER to the pad.\nBias: RB (res_xhigh_po_1p41) into diode MNB; MNB2/MPB derive the PMOS bias. All MOS sky130_fd_pr g5v0d10v5 (5 V-class thick oxide).\nTopology change vs the gf180 source (resistor gate-slew) and every size: design/README.md.} -300 -700 0 0 0.3 0.3 {}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 0 0 0 0 {name=MP_ENA
L=0.5
W=2
nf=1
mult=1
ad=0.58
as=0.58
pd=4.58
ps=4.58
nrd=0.145 nrs=0.145
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 20 -30 0 0 {name=l1 lab=VDD}
C {devices/lab_pin.sym} -20 0 0 0 {name=l2 lab=DRVEN}
C {devices/lab_pin.sym} 20 30 0 0 {name=l3 lab=ENB}
C {devices/lab_pin.sym} 20 0 0 0 {name=l4 lab=VDD}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 150 0 0 0 {name=MP_ENB
L=0.5
W=2
nf=1
mult=1
ad=0.58
as=0.58
pd=4.58
ps=4.58
nrd=0.145 nrs=0.145
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 170 -30 0 0 {name=l5 lab=VDD}
C {devices/lab_pin.sym} 130 0 0 0 {name=l6 lab=OE}
C {devices/lab_pin.sym} 170 30 0 0 {name=l7 lab=ENB}
C {devices/lab_pin.sym} 170 0 0 0 {name=l8 lab=VDD}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 300 0 0 0 {name=MN_ENA
L=0.5
W=2
nf=1
mult=1
ad=0.58
as=0.58
pd=4.58
ps=4.58
nrd=0.145 nrs=0.145
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 320 -30 0 0 {name=l9 lab=ENB}
C {devices/lab_pin.sym} 280 0 0 0 {name=l10 lab=DRVEN}
C {devices/lab_pin.sym} 320 30 0 0 {name=l11 lab=ENX}
C {devices/lab_pin.sym} 320 0 0 0 {name=l12 lab=VSS}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 450 0 0 0 {name=MN_ENB
L=0.5
W=2
nf=1
mult=1
ad=0.58
as=0.58
pd=4.58
ps=4.58
nrd=0.145 nrs=0.145
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 470 -30 0 0 {name=l13 lab=ENX}
C {devices/lab_pin.sym} 430 0 0 0 {name=l14 lab=OE}
C {devices/lab_pin.sym} 470 30 0 0 {name=l15 lab=VSS}
C {devices/lab_pin.sym} 470 0 0 0 {name=l16 lab=VSS}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 600 0 0 0 {name=MP_ENI
L=0.5
W=4
nf=1
mult=1
ad=1.16
as=1.16
pd=8.58
ps=8.58
nrd=0.0725 nrs=0.0725
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 620 -30 0 0 {name=l17 lab=VDD}
C {devices/lab_pin.sym} 580 0 0 0 {name=l18 lab=ENB}
C {devices/lab_pin.sym} 620 30 0 0 {name=l19 lab=EN}
C {devices/lab_pin.sym} 620 0 0 0 {name=l20 lab=VDD}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 750 0 0 0 {name=MN_ENI
L=0.5
W=2
nf=1
mult=1
ad=0.58
as=0.58
pd=4.58
ps=4.58
nrd=0.145 nrs=0.145
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 770 -30 0 0 {name=l21 lab=EN}
C {devices/lab_pin.sym} 730 0 0 0 {name=l22 lab=ENB}
C {devices/lab_pin.sym} 770 30 0 0 {name=l23 lab=VSS}
C {devices/lab_pin.sym} 770 0 0 0 {name=l24 lab=VSS}
C {sky130_fd_pr/res_xhigh_po_1p41.sym} 900 0 0 0 {name=RB
L=30
model=res_xhigh_po_1p41
spiceprefix=X
mult=1
}
C {devices/lab_pin.sym} 900 -30 0 0 {name=l25 lab=VDD}
C {devices/lab_pin.sym} 900 30 0 0 {name=l26 lab=VBN}
C {devices/lab_pin.sym} 880 0 0 0 {name=l27 lab=VSS}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 1050 0 0 0 {name=MNB
L=1
W=4
nf=1
mult=1
ad=1.16
as=1.16
pd=8.58
ps=8.58
nrd=0.0725 nrs=0.0725
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 1070 -30 0 0 {name=l28 lab=VBN}
C {devices/lab_pin.sym} 1030 0 0 0 {name=l29 lab=VBN}
C {devices/lab_pin.sym} 1070 30 0 0 {name=l30 lab=VSS}
C {devices/lab_pin.sym} 1070 0 0 0 {name=l31 lab=VSS}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 1200 0 0 0 {name=MNB2
L=1
W=4
nf=1
mult=1
ad=1.16
as=1.16
pd=8.58
ps=8.58
nrd=0.0725 nrs=0.0725
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 1220 -30 0 0 {name=l32 lab=VBP}
C {devices/lab_pin.sym} 1180 0 0 0 {name=l33 lab=VBN}
C {devices/lab_pin.sym} 1220 30 0 0 {name=l34 lab=VSS}
C {devices/lab_pin.sym} 1220 0 0 0 {name=l35 lab=VSS}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 1350 0 0 0 {name=MPB
L=1
W=8
nf=1
mult=1
ad=2.32
as=2.32
pd=16.58
ps=16.58
nrd=0.0362 nrs=0.0362
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 1370 -30 0 0 {name=l36 lab=VDD}
C {devices/lab_pin.sym} 1330 0 0 0 {name=l37 lab=VBP}
C {devices/lab_pin.sym} 1370 30 0 0 {name=l38 lab=VBP}
C {devices/lab_pin.sym} 1370 0 0 0 {name=l39 lab=VDD}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 0 300 0 0 {name=MP_PA1_DP
L=0.5
W=2
nf=1
mult=1
ad=0.58
as=0.58
pd=4.58
ps=4.58
nrd=0.145 nrs=0.145
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 20 270 0 0 {name=l40 lab=VDD}
C {devices/lab_pin.sym} -20 300 0 0 {name=l41 lab=TXDP}
C {devices/lab_pin.sym} 20 330 0 0 {name=l42 lab=PA_DP}
C {devices/lab_pin.sym} 20 300 0 0 {name=l43 lab=VDD}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 150 300 0 0 {name=MP_PA2_DP
L=0.5
W=2
nf=1
mult=1
ad=0.58
as=0.58
pd=4.58
ps=4.58
nrd=0.145 nrs=0.145
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 170 270 0 0 {name=l44 lab=VDD}
C {devices/lab_pin.sym} 130 300 0 0 {name=l45 lab=EN}
C {devices/lab_pin.sym} 170 330 0 0 {name=l46 lab=PA_DP}
C {devices/lab_pin.sym} 170 300 0 0 {name=l47 lab=VDD}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 300 300 0 0 {name=MN_PA1_DP
L=0.5
W=2
nf=1
mult=1
ad=0.58
as=0.58
pd=4.58
ps=4.58
nrd=0.145 nrs=0.145
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 320 270 0 0 {name=l48 lab=PA_DP}
C {devices/lab_pin.sym} 280 300 0 0 {name=l49 lab=TXDP}
C {devices/lab_pin.sym} 320 330 0 0 {name=l50 lab=PAX_DP}
C {devices/lab_pin.sym} 320 300 0 0 {name=l51 lab=VSS}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 450 300 0 0 {name=MN_PA2_DP
L=0.5
W=2
nf=1
mult=1
ad=0.58
as=0.58
pd=4.58
ps=4.58
nrd=0.145 nrs=0.145
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 470 270 0 0 {name=l52 lab=PAX_DP}
C {devices/lab_pin.sym} 430 300 0 0 {name=l53 lab=EN}
C {devices/lab_pin.sym} 470 330 0 0 {name=l54 lab=VSS}
C {devices/lab_pin.sym} 470 300 0 0 {name=l55 lab=VSS}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 600 300 0 0 {name=MP_PINV_DP
L=0.5
W=8
nf=1
mult=1
ad=2.32
as=2.32
pd=16.58
ps=16.58
nrd=0.0362 nrs=0.0362
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 620 270 0 0 {name=l56 lab=VDD}
C {devices/lab_pin.sym} 580 300 0 0 {name=l57 lab=PA_DP}
C {devices/lab_pin.sym} 620 330 0 0 {name=l58 lab=PON_DP}
C {devices/lab_pin.sym} 620 300 0 0 {name=l59 lab=VDD}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 750 300 0 0 {name=MN_PINV_DP
L=0.5
W=4
nf=1
mult=1
ad=1.16
as=1.16
pd=8.58
ps=8.58
nrd=0.0725 nrs=0.0725
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 770 270 0 0 {name=l60 lab=PON_DP}
C {devices/lab_pin.sym} 730 300 0 0 {name=l61 lab=PA_DP}
C {devices/lab_pin.sym} 770 330 0 0 {name=l62 lab=VSS}
C {devices/lab_pin.sym} 770 300 0 0 {name=l63 lab=VSS}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 900 300 0 0 {name=MP_NB1_DP
L=0.5
W=4
nf=1
mult=1
ad=1.16
as=1.16
pd=8.58
ps=8.58
nrd=0.0725 nrs=0.0725
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 920 270 0 0 {name=l64 lab=VDD}
C {devices/lab_pin.sym} 880 300 0 0 {name=l65 lab=TXDP}
C {devices/lab_pin.sym} 920 330 0 0 {name=l66 lab=NBX_DP}
C {devices/lab_pin.sym} 920 300 0 0 {name=l67 lab=VDD}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 1050 300 0 0 {name=MP_NB2_DP
L=0.5
W=4
nf=1
mult=1
ad=1.16
as=1.16
pd=8.58
ps=8.58
nrd=0.0725 nrs=0.0725
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 1070 270 0 0 {name=l68 lab=NBX_DP}
C {devices/lab_pin.sym} 1030 300 0 0 {name=l69 lab=ENB}
C {devices/lab_pin.sym} 1070 330 0 0 {name=l70 lab=NB_DP}
C {devices/lab_pin.sym} 1070 300 0 0 {name=l71 lab=VDD}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 1200 300 0 0 {name=MN_NB1_DP
L=0.5
W=1
nf=1
mult=1
ad=0.29
as=0.29
pd=2.58
ps=2.58
nrd=0.29 nrs=0.29
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 1220 270 0 0 {name=l72 lab=NB_DP}
C {devices/lab_pin.sym} 1180 300 0 0 {name=l73 lab=TXDP}
C {devices/lab_pin.sym} 1220 330 0 0 {name=l74 lab=VSS}
C {devices/lab_pin.sym} 1220 300 0 0 {name=l75 lab=VSS}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 1350 300 0 0 {name=MN_NB2_DP
L=0.5
W=1
nf=1
mult=1
ad=0.29
as=0.29
pd=2.58
ps=2.58
nrd=0.29 nrs=0.29
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 1370 270 0 0 {name=l76 lab=NB_DP}
C {devices/lab_pin.sym} 1330 300 0 0 {name=l77 lab=ENB}
C {devices/lab_pin.sym} 1370 330 0 0 {name=l78 lab=VSS}
C {devices/lab_pin.sym} 1370 300 0 0 {name=l79 lab=VSS}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 1500 300 0 0 {name=MP_NINV_DP
L=0.5
W=8
nf=1
mult=1
ad=2.32
as=2.32
pd=16.58
ps=16.58
nrd=0.0362 nrs=0.0362
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 1520 270 0 0 {name=l80 lab=VDD}
C {devices/lab_pin.sym} 1480 300 0 0 {name=l81 lab=NB_DP}
C {devices/lab_pin.sym} 1520 330 0 0 {name=l82 lab=NONB_DP}
C {devices/lab_pin.sym} 1520 300 0 0 {name=l83 lab=VDD}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 1650 300 0 0 {name=MN_NINV_DP
L=0.5
W=4
nf=1
mult=1
ad=1.16
as=1.16
pd=8.58
ps=8.58
nrd=0.0725 nrs=0.0725
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 1670 270 0 0 {name=l84 lab=NONB_DP}
C {devices/lab_pin.sym} 1630 300 0 0 {name=l85 lab=NB_DP}
C {devices/lab_pin.sym} 1670 330 0 0 {name=l86 lab=VSS}
C {devices/lab_pin.sym} 1670 300 0 0 {name=l87 lab=VSS}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 0 500 0 0 {name=MP_POFF_DP
L=0.5
W=20
nf=1
mult=1
ad=5.8
as=5.8
pd=40.58
ps=40.58
nrd=0.0145 nrs=0.0145
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 20 470 0 0 {name=l88 lab=VDD}
C {devices/lab_pin.sym} -20 500 0 0 {name=l89 lab=PON_DP}
C {devices/lab_pin.sym} 20 530 0 0 {name=l90 lab=PG_DP}
C {devices/lab_pin.sym} 20 500 0 0 {name=l91 lab=VDD}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 150 500 0 0 {name=MN_PSW_DP
L=0.5
W=16
nf=1
mult=1
ad=4.64
as=4.64
pd=32.58
ps=32.58
nrd=0.0181 nrs=0.0181
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 170 470 0 0 {name=l92 lab=PG_DP}
C {devices/lab_pin.sym} 130 500 0 0 {name=l93 lab=PON_DP}
C {devices/lab_pin.sym} 170 530 0 0 {name=l94 lab=XP_DP}
C {devices/lab_pin.sym} 170 500 0 0 {name=l95 lab=VSS}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 300 500 0 0 {name=MN_PSRC_DP
L=1
W=4
nf=1
mult=25
ad=1.16
as=1.16
pd=8.58
ps=8.58
nrd=0.0725 nrs=0.0725
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 320 470 0 0 {name=l96 lab=XP_DP}
C {devices/lab_pin.sym} 280 500 0 0 {name=l97 lab=VBN}
C {devices/lab_pin.sym} 320 530 0 0 {name=l98 lab=VSS}
C {devices/lab_pin.sym} 320 500 0 0 {name=l99 lab=VSS}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 450 500 0 0 {name=MN_NOFF_DP
L=0.5
W=20
nf=1
mult=1
ad=5.8
as=5.8
pd=40.58
ps=40.58
nrd=0.0145 nrs=0.0145
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 470 470 0 0 {name=l100 lab=NG_DP}
C {devices/lab_pin.sym} 430 500 0 0 {name=l101 lab=NONB_DP}
C {devices/lab_pin.sym} 470 530 0 0 {name=l102 lab=VSS}
C {devices/lab_pin.sym} 470 500 0 0 {name=l103 lab=VSS}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 600 500 0 0 {name=MP_NSW_DP
L=0.5
W=8
nf=1
mult=1
ad=2.32
as=2.32
pd=16.58
ps=16.58
nrd=0.0362 nrs=0.0362
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 620 470 0 0 {name=l104 lab=XN_DP}
C {devices/lab_pin.sym} 580 500 0 0 {name=l105 lab=NONB_DP}
C {devices/lab_pin.sym} 620 530 0 0 {name=l106 lab=NG_DP}
C {devices/lab_pin.sym} 620 500 0 0 {name=l107 lab=VDD}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 750 500 0 0 {name=MP_NSRC_DP
L=1
W=8
nf=1
mult=8
ad=2.32
as=2.32
pd=16.58
ps=16.58
nrd=0.0362 nrs=0.0362
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 770 470 0 0 {name=l108 lab=VDD}
C {devices/lab_pin.sym} 730 500 0 0 {name=l109 lab=VBP}
C {devices/lab_pin.sym} 770 530 0 0 {name=l110 lab=XN_DP}
C {devices/lab_pin.sym} 770 500 0 0 {name=l111 lab=VDD}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 0 700 0 0 {name=MP_KREP_DP
L=0.5
W=10
nf=1
mult=1
ad=2.9
as=2.9
pd=20.58
ps=20.58
nrd=0.029 nrs=0.029
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 20 670 0 0 {name=l112 lab=VDD}
C {devices/lab_pin.sym} -20 700 0 0 {name=l113 lab=PG_DP}
C {devices/lab_pin.sym} 20 730 0 0 {name=l114 lab=KSP_DP}
C {devices/lab_pin.sym} 20 700 0 0 {name=l115 lab=VDD}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 150 700 0 0 {name=MN_KBIAS_DP
L=1
W=4
nf=1
mult=1
ad=1.16
as=1.16
pd=8.58
ps=8.58
nrd=0.0725 nrs=0.0725
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 170 670 0 0 {name=l116 lab=KSP_DP}
C {devices/lab_pin.sym} 130 700 0 0 {name=l117 lab=VBN}
C {devices/lab_pin.sym} 170 730 0 0 {name=l118 lab=VSS}
C {devices/lab_pin.sym} 170 700 0 0 {name=l119 lab=VSS}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 300 700 0 0 {name=MP_KINV_DP
L=0.5
W=2
nf=1
mult=1
ad=0.58
as=0.58
pd=4.58
ps=4.58
nrd=0.145 nrs=0.145
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 320 670 0 0 {name=l120 lab=VDD}
C {devices/lab_pin.sym} 280 700 0 0 {name=l121 lab=KSP_DP}
C {devices/lab_pin.sym} 320 730 0 0 {name=l122 lab=KSPB_DP}
C {devices/lab_pin.sym} 320 700 0 0 {name=l123 lab=VDD}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 450 700 0 0 {name=MN_KINV_DP
L=0.5
W=1
nf=1
mult=1
ad=0.29
as=0.29
pd=2.58
ps=2.58
nrd=0.29 nrs=0.29
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 470 670 0 0 {name=l124 lab=KSPB_DP}
C {devices/lab_pin.sym} 430 700 0 0 {name=l125 lab=KSP_DP}
C {devices/lab_pin.sym} 470 730 0 0 {name=l126 lab=VSS}
C {devices/lab_pin.sym} 470 700 0 0 {name=l127 lab=VSS}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 600 700 0 0 {name=MN_KICK1_DP
L=0.5
W=4
nf=1
mult=1
ad=1.16
as=1.16
pd=8.58
ps=8.58
nrd=0.0725 nrs=0.0725
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 620 670 0 0 {name=l128 lab=PG_DP}
C {devices/lab_pin.sym} 580 700 0 0 {name=l129 lab=PON_DP}
C {devices/lab_pin.sym} 620 730 0 0 {name=l130 lab=KPX_DP}
C {devices/lab_pin.sym} 620 700 0 0 {name=l131 lab=VSS}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 750 700 0 0 {name=MN_KICK2_DP
L=0.5
W=4
nf=1
mult=1
ad=1.16
as=1.16
pd=8.58
ps=8.58
nrd=0.0725 nrs=0.0725
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 770 670 0 0 {name=l132 lab=KPX_DP}
C {devices/lab_pin.sym} 730 700 0 0 {name=l133 lab=KSPB_DP}
C {devices/lab_pin.sym} 770 730 0 0 {name=l134 lab=VSS}
C {devices/lab_pin.sym} 770 700 0 0 {name=l135 lab=VSS}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 900 700 0 0 {name=MN_KREPN_DP
L=0.5
W=4
nf=1
mult=1
ad=1.16
as=1.16
pd=8.58
ps=8.58
nrd=0.0725 nrs=0.0725
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 920 670 0 0 {name=l136 lab=KSN_DP}
C {devices/lab_pin.sym} 880 700 0 0 {name=l137 lab=NG_DP}
C {devices/lab_pin.sym} 920 730 0 0 {name=l138 lab=VSS}
C {devices/lab_pin.sym} 920 700 0 0 {name=l139 lab=VSS}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 1050 700 0 0 {name=MP_KBIASN_DP
L=1
W=8
nf=1
mult=1
ad=2.32
as=2.32
pd=16.58
ps=16.58
nrd=0.0362 nrs=0.0362
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 1070 670 0 0 {name=l140 lab=VDD}
C {devices/lab_pin.sym} 1030 700 0 0 {name=l141 lab=VBP}
C {devices/lab_pin.sym} 1070 730 0 0 {name=l142 lab=KSN_DP}
C {devices/lab_pin.sym} 1070 700 0 0 {name=l143 lab=VDD}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 1200 700 0 0 {name=MP_KINVN_DP
L=0.5
W=2
nf=1
mult=1
ad=0.58
as=0.58
pd=4.58
ps=4.58
nrd=0.145 nrs=0.145
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 1220 670 0 0 {name=l144 lab=VDD}
C {devices/lab_pin.sym} 1180 700 0 0 {name=l145 lab=KSN_DP}
C {devices/lab_pin.sym} 1220 730 0 0 {name=l146 lab=KSNB_DP}
C {devices/lab_pin.sym} 1220 700 0 0 {name=l147 lab=VDD}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 1350 700 0 0 {name=MN_KINVN_DP
L=0.5
W=1
nf=1
mult=1
ad=0.29
as=0.29
pd=2.58
ps=2.58
nrd=0.29 nrs=0.29
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 1370 670 0 0 {name=l148 lab=KSNB_DP}
C {devices/lab_pin.sym} 1330 700 0 0 {name=l149 lab=KSN_DP}
C {devices/lab_pin.sym} 1370 730 0 0 {name=l150 lab=VSS}
C {devices/lab_pin.sym} 1370 700 0 0 {name=l151 lab=VSS}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 1500 700 0 0 {name=MP_KICK1N_DP
L=0.5
W=4
nf=1
mult=1
ad=1.16
as=1.16
pd=8.58
ps=8.58
nrd=0.0725 nrs=0.0725
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 1520 670 0 0 {name=l152 lab=KNX_DP}
C {devices/lab_pin.sym} 1480 700 0 0 {name=l153 lab=NONB_DP}
C {devices/lab_pin.sym} 1520 730 0 0 {name=l154 lab=NG_DP}
C {devices/lab_pin.sym} 1520 700 0 0 {name=l155 lab=VDD}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 1650 700 0 0 {name=MP_KICK2N_DP
L=0.5
W=4
nf=1
mult=1
ad=1.16
as=1.16
pd=8.58
ps=8.58
nrd=0.0725 nrs=0.0725
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 1670 670 0 0 {name=l156 lab=VDD}
C {devices/lab_pin.sym} 1630 700 0 0 {name=l157 lab=KSNB_DP}
C {devices/lab_pin.sym} 1670 730 0 0 {name=l158 lab=KNX_DP}
C {devices/lab_pin.sym} 1670 700 0 0 {name=l159 lab=VDD}
C {sky130_fd_pr/cap_mim_m3_1.sym} 900 500 0 0 {name=CP_DP model=cap_mim_m3_1 W=42 L=42 MF=1 spiceprefix=X}
C {devices/lab_pin.sym} 900 470 0 0 {name=l160 lab=PG_DP}
C {devices/lab_pin.sym} 900 530 0 0 {name=l161 lab=OUTI_DP}
C {sky130_fd_pr/cap_mim_m3_1.sym} 1050 500 0 0 {name=CN_DP model=cap_mim_m3_1 W=24 L=24 MF=1 spiceprefix=X}
C {devices/lab_pin.sym} 1050 470 0 0 {name=l162 lab=NG_DP}
C {devices/lab_pin.sym} 1050 530 0 0 {name=l163 lab=OUTI_DP}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 1200 500 0 0 {name=MP_OUT_DP
L=0.5
W=20
nf=1
mult=40
ad=5.8
as=5.8
pd=40.58
ps=40.58
nrd=0.0145 nrs=0.0145
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 1220 470 0 0 {name=l164 lab=VDD}
C {devices/lab_pin.sym} 1180 500 0 0 {name=l165 lab=PG_DP}
C {devices/lab_pin.sym} 1220 530 0 0 {name=l166 lab=OUTI_DP}
C {devices/lab_pin.sym} 1220 500 0 0 {name=l167 lab=VDD}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 1350 500 0 0 {name=MN_OUT_DP
L=0.5
W=20
nf=1
mult=13
ad=5.8
as=5.8
pd=40.58
ps=40.58
nrd=0.0145 nrs=0.0145
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 1370 470 0 0 {name=l168 lab=OUTI_DP}
C {devices/lab_pin.sym} 1330 500 0 0 {name=l169 lab=NG_DP}
C {devices/lab_pin.sym} 1370 530 0 0 {name=l170 lab=VSS}
C {devices/lab_pin.sym} 1370 500 0 0 {name=l171 lab=VSS}
C {sky130_fd_pr/res_generic_po.sym} 1500 500 0 0 {name=RSER_DP
W=20
L=10.8
model=res_generic_po
spiceprefix=X
mult=1
}
C {devices/lab_pin.sym} 1500 470 0 0 {name=l172 lab=OUTI_DP}
C {devices/lab_pin.sym} 1500 530 0 0 {name=l173 lab=DP}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 0 900 0 0 {name=MP_PA1_DM
L=0.5
W=2
nf=1
mult=1
ad=0.58
as=0.58
pd=4.58
ps=4.58
nrd=0.145 nrs=0.145
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 20 870 0 0 {name=l174 lab=VDD}
C {devices/lab_pin.sym} -20 900 0 0 {name=l175 lab=TXDM}
C {devices/lab_pin.sym} 20 930 0 0 {name=l176 lab=PA_DM}
C {devices/lab_pin.sym} 20 900 0 0 {name=l177 lab=VDD}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 150 900 0 0 {name=MP_PA2_DM
L=0.5
W=2
nf=1
mult=1
ad=0.58
as=0.58
pd=4.58
ps=4.58
nrd=0.145 nrs=0.145
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 170 870 0 0 {name=l178 lab=VDD}
C {devices/lab_pin.sym} 130 900 0 0 {name=l179 lab=EN}
C {devices/lab_pin.sym} 170 930 0 0 {name=l180 lab=PA_DM}
C {devices/lab_pin.sym} 170 900 0 0 {name=l181 lab=VDD}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 300 900 0 0 {name=MN_PA1_DM
L=0.5
W=2
nf=1
mult=1
ad=0.58
as=0.58
pd=4.58
ps=4.58
nrd=0.145 nrs=0.145
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 320 870 0 0 {name=l182 lab=PA_DM}
C {devices/lab_pin.sym} 280 900 0 0 {name=l183 lab=TXDM}
C {devices/lab_pin.sym} 320 930 0 0 {name=l184 lab=PAX_DM}
C {devices/lab_pin.sym} 320 900 0 0 {name=l185 lab=VSS}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 450 900 0 0 {name=MN_PA2_DM
L=0.5
W=2
nf=1
mult=1
ad=0.58
as=0.58
pd=4.58
ps=4.58
nrd=0.145 nrs=0.145
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 470 870 0 0 {name=l186 lab=PAX_DM}
C {devices/lab_pin.sym} 430 900 0 0 {name=l187 lab=EN}
C {devices/lab_pin.sym} 470 930 0 0 {name=l188 lab=VSS}
C {devices/lab_pin.sym} 470 900 0 0 {name=l189 lab=VSS}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 600 900 0 0 {name=MP_PINV_DM
L=0.5
W=8
nf=1
mult=1
ad=2.32
as=2.32
pd=16.58
ps=16.58
nrd=0.0362 nrs=0.0362
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 620 870 0 0 {name=l190 lab=VDD}
C {devices/lab_pin.sym} 580 900 0 0 {name=l191 lab=PA_DM}
C {devices/lab_pin.sym} 620 930 0 0 {name=l192 lab=PON_DM}
C {devices/lab_pin.sym} 620 900 0 0 {name=l193 lab=VDD}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 750 900 0 0 {name=MN_PINV_DM
L=0.5
W=4
nf=1
mult=1
ad=1.16
as=1.16
pd=8.58
ps=8.58
nrd=0.0725 nrs=0.0725
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 770 870 0 0 {name=l194 lab=PON_DM}
C {devices/lab_pin.sym} 730 900 0 0 {name=l195 lab=PA_DM}
C {devices/lab_pin.sym} 770 930 0 0 {name=l196 lab=VSS}
C {devices/lab_pin.sym} 770 900 0 0 {name=l197 lab=VSS}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 900 900 0 0 {name=MP_NB1_DM
L=0.5
W=4
nf=1
mult=1
ad=1.16
as=1.16
pd=8.58
ps=8.58
nrd=0.0725 nrs=0.0725
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 920 870 0 0 {name=l198 lab=VDD}
C {devices/lab_pin.sym} 880 900 0 0 {name=l199 lab=TXDM}
C {devices/lab_pin.sym} 920 930 0 0 {name=l200 lab=NBX_DM}
C {devices/lab_pin.sym} 920 900 0 0 {name=l201 lab=VDD}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 1050 900 0 0 {name=MP_NB2_DM
L=0.5
W=4
nf=1
mult=1
ad=1.16
as=1.16
pd=8.58
ps=8.58
nrd=0.0725 nrs=0.0725
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 1070 870 0 0 {name=l202 lab=NBX_DM}
C {devices/lab_pin.sym} 1030 900 0 0 {name=l203 lab=ENB}
C {devices/lab_pin.sym} 1070 930 0 0 {name=l204 lab=NB_DM}
C {devices/lab_pin.sym} 1070 900 0 0 {name=l205 lab=VDD}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 1200 900 0 0 {name=MN_NB1_DM
L=0.5
W=1
nf=1
mult=1
ad=0.29
as=0.29
pd=2.58
ps=2.58
nrd=0.29 nrs=0.29
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 1220 870 0 0 {name=l206 lab=NB_DM}
C {devices/lab_pin.sym} 1180 900 0 0 {name=l207 lab=TXDM}
C {devices/lab_pin.sym} 1220 930 0 0 {name=l208 lab=VSS}
C {devices/lab_pin.sym} 1220 900 0 0 {name=l209 lab=VSS}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 1350 900 0 0 {name=MN_NB2_DM
L=0.5
W=1
nf=1
mult=1
ad=0.29
as=0.29
pd=2.58
ps=2.58
nrd=0.29 nrs=0.29
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 1370 870 0 0 {name=l210 lab=NB_DM}
C {devices/lab_pin.sym} 1330 900 0 0 {name=l211 lab=ENB}
C {devices/lab_pin.sym} 1370 930 0 0 {name=l212 lab=VSS}
C {devices/lab_pin.sym} 1370 900 0 0 {name=l213 lab=VSS}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 1500 900 0 0 {name=MP_NINV_DM
L=0.5
W=8
nf=1
mult=1
ad=2.32
as=2.32
pd=16.58
ps=16.58
nrd=0.0362 nrs=0.0362
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 1520 870 0 0 {name=l214 lab=VDD}
C {devices/lab_pin.sym} 1480 900 0 0 {name=l215 lab=NB_DM}
C {devices/lab_pin.sym} 1520 930 0 0 {name=l216 lab=NONB_DM}
C {devices/lab_pin.sym} 1520 900 0 0 {name=l217 lab=VDD}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 1650 900 0 0 {name=MN_NINV_DM
L=0.5
W=4
nf=1
mult=1
ad=1.16
as=1.16
pd=8.58
ps=8.58
nrd=0.0725 nrs=0.0725
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 1670 870 0 0 {name=l218 lab=NONB_DM}
C {devices/lab_pin.sym} 1630 900 0 0 {name=l219 lab=NB_DM}
C {devices/lab_pin.sym} 1670 930 0 0 {name=l220 lab=VSS}
C {devices/lab_pin.sym} 1670 900 0 0 {name=l221 lab=VSS}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 0 1100 0 0 {name=MP_POFF_DM
L=0.5
W=20
nf=1
mult=1
ad=5.8
as=5.8
pd=40.58
ps=40.58
nrd=0.0145 nrs=0.0145
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 20 1070 0 0 {name=l222 lab=VDD}
C {devices/lab_pin.sym} -20 1100 0 0 {name=l223 lab=PON_DM}
C {devices/lab_pin.sym} 20 1130 0 0 {name=l224 lab=PG_DM}
C {devices/lab_pin.sym} 20 1100 0 0 {name=l225 lab=VDD}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 150 1100 0 0 {name=MN_PSW_DM
L=0.5
W=16
nf=1
mult=1
ad=4.64
as=4.64
pd=32.58
ps=32.58
nrd=0.0181 nrs=0.0181
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 170 1070 0 0 {name=l226 lab=PG_DM}
C {devices/lab_pin.sym} 130 1100 0 0 {name=l227 lab=PON_DM}
C {devices/lab_pin.sym} 170 1130 0 0 {name=l228 lab=XP_DM}
C {devices/lab_pin.sym} 170 1100 0 0 {name=l229 lab=VSS}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 300 1100 0 0 {name=MN_PSRC_DM
L=1
W=4
nf=1
mult=25
ad=1.16
as=1.16
pd=8.58
ps=8.58
nrd=0.0725 nrs=0.0725
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 320 1070 0 0 {name=l230 lab=XP_DM}
C {devices/lab_pin.sym} 280 1100 0 0 {name=l231 lab=VBN}
C {devices/lab_pin.sym} 320 1130 0 0 {name=l232 lab=VSS}
C {devices/lab_pin.sym} 320 1100 0 0 {name=l233 lab=VSS}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 450 1100 0 0 {name=MN_NOFF_DM
L=0.5
W=20
nf=1
mult=1
ad=5.8
as=5.8
pd=40.58
ps=40.58
nrd=0.0145 nrs=0.0145
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 470 1070 0 0 {name=l234 lab=NG_DM}
C {devices/lab_pin.sym} 430 1100 0 0 {name=l235 lab=NONB_DM}
C {devices/lab_pin.sym} 470 1130 0 0 {name=l236 lab=VSS}
C {devices/lab_pin.sym} 470 1100 0 0 {name=l237 lab=VSS}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 600 1100 0 0 {name=MP_NSW_DM
L=0.5
W=8
nf=1
mult=1
ad=2.32
as=2.32
pd=16.58
ps=16.58
nrd=0.0362 nrs=0.0362
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 620 1070 0 0 {name=l238 lab=XN_DM}
C {devices/lab_pin.sym} 580 1100 0 0 {name=l239 lab=NONB_DM}
C {devices/lab_pin.sym} 620 1130 0 0 {name=l240 lab=NG_DM}
C {devices/lab_pin.sym} 620 1100 0 0 {name=l241 lab=VDD}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 750 1100 0 0 {name=MP_NSRC_DM
L=1
W=8
nf=1
mult=8
ad=2.32
as=2.32
pd=16.58
ps=16.58
nrd=0.0362 nrs=0.0362
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 770 1070 0 0 {name=l242 lab=VDD}
C {devices/lab_pin.sym} 730 1100 0 0 {name=l243 lab=VBP}
C {devices/lab_pin.sym} 770 1130 0 0 {name=l244 lab=XN_DM}
C {devices/lab_pin.sym} 770 1100 0 0 {name=l245 lab=VDD}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 0 1300 0 0 {name=MP_KREP_DM
L=0.5
W=10
nf=1
mult=1
ad=2.9
as=2.9
pd=20.58
ps=20.58
nrd=0.029 nrs=0.029
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 20 1270 0 0 {name=l246 lab=VDD}
C {devices/lab_pin.sym} -20 1300 0 0 {name=l247 lab=PG_DM}
C {devices/lab_pin.sym} 20 1330 0 0 {name=l248 lab=KSP_DM}
C {devices/lab_pin.sym} 20 1300 0 0 {name=l249 lab=VDD}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 150 1300 0 0 {name=MN_KBIAS_DM
L=1
W=4
nf=1
mult=1
ad=1.16
as=1.16
pd=8.58
ps=8.58
nrd=0.0725 nrs=0.0725
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 170 1270 0 0 {name=l250 lab=KSP_DM}
C {devices/lab_pin.sym} 130 1300 0 0 {name=l251 lab=VBN}
C {devices/lab_pin.sym} 170 1330 0 0 {name=l252 lab=VSS}
C {devices/lab_pin.sym} 170 1300 0 0 {name=l253 lab=VSS}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 300 1300 0 0 {name=MP_KINV_DM
L=0.5
W=2
nf=1
mult=1
ad=0.58
as=0.58
pd=4.58
ps=4.58
nrd=0.145 nrs=0.145
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 320 1270 0 0 {name=l254 lab=VDD}
C {devices/lab_pin.sym} 280 1300 0 0 {name=l255 lab=KSP_DM}
C {devices/lab_pin.sym} 320 1330 0 0 {name=l256 lab=KSPB_DM}
C {devices/lab_pin.sym} 320 1300 0 0 {name=l257 lab=VDD}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 450 1300 0 0 {name=MN_KINV_DM
L=0.5
W=1
nf=1
mult=1
ad=0.29
as=0.29
pd=2.58
ps=2.58
nrd=0.29 nrs=0.29
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 470 1270 0 0 {name=l258 lab=KSPB_DM}
C {devices/lab_pin.sym} 430 1300 0 0 {name=l259 lab=KSP_DM}
C {devices/lab_pin.sym} 470 1330 0 0 {name=l260 lab=VSS}
C {devices/lab_pin.sym} 470 1300 0 0 {name=l261 lab=VSS}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 600 1300 0 0 {name=MN_KICK1_DM
L=0.5
W=4
nf=1
mult=1
ad=1.16
as=1.16
pd=8.58
ps=8.58
nrd=0.0725 nrs=0.0725
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 620 1270 0 0 {name=l262 lab=PG_DM}
C {devices/lab_pin.sym} 580 1300 0 0 {name=l263 lab=PON_DM}
C {devices/lab_pin.sym} 620 1330 0 0 {name=l264 lab=KPX_DM}
C {devices/lab_pin.sym} 620 1300 0 0 {name=l265 lab=VSS}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 750 1300 0 0 {name=MN_KICK2_DM
L=0.5
W=4
nf=1
mult=1
ad=1.16
as=1.16
pd=8.58
ps=8.58
nrd=0.0725 nrs=0.0725
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 770 1270 0 0 {name=l266 lab=KPX_DM}
C {devices/lab_pin.sym} 730 1300 0 0 {name=l267 lab=KSPB_DM}
C {devices/lab_pin.sym} 770 1330 0 0 {name=l268 lab=VSS}
C {devices/lab_pin.sym} 770 1300 0 0 {name=l269 lab=VSS}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 900 1300 0 0 {name=MN_KREPN_DM
L=0.5
W=4
nf=1
mult=1
ad=1.16
as=1.16
pd=8.58
ps=8.58
nrd=0.0725 nrs=0.0725
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 920 1270 0 0 {name=l270 lab=KSN_DM}
C {devices/lab_pin.sym} 880 1300 0 0 {name=l271 lab=NG_DM}
C {devices/lab_pin.sym} 920 1330 0 0 {name=l272 lab=VSS}
C {devices/lab_pin.sym} 920 1300 0 0 {name=l273 lab=VSS}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 1050 1300 0 0 {name=MP_KBIASN_DM
L=1
W=8
nf=1
mult=1
ad=2.32
as=2.32
pd=16.58
ps=16.58
nrd=0.0362 nrs=0.0362
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 1070 1270 0 0 {name=l274 lab=VDD}
C {devices/lab_pin.sym} 1030 1300 0 0 {name=l275 lab=VBP}
C {devices/lab_pin.sym} 1070 1330 0 0 {name=l276 lab=KSN_DM}
C {devices/lab_pin.sym} 1070 1300 0 0 {name=l277 lab=VDD}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 1200 1300 0 0 {name=MP_KINVN_DM
L=0.5
W=2
nf=1
mult=1
ad=0.58
as=0.58
pd=4.58
ps=4.58
nrd=0.145 nrs=0.145
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 1220 1270 0 0 {name=l278 lab=VDD}
C {devices/lab_pin.sym} 1180 1300 0 0 {name=l279 lab=KSN_DM}
C {devices/lab_pin.sym} 1220 1330 0 0 {name=l280 lab=KSNB_DM}
C {devices/lab_pin.sym} 1220 1300 0 0 {name=l281 lab=VDD}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 1350 1300 0 0 {name=MN_KINVN_DM
L=0.5
W=1
nf=1
mult=1
ad=0.29
as=0.29
pd=2.58
ps=2.58
nrd=0.29 nrs=0.29
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 1370 1270 0 0 {name=l282 lab=KSNB_DM}
C {devices/lab_pin.sym} 1330 1300 0 0 {name=l283 lab=KSN_DM}
C {devices/lab_pin.sym} 1370 1330 0 0 {name=l284 lab=VSS}
C {devices/lab_pin.sym} 1370 1300 0 0 {name=l285 lab=VSS}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 1500 1300 0 0 {name=MP_KICK1N_DM
L=0.5
W=4
nf=1
mult=1
ad=1.16
as=1.16
pd=8.58
ps=8.58
nrd=0.0725 nrs=0.0725
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 1520 1270 0 0 {name=l286 lab=KNX_DM}
C {devices/lab_pin.sym} 1480 1300 0 0 {name=l287 lab=NONB_DM}
C {devices/lab_pin.sym} 1520 1330 0 0 {name=l288 lab=NG_DM}
C {devices/lab_pin.sym} 1520 1300 0 0 {name=l289 lab=VDD}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 1650 1300 0 0 {name=MP_KICK2N_DM
L=0.5
W=4
nf=1
mult=1
ad=1.16
as=1.16
pd=8.58
ps=8.58
nrd=0.0725 nrs=0.0725
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 1670 1270 0 0 {name=l290 lab=VDD}
C {devices/lab_pin.sym} 1630 1300 0 0 {name=l291 lab=KSNB_DM}
C {devices/lab_pin.sym} 1670 1330 0 0 {name=l292 lab=KNX_DM}
C {devices/lab_pin.sym} 1670 1300 0 0 {name=l293 lab=VDD}
C {sky130_fd_pr/cap_mim_m3_1.sym} 900 1100 0 0 {name=CP_DM model=cap_mim_m3_1 W=42 L=42 MF=1 spiceprefix=X}
C {devices/lab_pin.sym} 900 1070 0 0 {name=l294 lab=PG_DM}
C {devices/lab_pin.sym} 900 1130 0 0 {name=l295 lab=OUTI_DM}
C {sky130_fd_pr/cap_mim_m3_1.sym} 1050 1100 0 0 {name=CN_DM model=cap_mim_m3_1 W=24 L=24 MF=1 spiceprefix=X}
C {devices/lab_pin.sym} 1050 1070 0 0 {name=l296 lab=NG_DM}
C {devices/lab_pin.sym} 1050 1130 0 0 {name=l297 lab=OUTI_DM}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 1200 1100 0 0 {name=MP_OUT_DM
L=0.5
W=20
nf=1
mult=40
ad=5.8
as=5.8
pd=40.58
ps=40.58
nrd=0.0145 nrs=0.0145
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 1220 1070 0 0 {name=l298 lab=VDD}
C {devices/lab_pin.sym} 1180 1100 0 0 {name=l299 lab=PG_DM}
C {devices/lab_pin.sym} 1220 1130 0 0 {name=l300 lab=OUTI_DM}
C {devices/lab_pin.sym} 1220 1100 0 0 {name=l301 lab=VDD}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 1350 1100 0 0 {name=MN_OUT_DM
L=0.5
W=20
nf=1
mult=13
ad=5.8
as=5.8
pd=40.58
ps=40.58
nrd=0.0145 nrs=0.0145
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 1370 1070 0 0 {name=l302 lab=OUTI_DM}
C {devices/lab_pin.sym} 1330 1100 0 0 {name=l303 lab=NG_DM}
C {devices/lab_pin.sym} 1370 1130 0 0 {name=l304 lab=VSS}
C {devices/lab_pin.sym} 1370 1100 0 0 {name=l305 lab=VSS}
C {sky130_fd_pr/res_generic_po.sym} 1500 1100 0 0 {name=RSER_DM
W=20
L=10.8
model=res_generic_po
spiceprefix=X
mult=1
}
C {devices/lab_pin.sym} 1500 1070 0 0 {name=l306 lab=OUTI_DM}
C {devices/lab_pin.sym} 1500 1130 0 0 {name=l307 lab=DM}
C {devices/iopin.sym} -300 -300 0 0 {name=p_vdd lab=VDD}
C {devices/iopin.sym} -300 -240 0 0 {name=p_vss lab=VSS}
C {devices/ipin.sym} -300 -180 0 0 {name=p_txdp lab=TXDP}
C {devices/ipin.sym} -300 -120 0 0 {name=p_txdm lab=TXDM}
C {devices/ipin.sym} -300 -60 0 0 {name=p_drven lab=DRVEN}
C {devices/ipin.sym} -300 0 0 0 {name=p_oe lab=OE}
C {devices/iopin.sym} -300 60 0 0 {name=p_dp lab=DP}
C {devices/iopin.sym} -300 120 0 0 {name=p_dm lab=DM}
