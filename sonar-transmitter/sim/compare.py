"""Overlay a measured scope/analyser export on the Sim-0 prediction.

    python compare.py MEASURED.csv --waveform lfm_hann

Accepts either
  * time,voltage   (oscilloscope capture of one or more whole pulses), or
  * frequency,dB   (spectrum-analyser / scope-FFT export; Hz in column 1).
Rigol-style exports (index column + "Start,Increment" header) are handled too.
"""
import argparse
import os
import re

import numpy as np

import sim0
from plot import C, INK2, band, legend_below, plt, save


def load_csv(path):
    """Return (kind, col1, col2, synthetic). kind is 'time', 'spectrum' or None."""
    rows, header, start_inc, synthetic = [], "", None, False
    with open(path, errors="replace") as fh:
        lines = fh.readlines()
    for i, line in enumerate(lines):
        if "SYNTHETIC" in line.upper():
            synthetic = True
        fields = [p for p in re.split(r"[,;\t ]+", line.strip()) if p]
        try:
            rows.append((float(fields[0]), float(fields[1])))
            continue
        except (ValueError, IndexError):
            pass
        if not rows and not line.lstrip().startswith("#"):
            header += " " + line.lower()
            low = [p.lower() for p in fields]
            if "start" in low and "increment" in low and i + 1 < len(lines):  # Rigol
                nxt = re.split(r"[,;\t ]+", lines[i + 1].strip())
                try:
                    start_inc = (float(nxt[low.index("start")]), float(nxt[low.index("increment")]))
                except (ValueError, IndexError):
                    pass
    a = np.array(rows, float)
    if len(a) < 16:
        raise SystemExit(f"{path}: fewer than 16 numeric rows found")
    x, y = a[:, 0], a[:, 1]
    if start_inc:
        x = start_inc[0] + np.arange(len(x)) * start_inc[1]
        return "time", x, y, synthetic
    kind = None
    if re.search(r"freq|hz", header):
        kind = "spectrum"
    elif re.search(r"time|second|\bs\b|volt", header):
        kind = "time"
    return kind, x, y, synthetic


def _fit_offset(f_meas, d_meas, f_pred, d_pred, thresh=-20.0):
    """dB shift that best lays measured onto predicted where the prediction is
    within `thresh` dB of its peak (i.e. over the occupied band)."""
    p = np.interp(f_meas, f_pred, d_pred)
    m = (p > thresh) & (f_meas > 20e3)
    off = np.mean(p[m] - d_meas[m])
    rms = np.sqrt(np.mean((d_meas[m] + off - p[m]) ** 2))
    return off, rms, m


def _smooth_rbw(f, d, rbw):
    if not rbw:
        return d
    df = f[1] - f[0]
    k = max(1, int(round(rbw / df)))
    lin = np.convolve(10 ** (d / 10), np.ones(k) / k, mode="same")
    return 10 * np.log10(lin / lin.max() + 1e-30) + d.max()


