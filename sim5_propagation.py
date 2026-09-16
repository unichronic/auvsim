"""
SIM-5 -- underwater absorption and the frequency-adaptation table.

The bench doc calls the adaptation mapping the project's weakest claim: right
now it is a heuristic, and that is what a judge will probe.  Modelled loss
curves turn each row into a derived number.

Two independent absorption models are implemented -- Ainslie & McColl (1998)
and Francois & Garrison (1982).  F-G is what NPL's online calculator serves,
so agreement between the two is a genuine cross-check of the implementation
rather than a restatement of it.  Absorption and geometric spreading are kept
separate in the reasoning throughout.

Bellhop/arlpy would add multipath structure on top of this; the absorption
term is what actually sets the frequency-vs-range trade, and it needs no
Fortran toolchain.
"""
import numpy as np

def sound_speed(T, S, D):
    """Mackenzie-style linear fit used inside Francois-Garrison. D in metres."""
    return 1412.0 + 3.21 * T + 1.19 * S + 0.0167 * D

def alpha_ainslie_mccoll(f_khz, T=15.0, S=35.0, pH=8.0, z_km=0.01):
    """Absorption [dB/km].  Ainslie & McColl, JASA 103(3) 1998, eq. 3."""
    f = np.asarray(f_khz, dtype=float)
    f1 = 0.78 * np.sqrt(S / 35.0) * np.exp(T / 26.0)      # boric acid relax [kHz]
    f2 = 42.0 * np.exp(T / 17.0)                          # MgSO4 relax     [kHz]
    boric = 0.106 * (f1 * f**2) / (f1**2 + f**2) * np.exp((pH - 8.0) / 0.56)
    mgso4 = (0.52 * (1 + T / 43.0) * (S / 35.0)
             * (f2 * f**2) / (f2**2 + f**2) * np.exp(-z_km / 6.0))
    water = 0.00049 * f**2 * np.exp(-(T / 27.0 + z_km / 17.0))
    return boric + mgso4 + water

def alpha_francois_garrison(f_khz, T=15.0, S=35.0, pH=8.0, D_m=10.0):
    """Absorption [dB/km].  Francois & Garrison, JASA 72(6) 1982 -- the model
    behind NPL's published calculator."""
    f = np.asarray(f_khz, dtype=float)
    c = sound_speed(T, S, D_m)
    # boric acid
    A1 = 8.86 / c * 10 ** (0.78 * pH - 5.0)
    f1 = 2.8 * np.sqrt(S / 35.0) * 10 ** (4.0 - 1245.0 / (T + 273.0))
    b1 = A1 * f1 * f**2 / (f1**2 + f**2)
    # magnesium sulphate
    A2 = 21.44 * (S / c) * (1.0 + 0.025 * T)
    P2 = 1.0 - 1.37e-4 * D_m + 6.2e-9 * D_m**2
    f2 = 8.17 * 10 ** (8.0 - 1990.0 / (T + 273.0)) / (1.0 + 0.0018 * (S - 35.0))
    b2 = A2 * P2 * f2 * f**2 / (f2**2 + f**2)
    # pure water viscosity
    if T <= 20.0:
        A3 = 4.937e-4 - 2.59e-5*T + 9.11e-7*T**2 - 1.50e-8*T**3
    else:
        A3 = 3.964e-4 - 1.146e-5*T + 1.45e-7*T**2 - 6.50e-10*T**3
    P3 = 1.0 - 3.83e-5 * D_m + 4.9e-10 * D_m**2
    b3 = A3 * P3 * f**2
    return b1 + b2 + b3

def two_way_loss(f_khz, range_m, **kw):
    """Two-way transmission loss [dB]: spherical spreading + absorption.
    Returns (total, spreading, absorption) so the two are never conflated."""
    r_km = range_m / 1000.0
    spreading = 40.0 * np.log10(np.maximum(range_m, 1e-6))   # 2 x 20log10(r)
    absorption = 2.0 * alpha_ainslie_mccoll(f_khz, **kw) * r_km
    return spreading + absorption, spreading, absorption

def max_range(f_khz, budget_db, T=15.0, S=35.0, pH=8.0, z_km=0.01):
    """Largest range whose two-way loss fits the budget. Bisection; monotonic."""
    lo, hi = 0.1, 20000.0
    a = alpha_ainslie_mccoll(f_khz, T=T, S=S, pH=pH, z_km=z_km)
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        tl = 40.0 * np.log10(mid) + 2.0 * a * mid / 1000.0
        if tl < budget_db: lo = mid
        else: hi = mid
    return lo

def range_resolution(bandwidth_hz, c=1500.0):
    """Pulse-compressed range resolution [m] = c / (2B)."""
    return c / (2.0 * bandwidth_hz)
