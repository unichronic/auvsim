"""Small, dependency-free adaptive sonar and water-channel model.

The PS names two demonstration conditions but gives no numeric sensor limits.
The presets below are explicit demo assumptions, not calibration data. The
controller is intentionally implementable on the Shrike-Lite RP2040: a
filtered/median environmental reading selects one of two fixed-point waveform
profiles, with hysteresis at the boundary, while the FPGA only synthesizes the
selected pulse.
"""

from __future__ import annotations

import math
from typing import Any


SCENARIO_PRESETS: dict[str, dict[str, Any]] = {
    "muddy_estuary": {
        "label": "Entering Muddy Estuary",
        "description": "High suspended sediment: favor penetration and link margin over fine range resolution.",
        "environment": {
            "temperature_c": 26.0,
            "salinity_psu": 20.0,
            "depth_m": 12.0,
            "ph": 7.6,
            "range_m": 250.0,
            "ambient_noise_db": 42.0,
            "turbidity_ntu": 250.0,
        },
    },
    "clear_shallow_reef": {
        "label": "Entering Clear Shallow Reef",
        "description": "Low suspended sediment and shallow water: spend margin on a wider, higher-frequency pulse for resolution.",
        "environment": {
            "temperature_c": 24.0,
            "salinity_psu": 35.0,
            "depth_m": 8.0,
            "ph": 8.1,
            "range_m": 120.0,
            "ambient_noise_db": 48.0,
            "turbidity_ntu": 2.0,
        },
    },
}

SUPPORTED_MODULATIONS = ("lfm", "geom", "bpsk")
SUPPORTED_WINDOWS = ("rect", "hamming", "hann", "blackman")

# Existing SIM-5 calibration anchor: two-way loss of the 100 kHz reference at
# 500 m in temperate coastal water. It is a relative detection budget, not a
# claim about a particular transducer or target.
DETECTION_BUDGET_DB = 145.923231493001
REFERENCE_NOISE_DBC = 48.0
Q15_SCALE = 1 << 15


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _number(value: Any, default: float) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    return value if math.isfinite(value) else default


def scenario_environment(scenario: str) -> dict[str, float]:
    preset = SCENARIO_PRESETS.get(str(scenario).strip())
    if not preset:
        raise ValueError(f"unknown sonar scenario: {scenario}")
    return {key: float(value) for key, value in preset["environment"].items()}


def median_of_three(values: list[float] | tuple[float, float, float]) -> float:
    """Return a deterministic median for three noisy ADC channels."""
    if len(values) != 3:
        raise ValueError("median_of_three requires exactly three values")
    return sorted(float(value) for value in values)[1]


def sound_speed_mps(environment: dict[str, float]) -> float:
    return (
        1412.0
        + 3.21 * environment["temperature_c"]
        + 1.19 * environment["salinity_psu"]
        + 0.0167 * environment["depth_m"]
    )


def absorption_db_per_km(frequency_hz: float, environment: dict[str, float]) -> float:
    """Scalar Ainslie-McColl absorption, matching sim5_propagation.py."""
    frequency_khz = max(frequency_hz / 1000.0, 0.001)
    temperature = environment["temperature_c"]
    salinity = environment["salinity_psu"]
    depth_km = environment["depth_m"] / 1000.0
    f1 = 0.78 * math.sqrt(max(salinity, 0.0) / 35.0) * math.exp(temperature / 26.0)
    f2 = 42.0 * math.exp(temperature / 17.0)
    boric = 0.106 * (f1 * frequency_khz**2) / (f1**2 + frequency_khz**2) * math.exp((environment["ph"] - 8.0) / 0.56)
    magnesium = (
        0.52
        * (1.0 + temperature / 43.0)
        * (salinity / 35.0)
        * (f2 * frequency_khz**2) / (f2**2 + frequency_khz**2)
        * math.exp(-depth_km / 6.0)
    )
    water = 0.00049 * frequency_khz**2 * math.exp(-(temperature / 27.0 + depth_km / 17.0))
    return max(0.0, boric + magnesium + water)


