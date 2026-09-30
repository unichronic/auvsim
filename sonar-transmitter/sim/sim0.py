"""Sim-0 core: the golden reference model of the SIH26058 transmitter.

Signal chain modelled (numbers from COMPONENTS.md / CONTEXT.md §4):

    float waveform x[n] in [-1, 1]          (modulation x window)
      -> 8-bit unsigned code, mid-scale 128 (what PIO+DMA puts on GPIO16-23)
      -> R-2R ladder: V = VREF * code / 256  (ideal; nonlinearity only in the
                                              synthetic "measured" data)
      -> zero-order hold at FS              (the '574 latch holds each code)
      -> 3rd-order low-pass, fc ~700 kHz    (reconstruction filter)

Amplitude is NOT modelled digitally: every table is full-scale (+/-127 codes),
because amplitude is set in analog by the MCP41010 (a settled design decision).
"""
import numpy as np
from scipy import signal

# ---- constants taken from the docs -------------------------------------------
FS = 10e6              # target sample rate (BUILD_GUIDE: "PIO + DMA ... <=10 MS/s")
FS_FALLBACK = 5e6      # documented graceful fallback
BITS = 8
MID = 128              # idle / zero code
AMP = 127              # full-scale swing: codes 1..255, symmetric about 128
VREF = 3.3             # ladder driven from the 3.3 V '574
BAND = (100e3, 500e3)
FILTER_FC = 700e3      # "3rd-order low-pass, corner ~700 kHz"
FILTER_ORDER = 3
EQUAL_R, EQUAL_C = 1e3, 220e-12   # "Roughly 1 kOhm with 220 pF per section"
UPSAMPLE = 16          # analog-model grid = FS * 16 = 160 MS/s

# ---- defaults chosen here (listed as assumptions in README) -----------------
PULSE_T = 500e-6       # 500 us -> 5000 samples at 10 MS/s
BARKER13 = np.array([1, 1, 1, 1, 1, -1, -1, 1, 1, -1, 1, -1, 1])
BARKER_FC = 250e3      # 40 samples/cycle at 10 MS/s, 20 at 5 MS/s
BARKER_CYCLES_PER_CHIP = 8   # chip = 32 us; 13 chips = 416 us
CENTRES = (100e3, 200e3, 350e3, 500e3)  # BUILD_GUIDE demand 13
CENTRE_FRAC_BW = 0.20  # bandwidth = 20 % of centre for the centre-frequency set
WINDOWS = ("rect", "hann", "hamming", "blackman")


# ---- waveform generation ------------------------------------------------------
def n_samples(T, fs):
    return int(round(T * fs))


def lfm(f0, f1, T=PULSE_T, fs=FS):
    t = np.arange(n_samples(T, fs)) / fs
    k = (f1 - f0) / T
    return np.sin(2 * np.pi * (f0 * t + 0.5 * k * t * t))


def geometric(f0, f1, T=PULSE_T, fs=FS):
    """Geometric (exponential) sweep: f(t) = f0 * (f1/f0)^(t/T)."""
    t = np.arange(n_samples(T, fs)) / fs
    L = np.log(f1 / f0)
    return np.sin(2 * np.pi * f0 * T / L * (np.exp(L * t / T) - 1))


def barker(fc=BARKER_FC, cycles_per_chip=BARKER_CYCLES_PER_CHIP, code=BARKER13, fs=FS):
    """BPSK phase-coded pulse. Chips span whole carrier cycles, so every phase
    flip lands on a carrier zero crossing (no voltage step)."""
    Tc = cycles_per_chip / fc
    t = np.arange(n_samples(len(code) * Tc, fs)) / fs
    chip = np.minimum((t / Tc).astype(int), len(code) - 1)
    return code[chip] * np.sin(2 * np.pi * fc * t)


def window(name, N):
    if name == "rect":
        return np.ones(N)
    # symmetric windows: first and last sample are the pulse edges
    return signal.get_window(name, N, fftbins=False)


