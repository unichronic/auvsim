# ForgeFPGA starting project

`ForgeFpgaDDS.ffpga` is generated from the open Shrike/SLG47910 project
generator and is intended to be opened directly in Go Configure Software Hub.
It reuses the board's clock, GPIO18 reset input, oscillator-enable, and eight
GPIO output conventions. The source list points at `shrike_dds_top.v` and the
existing byte-exact `dds.v`.

The wrapper fixes the test tone at 100 kHz and emits an update enable every
five 50-MHz oscillator cycles, matching the bench's 10-MS/s model. It is a
baseline synthesis project, not yet the final MCU-controlled interface or the
final BRAM-backed implementation.

## Run

1. Open `ForgeFpgaDDS.ffpga` in Go Configure Software Hub.
2. Synthesize and generate the bitstream.
3. Open the Resources Report and Timing Analysis windows.
4. Record LUTs, FFs, pins, BRAM usage, fit status, and timing at 50 MHz.
5. Record whether `qlut` became LUT/distributed memory or dedicated BRAM. A
   plain Verilog memory array is not proof that the external ForgeFPGA BRAM is
   used; the device requires dedicated BRAM ports and BRAM-block connections.

The LUT file is referenced as `sim3_gateware/qlut.hex` when the project is
opened from the repository root. If the GUI changes its working directory,
set the `LUT_FILE` parameter to the corresponding project-relative path.

## Rebuild the project XML

The generator and pin database are from
[`trholding/shrike-gen`](https://github.com/trholding/shrike-gen):

```bash
python3 /path/to/shrike-gen/shrike_gen/gen_ffpga.py \
  --project ForgeFpgaDDS \
  --sources sim3_gateware/shrike_dds_top.v sim3_gateware/dds.v \
  --pcf sim3_gateware/shrike_dds.pcf \
  --max-cpu 1 \
  --out ForgeFpgaDDS.ffpga
```

The board examples and BRAM wiring reference are in
[`vicharak-in/shrike`](https://github.com/vicharak-in/shrike), especially the
[`shrike_picorv32` project](https://github.com/vicharak-in/shrike/tree/main/examples/shrike_picorv32).
For BRAM behavior, use Renesas' [AN-FG-011 FIFO using BRAM](https://www.renesas.com/en/document/apn/fg-011-fifo-using-bram)
as the device-level reference.

If the baseline maps the LUT into logic or exceeds 1,120 LUTs, the next
implementation should reuse the explicit BRAM ports from the Shrike
`shrike_picorv32` project or Renesas AN-FG-011, and load the table from the
MCU at startup (or use a ForgeFPGA-supported BRAM initialization path).

This scaffold intentionally does not claim Gate 6 is passed: the vendor
resource, BRAM mapping, and timing reports are still the evidence required by
the gate.
