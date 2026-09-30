# Adaptive Sonar Transmitter Payload

A low-power, real-time adaptive software-defined sonar transmitter for autonomous underwater
vehicles (AUVs) — built for Smart India Hackathon problem statement **SIH26058**
(Ministry of Earth Sciences / National Institute of Ocean Technology).

## The problem

AUV side-scan sonar performance is set by the physical characteristics of the transmitted
"ping." A high-frequency chirp (~500 kHz) gives sharp images but scatters instantly in muddy
or deep water; a low-frequency chirp (~100 kHz) penetrates murky water and travels far but
yields a blurry image. Sound also behaves differently with depth, turbidity, temperature and
salinity. For an AUV to map effectively without draining its battery, the transmitter needs to
behave like a software-defined radio — reshaping its analog pulse waveform in real time based
on what the water is actually doing.

## Architecture

A single RP2040 + FPGA board (Vicharak Shrike Lite) reads four real sensors — temperature,
turbidity, salinity, and battery/power state — plus one potentiometer standing in for depth
(a judging-table bench cannot reproduce real hydrostatic pressure, and using a dial for that
one variable is explicitly permitted). An adaptation loop picks centre frequency, bandwidth,
pulse duration, amplitude, and one of three modulation types (LFM chirp, geometric sweep,
Barker-13 phase-coded pulse) every transmitted pulse.

```
Sensors → Adaptation logic (RP2040) → sample buffer (SRAM) → PIO + DMA
   → 74HC574 latch → 8-bit R-2R ladder DAC → 3rd-order active filter
   → analog amplitude control (digital pot, ahead of the output stage)
   → op-amp output → BNC → oscilloscope / spectrum analyser
```

Samples stream through the RP2040's PIO and DMA hardware at roughly **10 megasamples per
second with zero CPU cycles spent per sample** — the CPU is free to run the adaptation loop
and telemetry concurrently. The DAC itself is a hand-built 8-bit R-2R resistor ladder, not a
DAC chip: at 10 MS/s it reaches the transmit band the problem statement describes, and it
upgrades cleanly on the same parallel-bus interface if a faster DAC is swapped in later.
Amplitude is controlled **in the analog domain** (a digital potentiometer ahead of the output
op-amp), not by scaling digital sample values — digital scaling costs DAC resolution exactly
when the signal is smallest.

Full component specs, pin map and rationale: [`COMPONENTS.md`](COMPONENTS.md).
Full stage-by-stage wiring diagrams (pictorial, pin-labelled, not abstract schematics):
[`diagrams/`](diagrams/).

## The algorithm, and results

`sim/` is a Python golden-reference simulator that generates the exact 8-bit sample codes the
firmware streams — all three modulation types, all four windows (rectangular, Hann, Hamming,
Blackman), the DAC's zero-order-hold response, and the reconstruction filter — before any
hardware measurement is taken. It emits ready-to-flash firmware tables (with CRC-32 checks)
and can overlay a real oscilloscope/spectrum-analyser capture against its own prediction.

Headline results at the design sample rate (10 MS/s):

| Metric | Result |
|---|---|
| Quantisation SQNR, full-scale sine (theory: 6.02·8+1.76 dB) | 49.9 dB |
| Quantisation SQNR, windowed LFM chirp (Hann / Blackman) | 45.7 / 44.9 dB |
| Blackman window peak sidelobe, after 8-bit quantisation (theory: −58.1 dB) | −57.3 dB |
| Reconstruction filter image rejection at the first DAC image (9.5 MHz) | 93.0 dB combined |
| Digitally-scaled amplitude at 25%, SQNR cost | 37.7 dB (≈6 bits) — confirms analog amplitude control is the right call |

One finding worth calling out: **the Barker-13 phase-coded pulse must use a rectangular
window, not a tapered one.** Applying Hann/Hamming/Blackman to it collapses its matched-filter
peak sidelobe from −22.3 dB to as little as −4.8 dB — windowing helps the chirps, but it
destroys the phase code's own autocorrelation property. This was caught in simulation before
it was ever built.

Full methodology, all figures, and the complete numbers: [`sim/README.md`](sim/README.md).

## What we looked at before deciding this

We researched a broad range of publicly documented approaches to this class of problem before
settling on this architecture. The patterns we found — and how they shaped our decisions —
are summarised without naming specific projects in
[`research/DESIGN_RESEARCH.md`](research/DESIGN_RESEARCH.md).

## Status

The signal-chain architecture, component selection and modulation/windowing algorithm are
finalised and verified in simulation. Hardware bring-up follows a nine-stage, test-gated build
so that a fault is caught at the smallest possible stage rather than debugged blind in a fully
assembled system. `firmware/` contains the stages completed so far:

- **Stage 1** — toolchain and first blink: passed
- **Stage 2** — DAC bus wiring proof (all 8 bus lines verified, correct identity, no bridges): passed
- Stages 3–9 (sensors, the R-2R ladder build, first waveform, filter/amplifier, full
  modulation set, closing the adaptation loop, power optimisation) — in progress

This covers the waveform engine, validated electrically per this round's requirements — no
transducer, water, or acoustic transmission is required or claimed this round. The acoustic
chain attaches at the BNC output, a deliberate module boundary, without requiring any change
upstream of it.

## Repository layout

```
COMPONENTS.md          Full part specs, pin map, power budget
diagrams/               Stage-by-stage pictorial wiring diagrams (source + rendered)
sim/                     Golden-reference simulator, generated tables, figures, results
firmware/                Completed build-stage firmware
research/                Anonymised design-research summary
```

## License

MIT — see [`../LICENSE`](../LICENSE).