def sediment_scattering_db_per_km(frequency_hz: float, environment: dict[str, float]) -> float:
    """A clearly-labelled turbidity heuristic for scenario comparison.

    NTU alone does not identify particle size or concentration, so this is not
    a field-calibrated acoustic law. It makes the PS's stated high-frequency
    muddy-water penalty visible until tank data can replace the coefficient.
    """
    frequency_ratio = max(frequency_hz / 100_000.0, 0.1)
    return 0.02 * max(environment.get("turbidity_ntu", 0.0), 0.0) * frequency_ratio**1.8


def _mud_score(environment: dict[str, float]) -> float:
    return _clamp(
        max(
            max(environment.get("turbidity_ntu", 0.0), 0.0) / 200.0,
            max(environment.get("depth_m", 0.0), 0.0) / 100.0,
            max(environment.get("range_m", 0.0), 0.0) / 500.0,
        ),
        0.0,
        1.0,
    )


def _q15(value: float) -> int:
    return int(math.floor(_clamp(value, 0.0, 1.0) * Q15_SCALE + 0.5))


def adapt_transmit_plan(environment: dict[str, float], previous_class: str | None = None) -> dict[str, Any]:
    """Choose the small waveform profile the RP2040 can select in real time."""
    score_q15 = _q15(_mud_score(environment))
    if previous_class == "muddy_estuary":
        muddy = score_q15 >= _q15(0.45)
    elif previous_class == "clear_shallow_reef":
        muddy = score_q15 >= _q15(0.55)
    else:
        muddy = score_q15 >= _q15(0.50)

    if muddy:
        start_hz, end_hz, duration_ms, amplitude = 100_000.0, 200_000.0, 2.0, 0.95
        classification = "muddy_estuary"
        rationale = "lower band limits sediment scattering and preserves range margin"
    else:
        start_hz, end_hz, duration_ms, amplitude = 300_000.0, 500_000.0, 1.0, 0.75
        classification = "clear_shallow_reef"
        rationale = "wider high-frequency band improves range resolution while margin remains available"

    return {
        "controller": "median-of-three ADC filter → fixed-point lookup → hysteresis",
        "policy": "shrike_lite_environment_lookup",
        "classification": classification,
        "mud_score": round(score_q15 / Q15_SCALE, 4),
        "mud_score_q15": score_q15,
        "modulation": "lfm",
        "window": "hann",
        "start_frequency_hz": start_hz,
        "end_frequency_hz": end_hz,
        "center_frequency_hz": (start_hz + end_hz) / 2.0,
        "bandwidth_hz": end_hz - start_hz,
        "pulse_duration_ms": duration_ms,
        "amplitude": amplitude,
        "rationale": rationale,
        "supported_modulations": list(SUPPORTED_MODULATIONS),
        "supported_windows": list(SUPPORTED_WINDOWS),
    }


def _two_way_loss_db(frequency_hz: float, range_m: float, environment: dict[str, float]) -> dict[str, float]:
    range_m = max(range_m, 1.0)
    range_km = range_m / 1000.0
    spreading = 40.0 * math.log10(range_m)
    absorption = 2.0 * absorption_db_per_km(frequency_hz, environment) * range_km
    scattering = 2.0 * sediment_scattering_db_per_km(frequency_hz, environment) * range_km
    return {
        "total_db": spreading + absorption + scattering,
        "spreading_db": spreading,
        "absorption_db": absorption,
        "scattering_db": scattering,
    }


def _link_margin_db(plan: dict[str, Any], environment: dict[str, float], range_m: float) -> float:
    loss = _two_way_loss_db(plan["center_frequency_hz"], range_m, environment)["total_db"]
    pulse_gain = 10.0 * math.log10(max(plan["bandwidth_hz"] * plan["pulse_duration_ms"] / 1000.0, 1.0))
    transmit_gain = 20.0 * math.log10(max(plan["amplitude"], 1e-6))
    noise_penalty = max(0.0, REFERENCE_NOISE_DBC - environment.get("ambient_noise_db", REFERENCE_NOISE_DBC))
    return DETECTION_BUDGET_DB + pulse_gain + transmit_gain - noise_penalty - loss


