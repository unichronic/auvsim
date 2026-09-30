# COMPONENTS.md — specs, pin map, power

Every part, what it does, and the electrical details that matter. **Verify all pinouts against manufacturer datasheets before wiring.**

---

## 1. Compute board

### Vicharak Shrike Lite (owned)

A single board carrying two processors, linked on-PCB.

| | |
|---|---|
| **MCU** | RP2040 — dual Cortex-M0+ @ 133 MHz (overclockable well past 200 MHz), 264 KB SRAM, 4 MB QSPI flash, 12 DMA channels, PIO blocks |
| **FPGA** | Renesas SLG47910 "ForgeFPGA" — 1,120 five-input LUTs, 1,120 flip-flops, **32 kb block RAM**, 5 kb distributed memory, **50 MHz on-chip oscillator with PLL**, 14 exposed GPIO |
| **Inter-chip link** | 6-bit bus between RP2040 and FPGA |
| **I/O level** | 3.3 V |
| **Other** | PMOD connector, breadboard-compatible, USB-C for power and programming |
| **Cost** | ~$4 |

**Toolchain:** Arduino IDE + arduino-pico core (Earle Philhower) for the RP2040 — fastest route, includes PIO access and USB serial. FPGA side uses Renesas **ForgeFPGA Workshop** via Go Configure Software Hub — free, all major OSes, Verilog 2005 + SystemVerilog, partly built on Yosys, and **it has a built-in simulator**.

**Docs:** `vicharak-in/shrike` repo, particularly `docs/shrike_pinouts.md`. Also a CORDIC example in that repo. ⚠️ DeepWiki's pin reference for this board is AI-generated and wrong.

### Why the M0+ shapes the architecture

No FPU. It **cannot** synthesise samples in real time at 10 MS/s (~13 cycles per sample available — nowhere near enough for trig). Hence precompute-into-SRAM then DMA-stream, which is exactly what the spec asks for.

A software DDS loop (phase accumulator + sine LUT, integer math) runs ~12–15 cycles per sample, so a 50,000-sample buffer takes ~5.6 ms to generate. Continuous unbounded streaming caps around 5 MS/s (15 cycles × 10 MS/s = 150M cycles/s needed vs 133M available); precomputed buffers avoid the issue entirely.

**Useful accelerators:** SIO interpolators (INTERP0/INTERP1) are designed for phase-accumulate and LUT-index workloads. SIO hardware divider is 8 cycles for a 32-bit divide.

---

## 2. Pin map (RP2040)

**Reserved by the board:** GPIO0–3 (FPGA SPI config), GPIO4 (LED), GPIO12 (PWR), GPIO13 (EN), GPIO14–15 (wired to FPGA).
**Usable:** GPIO5–11 and GPIO16–29 — 21 pins. 19 assigned below (GPIO8 and GPIO27 added for Stage 9).

| Pin | Function | Peripheral | Note |
|---|---|---|---|
| **GPIO16–23** | DAC data D0–D7 | PIO SM0 parallel out | **Must be contiguous** — PIO writes a pin group from a base |
| **GPIO24** | Latch clock | PIO **side-set** | Side-set guarantees the clock edge aligns with the data write in the same instruction |
| **GPIO25** | TX-enable / scope trigger | GPIO | Asserted before the burst |
| **GPIO6 / GPIO7** | I²C SDA / SCL | I2C1 | ADS1115 + INA219 share the bus |
| **GPIO5** | 1-Wire | PIO or bit-bang | DS18B20 |
| **GPIO9 / 10 / 11** | SPI CS / SCK / MOSI | SPI1 | MCP41010 |
| **GPIO8** | '574 /OE (output enable) | GPIO | Stage 9: HIGH turns the ladder off between pings (was tied to GND) |
| **GPIO27** | Turbidity power switch | GPIO | Stage 9: drives the 2N2222 base through 1 kΩ |
| GPIO26, 28, 29 | Spare (3) | — | ADC-capable. GPIO26 doubles as the Stage 2 loopback probe input |

