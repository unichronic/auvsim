"""
SIM-2b -- reconstruction filter and op-amp headroom.

Answers three questions the parts order depends on:
  1. is the passband flat across 100-500 kHz?
  2. is the 9.5 MHz image suppressed?
  3. does a >=20 MHz op-amp hold 500 kHz at full amplitude without slewing?
"""
import numpy as np
from scipy import signal
import params as P

def filter_response(freqs, order=P.FILTER_ORDER, fc=P.FILTER_FC):
    """Analogue Butterworth magnitude response [dB]."""
    b, a = signal.butter(order, 2 * np.pi * fc, btype="low", analog=True)
    _, h = signal.freqs(b, a, worN=2 * np.pi * np.asarray(freqs))
    return 20 * np.log10(np.abs(h))

def slew_required(f_hz, vpp=P.VREF):
    """Peak slew rate of a full-scale sine [V/us]."""
    return 2 * np.pi * f_hz * (vpp / 2.0) / 1e6

def gbw_required(fc=P.FILTER_FC, order=P.FILTER_ORDER, margin=20.0):
    """Rule of thumb: each active stage wants GBW >= margin * f_c * Q.
    Q of the complex pole pair in a 3rd-order Butterworth is 1.0."""
    q_max = 1.0
    return margin * fc * q_max

def analyse():
    band = np.linspace(P.F_LO, P.F_HI, 400)
    resp = filter_response(band)
    zoh = 20 * np.log10(np.abs(np.sinc(band / P.FS)))
    total = resp + zoh
    img = float(filter_response(np.array([P.F_IMAGE]))[0])
    sr_needed = slew_required(P.F_HI)
    return {
        "filter": {"order": P.FILTER_ORDER, "fc_kHz": P.FILTER_FC / 1e3},
        "passband_ripple_db":      round(float(resp.max() - resp.min()), 3),
        "passband_droop_at_500k_db": round(float(resp[-1]), 3),
        "with_zoh_ripple_db":      round(float(total.max() - total.min()), 3),
        "image_attenuation_db":    round(img, 1),
        "image_freq_MHz":          P.F_IMAGE / 1e6,
        "slew_required_V_per_us":  round(float(sr_needed), 2),
        "slew_available_V_per_us": P.OPAMP_SR_MIN,
        "slew_margin_x":           round(float(P.OPAMP_SR_MIN / sr_needed), 2),
        "gbw_required_MHz":        round(gbw_required() / 1e6, 1),
        "gbw_available_MHz":       P.OPAMP_GBW_MIN / 1e6,
        "gbw_ok":                  bool(P.OPAMP_GBW_MIN >= gbw_required()),
    }
