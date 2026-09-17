"""Run every stage in dependency order, then the gate check."""
import subprocess, sys, shutil
STAGES = [("run_sim0.py", "golden reference + C tables"),
          ("sim1_diff.py", "bit-exact firmware diff"),
          ("run_sim2.py",  "R-2R Monte Carlo + filter"),
          ("run_sim4.py",  "chained predicted spectrogram"),
          ("run_sim5.py",  "absorption + adaptation table"),
          ("sim6_scenarios.py", "PS scenarios + adaptive sonar preview")]
OPTIONAL = [("sim2_spice_check.py", "ngspice", "SPICE cross-check of the nodal solve"),
            ("sim3_check.py",       "iverilog", "gateware vs SIM-0")]
def main():
    for script, desc in STAGES:
        print(f"==> {script:<20} {desc}")
        if subprocess.run([sys.executable, script]).returncode:
            print("    FAILED"); return 1
    for script, tool, desc in OPTIONAL:
        if shutil.which(tool):
            print(f"==> {script:<20} {desc}")
            subprocess.run([sys.executable, script])
        else:
            print(f"==> {script:<20} SKIPPED ({tool} not on PATH)")
    print("\n==> gate_check.py")
    return subprocess.run([sys.executable, "gate_check.py"]).returncode
if __name__ == "__main__":
    sys.exit(main())
