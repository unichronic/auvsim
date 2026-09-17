# Pre-Silicon Bench — SIH26058 transmitter chain

AUV project simulator and pre-silicon verification bench.

Laptop verification of the whole transmitter chain before any part is ordered.
Companion to the **Pre-Silicon Bench** artifact.

**Not the deliverable.** SIH26058 requires a physical hardware unit; this is
preparation, and the predicted-vs-measured overlay is evidence you understood
your system, never a substitute for building it.

## Run it

```bash
python3 run_all.py      # every runnable stage, then the gate check
```

or individually:

```bash
python3 run_sim0.py     # golden reference + C tables      (no extra tools)
python3 sim1_diff.py    # bit-exact firmware diff          (gcc)
python3 run_sim2.py     # R-2R Monte Carlo + filter        (no extra tools, ~90 s)
python3 run_sim4.py     # predicted spectrogram            (no extra tools)
python3 run_sim5.py     # absorption + adaptation table    (no extra tools)
python3 gate_check.py   # the 8 go/no-go gates
python3 sim2_spice_check.py  # ngspice vs the nodal solve, 256 codes
python3 sim3_check.py        # gateware diff vs SIM-0
```

The reusable ForgeFPGA baseline project is [`ForgeFpgaDDS.ffpga`](ForgeFpgaDDS.ffpga),
with the Shrike wrapper and pin map documented in
[`sim3_gateware/FORGEFPGA.md`](sim3_gateware/FORGEFPGA.md). It is the vendor-tool
input for the first Gate 6 synthesis pass; it does not replace the required
ForgeFPGA resource report or prove that the LUT array mapped to dedicated BRAM.

## Use the interactive signal lab

The original bench validates one fixed transmitter chain. The local GUI adds
the experiment loop: up to four configurable sensor channels with distinct
default behaviors (tone, up-chirp, burst, and dropout), recorded CSV/TXT trace
import, explicit water/environment controls, a selectable frequency algorithm,
an explicit software-plugin handoff, and a separate hardware circuit model.
The patch bay keeps the simulated netlist visible:

```text
sensor inputs → algorithm → 32-bit DDS → 8-bit R-2R → reconstruction filter → output probe
```

The board is draggable; sensor blocks can be moved with a mouse or keyboard.
The hardware plane exposes clock, phase-accumulator, DAC, reference, filter,
and resistor-tolerance specs. The software plane lets you open the source file
you want to check, edit it in the browser, select a test scenario, and report
whether the adapter contract passed alongside the output frequency, voltage,
FTW, coherence, and waveforms.

The environment plane exposes temperature, salinity, depth, pH, source range,
and ambient noise. For modeled channels, those values affect sound speed,
frequency-dependent Ainslie-McColl absorption, propagation phase delay, and the
noise floor before estimation. Uploaded traces are not re-shaped: they are
treated as measurements that already include the conditions of their capture.
These are propagation-level preview controls, not calibrated transfer
functions for the project's final sensor hardware.

The four defaults are deliberately generic fixtures, not a claim that the
repository already contains the exact three project sensor models. To make the
bench project-accurate, map each real sensor's model number/datasheet to a
channel-specific response, sensitivity, bandwidth, and calibration file.

```bash
python3 launch_gui.py
# open http://127.0.0.1:8765
```

The GUI is dependency-free. `launch_gui.py` serves it locally; the same static
frontend and simulation are Vercel-ready through `vercel.json` and `api/`.
The sensor models are deterministic and reproducible; a recorded trace is
resampled at the configured simulation clock. The software editor is a safe
contract check: it does not execute arbitrary pasted code. A plugin must
contain the configured entrypoint (normally `on_measurement`) and call
`bench_set_algorithm(...)` or `bench_set_algorithm_from_config(...)`. The
selected algorithm then drives the hardware model. This is the integration
seam for the real product plugin; provide its SDK/API when it is ready to
replace the contract check with an actual compiler/runtime adapter.

## Deploy for team use

Vercel is the supported hosted path. Import this repository into Vercel or run
`vercel` from the repository root. The platform serves the `gui/` assets and
maps `/api/simulate` and `/api/status` to the Python Functions in `api/`.
No runtime dependencies are required. `launch_gui.py` remains the local path.

Hosted runs are independent per browser: the current layout is stored in
`localStorage`, not in a shared database. The hosted API receives the submitted
sensor, hardware, connection, and plugin-contract payload for each run. Add
authentication and persistent storage before putting sensitive code or shared
project state behind a public URL. Netlify can serve the static GUI, but the
current Python API needs a separate service or a JavaScript/TypeScript port.

It does not replace ForgeFPGA synthesis, the existing RTL/SPICE stages, or a
physical sensor/analog test. Those remain separate verification steps, while
the GUI gives you a repeatable whole-system test bench before those tools run.

## Design parameters

Everything lives in `params.py`. 8-bit R-2R ladder at 10 MS/s, 100–500 kHz
acoustic band, first image at 9.5 MHz, 3rd-order reconstruction filter at
700 kHz, Renesas SLG47910 (1120 LUTs, 32 kb BRAM, 50 MHz osc + PLL).

