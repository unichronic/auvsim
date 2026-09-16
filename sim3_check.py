"""SIM-3 check: diff the Verilog DDS output against the SIM-0 reference.
Requires iverilog.  Run: python3 sim3_check.py"""
import subprocess, shutil, sys, pathlib
import numpy as np
import params as P, sim0_reference as s0

GW = P.ROOT / "sim3_gateware"
N, F_TONE = 8192, 100e3

def main():
    if not shutil.which("iverilog"):
        print("iverilog not installed -- SIM-3 cannot run yet.")
        print("  conda install -c conda-forge iverilog     (needs ~1.5 GB free)")
        return 2
    subprocess.run(["iverilog", "-o", "dds_sim", "dds.v", "dds_tb.v"], cwd=GW, check=True)
    subprocess.run(["vvp", "dds_sim", f"+ftw={P.ftw(F_TONE)}"], cwd=GW, check=True)
    got = np.loadtxt(GW / "dds_out.txt", dtype=np.uint8)[:N]
    w = s0.make_window("rect", N)
    exp, _ = s0.gen_bpsk(F_TONE, N, w, code=np.array([1], dtype=np.int8))
    bad = np.flatnonzero(got != exp[:len(got)])
    if bad.size == 0:
        print(f"PASS  gateware matches SIM-0 byte-for-byte over {len(got)} samples")
        return 0
    i = bad[0]
    print(f"FAIL  {bad.size} samples differ; first at {i}: rtl={got[i]} ref={exp[i]}")
    return 1

if __name__ == "__main__":
    sys.exit(main())
