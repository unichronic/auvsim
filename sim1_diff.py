"""
SIM-1 -- bit-exact diff: host-compiled firmware C vs the SIM-0 reference.

Passing means the routine that will run on the RP2040 produces byte-identical
output to the golden reference, for every modulation and every window.
The `lfm_down` case is deliberate: a down-chirp drives the tuning-word
interpolation negative, which is where C's truncating division and Python's
flooring division part company.  If floordiv() in waveform.c were written as a
plain `/`, this is the case that would catch it.
"""
import subprocess, sys, pathlib
import numpy as np
import params as P
import sim0_reference as s0

FW = P.ROOT / "sim1_firmware"

CASES = [(m, w) for m in ("lfm", "geom", "bpsk", "lfm_down") for w in P.WINDOWS]

def reference(mode, wname):
    w = s0.make_window(wname, P.N_PULSE)
    if mode == "lfm":      return s0.gen_lfm(P.F_LO, P.F_HI, P.N_PULSE, w)[0]
    if mode == "lfm_down": return s0.gen_lfm(P.F_HI, P.F_LO, P.N_PULSE, w)[0]
    if mode == "geom":     return s0.gen_geom(P.F_LO, P.F_HI, P.N_PULSE, w)[0]
    if mode == "bpsk":     return s0.gen_bpsk(200e3, P.N_PULSE, w)[0]
    raise ValueError(mode)

def main():
    subprocess.run(["make", "-s"], cwd=FW, check=True)
    fails = 0
    print(f"{'mode':<10}{'window':<10}{'result':<12}{'detail'}")
    print("-" * 60)
    for mode, wname in CASES:
        binf = FW / f"{mode}_{wname}.bin"
        subprocess.run([str(FW / "wfgen"), mode, wname, str(binf)], check=True)
        got = np.fromfile(binf, dtype=np.uint8)
        exp = reference(mode, wname)
        if got.shape != exp.shape:
            print(f"{mode:<10}{wname:<10}{'FAIL':<12}length {got.shape} vs {exp.shape}")
            fails += 1; continue
        bad = np.flatnonzero(got != exp)
        if bad.size == 0:
            print(f"{mode:<10}{wname:<10}{'PASS':<12}{len(got)} bytes identical")
        else:
            i = bad[0]
            print(f"{mode:<10}{wname:<10}{'FAIL':<12}{bad.size} bytes differ; "
                  f"first at {i}: fw={got[i]} ref={exp[i]}")
            fails += 1
        binf.unlink(missing_ok=True)
    print("-" * 60)
    print(f"{len(CASES)-fails}/{len(CASES)} cases byte-identical")
    return 1 if fails else 0

if __name__ == "__main__":
    sys.exit(main())
