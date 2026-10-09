v {xschem version=3.4.7 file_version=1.2}
G {}
K {type=subcircuit
format="@name @pinlist @symname"
template="name=x1"}
V {}
S {}
E {}
T {dplus_pullup -- USB 2.0 FS D+ 1.5 kohm pull-up with 4-bit trim ladder, sky130 port (issue #113)\nPin contract: dplus_pullup DP VPU VSS PU_EN TRIM0 TRIM1 TRIM2 TRIM3. DP inout (the D+ line); VPU inout (pull-up supply, an INPUT: 3.0-3.6 V,\nnot generated here); VSS inout; PU_EN, TRIM0..TRIM3 in, active high, logic levels 0 / VPU. PU_EN=1 connects the pull-up; PU_EN=0 disables it (high impedance).\nTRIM<i>=1 shorts ladder segment i (60/119/238/476 ohm nominal); all-zero TRIM is the maximum resistance. Series path: VPU - enable switch - RBASE (1.0 kohm) - segments 0..3 - DP.\nPorted from gf180-usb2-phy @0aab249 (devices re-derived). All MOS sky130_fd_pr thick-oxide g5v0d10v5 (L=0.5, nf=1, mult only); ladder res_generic_po W=2.\nReasons and sizing record: design/README.md.} -700 -800 0 0 0.3 0.3 {}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} -400 -400 0 0 {name=MP_EN
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
spiceprefix=X}
C {devices/lab_pin.sym} -380 -370 0 0 {name=l1 lab=PU_ENB}
C {devices/lab_pin.sym} -420 -400 0 0 {name=l2 lab=PU_EN}
C {devices/lab_pin.sym} -380 -430 0 0 {name=l3 lab=VPU}
C {devices/lab_pin.sym} -380 -400 0 0 {name=l4 lab=VPU}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} -280 -400 0 0 {name=MN_EN
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
spiceprefix=X}
C {devices/lab_pin.sym} -260 -430 0 0 {name=l5 lab=PU_ENB}
C {devices/lab_pin.sym} -300 -400 0 0 {name=l6 lab=PU_EN}
C {devices/lab_pin.sym} -260 -370 0 0 {name=l7 lab=VSS}
C {devices/lab_pin.sym} -260 -400 0 0 {name=l8 lab=VSS}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} -100 -400 0 0 {name=MP_T0
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
spiceprefix=X}
C {devices/lab_pin.sym} -80 -370 0 0 {name=l9 lab=TRIM0B}
C {devices/lab_pin.sym} -120 -400 0 0 {name=l10 lab=TRIM0}
C {devices/lab_pin.sym} -80 -430 0 0 {name=l11 lab=VPU}
C {devices/lab_pin.sym} -80 -400 0 0 {name=l12 lab=VPU}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 20 -400 0 0 {name=MN_T0
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
spiceprefix=X}
C {devices/lab_pin.sym} 40 -430 0 0 {name=l13 lab=TRIM0B}
C {devices/lab_pin.sym} 0 -400 0 0 {name=l14 lab=TRIM0}
C {devices/lab_pin.sym} 40 -370 0 0 {name=l15 lab=VSS}
C {devices/lab_pin.sym} 40 -400 0 0 {name=l16 lab=VSS}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 200 -400 0 0 {name=MP_T1
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
spiceprefix=X}
C {devices/lab_pin.sym} 220 -370 0 0 {name=l17 lab=TRIM1B}
C {devices/lab_pin.sym} 180 -400 0 0 {name=l18 lab=TRIM1}
C {devices/lab_pin.sym} 220 -430 0 0 {name=l19 lab=VPU}
C {devices/lab_pin.sym} 220 -400 0 0 {name=l20 lab=VPU}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 320 -400 0 0 {name=MN_T1
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
spiceprefix=X}
C {devices/lab_pin.sym} 340 -430 0 0 {name=l21 lab=TRIM1B}
C {devices/lab_pin.sym} 300 -400 0 0 {name=l22 lab=TRIM1}
C {devices/lab_pin.sym} 340 -370 0 0 {name=l23 lab=VSS}
C {devices/lab_pin.sym} 340 -400 0 0 {name=l24 lab=VSS}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 500 -400 0 0 {name=MP_T2
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
spiceprefix=X}
C {devices/lab_pin.sym} 520 -370 0 0 {name=l25 lab=TRIM2B}
C {devices/lab_pin.sym} 480 -400 0 0 {name=l26 lab=TRIM2}
C {devices/lab_pin.sym} 520 -430 0 0 {name=l27 lab=VPU}
C {devices/lab_pin.sym} 520 -400 0 0 {name=l28 lab=VPU}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 620 -400 0 0 {name=MN_T2
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
spiceprefix=X}
C {devices/lab_pin.sym} 640 -430 0 0 {name=l29 lab=TRIM2B}
C {devices/lab_pin.sym} 600 -400 0 0 {name=l30 lab=TRIM2}
C {devices/lab_pin.sym} 640 -370 0 0 {name=l31 lab=VSS}
C {devices/lab_pin.sym} 640 -400 0 0 {name=l32 lab=VSS}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 800 -400 0 0 {name=MP_T3
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
spiceprefix=X}
C {devices/lab_pin.sym} 820 -370 0 0 {name=l33 lab=TRIM3B}
C {devices/lab_pin.sym} 780 -400 0 0 {name=l34 lab=TRIM3}
C {devices/lab_pin.sym} 820 -430 0 0 {name=l35 lab=VPU}
C {devices/lab_pin.sym} 820 -400 0 0 {name=l36 lab=VPU}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 920 -400 0 0 {name=MN_T3
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
spiceprefix=X}
C {devices/lab_pin.sym} 940 -430 0 0 {name=l37 lab=TRIM3B}
C {devices/lab_pin.sym} 900 -400 0 0 {name=l38 lab=TRIM3}
C {devices/lab_pin.sym} 940 -370 0 0 {name=l39 lab=VSS}
C {devices/lab_pin.sym} 940 -400 0 0 {name=l40 lab=VSS}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} -400 -100 0 0 {name=MP_ENSW
L=0.5
W=100
nf=1
mult=10
ad=29
as=29
pd=200.58
ps=200.58
nrd=0.0029 nrs=0.0029
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X}
C {devices/lab_pin.sym} -380 -70 0 0 {name=l41 lab=N0}
C {devices/lab_pin.sym} -420 -100 0 0 {name=l42 lab=PU_ENB}
C {devices/lab_pin.sym} -380 -130 0 0 {name=l43 lab=VPU}
C {devices/lab_pin.sym} -380 -100 0 0 {name=l44 lab=VPU}
C {sky130_fd_pr/res_generic_po.sym} -100 -100 0 0 {name=RBASE
W=2
L=40.3
model=res_generic_po
spiceprefix=X
mult=1}
C {devices/lab_pin.sym} -100 -130 0 0 {name=l45 lab=N0}
C {devices/lab_pin.sym} -100 -70 0 0 {name=l46 lab=N1}
C {sky130_fd_pr/res_generic_po.sym} 100 -100 0 0 {name=R0
W=2
L=2.4
model=res_generic_po
spiceprefix=X
mult=1}
C {devices/lab_pin.sym} 100 -130 0 0 {name=l47 lab=N1}
C {devices/lab_pin.sym} 100 -70 0 0 {name=l48 lab=N2}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 220 100 0 0 {name=MP_B0
L=0.5
W=100
nf=1
mult=8
ad=29
as=29
pd=200.58
ps=200.58
nrd=0.0029 nrs=0.0029
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X}
C {devices/lab_pin.sym} 240 130 0 0 {name=l49 lab=N1}
C {devices/lab_pin.sym} 200 100 0 0 {name=l50 lab=TRIM0B}
C {devices/lab_pin.sym} 240 70 0 0 {name=l51 lab=N2}
C {devices/lab_pin.sym} 240 100 0 0 {name=l52 lab=VPU}
C {sky130_fd_pr/res_generic_po.sym} 400 -100 0 0 {name=R1
W=2
L=4.8
model=res_generic_po
spiceprefix=X
mult=1}
C {devices/lab_pin.sym} 400 -130 0 0 {name=l53 lab=N2}
C {devices/lab_pin.sym} 400 -70 0 0 {name=l54 lab=N3}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 520 100 0 0 {name=MP_B1
L=0.5
W=100
nf=1
mult=4
ad=29
as=29
pd=200.58
ps=200.58
nrd=0.0029 nrs=0.0029
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X}
C {devices/lab_pin.sym} 540 130 0 0 {name=l55 lab=N2}
C {devices/lab_pin.sym} 500 100 0 0 {name=l56 lab=TRIM1B}
C {devices/lab_pin.sym} 540 70 0 0 {name=l57 lab=N3}
C {devices/lab_pin.sym} 540 100 0 0 {name=l58 lab=VPU}
C {sky130_fd_pr/res_generic_po.sym} 700 -100 0 0 {name=R2
W=2
L=9.6
model=res_generic_po
spiceprefix=X
mult=1}
C {devices/lab_pin.sym} 700 -130 0 0 {name=l59 lab=N3}
C {devices/lab_pin.sym} 700 -70 0 0 {name=l60 lab=N4}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 820 100 0 0 {name=MP_B2
L=0.5
W=100
nf=1
mult=2
ad=29
as=29
pd=200.58
ps=200.58
nrd=0.0029 nrs=0.0029
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X}
C {devices/lab_pin.sym} 840 130 0 0 {name=l61 lab=N3}
C {devices/lab_pin.sym} 800 100 0 0 {name=l62 lab=TRIM2B}
C {devices/lab_pin.sym} 840 70 0 0 {name=l63 lab=N4}
C {devices/lab_pin.sym} 840 100 0 0 {name=l64 lab=VPU}
C {sky130_fd_pr/res_generic_po.sym} 1000 -100 0 0 {name=R3
W=2
L=19.2
model=res_generic_po
spiceprefix=X
mult=1}
C {devices/lab_pin.sym} 1000 -130 0 0 {name=l65 lab=N4}
C {devices/lab_pin.sym} 1000 -70 0 0 {name=l66 lab=DP}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 1120 100 0 0 {name=MP_B3
L=0.5
W=100
nf=1
mult=1
ad=29
as=29
pd=200.58
ps=200.58
nrd=0.0029 nrs=0.0029
sa=0 sb=0 sd=0
model=pfet_g5v0d10v5
spiceprefix=X}
C {devices/lab_pin.sym} 1140 130 0 0 {name=l67 lab=N4}
C {devices/lab_pin.sym} 1100 100 0 0 {name=l68 lab=TRIM3B}
C {devices/lab_pin.sym} 1140 70 0 0 {name=l69 lab=DP}
C {devices/lab_pin.sym} 1140 100 0 0 {name=l70 lab=VPU}
C {devices/iopin.sym} -700 -700 0 0 {name=p_dp lab=DP}
C {devices/iopin.sym} -700 -640 0 0 {name=p_vpu lab=VPU}
C {devices/iopin.sym} -700 -580 0 0 {name=p_vss lab=VSS}
C {devices/ipin.sym} -700 -520 0 0 {name=p_pu_en lab=PU_EN}
C {devices/ipin.sym} -700 -460 0 0 {name=p_trim0 lab=TRIM0}
C {devices/ipin.sym} -700 -400 0 0 {name=p_trim1 lab=TRIM1}
C {devices/ipin.sym} -700 -340 0 0 {name=p_trim2 lab=TRIM2}
C {devices/ipin.sym} -700 -280 0 0 {name=p_trim3 lab=TRIM3}
