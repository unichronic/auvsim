"""Run SIM-2: R-2R Monte Carlo, spur impact, reconstruction filter, plots."""
import json
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import params as P
import sim2_r2r as s2
import sim2_filter as s2f

def main(trials=2000):
    rep = {}
    for tol in P.R_TOL_CANDIDATES:
        key = f"{tol*100:.1f}%"
        rep[key] = s2.monte_carlo(tol, trials=trials)
        rep[key]["spur"] = s2.spur_impact(tol)
    rep["filter"] = s2f.analyse()

    fig, ax = plt.subplots(1, 3, figsize=(13, 3.9))
    rng = np.random.default_rng(7)
    for tol, col in zip(P.R_TOL_CANDIDATES, ("tab:green", "tab:red")):
        lab = f"{tol*100:.1f}%"
        for i in range(40):
            inl, dnl, _ = s2.inl_dnl(s2.trial(tol, rng))
            ax[0].plot(inl, color=col, alpha=.18, lw=.7)
            ax[1].plot(dnl, color=col, alpha=.18, lw=.7)
        ax[0].plot([], [], color=col, label=lab); ax[1].plot([], [], color=col, label=lab)
    ax[1].axhline(-1, color="k", ls="--", lw=1)
    ax[1].text(5, -1.1, "non-monotonic below here", fontsize=7, va="top")
    ax[0].set_title("INL [LSB]", fontsize=9, loc="left"); ax[0].set_xlabel("code")
    ax[1].set_title("DNL [LSB]", fontsize=9, loc="left"); ax[1].set_xlabel("code")
    for a in ax[:2]: a.grid(alpha=.3); a.legend(fontsize=8)

    f = np.logspace(4, 7.7, 600)
    ax[2].semilogx(f / 1e6, s2f.filter_response(f), lw=1.5)
    ax[2].axvspan(P.F_LO/1e6, P.F_HI/1e6, color="tab:green", alpha=.18)
    ax[2].axvline(P.F_IMAGE/1e6, color="tab:red", ls="--", lw=1)
    ax[2].text(P.F_IMAGE/1e6, -30, f" {rep['filter']['image_attenuation_db']} dB\n @9.5MHz",
               fontsize=7, color="tab:red")
    ax[2].set_title("3rd-order reconstruction filter", fontsize=9, loc="left")
    ax[2].set_xlabel("frequency [MHz]"); ax[2].set_ylabel("dB")
    ax[2].set_ylim(-100, 5); ax[2].grid(which="both", alpha=.3)
    fig.tight_layout(); fig.savefig(P.OUT / "sim2_r2r.png", dpi=110); plt.close(fig)

    (P.OUT / "sim2_r2r_report.json").write_text(json.dumps(rep, indent=2))
    return rep

if __name__ == "__main__":
    r = main()
    for tol in P.R_TOL_CANDIDATES:
        k = f"{tol*100:.1f}%"; d = r[k]
        print(f"{k:>6}: INL p99 {d['inl_lsb_p99']:.3f}  DNL p99 {d['dnl_lsb_p99']:.3f}  "
              f"non-monotonic {d['nonmonotonic_pct']:.1f}%  "
              f"SFDR degrades {d['spur']['degradation_worst_db']:.1f} dB")
    fl = r["filter"]
    print(f"filter: ripple {fl['passband_ripple_db']} dB, image {fl['image_attenuation_db']} dB, "
          f"slew margin {fl['slew_margin_x']}x, GBW ok {fl['gbw_ok']}")