def _max_range_m(plan: dict[str, Any], environment: dict[str, float]) -> float:
    if _link_margin_db(plan, environment, 1.0) < 0.0:
        return 0.0
    if _link_margin_db(plan, environment, 20_000.0) >= 0.0:
        return 20_000.0
    low, high = 1.0, 20_000.0
    for _ in range(64):
        middle = (low + high) / 2.0
        if _link_margin_db(plan, environment, middle) >= 0.0:
            low = middle
        else:
            high = middle
    return low


def _window_value(kind: str, fraction: float) -> float:
    if kind == "hamming":
        return 0.54 - 0.46 * math.cos(2.0 * math.pi * fraction)
    if kind == "hann":
        return 0.5 - 0.5 * math.cos(2.0 * math.pi * fraction)
    if kind == "blackman":
        return 0.42 - 0.5 * math.cos(2.0 * math.pi * fraction) + 0.08 * math.cos(4.0 * math.pi * fraction)
    return 1.0


def pulse_preview(plan: dict[str, Any], count: int = 256) -> list[float]:
    """Return a compact normalized preview of the selected transmitted pulse."""
    count = max(2, min(int(count), 512))
    start_hz = float(plan["start_frequency_hz"])
    end_hz = float(plan["end_frequency_hz"])
    duration_s = max(float(plan["pulse_duration_ms"]) / 1000.0, 1e-9)
    sweep_rate = (end_hz - start_hz) / duration_s
    values: list[float] = []
    for index in range(count):
        fraction = index / (count - 1)
        time_s = fraction * duration_s
        cycles = start_hz * time_s + 0.5 * sweep_rate * time_s**2
        envelope = _window_value(str(plan["window"]), fraction)
        values.append(round(float(plan["amplitude"]) * envelope * math.sin(2.0 * math.pi * cycles), 6))
    return values


def evaluate_sonar(plan: dict[str, Any], environment: dict[str, float]) -> dict[str, Any]:
    center_hz = float(plan["center_frequency_hz"])
    loss = _two_way_loss_db(center_hz, environment["range_m"], environment)
    margin = _link_margin_db(plan, environment, environment["range_m"])
    bandwidth = max(float(plan["bandwidth_hz"]), 1.0)
    duration_s = max(float(plan["pulse_duration_ms"]) / 1000.0, 1e-9)
    pulse_gain = 10.0 * math.log10(max(bandwidth * duration_s, 1.0))
    noise_penalty = max(0.0, REFERENCE_NOISE_DBC - environment.get("ambient_noise_db", REFERENCE_NOISE_DBC))
    return {
        **plan,
        "sound_speed_mps": round(sound_speed_mps(environment), 4),
        "absorption_db_per_km": round(absorption_db_per_km(center_hz, environment), 6),
        "sediment_scattering_db_per_km": round(sediment_scattering_db_per_km(center_hz, environment), 6),
        "spreading_loss_db": round(loss["spreading_db"], 6),
        "absorption_loss_db": round(loss["absorption_db"], 6),
        "scattering_loss_db": round(loss["scattering_db"], 6),
        "two_way_loss_db": round(loss["total_db"], 6),
        "matched_filter_gain_db": round(pulse_gain, 6),
        "ambient_noise_penalty_db": round(noise_penalty, 6),
        "detection_margin_db": round(margin, 6),
        "detected_at_range": margin >= 0.0,
        "predicted_max_range_m": round(_max_range_m(plan, environment), 3),
        "range_resolution_m": round(sound_speed_mps(environment) / (2.0 * bandwidth), 6),
        "pulse_preview": pulse_preview(plan),
        "assumptions": [
            "relative detection budget is calibrated to the existing SIM-5 100 kHz / 500 m anchor",
            "turbidity loss is a heuristic until particle-size/tank data is available",
            "target strength, beam pattern, multipath, transducer efficiency, and amplifier limits are not modeled",
        ],
    }