def quantise(x):
    """Float [-1,1] -> unsigned 8-bit code exactly as firmware must do it:
    code = floor(128 + 127*x + 0.5), clipped to 0..255 (round half up)."""
    return np.clip(np.floor(MID + AMP * np.asarray(x) + 0.5), 0, 255).astype(np.uint8)


def build(mod, win, fs=FS, **kw):
    """Return (float_waveform_windowed, codes, meta) for one table."""
    if mod == "lfm":
        f0, f1, T = kw.get("f0", BAND[0]), kw.get("f1", BAND[1]), kw.get("T", PULSE_T)
        s = lfm(f0, f1, T, fs)
        meta = dict(mod="lfm", f0=f0, f1=f1, T=T)
    elif mod == "geo":
        f0, f1, T = kw.get("f0", BAND[0]), kw.get("f1", BAND[1]), kw.get("T", PULSE_T)
        s = geometric(f0, f1, T, fs)
        meta = dict(mod="geo", f0=f0, f1=f1, T=T)
    elif mod == "barker13":
        fc = kw.get("fc", BARKER_FC)
        cpc = kw.get("cycles_per_chip", BARKER_CYCLES_PER_CHIP)
        s = barker(fc, cpc, BARKER13, fs)
        meta = dict(mod="barker13", fc=fc, cycles_per_chip=cpc, T=len(s) / fs)
    else:
        raise ValueError(mod)
    x = s * window(win, len(s))
    meta.update(window=win, fs=fs, n=len(x))
    return x, quantise(x), meta


def table_registry(fs=FS):
    """Every table the firmware gets, keyed by name. The same registry is what
    `compare` regenerates its prediction from, so they cannot drift apart."""
    reg = {}
    for mod in ("lfm", "geo", "barker13"):
        for w in WINDOWS:
            reg[f"{mod}_{w}"] = build(mod, w, fs)
    for fc in CENTRES:
        bw = CENTRE_FRAC_BW * fc
        reg[f"lfm_c{int(fc / 1e3)}k_hann"] = build("lfm", "hann", fs, f0=fc - bw / 2, f1=fc + bw / 2)
    return reg


# ---- analog model -------------------------------------------------------------
def filter_response(f, kind="butter", fc=FILTER_FC):
    f = np.asarray(f, float)
    if kind == "none":
        return np.ones_like(f, dtype=complex)
    if kind == "butter":
        b, a = signal.butter(FILTER_ORDER, 2 * np.pi * fc, analog=True)
        return signal.freqs(b, a, 2 * np.pi * np.atleast_1d(f))[1].reshape(f.shape)
    if kind == "equal":  # three coincident real poles, 1k/220p each
        fe = 1 / (2 * np.pi * EQUAL_R * EQUAL_C)
        return 1 / (1 + 1j * f / fe) ** 3
    raise ValueError(kind)


def zoh_db(f, fs=FS):
    return 20 * np.log10(np.abs(np.sinc(np.asarray(f) / fs)))


def analog(codes, fs=FS, up=UPSAMPLE, filt="butter", fc=FILTER_FC,
           pre=20e-6, post=60e-6):
    """Ladder output (AC part, volts) after ZOH and filter, on a grid of fs*up.
    `codes` may be float (the unquantised ideal) or uint8."""
    c = np.concatenate([np.full(int(pre * fs), MID, float),
                        np.asarray(codes, float),
                        np.full(int(post * fs), MID, float)])
    y = np.repeat((c - MID) * VREF / 256, up)        # exact zero-order hold
    fa = fs * up
    if filt != "none":
        n = len(y)
        nfft = 1 << int(np.ceil(np.log2(2 * n)))
        Y = np.fft.rfft(y, nfft) * filter_response(np.fft.rfftfreq(nfft, 1 / fa), filt, fc)
        y = np.fft.irfft(Y, nfft)[:n]
    t = np.arange(len(y)) / fa - pre
    return t, y, fa