def compare(path, waveform="lfm_hann", fs=sim0.FS, filt="butter", kind="auto",
            rbw=None, out=None, label=None, xmax=1.5e6):
    reg = sim0.table_registry(fs)
    if waveform not in reg:
        raise SystemExit(f"unknown waveform {waveform}; choose from: {', '.join(reg)}")
    x_f, codes, meta = reg[waveform]
    k, c1, c2, synthetic = load_csv(path)
    if kind == "auto":
        kind = k or ("time" if np.nanmax(np.abs(c1)) < 1.0 else "spectrum")
    stem = os.path.splitext(os.path.basename(path))[0]
    out = out or os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
    os.makedirs(out, exist_ok=True)
    mlabel = label or ("SYNTHETIC 'measured' (pipeline test)" if synthetic else "Measured")

    t_p, y_p, fa = sim0.analog(codes, fs, filt=filt)
    f_p, d_p = sim0.esd_db(y_p, fa, nfft=1 << 20, ref_band=(50e3, 1e6))
    res = dict(file=path, waveform=waveform, kind=kind, synthetic=synthetic)

    if kind == "time":
        t_m, v_m = c1, c2
        fs_m = 1 / np.median(np.diff(t_m))
        v_m = v_m - np.median(v_m)                       # idle baseline
        # predicted on the measured sample grid, then find delay by x-correlation
        tp_grid = np.arange(t_p[0], t_p[-1], 1 / fs_m)
        yp_m = np.interp(tp_grid, t_p, y_p)
        n = 1 << int(np.ceil(np.log2(len(v_m) + len(yp_m))))
        xc = np.fft.irfft(np.fft.rfft(v_m, n) * np.conj(np.fft.rfft(yp_m, n)), n)
        lag = int(np.argmax(np.abs(xc)))
        lag = lag - n if lag > n // 2 else lag
        delay = t_m[0] + lag / fs_m - tp_grid[0]      # measured time of predicted t=0
        pred_on_m = np.interp(t_m - delay, t_p, y_p, left=0, right=0)
        gain = np.dot(pred_on_m, v_m) / np.dot(pred_on_m, pred_on_m)
        pred_on_m *= gain
        corr = np.corrcoef(pred_on_m, v_m)[0, 1]
        f_m, d_m = sim0.esd_db(v_m, fs_m, nfft=1 << int(np.ceil(np.log2(8 * len(v_m)))),
                               ref_band=(50e3, 1e6))
        res.update(fs_measured=fs_m, delay_s=delay, gain_v_per_v=gain, time_corr=corr)
    else:
        f_m, d_m = c1, c2 - np.max(c2[(c1 >= 50e3) & (c1 <= 1e6)])
        d_p = _smooth_rbw(f_p, d_p, rbw)

    off, rms, m = _fit_offset(f_m, d_m, f_p, d_p)
    d_m = d_m + off
    res.update(offset_db=off, inband_rms_error_db=rms)

    # ---- figure ----
    title_tag = "  [SYNTHETIC DATA — NOT A MEASUREMENT]" if synthetic else ""
    if kind == "time":
        fig, ax = plt.subplots(2, 2, figsize=(13, 8))
        a = ax[0, 0]
        a.plot((t_m - delay) * 1e6, v_m, color=C[1], lw=0.8, label=mlabel)
        a.plot((t_m - delay) * 1e6, pred_on_m, color=C[0], lw=0.8, alpha=0.85, label="Sim-0 prediction")
        a.set_xlim(-10, meta["T"] * 1e6 + 20)
        a.set(xlabel="Time from pulse start (µs)", ylabel="Output, AC-coupled (V)",
              title=f"Time domain, aligned (r = {corr:.4f})")
        legend_below(a)
        a = ax[0, 1]
        mid = meta["T"] / 2 * 1e6
        a.plot((t_m - delay) * 1e6, v_m, color=C[1], marker=".", ms=3, lw=0.8, label=mlabel)
        a.plot((t_m - delay) * 1e6, pred_on_m, color=C[0], lw=1.2, label="Sim-0 prediction")
        a.set_xlim(mid - 5, mid + 5)
        a.set(xlabel="Time from pulse start (µs)", ylabel="V", title="Zoom: 10 µs at pulse centre")
        legend_below(a)
        axs = ax[1]
    else:
        fig, axs = plt.subplots(1, 2, figsize=(13, 4.6))
    for a, xm, ttl in ((axs[0], xmax, "Spectrum, operating region"),
                       (axs[1], min(f_m.max(), 30e6), "Spectrum, wide (images near k·fs)")):
        sel_p, sel_m = f_p <= xm, f_m <= xm
        band(a, 1e3 if xm <= 3e6 else 1e6)
        u = 1e3 if xm <= 3e6 else 1e6
        a.plot(f_m[sel_m] / u, d_m[sel_m], color=C[1], lw=0.9, label=mlabel)
        a.plot(f_p[sel_p] / u, d_p[sel_p], color=C[0], lw=1.1, label="Sim-0 prediction")
        a.set(xlabel=f"Frequency ({'kHz' if u == 1e3 else 'MHz'})",
              ylabel="Energy spectral density (dB rel. in-band peak)", title=ttl, ylim=(-120, 5))
        a.legend(loc="upper right")
    axs[0].text(0.02, 0.04, f"in-band RMS difference: {rms:.2f} dB\n(level fit offset {off:+.1f} dB)",
                transform=axs[0].transAxes, fontsize=9, color=INK2)
    fig.suptitle(f"Predicted vs measured — {waveform}  (fs = {fs / 1e6:g} MS/s, "
                 f"{filt} filter){title_tag}", fontweight="bold")
    fig.tight_layout()
    png = os.path.join(out, f"compare_{stem}.png")
    save(fig, png)

    csv = os.path.join(out, f"compare_{stem}.csv")
    sel = f_m <= min(f_m.max(), 30e6)
    step = max(1, sel.sum() // 20000)
    np.savetxt(csv, np.column_stack([f_m[sel][::step], np.interp(f_m[sel][::step], f_p, d_p),
                                     d_m[sel][::step]]),
               delimiter=",", fmt="%.6g", header=("SYNTHETIC input. " if synthetic else "")
               + "frequency_hz,predicted_db,measured_db_aligned", comments="# ")
    print("  wrote", csv)
    res.update(png=png, csv=csv)
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--waveform", default="lfm_hann", help="table name, e.g. lfm_hann, geo_rect, barker13_hann, lfm_c350k_hann")
    ap.add_argument("--fs", type=float, default=sim0.FS, help="DAC sample rate the firmware ran at (Hz)")
    ap.add_argument("--filter", default="butter", choices=["butter", "equal", "none"],
                    help="filter model: butter (design intent), equal (1k/220p x3 real poles), none (raw ladder)")
    ap.add_argument("--kind", default="auto", choices=["auto", "time", "spectrum"])
    ap.add_argument("--rbw", type=float, help="analyser RBW in Hz (spectrum input only): smooths the prediction to match")
    ap.add_argument("--label", help="legend label for the measured trace")
    ap.add_argument("--xmax", type=float, default=1.5e6, help="upper frequency of the operating-region panel (Hz)")
    ap.add_argument("--out", help="output directory (default sim/sim0/out)")
    a = ap.parse_args()
    r = compare(a.csv, a.waveform, a.fs, a.filter, a.kind, a.rbw, a.out, a.label, a.xmax)
    for k, v in r.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
