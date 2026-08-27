# usb2-phy comp data (generated, public-sources-only)

Generated 2026-08-27 from the upstream comp library's `usb2-phy.md` entry by an internal, private-repo-only tool. This is a derived, filtered copy — regenerate rather than hand-edit. Every row below cites a public vendor datasheet or a public distributor pricing page; nothing internal survived extraction.

## Comparable parts

| Vendor | Part | Class | Interface | Speed | Driver rise/fall (FS) | Crossover | Diff. input sensitivity | Common-mode range | D+ pull-up | Supply current (FS active) | Price | Source |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Texas Instruments | TUSB1106 | Analog-only USB transceiver (no digital NRZI core) | Single-ended/differential serial (MODE pin), no UTMI/ULPI digital bus | FS (12 Mb/s) + LS (1.5 Mb/s); no HS | 4–20 ns (into implied USB2.0 load) | 1.3–2.0 V | 200 mV (\|VI(D+) − VI(D−)\|) | 0.8–2.5 V | **External** 1.5 kΩ discrete resistor to VPU(3.3) — not integrated | ICC 6–8 mA + ICC(I/O) 2.3–2.5 mA (FS TX/RX) | $0.779 (TUSB1106PWR, ti.com store, 1ku tier) | Datasheet: [ti.com/lit/ds/symlink/tusb1106.pdf](https://www.ti.com/lit/ds/symlink/tusb1106.pdf) (SCAS818E). Pricing: [ti.com/product/TUSB1106](https://www.ti.com/product/TUSB1106) |
| Texas Instruments | TUSB1210 | Full HS/FS/LS USB2.0 PHY (complete analog front end + protocol-level register set) | ULPI (12-pin SDR, 60 MHz clock) — not UTMI | HS (480 Mb/s) + FS (12 Mb/s) + LS; supports OTG (HNP/SRP) | 4–20 ns | 1.3–2.0 V | 200 mV | not separately headlined for FS (HS common-mode/signaling levels stated instead) | **Internal** 1.5 kΩ pull-up, software-controlled via TERMSELECT register | ITOTAL ≈ 31.7 mA (FS USB operation, synchronous mode, typ) | $2.296 (1–99 units) / $1.025 (1ku), TUSB1210BRHBR, ti.com store | Datasheet: [ti.com/lit/ds/symlink/tusb1210.pdf](https://www.ti.com/lit/ds/symlink/tusb1210.pdf). Pricing: [ti.com/product/TUSB1210](https://www.ti.com/product/TUSB1210) |

## Sources

| URL | Establishes | Fetched |
|---|---|---|
| https://www.ti.com/lit/ds/symlink/tusb1106.pdf | TUSB1106 electrical characteristics (rise/fall, crossover, sensitivity, common-mode, pull-up, supply current) | 2026-08-24 |
| https://www.ti.com/product/TUSB1106 | TUSB1106PWR ti.com store pricing | 2026-08-24 |
| https://www.ti.com/lit/ds/symlink/tusb1210.pdf | TUSB1210 electrical characteristics (rise/fall, crossover, sensitivity, pull-up, power consumption table) | 2026-08-24 |
| https://www.ti.com/product/TUSB1210 | TUSB1210BRHBR ti.com store pricing (tiered) | 2026-08-24 |

