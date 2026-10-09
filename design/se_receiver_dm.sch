v {xschem version=3.4.7 file_version=1.2}
G {}
K {type=subcircuit
format="@name @pinlist @symname"
template="name=x1"}
V {}
S {}
E {}
T {se_receiver_dm -- USB 2.0 FS single-ended D- receiver, sky130 port (issue #110)\nPin contract: se_receiver_dm VDD VSS DM RXDM. VDD/VSS inout (3.0-3.6 V I/O rail / ground),\nDM in (analog, the D- line, 0 V..VDD), RXDM out (3.3 V domain; RXDM=1 when DM is above the VREF threshold). No enable pin.\nTopology (ported from gf180-usb2-phy @0aab249, devices re-derived): the differential receiver's self-biased 5T OTA\nwith DM on the diode-side input and VREF (R1/R2 ratiometric divider off VDD, ~0.425 x VDD) on the mirror-side input,\n+ two-inverter buffer, first inverter P-heavy. All MOS sky130_fd_pr thick-oxide g5v0d10v5 (5 V-class, rated for the\n3.6 V rail); R1, R2 and RBIAS res_xhigh_po_1p41. Sizing record: design/README.md.} -600 -700 0 0 0.3 0.3 {}
C {sky130_fd_pr/res_xhigh_po_1p41.sym} -500 -300 0 0 {name=R1
L=19
model=res_xhigh_po_1p41
spiceprefix=X
mult=1
}
C {devices/lab_pin.sym} -500 -330 0 0 {name=l44 lab=VDD}
C {devices/lab_pin.sym} -500 -270 0 0 {name=l45 lab=VREF}
C {devices/lab_pin.sym} -520 -300 0 0 {name=l46 lab=VSS}
C {sky130_fd_pr/res_xhigh_po_1p41.sym} -500 -150 0 0 {name=R2
L=14
model=res_xhigh_po_1p41
spiceprefix=X
mult=1
}
C {devices/lab_pin.sym} -500 -180 0 0 {name=l47 lab=VREF}
C {devices/lab_pin.sym} -500 -120 0 0 {name=l48 lab=VSS}
C {devices/lab_pin.sym} -520 -150 0 0 {name=l49 lab=VSS}
C {sky130_fd_pr/res_xhigh_po_1p41.sym} -500 0 0 0 {name=RBIAS
L=140
model=res_xhigh_po_1p41
spiceprefix=X
mult=1
}
C {devices/lab_pin.sym} -500 -30 0 0 {name=l1 lab=VDD}
C {devices/lab_pin.sym} -500 30 0 0 {name=l2 lab=IBIASN}
C {devices/lab_pin.sym} -520 0 0 0 {name=l3 lab=VSS}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} -280 0 0 0 {name=MNBIAS
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
C {devices/lab_pin.sym} -260 -30 0 0 {name=l4 lab=IBIASN}
C {devices/lab_pin.sym} -300 0 0 0 {name=l5 lab=IBIASN}
C {devices/lab_pin.sym} -260 30 0 0 {name=l6 lab=VSS}
C {devices/lab_pin.sym} -260 0 0 0 {name=l7 lab=VSS}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} -60 0 0 0 {name=MTAIL
L=0.5
W=4
nf=1
mult=2
ad=1.16
as=1.16
pd=8.58
ps=8.58
nrd=0.0725 nrs=0.0725
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} -40 -30 0 0 {name=l8 lab=TAIL}
C {devices/lab_pin.sym} -80 0 0 0 {name=l9 lab=IBIASN}
C {devices/lab_pin.sym} -40 30 0 0 {name=l10 lab=VSS}
C {devices/lab_pin.sym} -40 0 0 0 {name=l11 lab=VSS}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 160 0 0 0 {name=MN_INA
L=0.5
W=10
nf=1
mult=2
ad=2.9
as=2.9
pd=20.58
ps=20.58
nrd=0.029 nrs=0.029
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 180 -30 0 0 {name=l12 lab=LOADDIODE}
C {devices/lab_pin.sym} 140 0 0 0 {name=l13 lab=DM}
C {devices/lab_pin.sym} 180 30 0 0 {name=l14 lab=TAIL}
C {devices/lab_pin.sym} 180 0 0 0 {name=l15 lab=VSS}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 380 0 0 0 {name=MN_INB
L=0.5
W=10
nf=1
mult=2
ad=2.9
as=2.9
pd=20.58
ps=20.58
nrd=0.029 nrs=0.029
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 400 -30 0 0 {name=l16 lab=AMPOUT}
C {devices/lab_pin.sym} 360 0 0 0 {name=l17 lab=VREF}
C {devices/lab_pin.sym} 400 30 0 0 {name=l18 lab=TAIL}
C {devices/lab_pin.sym} 400 0 0 0 {name=l19 lab=VSS}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 600 0 0 0 {name=MP_LOADA
L=0.5
W=10
nf=1
mult=4
ad=2.9
as=2.9
pd=20.58
ps=20.58
nrd=0.029 nrs=0.029
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 620 30 0 0 {name=l20 lab=LOADDIODE}
C {devices/lab_pin.sym} 580 0 0 0 {name=l21 lab=LOADDIODE}
C {devices/lab_pin.sym} 620 -30 0 0 {name=l22 lab=VDD}
C {devices/lab_pin.sym} 620 0 0 0 {name=l23 lab=VDD}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 820 0 0 0 {name=MP_LOADB
L=0.5
W=10
nf=1
mult=4
ad=2.9
as=2.9
pd=20.58
ps=20.58
nrd=0.029 nrs=0.029
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 840 30 0 0 {name=l24 lab=AMPOUT}
C {devices/lab_pin.sym} 800 0 0 0 {name=l25 lab=LOADDIODE}
C {devices/lab_pin.sym} 840 -30 0 0 {name=l26 lab=VDD}
C {devices/lab_pin.sym} 840 0 0 0 {name=l27 lab=VDD}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 1040 0 0 0 {name=MP_B1
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
C {devices/lab_pin.sym} 1060 30 0 0 {name=l28 lab=BUF1}
C {devices/lab_pin.sym} 1020 0 0 0 {name=l29 lab=AMPOUT}
C {devices/lab_pin.sym} 1060 -30 0 0 {name=l30 lab=VDD}
C {devices/lab_pin.sym} 1060 0 0 0 {name=l31 lab=VDD}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 1260 0 0 0 {name=MN_B1
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
C {devices/lab_pin.sym} 1280 -30 0 0 {name=l32 lab=BUF1}
C {devices/lab_pin.sym} 1240 0 0 0 {name=l33 lab=AMPOUT}
C {devices/lab_pin.sym} 1280 30 0 0 {name=l34 lab=VSS}
C {devices/lab_pin.sym} 1280 0 0 0 {name=l35 lab=VSS}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 1480 0 0 0 {name=MP_B2
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
C {devices/lab_pin.sym} 1500 30 0 0 {name=l36 lab=RXDM}
C {devices/lab_pin.sym} 1460 0 0 0 {name=l37 lab=BUF1}
C {devices/lab_pin.sym} 1500 -30 0 0 {name=l38 lab=VDD}
C {devices/lab_pin.sym} 1500 0 0 0 {name=l39 lab=VDD}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 1700 0 0 0 {name=MN_B2
L=0.5
W=5
nf=1
mult=1
ad=1.45
as=1.45
pd=10.58
ps=10.58
nrd=0.058 nrs=0.058
sa=0 sb=0 sd=0
model=nfet_g5v0d10v5
spiceprefix=X
}
C {devices/lab_pin.sym} 1720 -30 0 0 {name=l40 lab=RXDM}
C {devices/lab_pin.sym} 1680 0 0 0 {name=l41 lab=BUF1}
C {devices/lab_pin.sym} 1720 30 0 0 {name=l42 lab=VSS}
C {devices/lab_pin.sym} 1720 0 0 0 {name=l43 lab=VSS}
C {devices/iopin.sym} -700 -400 0 0 {name=p_vdd lab=VDD}
C {devices/iopin.sym} -700 -340 0 0 {name=p_vss lab=VSS}
C {devices/ipin.sym} -700 -280 0 0 {name=p_dm lab=DM}
C {devices/iopin.sym} -700 -220 0 0 {name=p_rxdm lab=RXDM}