**14-bit upgrade path:** would use GPIO16–29 for data, pushing all seven auxiliary functions into GPIO5–11 — exactly seven pins for seven functions, leaving 1-Wire homeless. Fix by swapping the DS18B20 for an I²C temperature sensor on the existing bus, or moving latch clock and trigger to FPGA GPIOs.

---

## 3. Output stage

### 74HC574 — octal D-type flip-flop, tri-state, DIP-20

Latches all 8 DAC bits on one clock edge. Without it, GPIO skew means the ladder briefly sees invalid codes during transitions — going 127→128, if the MSB lands first you momentarily output 255. Full-scale glitches, twice per cycle, smearing spurs across the FFT.

| | |
|---|---|
| **Supply** | **3.3 V — not 5 V.** At 5 V, VIH ≈ 0.7 × VDD = 3.5 V, and the RP2040 only outputs 3.3 V. At 3.3 V the threshold is ~2.3 V |
| **Pinout** (verify against datasheet) | 1 = OE̅ · 2–9 = D0–D7 · 10 = GND · 11 = CP (clock) · 12–19 = Q7–Q0 · 20 = VCC |
| **Layout note** | Outputs run Q7 at pin 12 through Q0 at pin 19, so a left-to-right ladder sits alongside the chip in physical pin order |
| **Power trick** | OE̅ is tri-state — tie it to a spare GPIO and disable outputs between pulses; the ladder then draws no static current when idle |
| **Concern** | HC at 3.3 V has output impedance on the order of 100 Ω, which adds to each 2 kΩ ladder arm (~5% error) and dominates linearity. A 74LVC574 (~10–25 Ω) would be better if sourced later. Mitigate with a calibration LUT |

Decoupling: 0.1 µF between pin 20 and pin 10, physically close.

### R-2R ladder — 25 × 1 kΩ

**This is the DAC.** There is no DAC chip.

- Topology: 7 × R in series between 8 nodes; 9 × 2R (one per bit plus one terminating to ground)
- **2R is made from two 1 kΩ in series**, so everything uses one value — parts from one reel match each other far better than their ±1% spec implies, and series pairs average their errors
- **Why 1 kΩ:** at 10 MS/s the sample period is 100 ns. 10 kΩ against ~20 pF stray gives a 200 ns RC — samples smear. 1 kΩ gives ~20 ns
- **Matching target:** 8-bit LSB = 0.39%, so you want better than ~0.2% matching for monotonicity. But see the note above — driver impedance likely dominates, so don't over-invest here
- Add **~33 Ω series damping resistors** on the eight lines between latch and ladder to tame ringing

### TSH82IDT — dual op-amp, SOIC-8

| | |
|---|---|
| **Bandwidth** | 100 MHz |
| **Slew rate** | **118 V/µs** — against a 15.7 V/µs minimum for 500 kHz at 5 Vpk. ~7.5× margin |
| **Output** | Rail-to-rail |
| **Supply** | **4.5 V to 12 V — will not run on 3.3 V.** Run the analog section from 5 V (VBUS) |
| **Package** | SOIC-8 → mount on a SOP8→DIP8 adapter, seat in a DIP-8 socket |
| **Stock** | Vendor limited to 1 qty — **no spare.** Practise SOIC technique on a blank adapter first |

Used for: the active element of the 3rd-order low-pass, and buffering the ladder's ~1 kΩ output impedance so it can drive a cable.

**Mid-rail bias:** two 10 kΩ from 5 V to ground, 0.1 µF from the midpoint to ground. That 2.5 V point is what the signal swings around on a single supply.

### Reconstruction filter

3rd-order low-pass, corner ~700 kHz. Roughly 1 kΩ with 220 pF per section.

At 10 MS/s the first image is at 9.5 MHz: 3rd-order gives ~68 dB there, plus ~25 dB from the DAC's zero-order-hold sinc = ~93 dB combined. **C0G/NP0 dielectric in the signal path** — X7R's capacitance shifts with applied voltage, making it nonlinear and generating distortion straight into the graded FFT. At 100–470 pF, through-hole ceramics are generally NP0 anyway, but verify the two or three that carry signal.

