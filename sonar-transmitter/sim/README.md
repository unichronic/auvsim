# Sim-0: Python golden reference

Sim-0 predicts, bit for bit, what the 8-bit R-2R transmitter should put on the oscilloscope. It does five things:

1. Generates the three modulation types the spec requires: an LFM chirp, a geometric (exponential) sweep, and a phase-coded pulse (Barker-13 BPSK).
2. Applies each window (rectangular, Hann, Hamming, Blackman) and quantises to **unsigned 8-bit codes with mid-scale 128**, which is exactly what PIO+DMA writes to GPIO16–23.
3. Models the latch's **zero-order hold** (ZOH: each code is held flat for one sample period, which gives a sinc roll-off plus images at k·fs ± f) and the **3rd-order ~700 kHz reconstruction filter**.
4. Emits **firmware C headers** holding those exact codes, so the board transmits the same samples that were simulated.
5. Overlays a real scope or analyser export on the prediction (`compare.py`). PLAN.md calls this the single most persuasive submission artifact.

## Commands

Run everything from the repo root. The venv lives at `.venv` and is gitignored.

```bash
# one-time setup (numpy, scipy, matplotlib only)
python3 -m venv .venv && .venv/bin/pip install numpy scipy matplotlib

# regenerate EVERYTHING (tables, metrics, figures, synthetic compare test) — ~15 s
.venv/bin/python sim/sim0/run_all.py

# same thing for the documented 5 MS/s fallback rate (writes to sim/sim0/out/fs5M/)
.venv/bin/python sim/sim0/run_all.py --fs 5e6
```

### Using `compare` once real data exists (Stage 7)

1. Stream one table from `out/firmware/` (for example `SIM0_LFM_HANN`) at the same sample rate, with the MCP41010 at any setting.
2. On the scope, capture **at least one whole pulse plus some idle time either side**. Use ≥ 25 MS/s so the 10 MS/s images are visible too. Export the capture as CSV.
3. Run:

```bash
.venv/bin/python sim/sim0/compare.py path/to/capture.csv --waveform lfm_hann
#   --fs 5e6            if firmware ran at the fallback rate
#   --filter equal      if you built the filter as three equal 1k/220p poles (see findings)
#   --filter none       if you probed the raw ladder before the filter (Stage 6 "before" shot)
#   --kind spectrum --rbw 3000   for a frequency,dB export from an analyser / scope FFT
```

It writes `out/compare_<file>.png` and `out/compare_<file>.csv`, and prints the aligned delay, gain, time-domain correlation and the in-band RMS dB difference.

Accepted inputs:
- `time,voltage` CSVs, including Rigol's `X,CH1,Start,Increment` layout and Siglent-style preambles. Any non-numeric line is skipped.
- `frequency,dB` CSVs, with frequency in Hz.
- Detection is automatic from the header. If it guesses wrong, force it with `--kind`.

How the two traces are lined up:
- **Time data:** the DC baseline is removed. The delay is found by cross-correlating with the prediction, and the gain by least squares. No manual scaling is needed.
- **Spectra:** both are expressed relative to their in-band peak. They are then fitted with a single dB offset over the region where the prediction is within 20 dB of its peak.
- **What to compare:** the in-band shape and the band edges. The out-of-band floor of a real capture is usually set by the **scope's own 8-bit ADC**, not by the DAC (see finding 7).

`--waveform` accepts any table name in `out/firmware/tables_manifest.csv`.

## Outputs (`sim/sim0/out/`)

| File | What it shows / is for |
|---|---|
| `fig1_waveforms.png` | The three modulation types as 8-bit codes with the Hann envelope, plus a 12 µs zoom showing the ZOH stair-steps |
| `fig2_modulation_spectra.png` | Predicted output spectrum of each type (8-bit + ZOH + filter vs unquantised), with the 100–500 kHz band shaded |
| `fig3_spectrograms.png` | Spectrograms: chirps centred at 100/200/350/500 kHz (Demand 13) and all three modulation types |
| `fig4_window_comparison.png` | **Demand 10:** rect vs Hann chirp spectrum, tone-burst sidelobes for all four windows, matched-filter range sidelobes |
| `fig5_quantisation.png` | Is the 8-bit floor below Blackman's −58 dB sidelobes? The CW −86 dB check. SQNR if amplitude were scaled digitally |
| `fig6_zoh_filter.png` | ZOH images out to 3·fs, the sinc envelope, the filter, and passband droop across the band |
| `compare_synthetic_measured_lfm_hann_{time,spectrum}.png/.csv` | Pipeline test of `compare` on **SYNTHETIC** data. Every title is stamped "SYNTHETIC DATA — NOT A MEASUREMENT" |
| `synthetic_measured_lfm_hann_{time,spectrum}.csv` | The synthetic "measurements". Each file's first line says SYNTHETIC. **Never submit these as evidence** |
| `firmware/sim0_{lfm,geo,barker13,lfm_centres}.h` | Firmware tables. 16 tables: {lfm, geo, barker13} × {rect, hann, hamming, blackman}, plus four Hann chirps centred at 100/200/350/500 kHz. Each has a `_LEN` and a `_CRC32` |
| `firmware/tables_manifest.csv` | Name, parameters, length and CRC-32 of every table |
| `metrics.json` | Every number quoted below, machine-readable |

