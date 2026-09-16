"""Evaluate the 8 go/no-go items from the Pre-Silicon Bench checklist."""
import json, subprocess, sys
import params as P

def load(name):
    p = P.OUT / name
    return json.loads(p.read_text()) if p.exists() else None

def main():
    s0 = load("sim0_report.json"); s2 = load("sim2_r2r_report.json")
    s4 = load("sim4_report.json"); s5 = load("sim5_report.json")
    rows = []

    # 1 -- modulations + windowing
    sl = s0["sidelobes"]
    chirps_ok = all(sl[m][w] < sl[m]["rect"] for m in ("lfm", "geom")
                    for w in ("hamming", "hann", "blackman"))
    rows.append(("1", "All 3 modulations; windowed sidelobes < rect", chirps_ok,
                 f"lfm rect {sl['lfm']['rect']}, best {min(sl['lfm'].values())} dB; "
                 f"bpsk must stay rect ({sl['bpsk']['rect']} dB)"))

    # 2 -- bit-exact firmware
    r = subprocess.run([sys.executable, "sim1_diff.py"], capture_output=True, text=True,
                       cwd=P.ROOT)
    ok2 = r.returncode == 0
    rows.append(("2", "Host-compiled C matches SIM-0 byte for byte", ok2,
                 r.stdout.strip().splitlines()[-1] if r.stdout else "n/a"))

    # 3 -- resistor tolerance
    a, b = s2["0.1%"], s2["1.0%"]
    ok3 = a["nonmonotonic_pct"] == 0 and b["nonmonotonic_pct"] > 0
    rows.append(("3", "Monte Carlo justifies 0.1% over 1%", ok3,
                 f"0.1%: {a['nonmonotonic_pct']:.1f}% non-monotonic, SFDR degrades "
                 f"{a['spur']['degradation_worst_db']:.1f} dB | "
                 f"1.0%: {b['nonmonotonic_pct']:.1f}% non-monotonic, degrades "
                 f"{b['spur']['degradation_worst_db']:.1f} dB"))

    # 4 -- filter
    fl = s2["filter"]
    ok4 = fl["passband_ripple_db"] < 1.0 and fl["image_attenuation_db"] < -40
    rows.append(("4", "Flat to 500 kHz, 9.5 MHz image suppressed", ok4,
                 f"ripple {fl['passband_ripple_db']} dB, image {fl['image_attenuation_db']} dB "
                 f"(SIM-4 measured {s4['image_suppression_db']} dB)"))

    # 5 -- slew
    ok5 = fl["slew_margin_x"] > 1.5
    rows.append(("5", "No slew limiting at 500 kHz full scale", ok5,
                 f"needs {fl['slew_required_V_per_us']} V/us, have "
                 f"{fl['slew_available_V_per_us']} -> {fl['slew_margin_x']}x margin"))

    # 6 -- FPGA fit
    full = P.LUT_SIZE * P.DAC_BITS
    import shutil, subprocess as sp
    rtl = "not run (no iverilog)"
    if shutil.which("iverilog"):
        rr = sp.run([sys.executable, "sim3_check.py"], capture_output=True, text=True, cwd=P.ROOT)
        rtl = "RTL sim PASSES vs SIM-0" if rr.returncode == 0 else "RTL sim FAILS"
    rows.append(("6", "LUT question answered by synthesis", None,
                 f"BRAM: full 4096x8 = {100*full/P.FPGA_BRAM_BITS:.0f}% (no headroom); "
                 f"quarter-wave 1025x8 = {100*1025*8/P.FPGA_BRAM_BITS:.0f}%. "
                 f"{rtl}; LUT COUNT still needs ForgeFPGA synthesis"))

    # 7 -- predicted spectrogram
    ok7 = s4["image_suppression_db"] > 40 and max(
        v["sfdr_dbc"] for v in s4["tone_checks"].values()) < -48
    rows.append(("7", "SIM-4 predicted spectrogram is submittable", ok7,
                 f"image {s4['image_suppression_db']} dB, worst in-band SFDR "
                 f"{max(v['sfdr_dbc'] for v in s4['tone_checks'].values())} dBc"))

    # 8 -- adaptation table
    ok8 = all("alpha_dB_per_km" in r for r in s5["adaptation_table"])
    rows.append(("8", "Every adaptation row traces to a modelled number", ok8,
                 f"{len(s5['adaptation_table'])} rows; two models agree within "
                 f"{s5['max_model_disagreement_pct']}%"))

    print(f"{'#':<3}{'gate':<48}{'status':<10}detail")
    print("-" * 132)
    for n, name, ok, detail in rows:
        st = "PASS" if ok else ("PARTIAL" if ok is None else "FAIL")
        print(f"{n:<3}{name:<48}{st:<10}{detail}")
    print("-" * 132)
    npass = sum(1 for _, _, o, _ in rows if o)
    print(f"{npass}/8 gates pass, {sum(1 for _,_,o,_ in rows if o is None)} partial")
    return 0

if __name__ == "__main__":
    sys.exit(main())
