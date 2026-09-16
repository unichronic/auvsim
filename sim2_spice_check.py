"""
SIM-2 cross-check: ngspice vs the Python nodal solve.

sim2_r2r.py claims the R-2R ladder's DC transfer curve is an exact linear
solve.  This drives the same topology through a real circuit simulator for
every one of the 256 codes and diffs the result.  If the two disagree, the
Monte Carlo that justified the 0.1% resistors is not trustworthy.

Requires ngspice on PATH.
"""
import re, shutil, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
import params as P
import sim2_r2r as s2

NETLIST = """* R-2R ladder, code {code}
.param R=10k
{sources}
Rs0 b0 n0 {{2*R}}
Rs1 b1 n1 {{2*R}}
Rs2 b2 n2 {{2*R}}
Rs3 b3 n3 {{2*R}}
Rs4 b4 n4 {{2*R}}
Rs5 b5 n5 {{2*R}}
Rs6 b6 n6 {{2*R}}
Rs7 b7 n7 {{2*R}}
Rl0 n0 n1 {{R}}
Rl1 n1 n2 {{R}}
Rl2 n2 n3 {{R}}
Rl3 n3 n4 {{R}}
Rl4 n4 n5 {{R}}
Rl5 n5 n6 {{R}}
Rl6 n6 n7 {{R}}
Rt  n0 0  {{2*R}}
.control
set numdgt=12
op
print v(n7)
.endc
.end
"""

def run_code(code, workdir):
    src = "\n".join(f"Vb{i} b{i} 0 DC {P.VREF if (code >> i) & 1 else 0.0}"
                    for i in range(8))
    f = Path(workdir) / f"c{code}.cir"
    f.write_text(NETLIST.format(code=code, sources=src))
    r = subprocess.run(["ngspice", "-b", str(f)], capture_output=True, text=True)
    m = re.search(r"v\(n7\)\s*=\s*([-+0-9.eE]+)", r.stdout)
    if not m:
        raise RuntimeError(f"could not parse ngspice output for code {code}:\n{r.stdout[-500:]}")
    return float(m.group(1))

def main(n_codes=256):
    if not shutil.which("ngspice"):
        print("ngspice not installed -- SIM-2 SPICE cross-check cannot run.")
        return 2
    ideal = s2.transfer_curve(np.full(7, 10e3), np.full(8, 20e3), 20e3)
    codes = np.linspace(0, 255, n_codes).astype(int) if n_codes < 256 else np.arange(256)
    with tempfile.TemporaryDirectory() as wd:
        got = np.array([run_code(int(c), wd) for c in codes])
    exp = ideal[codes]
    err = np.abs(got - exp)
    lsb = (ideal[-1] - ideal[0]) / 255.0
    print(f"codes checked        : {len(codes)}")
    print(f"max |ngspice-python| : {err.max():.3e} V  ({err.max()/lsb:.2e} LSB)")
    print(f"V(255) ngspice       : {got[-1]:.9f} V")
    print(f"V(255) python        : {exp[-1]:.9f} V")
    # Tolerance is set by ngspice's print precision, not by any physical
    # disagreement: at the default numdgt it reports ~7 significant figures,
    # which alone is 4e-5 LSB.  1e-3 LSB is still three orders of magnitude
    # tighter than the 0.1% resistor spread this model is used to judge.
    ok = err.max() / lsb < 1e-3
    print("PASS -- SPICE confirms the nodal solve" if ok else "FAIL -- models disagree")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 256))