### MCP41010 — digital potentiometer, SOIC-8

10 kΩ, 256 taps, SPI, 2.7–5.5 V. **Amplitude is controlled in analog.** Digital scaling would cost resolution: at 25% amplitude an 8-bit DAC is effectively 6-bit. Vendor limited to 1 qty; no spare.

**Runs at 3.3 V, wired as an attenuator** *between* the filter and op-amp B (PA0 = filtered signal, PB0 = GND, PW0 → 0.1 µF AC-coupling → op-amp B input, re-biased to 2.5 V). Changed on 25 Sep 2026 from the original "pot sets op-amp gain" design. Why (Microchip DS11195C):
- Logic-high threshold is 0.7 × VDD. At 5 V that's 3.5 V, which the RP2040's 3.3 V SPI can't reliably reach. At 3.3 V it's 2.3 V.
- The pot's terminals can't carry signal outside 0…VDD. In op-amp B's feedback path the signal swings toward 5 V, which would force VDD = 5 V and break SPI. Before op-amp B, the signal never exceeds 3.3 V.
- The rejected alternative (keep gain topology at 5 V, add an SPI level shifter) costs an extra part for no benefit.

Pinout (SOIC-8): 1 CS̅, 2 SCK, 3 SI, 4 VSS, 5 PA0, 6 PW0, 7 PB0, 8 VDD. SPI1: CS̅ ← GPIO9, SCK ← GPIO10, SI ← GPIO11.

**Two effects to account for, not surprises to discover:**
- **Bandwidth ~1 MHz at mid-scale (code 80h), and it varies with wiper position.** The top of the 100–500 kHz band will droop somewhat. Measure the response at 100/200/350/500 kHz for 2–3 wiper settings in Stage 6 and fold it into the Sim-0 prediction.
- **Firmware caps the wiper at ~75%** until the TSH82's input common-mode range at 5 V is checked (op-amp B's input swings 2.5 V ± up to 1.65 V at full wiper).

Full wiring: `docs/wiring-stages-3-6.md`.

---

## 4. Sensors and instrumentation

### ADS1115 — 16-bit ADC module

4 channels, I²C, programmable gain amplifier, 2.0–5.5 V, ~150 µA. Used because the RP2040's internal ADC is noisy and nonlinear enough that readings visibly jitter — which makes a working adaptation loop *look* broken on stage.

Channel allocation: A0 turbidity (via divider), A1 depth pot, A2 TDS/salinity, A3 spare.

### ASAIR AZDM01 — turbidity sensor

| | |
|---|---|
| **Supply** | **5 V**, 30 mA max |
| **Range** | 0–1000 NTU |
| **Source** | 940 nm infrared |
| **Output** | Analog, ~3.8–4.75 V at 0 NTU, **falling as turbidity rises — inverted** |
| **⚠️ Required** | **10 kΩ / 10 kΩ divider** before any 3.3 V ADC input. Its output exceeds the 3.3 V rail |
| **Power note** | At 150 mW this is the single largest consumer in the system — duty-cycle it |

### DS18B20 waterproof probe, 1 m

1-Wire digital, so it consumes **no ADC channel**. **Requires a 4.7 kΩ pull-up** from data to 3.3 V or it won't respond at all (reads −127 °C). Note: the cheaper non-"original chip" variant was purchased; clone failure modes are intermittent CRC errors and out-of-spec accuracy. If it misbehaves, swap rather than debug.

### DFRobot SEN0244 — analog TDS (salinity) — *not yet confirmed ordered*

3.3–5.5 V supply, **0–2.3 V output so no divider needed**. Range 0–1000 ppm. Honest limitation: real seawater is ~35,000 ppm, so it saturates there — but for demonstrating that adaptation *responds* to salinity (tap water ~200 ppm, add salt, watch it climb) it works perfectly. ₹1,229.

### INA219 — current/power monitor