# ---- spectra & metrics --------------------------------------------------------
def esd_db(x, fs, nfft=None, ref_band=(50e3, 1e6)):
    """Energy spectrum of a whole pulse record, dB relative to its peak inside
    ref_band. Zero-padded, no extra analysis window (the record contains the
    entire pulse, so the pulse's own window is what shapes the spectrum)."""
    x = np.asarray(x, float)
    nfft = nfft or max(1 << 16, 1 << int(np.ceil(np.log2(4 * len(x)))))
    f = np.fft.rfftfreq(nfft, 1 / fs)
    p = np.abs(np.fft.rfft(x, nfft)) ** 2
    m = (f >= ref_band[0]) & (f <= ref_band[1])
    return f, 10 * np.log10(p / p[m].max() + 1e-30)


def sqnr_db(x, codes):
    ideal = AMP * np.asarray(x)
    err = codes.astype(float) - MID - ideal
    return 10 * np.log10(np.sum(ideal ** 2) / np.sum(err ** 2))


def window_psl_db(name, N=4096, nfft=1 << 20):
    """Highest sidelobe of the window's own transform (textbook number)."""
    m = 20 * np.log10(np.abs(np.fft.rfft(window(name, N), nfft)) + 1e-300)
    m -= m[0]
    i = 1
    while not (m[i] < m[i - 1] and m[i] <= m[i + 1]):
        i += 1
    return float(m[i:].max())


MAINLOBE_NULL = {"rect": 1, "hann": 2, "hamming": 2, "blackman": 3}  # x 1/T


def burst_sidelobes(win, codes_or_x, fs, fc, T, span=200e3, floor_band=(1.5e6, 4.5e6)):
    """Peak sidelobe (outside the main lobe, within +/-span of fc) and mean
    far-out floor, both dB relative to the burst's spectral peak.
    Input is the AC signal (codes - MID, or AMP * float waveform)."""
    x = np.asarray(codes_or_x, float)
    f, d = esd_db(x, fs, nfft=1 << 20, ref_band=(fc - 50e3, fc + 50e3))
    edge = 1.05 * MAINLOBE_NULL[win] / T
    off = np.abs(f - fc)
    psl = d[(off > edge) & (off < span)].max()
    fl = (f >= floor_band[0]) & (f <= floor_band[1])
    floor = 10 * np.log10(np.mean(10 ** (d[fl] / 10)))
    return float(psl), float(floor)


def autocorr_pslr_db(x, fs, meta):
    """Matched-filter (autocorrelation) peak sidelobe ratio of the pulse.
    Main lobe ends at the first local minimum of the envelope within 12/B
    (B = swept bandwidth, or chip rate for the phase code). Returns None when
    the envelope decays monotonically (no distinct sidelobe)."""
    x = np.asarray(x, float)
    n = len(x)
    env = np.abs(signal.hilbert(signal.correlate(x, x, method="fft")))[n - 1:]  # lags >= 0
    B = meta["f1"] - meta["f0"] if "f1" in meta else meta["fc"] / meta["cycles_per_chip"]
    lim = min(len(env) - 1, int(12 / B * fs))
    i = next((i for i in range(1, lim) if env[i] < env[i - 1] and env[i] <= env[i + 1]), None)
    if i is None:
        return None
    return float(20 * np.log10(env[i:].max() / env[0]))


def cw_floor(f_tone, fs=FS, N=8192, bits=BITS):
    """Continuous full-scale tone, N-point rectangular FFT (coherent, so no
    leakage). Returns (mean noise per bin dBc, worst spur dBc)."""
    n = np.arange(N)
    x = np.sin(2 * np.pi * f_tone / fs * n)
    c = quantise(x).astype(float) - MID
    p = np.abs(np.fft.rfft(c)) ** 2
    k = int(round(f_tone / fs * N))
    carrier = p[k]
    rest = np.delete(p[1:], k - 1)
    return float(10 * np.log10(rest.mean() / carrier)), float(10 * np.log10(rest.max() / carrier))


def image_levels(codes, fs=FS, filt="butter", up=UPSAMPLE):
    """Worst first-image level (around fs) relative to in-band peak."""
    t, y, fa = analog(codes, fs, up, filt)
    f, d = esd_db(y, fa, nfft=1 << int(np.ceil(np.log2(4 * len(y)))), ref_band=BAND)
    m = (f > fs - 1e6) & (f < fs + 1e6)
    return float(d[m].max())