How the synthetic "measured" data is made: the predicted chain plus 0.4 % random R-2R bit-weight error, a filter corner 3 % low (680 kHz), op-amp gain 1.2 with about −62 dBc HD2 and −66 dBc HD3, 2 mV rms noise, and a 50 MS/s 8-bit scope at 0.5 V/div with its trigger 3.7 µs early. `compare` recovers the delay (3.700 µs) and gain (1.201) and gives r = 0.9998.

This test only proves the pipeline works. It says nothing about the hardware, because the synthetic non-idealities were chosen by hand.

### Firmware table contract

- `code = floor(128 + 127·x + 0.5)`, clipped to 0..255, where `x = modulation × window` and x is in [−1, 1]. Rounding is half-up. The codes span 1..255, symmetric about 128.
- The idle level between pulses is **128**.
- The tables are always full scale. Amplitude belongs to the MCP41010 (analog amplitude control is a settled design decision — see the main README).
- Tables are `static const`, so they live in flash. `memcpy` a table into an SRAM buffer before DMA streams it.
- Check the copy against `SIM0_<NAME>_CRC32`, a standard zlib/IEEE CRC-32 over the bytes. A match proves the board streams the golden samples.
- Each header has an `#error` guard if `SIM0_FS_HZ` differs from the rate the tables were generated for.
- If firmware later computes samples on-device (DDS), Sim-1 should diff them against these tables.

## Key numbers (fs = 10 MS/s)

