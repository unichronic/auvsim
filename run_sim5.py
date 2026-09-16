"""Run SIM-5: absorption curves, model cross-check, derived adaptation table."""
import json
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import params as P
import sim5_propagation as s5

COND = dict(T=15.0, S=35.0, pH=8.0)      # temperate coastal, shallow

def main():
    rep = {"conditions": COND}

    # ---- 1. cross-validate the two implementations --------------------
    fchk = np.array([1, 10, 50, 100, 200, 350, 500, 900], dtype=float)
    am = s5.alpha_ainslie_mccoll(fchk, **COND)
    fg = s5.alpha_francois_garrison(fchk, T=COND["T"], S=COND["S"], pH=COND["pH"])
    rep["model_crosscheck"] = {
        f"{f:.0f}kHz": {"ainslie_mccoll": round(float(a), 3),
                        "francois_garrison": round(float(g), 3),
                        "delta_pct": round(float(100 * (a - g) / g), 1)}
        for f, a, g in zip(fchk, am, fg)}
    rep["max_model_disagreement_pct"] = round(float(np.max(np.abs(100*(am-fg)/fg))), 1)

    # ---- 2. calibrate the loss budget against a production system -----
    # EdgeTech 4200: ~500 m range at 100 kHz.  Solve for the two-way budget
    # that reproduces it, then see what the same budget predicts at 900 kHz,
    # where EdgeTech quotes ~75 m.  This is an order-of-magnitude sanity
    # check on the model, not a precision claim: the datasheet figure folds in
    # detection threshold and bottom backscatter that we do not model.
    budget, _, _ = s5.two_way_loss(100.0, 500.0, **COND)
    r900 = s5.max_range(900.0, budget, **COND)
    rep["calibration"] = {
        "anchor": "EdgeTech 4200: 500 m @ 100 kHz",
        "implied_two_way_budget_db": round(float(budget), 1),
        "predicted_range_at_900kHz_m": round(float(r900), 1),
        "datasheet_range_at_900kHz_m": 75.0,
        "note": "same order; datasheet includes threshold/backscatter terms not modelled"}

    # ---- 3. the adaptation table --------------------------------------
    # Our transmitter spans 100-500 kHz.  Each row: what you get if you centre
    # the chirp here and use the bandwidth available below f_c.
    rows = []
    for fc_khz in [100, 150, 200, 250, 300, 350, 400, 450, 500]:
        a = float(s5.alpha_ainslie_mccoll(fc_khz, **COND))
        rng = float(s5.max_range(fc_khz, budget, **COND))
        bw = min(fc_khz * 0.5, 400.0) * 1e3          # usable sweep width [Hz]
        res = s5.range_resolution(bw)
        rows.append({"f_kHz": fc_khz, "alpha_dB_per_km": round(a, 1),
                     "max_range_m": round(rng, 1),
                     "bandwidth_kHz": round(bw / 1e3, 1),
                     "resolution_cm": round(res * 100, 2)})
    rep["adaptation_table"] = rows

    # ---- 4. plots ------------------------------------------------------
    f = np.logspace(0, 3, 400)
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
    ax[0].loglog(f, s5.alpha_ainslie_mccoll(f, **COND), lw=1.6, label="Ainslie-McColl")
    ax[0].loglog(f, s5.alpha_francois_garrison(f, T=COND["T"], S=COND["S"], pH=COND["pH"]),
                 "--", lw=1.2, label="Francois-Garrison")
    ax[0].axvspan(P.F_LO/1e3, P.F_HI/1e3, alpha=.15, color="tab:green", label="our band")
    ax[0].set_xlabel("frequency [kHz]"); ax[0].set_ylabel(r"$\alpha$ [dB/km]")
    ax[0].set_title("Absorption, two independent models", fontsize=10, loc="left")
    ax[0].grid(which="both", alpha=.3); ax[0].legend(fontsize=8)

    rr = np.array([r["max_range_m"] for r in rows])
    ff = np.array([r["f_kHz"] for r in rows])
    cc = np.array([r["resolution_cm"] for r in rows])
    ax2 = ax[1]; ax2.plot(ff, rr, "o-", color="tab:blue", lw=1.6)
    ax2.set_xlabel("centre frequency [kHz]"); ax2.set_ylabel("max range [m]", color="tab:blue")
    ax2.grid(alpha=.3); ax2.set_title("The range/resolution trade", fontsize=10, loc="left")
    ax3 = ax2.twinx(); ax3.plot(ff, cc, "s--", color="tab:red", lw=1.4)
    ax3.set_ylabel("resolution [cm]", color="tab:red")
    fig.tight_layout(); fig.savefig(P.OUT / "sim5_propagation.png", dpi=110); plt.close(fig)

    (P.OUT / "sim5_report.json").write_text(json.dumps(rep, indent=2))
    return rep

if __name__ == "__main__":
    r = main()
    c = r["calibration"]
    print(f"model agreement within {r['max_model_disagreement_pct']}% across 1-900 kHz")
    print(f"implied two-way budget : {c['implied_two_way_budget_db']} dB  (from {c['anchor']})")
    print(f"predicted @900kHz      : {c['predicted_range_at_900kHz_m']} m  vs datasheet {c['datasheet_range_at_900kHz_m']} m")
    print()
    print(f"{'f[kHz]':>7}{'a[dB/km]':>11}{'range[m]':>11}{'BW[kHz]':>10}{'res[cm]':>10}")
    for row in r["adaptation_table"]:
        print(f"{row['f_kHz']:>7}{row['alpha_dB_per_km']:>11}{row['max_range_m']:>11}"
              f"{row['bandwidth_kHz']:>10}{row['resolution_cm']:>10}")
