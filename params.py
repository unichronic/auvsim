"""
Single source of truth for the SIH26058 transmitter design parameters.

Every simulation stage imports from here. If a number is wrong, it is wrong
in exactly one place. Values trace to the Pre-Silicon Bench spec:
8-bit R-2R DAC clocked at 10 MS/s, 100-500 kHz acoustic passband,
3rd-order reconstruction filter, image at fs - f_max = 9.5 MHz.
"""
import numpy as np

# ---- DAC / sampling ---------------------------------------------------
FS          = 10e6        # DAC update rate [S/s]
DAC_BITS    = 8           # R-2R ladder width
DAC_LEVELS  = 1 << DAC_BITS
VREF        = 3.3         # ladder reference / full-scale [V]

# ---- Acoustic band ----------------------------------------------------
F_LO        = 100e3       # bottom of passband [Hz]
F_HI        = 500e3       # top of passband [Hz]
F_IMAGE     = FS - F_HI   # first image to suppress = 9.5 MHz

# Spot frequencies the predicted spectrogram is reported at (Sim-4)
F_TEST      = np.array([100e3, 200e3, 350e3, 500e3])

# ---- Pulse ------------------------------------------------------------
T_PULSE     = 1e-3        # 1 ms transmit pulse
N_PULSE     = int(round(T_PULSE * FS))   # 10_000 samples

# ---- Phase accumulator (must match firmware + gateware exactly) -------
PHASE_BITS  = 32          # accumulator width
LUT_BITS    = 12          # 4096-entry sine LUT  -> top 12 bits address it
LUT_SIZE    = 1 << LUT_BITS
PHASE_SCALE = 1 << PHASE_BITS

def ftw(f_hz, fs=FS):
    """Frequency tuning word: the integer the accumulator adds per sample."""
    return int(round(f_hz / fs * PHASE_SCALE)) & (PHASE_SCALE - 1)

# ---- Barker-13 (phase-coded mode) -------------------------------------
BARKER13 = np.array([1,1,1,1,1,-1,-1,1,1,-1,1,-1,1], dtype=np.int8)

# ---- Windows ----------------------------------------------------------
WINDOWS = ("rect", "hamming", "hann", "blackman")

# ---- Expected figures of merit ---------------------------------------
# Ideal SNR for an N-bit quantiser: 6.02 N + 1.76 dB
SNR_IDEAL_DB   = 6.02 * DAC_BITS + 1.76      # 49.9 dB for 8 bits
SPUR_FLOOR_DBC = -48.0                        # spec target from the bench doc

# ---- Analog frontend --------------------------------------------------
FILTER_ORDER   = 3
FILTER_FC      = 700e3     # reconstruction filter corner [Hz]
OPAMP_GBW_MIN  = 20e6      # minimum acceptable gain-bandwidth [Hz]
OPAMP_SR_MIN   = 20.0      # minimum slew rate [V/us]
R_TOL_CANDIDATES = (0.001, 0.01)   # 0.1% vs 1% -- the Sim-2 decision

# ---- FPGA target (Renesas SLG47910 / ForgeFPGA) -----------------------
FPGA_LUTS      = 1120
FPGA_BRAM_BITS = 32 * 1024
FPGA_OSC_HZ    = 50e6

# ---- Paths ------------------------------------------------------------
import pathlib
ROOT = pathlib.Path(__file__).resolve().parent
OUT  = ROOT / "out"
OUT.mkdir(exist_ok=True)