**Quantisation (SQNR: total quantisation noise relative to the waveform's own power)**

| Waveform | SQNR |
|---|---|
| Theory, full-scale sine (6.02·8 + 1.76) | 49.9 dB |
| LFM, rectangular | 49.9 dB |
| LFM, Hann | 45.7 dB |
| LFM, Hamming | 45.8 dB |
| LFM, Blackman | 44.9 dB |
| Barker-13, rectangular | 50.7 dB |
| Digitally scaled sine at 50 / 25 / 12.5 % | 43.6 / 37.7 / 31.8 dB (≈ 7 / 6 / 5 bits) |

**Window sidelobes**

| Window | Textbook peak sidelobe (window alone) | 300 kHz, 500 µs tone burst: ideal → 8-bit | 8-bit floor (mean, 1.5–4.5 MHz) |
|---|---|---|---|
| Rectangular | −13.3 dB | −13.2 → −13.2 dB | −82 dB |
| Hann | −31.5 dB | −31.5 → −31.5 dB | −78 dB |
| Hamming | −42.7 dB | −42.5 → −42.5 dB | −79 dB |
| Blackman | −58.1 dB | −58.1 → **−57.3 dB** | **−77 dB** |

**Chirps and codes (8-bit codes; 600 kHz level relative to the spectral peak)**

| Table | Matched-filter peak sidelobe | Level at 600 kHz | Worst first image after filter |
|---|---|---|---|
| lfm_rect | −13.4 dB | −29.9 dB | −94.0 dB |
| lfm_hann | −46.8 dB | −64.1 dB | −98.2 dB |
| lfm_hamming | −49.7 dB | −48.1 dB | −98.1 dB |
| lfm_blackman | −71.2 dB | −65.3 dB | −98.3 dB |
| geo_rect | −10.7 dB | −30.6 dB | −100.3 dB |
| geo_hann | −67.6 dB | −62.9 dB | −101.4 dB |
| barker13_rect | −22.3 dB | −43.5 dB | −100.4 dB |
| barker13_hann | **−4.8 dB** | −39.9 dB | −100.4 dB |

**ZOH and filter**

| | 10 MS/s | 5 MS/s |
|---|---|---|
| ZOH droop at 100 kHz | −0.0014 dB | −0.0057 dB |
| ZOH droop at 500 kHz | **−0.036 dB** | −0.143 dB |
| First image (fs − 500 kHz) | 9.5 MHz | 4.5 MHz |
| ZOH attenuation at the image (relative to 500 kHz) | 25.6 dB | 19.1 dB |
| 3rd-order Butterworth attenuation at the image | 68.0 dB | 48.5 dB |
| Total image rejection | **93.0 dB** | **67.0 dB** |
| Filter passband at 100 / 200 / 350 / 500 kHz: Butterworth | 0.00 / 0.00 / −0.07 / −0.54 dB | same |
| Filter passband at 100 / 200 / 350 / 500 kHz: three equal 1 kΩ/220 pF poles | −0.25 / −0.96 / −2.74 / **−5.09 dB** | same |

## Checking the docs' claims (reported as found; the sim was not tuned to match)

1. **"8 bits gives roughly a −48 dBc quantisation floor."** Roughly true, but slightly optimistic for what is actually transmitted. A full-scale sine or rectangular chirp gets 49.9 dB. Windowing lowers the waveform's RMS while the quantisation noise stays the same, so the windowed pulses the spec requires come out at **44.9–45.8 dB**. A fair wording is "≈ 45–50 dB SQNR depending on window".

2. **"FFT processing gain (~36 dB for 8192 points) puts the displayed floor near −86 dB."** The arithmetic holds only for a **continuous, non-periodic tone**: the sim gives −86.1 dB per bin. It is the wrong model for this transmitter in two ways:
   - **Pulses:** a pulse does not fill the FFT record. Its floor is set by the pulse's own sample count and bandwidth, not the FFT length. The simulated 8-bit floor relative to the spectral peak is **≈ −61 dB for the full-band Hann chirp** and ≈ −77 dB for a 500 µs Blackman tone burst. Neither is −86 dB.
   - **Tones at exact sample ratios:** the four showcase tones (100/200/350/500 kHz at 10 MS/s) repeat every 100/50/200/20 samples. Their quantisation error is therefore periodic, and it lands on **harmonic spurs at −61/−58/−61/−56 dBc** instead of spreading into a floor. This matters for the Stage 5 stepped-sine test: expect discrete spurs at 1.5, 2.5, 3.5 … MHz for a 500 kHz tone, not a flat floor.

3. **"We can resolve Blackman's −58 dB sidelobes with margin."** **True for tone bursts.** A 500 µs Blackman burst keeps a −57.3 dB peak sidelobe after 8-bit quantisation (ideal: −58.1 dB) on a −77 dB floor, so the margin is about 19 dB. The margin scales with pulse length, roughly 10·log10(N):
   - 100 µs: floor −69.7 dB, peak sidelobe −56.2 dB
   - 20 µs: floor −63.0 dB, peak sidelobe −54.4 dB. The margin is essentially gone

   For **chirps**, the window's −58 dB sidelobe is not the quantity that appears on the FFT. The Blackman chirp's out-of-band spectrum sits on the 8-bit floor (≈ −61 dB); an ideal DAC would put it at −183 dB.

4. **"3rd-order gives ~68 dB at 9.5 MHz, plus ~25 dB from ZOH sinc = ~93 dB" (and 48 + 19 = 67 dB at 5 MS/s).** **Holds exactly** for a 3rd-order Butterworth: 68.0 + 25.6 = 93.0 dB, and 48.5 + 19.1 = 67.0 dB. The simulated worst first image for the windowed chirps is −94 to −101 dB (−73 dB at 5 MS/s). It is better than the tone figure because a window leaves little energy at the 500 kHz band edge.

5. **Caution: "roughly 1 kΩ with 220 pF per section" (COMPONENTS.md).** If this is built literally as three equal RC poles (for example, an equal-component unity-gain Sallen-Key plus an RC), the result is **not** a Butterworth.
   - Image rejection is fine (67.2 dB at 9.5 MHz).
   - But the band droops **−2.7 dB at 350 kHz and −5.1 dB at 500 kHz**. A Butterworth droops only −0.54 dB at 500 kHz.
   - Fix: choose Butterworth component values, or correct per frequency via the MCP41010 gain (the ahoi gain-LUT pattern). `compare --filter equal` models the literal build, so the overlay will show which one was built.

6. **ZOH droop is negligible in band**, as the docs imply: −0.036 dB at 500 kHz at 10 MS/s, and −0.14 dB at 5 MS/s. Filter droop dominates.

7. **Instrument floor.** A typical 8-bit scope at 0.5 V/div adds its own quantisation. In the synthetic test that puts the "measured" out-of-band floor at about −65 dB, above the DAC's own floor. A measured floor that looks worse than predicted is therefore not automatically a DAC fault. Compare in-band shape first.

8. **Settled decision 4 (analog amplitude) is confirmed:** digitally scaling to 25 % drops SQNR from 50.0 to 37.7 dB (≈ 6 bits), matching the docs' "effectively 6-bit".

### Design findings the docs don't mention

- **Don't apply a full-length window to the phase-coded pulse.** Barker-13's matched-filter peak sidelobe is −22.3 dB with a rectangular window, but Hann makes it **−4.8 dB**, Hamming −5.7 dB and Blackman −3.7 dB. The taper suppresses the outer chips and destroys the code. (A chip-level check on 13 Hann-weighted chips confirms it: −5.5 dB.)
  - The rectangular Barker pulse has no voltage jump: every chip is 8 whole carrier cycles, so the pulse edges and every phase flip land on a zero crossing.
  - The phase code is also the spectrally dirtiest of the three types: the abrupt phase flips put −40 to −44 dB at 600 kHz. For Demand 10, show the windowing comparison on the chirps.
- **Hamming leaves an 8 % step at each pulse edge** (the window does not reach zero). Its chirp spectrum at 600 kHz is −48 dB, against −64 dB for Hann. That runs against the spec's stated purpose of windowing, "smooth voltage jumps at pulse edges". Prefer Hann or Blackman.
- **The geometric sweep with a rectangular window has worse range sidelobes than the LFM** (−10.7 vs −13.4 dB), because it lingers at low frequency. It needs a window even more.
- **Sample-clock divider (not modelled).** 10 MS/s from a 133 MHz RP2040 needs a fractional PIO divider (13.3), and fractional division adds jitter spurs. Run the system clock at an integer multiple of the sample rate (for example 120 or 200 MHz) so the sim's ideal clock matches the hardware.

## Assumptions (docs don't specify these; chosen here)

| Assumption | Value | Why |
|---|---|---|
| Sample rate | 10 MS/s (5 MS/s via `--fs`) | Docs' target and fallback |
| Code mapping | `floor(128 + 127·x + 0.5)`, codes 1..255 | Symmetric about an exactly representable idle code 128. ±127 rather than ±127.5 costs 0.03 dB |
| Ladder transfer | V = 3.3 V·code/256, ideal | Non-idealities only in the synthetic data |
| Pulse length | 500 µs (5000 samples) for the sweeps | Mid-range of the 10 ms buffer limit; fits comfortably in SRAM |
| LFM / geometric sweep | 100 → 500 kHz up-sweep | The full band |
| Phase code | Barker-13 BPSK, 250 kHz carrier, 8 cycles/chip (32 µs chips, 416 µs pulse) | Integer samples per cycle at both 10 and 5 MS/s; flips at zero crossings |
| Centre-frequency set | 100/200/350/500 kHz, bandwidth = 20 % of centre, Hann | Demand 13 names the centres. 20 % is a typical side-scan transducer fractional bandwidth. The 500 kHz set reaches 550 kHz |
| Windows | Symmetric scipy windows, full pulse length | Hann/Hamming/Blackman are named by the spec; rect is the baseline |
| Filter | 3rd-order analog Butterworth, fc = 700 kHz (default); "equal" = three real poles at 1/(2π·1k·220p) = 723 kHz | Docs specify order and corner only |
| Analog model grid | 16× oversampled (160 MS/s) | ZOH is exact on this grid. Images above 80 MHz fold back, which does not matter after the filter |
| Spectrum metric | Energy spectrum of the whole pulse, zero-padded, dB relative to the in-band peak | A pulse is a finite-energy signal, so this is independent of FFT length |
| Matched-filter peak sidelobe | Autocorrelation envelope of the 8-bit codes, outside the first null | For geo Hann/Blackman the value is floor-limited (8-bit noise), not a true sidelobe |
| "Floor" | Mean power 1.5–4.5 MHz, relative to the spectral peak | Clear of the band and the first filter roll-off |

Not modelled: R-2R/driver nonlinearity (except in the synthetic data), latch glitches, clock jitter, op-amp slew and distortion, ground bounce. Those are what the measured overlay will reveal.
