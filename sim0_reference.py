"""
SIM-0  --  Python golden reference.   Source of truth for every other stage.

Deliberate design choice: this does NOT use np.sin() to make the waveform.
It models the *exact integer datapath* the RP2040 firmware and the SLG47910
gateware will run -- 32-bit phase accumulator, 4096-entry 8-bit sine LUT,
Q15 window multiply.  That is what makes SIM-1's bit-exact diff meaningful;
a float reference would only ever prove that two different algorithms
roughly agree.

The LUT and window tables are generated here once and emitted to a C header,
so firmware and reference share literally the same numbers and no libm
rounding difference can creep in.
"""
import numpy as np
from scipy.signal import hilbert
import params as P

# ---------------------------------------------------------------- tables
def make_sine_lut():
    """4096 x 8-bit unsigned sine, DC-centred at 127.5 -> full 0..255 swing."""
    i = np.arange(P.LUT_SIZE)
    x = 127.5 + 127.5 * np.sin(2.0 * np.pi * i / P.LUT_SIZE)
    # floor(x+0.5), NOT np.round -- numpy rounds halves to even, C does not.
    return np.clip(np.floor(x + 0.5), 0, 255).astype(np.uint8)

def make_window(kind, n):
    """Amplitude envelope as unsigned Q15 (0..32768)."""
    k = np.arange(n)
    if kind == "rect":
        w = np.ones(n)
    elif kind == "hamming":
        w = 0.54 - 0.46 * np.cos(2 * np.pi * k / (n - 1))
    elif kind == "hann":
        w = 0.5 - 0.5 * np.cos(2 * np.pi * k / (n - 1))
    elif kind == "blackman":
        w = (0.42 - 0.5 * np.cos(2 * np.pi * k / (n - 1))
                  + 0.08 * np.cos(4 * np.pi * k / (n - 1)))
    else:
        raise ValueError(f"unknown window {kind!r}")
    return np.clip(np.floor(w * 32768.0 + 0.5), 0, 32768).astype(np.uint32)

SINE_LUT = make_sine_lut()
MASK32   = 0xFFFFFFFF

# ------------------------------------------------------- integer datapath
def _emit(phase_seq, win_q15):
    """Common back end: phase -> LUT -> window -> 8-bit DAC code."""
    addr = (phase_seq >> (P.PHASE_BITS - P.LUT_BITS)) & (P.LUT_SIZE - 1)
    raw  = SINE_LUT[addr].astype(np.int64)          # 0..255
    # centre, scale by Q15 window, recentre.  Arithmetic shift, truncating.
    centred = raw - 128
    scaled  = (centred * win_q15.astype(np.int64)) >> 15
    return np.clip(scaled + 128, 0, 255).astype(np.uint8)

def gen_lfm(f0, f1, n, win_q15):
    """Linear FM chirp. ftw ramps linearly; integer divide keeps it exact."""
    k     = np.arange(n, dtype=np.int64)
    tw0, tw1 = P.ftw(f0), P.ftw(f1)
    ftw   = tw0 + (tw1 - tw0) * k // n              # floor division
    phase = np.cumsum(ftw, dtype=np.int64) & MASK32
    phase = np.concatenate(([0], phase[:-1]))       # accumulate *after* output
    return _emit(phase, win_q15), ftw

def gen_geom(f0, f1, n, win_q15):
    """Geometric (log) sweep: ftw_{k+1} = (ftw_k * R) >> 32, R in Q32.
    Deterministic fixed-point recurrence -> replicable verbatim in C."""
    r   = (f1 / f0) ** (1.0 / n)
    R   = int(np.floor(r * (1 << 32) + 0.5))
    ftw = np.empty(n, dtype=np.int64)
    cur = P.ftw(f0)
    for i in range(n):                              # mirrors the firmware loop
        ftw[i] = cur
        cur = (cur * R) >> 32
    phase = np.cumsum(ftw, dtype=np.int64) & MASK32
    phase = np.concatenate(([0], phase[:-1]))
    return _emit(phase, win_q15), ftw

def gen_bpsk(fc, n, win_q15, code=P.BARKER13):
    """Barker-13 BPSK. A -1 chip adds pi == 2^31 to the accumulator phase."""
    k        = np.arange(n, dtype=np.int64)
    chip     = (k * len(code)) // n                 # which chip each sample is in
    inv      = (code[chip] < 0).astype(np.int64) << 31
    tw       = P.ftw(fc)
    phase    = (k * tw) & MASK32
    return _emit((phase + inv) & MASK32, win_q15), np.full(n, tw, dtype=np.int64)

# ------------------------------------------------------------- analysis
def spectrum(samples, fs=P.FS, nfft=None):
    """One-sided spectrum in dBc of an 8-bit DAC code array."""
    x = samples.astype(np.float64) - 128.0
    nfft = nfft or 1 << int(np.ceil(np.log2(len(x))))
    X = np.fft.rfft(x * np.hanning(len(x)), nfft)
    mag = np.abs(X)
    ref = mag.max() or 1.0
    return np.fft.rfftfreq(nfft, 1 / fs), 20 * np.log10(np.maximum(mag / ref, 1e-12))

def peak_sidelobe_db(samples):
    """Peak sidelobe level of the matched-filter (pulse-compressed) response.
    This is the number windowing actually buys you, and what a judge asks about.

    Measured on the *envelope* of the correlation, not the correlation itself:
    a bandpass signal's autocorrelation oscillates at the carrier, so a raw
    local-minimum search exits the mainlobe after one carrier cycle and
    reports nonsense (~-1 dB instead of ~-13 dB).
    """
    x  = samples.astype(np.float64) - 128.0
    ac = np.correlate(x, x, mode="full")
    env = np.abs(hilbert(ac))
    env /= env.max()
    pk = int(env.argmax())
    i = pk
    while i + 1 < len(env) and env[i + 1] <= env[i]:
        i += 1
    j = pk
    while j - 1 >= 0 and env[j - 1] <= env[j]:
        j -= 1
    side = np.concatenate([env[:j + 1], env[i:]])
    return 20 * np.log10(side.max()) if side.size else float("-inf")

def zoh_sinc(freqs, fs=P.FS):
    """Zero-order-hold droop of the DAC, in dB."""
    with np.errstate(divide="ignore", invalid="ignore"):
        s = np.sinc(freqs / fs)
    return 20 * np.log10(np.abs(np.where(s == 0, 1e-12, s)))