I²C, bidirectional. Turns the low-power claim into a number on screen. Paired with the **0.1 Ω 5 W shunt** for energy-per-ping measurement: average power hides what matters in a *pulsed* transmitter, and the spec says pulse duration controls total energy output, so energy-per-ping is the measurement that proves that claim.

### 10 kΩ potentiometer

Depth simulation. Explicitly permitted — the spec allows "analog voltage dials acting as sensor inputs." Label it with the spec's own wording.

### 2N2222 NPN — *not yet confirmed ordered*

Low-side switch for duty-cycling the turbidity sensor. 600 mA rating against a 30 mA load.

```
sensor VCC ──── 5V            (stays connected)
sensor GND ──── collector
                emitter ───── GND
GPIO ──[1kΩ]─── base
```

Firmware caveat: with low-side switching the sensor's output floats when off, so **only sample while powered**, allowing ~100 ms to settle.

---

## 5. Power budget

Estimates, but the shape is what matters.

| Block | Draw | Note |
|---|---|---|
| Turbidity sensor | **~150 mW** (30 mA @ 5 V) | Largest single consumer |
| RP2040 | ~100 mW | |
| TSH82IDT | ~50 mW | High-speed op-amps aren't cheap on current |
| ForgeFPGA | ~33 mW | |
| TDS sensor | ~25 mW | |
| R-2R ladder | ~15 mW | **Static** whenever the latch drives it |
| 74HC574 switching | ~13 mW | |
| ADS1115 + INA219 + digipot + DS18B20 | ~10 mW total | Negligible |
| **Total** | **~400 mW** | |

**Key finding: compute is only ~130 mW of that.** The spec's concern — that the processing unit not drain the battery computing trig — is already answered by the DMA-streamed architecture. Sensors and the analog stage dominate.

**Three optimisations, all demo-able:**
1. **Tri-state the '574 between pulses** — free, uses the OE̅ pin on a part you already have, and zeroes the ladder's static draw
2. **Duty-cycle the turbidity sensor** via the 2N2222 — cuts its average by >90%
3. **Check the TSH82 datasheet for a shutdown pin** — shut it down between pulses if it has one

Show INA219 readings before and after. That converts Demand #12 from an assertion into a measured optimisation.

---

## 6. Purchase record

| Part | Qty | ₹ | Source |
|---|---|---|---|
| SOP8→DIP8 adapter, pack of 5 | 5 | 29 | Robu |
| 74HC574 DIP-20 | 1 | 47 | Robu |
| MCP41010-I/SN SOIC-8 | 1 | 289 | Robu |
| ADS1115 module | 1 | 139 | Robu |
| INA219 module | 1 | 125 | Robu |
| 0.1 Ω 5 W sense resistor | 1 | 25 | Robu |
| BNC female 50 Ω right-angle PCB | 1 | 296 | Robu |
| Turbidity sensor AZDM01 | 1 | 489 | Robu |
| Ceramic cap kit 2 pF–0.1 µF | 1 | 160 | Robu |
| 10 kΩ pot module | 1 | 77 | Robu |
| TSH82IDT | 1 | 182 | Robu |
| DS18B20 waterproof probe 1 m | 1 | 51 | Robu |
| 600 pc metal film resistor kit | 1 | 174 | Robu |
| 1 kΩ metal film | 30 | — | earlier order |

**Owned:** Shrike Lite, ESP32 (unused), power bank.

**Outstanding — see STATE.md:** proto board (QuartzComponents 6×8 cm), DIP-20 + DIP-8 sockets, 2N2222, SEN0244 TDS sensor, logic analyser, and all soldering tools.

### Upgrade ladder (later, not now)

| Step | Change | Cost |
|---|---|---|
| Now | 8-bit R-2R at 10 MS/s | ₹2–3k total |
| Better fidelity | AD9708 module (8-bit, 125 MS/s) — same parallel bus, same PIO pattern | +₹1.5–3k |
| Production | AD9744 (14-bit) — widen bus to 14 lines | +₹2–3k |
| Acoustics | HV driver + transducers + housing — a new subsystem | +₹3–10k |

Firmware survives every step.