## Stage map

| stage | what it does | tools |
|---|---|---|
| `sim0_reference.py` | integer-exact golden reference (phase accumulator, LUT, Q15 window) | numpy/scipy |
| `sim1_firmware/` + `sim1_diff.py` | the real RP2040 routine compiled for x86, diffed byte-for-byte | gcc |
| `sim2_r2r.py` | R-2R Monte Carlo by exact nodal analysis | numpy |
| `sim2_filter.py` | reconstruction filter, slew and GBW headroom | scipy |
| `sim2_spice/` + `sim2_spice_check.py` | SPICE netlists — independent cross-check | ngspice ✅ |
| `sim3_gateware/` + `sim3_check.py` | DDS RTL with quarter-wave LUT | iverilog ✅ |
| `run_sim4.py` | chained prediction: codes → ladder → ZOH → filter → FFT | numpy/scipy |
| `sim5_propagation.py` | Ainslie-McColl + François-Garrison absorption | numpy |

## Things this exercise actually found

1. **A 4096×8 sine LUT is exactly 100% of the SLG47910's BRAM** (32768 of
   32768 bits), not "ample". Quarter-wave symmetry (1025×8 = 25%) is required,
   not an optimisation.

2. **Quarter-wave symmetry needs an explicit +1 correction on the negative
   half.** The table is `round(127.5 + 127.5·sin)`, and `floor(-x) ≠ -floor(x)`,
   so naive negation is one LSB high across all 2047 negative-half entries —
   even-order distortion. Encoded in `dds.v`, verified over all 4096 addresses.

3. **Never window a phase-coded pulse.** Barker-13's −22.3 dB autocorrelation
   depends on equal-amplitude chips; tapering destroys it (−21.8 dB rect →
   −3.8 dB Blackman). Windowing helps the chirps and ruins the code.

4. **1% resistors are genuinely not good enough**: 13.4% of Monte Carlo draws
   are non-monotonic and SFDR degrades 10.7 dB worst case, landing at −49 dBc
   against a −48 dBc target. 0.1% gives 0% non-monotonic and 1.8 dB.

5. **Filter section order matters, and an op-amp macromodel can lie.** The
   first netlist draft put the passive RC pole *before* the Sallen-Key, which
   loads it: the corner fell to 449 kHz and 500 kHz droop was 3.6 dB instead
   of 0.5 dB. Moving the RC after the op-amp output fixed it. Separately, the
   placeholder op-amp had `Cp=39.8p`, giving GBW = 2e12 Hz — an ideal part
   that would have hidden every bandwidth problem the stage exists to find.
   Correct value for 20 MHz GBW with A0=1e5 and Rp=200 is `Cp=3.98u`.

6. **Down-chirps are where fixed-point bugs hide.** C's `/` truncates toward
   zero, Python's `//` floors; they agree only while the numerator is
   non-negative. An up-chirp passes either way, a down-chirp does not —
   `sim1_diff.py` carries a `lfm_down` case specifically to catch it.

## Toolchain

`iverilog` 13.0 and `ngspice` 47 are built from source into `~/.local`
(already on PATH via `.bashrc`). The disk was full, so they were **built in
`/dev/shm`** — a 7.7 GB tmpfs — and only the ~50 MB of final binaries landed
on disk. `gperf` was built first; iverilog's git tarball needs it to generate
its keyword lexer. No conda env and no user data deleted.

To rebuild: `gperf` → `iverilog` (run `sh autoconf.sh` first) → `ngspice`
(`./autogen.sh`, `--without-x --enable-xspice`), each `--prefix=$HOME/.local`.

## Cross-validation

Numbers confirmed by independent routes, which is the point of the structure:

- filter image rejection: −68.0 dB analytic vs 69.0 dB measured through the
  full SIM-4 time-domain chain
- 350 kHz SFDR: −60.2 dBc (SIM-0) vs −59.8 dBc (SIM-2 ideal ladder)
- absorption: Ainslie-McColl vs François-Garrison agree within 7% over 1–900 kHz
- ideal R-2R nodal solve reproduces V(255) = VREF·255/256 to 1e-14 LSB
- **ngspice agrees with the Python nodal solve to 6.9e-14 LSB across all 256
  codes** — the Monte Carlo behind the 0.1% resistor decision is confirmed by
  an independent circuit simulator
- **the Verilog DDS matches SIM-0 byte-for-byte over 8192 samples** in real
  RTL simulation, confirming the quarter-wave LUT and its +1 correction
- retuned filter netlist: −0.40 dB at 500 kHz and −69.3 dB at 9.5 MHz in
  ngspice, against −0.54 dB and −68.0 dB analytic

## Status

7 of 8 gates pass; all six stages run. Gate 6 remains partial for one reason
only: the BRAM question is answered and the RTL now passes real iverilog
simulation against SIM-0, but **LUT count needs a ForgeFPGA Workshop synthesis
run** — a proprietary GUI tool that cannot be scripted. Everything else,
including both independent cross-checks, is green.
