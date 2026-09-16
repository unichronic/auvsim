"""
SIM-4 -- end-to-end predicted spectrogram.

Chains the verified stages: SIM-0 golden codes -> real (tolerance-perturbed)
R-2R transfer curve from SIM-2 -> zero-order hold -> reconstruction filter
-> FFT.  What comes out is a prediction of the exact artifact Module 4 is
graded on, produced with nothing built.

The ZOH is modelled by oversampling: each DAC code is held for OSR samples of
a 160 MS/s grid, which is what puts the images at fs +/- f and gives the
reconstruction filter something real to remove.  A plain FFT of the 10 MS/s
code array would show no images at all and would flatter the design.
"""
import json
import numpy as np
from scipy import signal
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import params as P
import sim2_r2r as s2

OSR  = 16
FS_A = P.FS * OSR                      # 160 MS/s analogue grid

def analog_chain(codes, tol=0.001, seed=3):
    """codes -> ladder -> ZOH -> reconstruction filter.  Returns (t, v)."""
    rng = np.random.default_rng(seed)
    curve = s2.trial(tol, rng)                       # real ladder, 256 levels
    curve = (curve - curve[0]) / (curve[-1] - curve[0])
    v_dac = curve[codes.astype(int)]                 # quantised + mismatched
    v_zoh = np.repeat(v_dac, OSR)                    # zero-order hold
    sos = signal.butter(P.FILTER_ORDER, P.FILTER_FC / (FS_A / 2), output="sos")
    v_out = signal.sosfilt(sos, v_zoh - v_zoh.mean())
    return np.arange(len(v_out)) / FS_A, v_out, v_zoh - v_zoh.mean()

def spec_db(x, nfft=1 << 16):
    w = signal.windows.blackmanharris(min(nfft, len(x)))
    seg = x[:len(w)] * w
    X = np.abs(np.fft.rfft(seg, nfft))
    return np.fft.rfftfreq(nfft, 1 / FS_A), 20 * np.log10(np.maximum(X / X.max(), 1e-14))

def main():
    rep = {"osr": OSR, "analogue_rate_MSps": FS_A / 1e6}

    codes = np.load(P.OUT / "sim0_lfm_hann.npy")
    t, v_out, v_pre = analog_chain(codes)

    f, S_pre = spec_db(v_pre)
    _, S_post = spec_db(v_out)

    def band_peak(S, lo, hi):
        m = (f >= lo) & (f <= hi)
        return float(S[m].max()) if m.any() else float("nan")

    rep["inband_peak_db"]       = round(band_peak(S_post, P.F_LO, P.F_HI), 2)
    rep["image_peak_pre_db"]    = round(band_peak(S_pre,  9.0e6, 10.0e6), 2)
    rep["image_peak_post_db"]   = round(band_peak(S_post, 9.0e6, 10.0e6), 2)
    rep["image_suppression_db"] = round(rep["image_peak_pre_db"] - rep["image_peak_post_db"], 1)

    # ---- spot checks at the four graded frequencies -------------------
    rep["tone_checks"] = {}
    for ft in P.F_TEST:
        import sim0_reference as s0
        w = s0.make_window("rect", 8192)
        tone, _ = s0.gen_bpsk(ft, 8192, w, code=np.array([1], dtype=np.int8))
        _, vt, _ = analog_chain(tone)
        ftq, St = spec_db(vt, nfft=1 << 15)
        pk = int(St.argmax())
        St2 = St.copy(); St2[max(0, pk-8):pk+9] = -300
        rep["tone_checks"][f"{ft/1e3:.0f}kHz"] = {
            "peak_at_kHz": round(float(ftq[pk] / 1e3), 1),
            "sfdr_dbc":    round(float(St2.max()), 1)}

    # ---- plots ---------------------------------------------------------
    fig = plt.figure(figsize=(11, 7.5))
    ax1 = fig.add_subplot(2, 1, 1)
    m = f <= 25e6
    ax1.plot(f[m] / 1e6, S_pre[m],  lw=.8, alpha=.55, label="at DAC pins (ZOH, unfiltered)")
    ax1.plot(f[m] / 1e6, S_post[m], lw=1.0, label="after reconstruction filter")
    ax1.axvspan(P.F_LO/1e6, P.F_HI/1e6, color="tab:green", alpha=.18, label="100-500 kHz band")
    ax1.axvline(P.F_IMAGE/1e6, color="tab:red", ls="--", lw=1, label="9.5 MHz image")
    ax1.set_xlabel("frequency [MHz]"); ax1.set_ylabel("dBc"); ax1.set_ylim(-140, 5)
    ax1.grid(alpha=.3); ax1.legend(fontsize=8)
    ax1.set_title("SIM-4  predicted output spectrum, LFM 100-500 kHz, Hann, 0.1% ladder",
                  fontsize=10, loc="left")

    ax2 = fig.add_subplot(2, 1, 2)
    # Decimate to 2 MS/s BEFORE the STFT.  At the 160 MS/s analogue rate an
    # nperseg of 1024 gives 156 kHz resolution -- the whole 100-500 kHz band is
    # under 3 bins and the chirp ramp smears into a blur.  Nyquist at 2 MS/s is
    # 1 MHz, comfortably above the 500 kHz top of band.
    dec = 80
    v_sg = signal.decimate(v_out, 10, ftype="fir", zero_phase=True)
    v_sg = signal.decimate(v_sg, 8, ftype="fir", zero_phase=True)
    fs_sg = FS_A / dec
    nper = 192
    ff, tt, Sxx = signal.spectrogram(v_sg, fs=fs_sg, nperseg=nper,
                                     noverlap=nper - 8, window="hann",
                                     detrend=False, scaling="spectrum")
    keep = ff <= 700e3
    Sdb = 10 * np.log10(np.maximum(Sxx[keep], 1e-20))
    im = ax2.pcolormesh(tt * 1e3, ff[keep] / 1e3, Sdb - Sdb.max(),
                        shading="gouraud", vmin=-50, vmax=0, cmap="magma")
    ax2.axhline(P.F_LO / 1e3, color="w", ls=":", lw=.8, alpha=.7)
    ax2.axhline(P.F_HI / 1e3, color="w", ls=":", lw=.8, alpha=.7)
    ax2.set_xlabel("time [ms]"); ax2.set_ylabel("frequency [kHz]")
    ax2.set_title(f"PREDICTED SPECTROGRAM ({fs_sg/1e6:.1f} MS/s, {fs_sg/nper/1e3:.1f} kHz bins)"
                  " -- place beside the measured one", fontsize=10, loc="left")
    fig.colorbar(im, ax=ax2, label="dB", pad=.01)
    fig.tight_layout(); fig.savefig(P.OUT / "sim4_predicted.png", dpi=115); plt.close(fig)

    (P.OUT / "sim4_report.json").write_text(json.dumps(rep, indent=2))
    return rep

if __name__ == "__main__":
    r = main()
    print(json.dumps(r, indent=2))
