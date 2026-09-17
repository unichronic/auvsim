"""Small, dependency-free adaptive sonar and water-channel model.

The PS gives two named examples, not an exhaustive ocean model.  The catalog
below therefore covers the useful equivalence classes and input boundaries for
the bench; its values are test fixtures, not calibration data.
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
    "brackish_transition": {
        "label": "Brackish transition zone",
        "description": "A moderate turbidity and salinity transition exercises the controller boundary between the two profiles.",
        "environment": {
            "temperature_c": 22.0,
            "salinity_psu": 15.0,
            "depth_m": 35.0,
            "ph": 7.8,
            "range_m": 180.0,
            "ambient_noise_db": 45.0,
            "turbidity_ntu": 60.0,
        },
    },
    "deep_clear_water": {
        "label": "Deep clear water",
        "description": "Low turbidity with long propagation distance checks depth-driven attenuation even when the water is optically clear.",
        "environment": {
            "temperature_c": 4.0,
            "salinity_psu": 35.0,
            "depth_m": 300.0,
            "ph": 8.0,
            "range_m": 700.0,
            "ambient_noise_db": 45.0,
            "turbidity_ntu": 1.0,
        },
    },
    "deep_muddy_water": {
        "label": "Deep muddy water",
        "description": "High turbidity plus depth is the worst-case environmental class for high-frequency scattering and range margin.",
        "environment": {
            "temperature_c": 10.0,
            "salinity_psu": 30.0,
            "depth_m": 1000.0,
            "ph": 7.7,
            "range_m": 1200.0,
            "ambient_noise_db": 38.0,
            "turbidity_ntu": 450.0,
        },
    },
    "high_noise_harbor": {
        "label": "High-noise harbor",
        "description": "Shallow, turbid water with strong ambient noise checks the detection floor and conservative power response.",
        "environment": {
            "temperature_c": 20.0,
            "salinity_psu": 28.0,
            "depth_m": 18.0,
            "ph": 7.9,
            "range_m": 150.0,
            "ambient_noise_db": 18.0,
            "turbidity_ntu": 120.0,
        },
    },
    "cold_freshwater": {
        "label": "Cold fresh water",
        "description": "Freshwater and low temperature exercise the lower environmental input limits with a clear channel.",
        "environment": {
            "temperature_c": 2.0,
            "salinity_psu": 0.0,
            "depth_m": 20.0,
            "ph": 7.0,
            "range_m": 100.0,
            "ambient_noise_db": 50.0,
            "turbidity_ntu": 5.0,
        },
    },
    "warm_hypersaline": {
        "label": "Warm hypersaline water",
        "description": "Warm, high-salinity water exercises the upper temperature/salinity region without relying on a named demo.",
        "environment": {
            "temperature_c": 38.0,
            "salinity_psu": 45.0,
            "depth_m": 50.0,
            "ph": 8.4,
            "range_m": 300.0,
            "ambient_noise_db": 46.0,
            "turbidity_ntu": 15.0,
        },
    },
    "boundary_clear": {
        "label": "Adaptation boundary · clear side",
        "description": "A mud score just below the hysteresis boundary verifies that the clear profile is retained.",
        "environment": {
            "temperature_c": 15.0,
            "salinity_psu": 35.0,
            "depth_m": 10.0,
            "ph": 8.0,
            "range_m": 100.0,
            "ambient_noise_db": 48.0,
            "turbidity_ntu": 99.0,
        },
    },
    "boundary_muddy": {
        "label": "Adaptation boundary · muddy side",
        "description": "A mud score just above the switching boundary verifies that the muddy profile is selected.",
        "environment": {
            "temperature_c": 15.0,
            "salinity_psu": 35.0,
            "depth_m": 10.0,
            "ph": 8.0,
            "range_m": 100.0,
            "ambient_noise_db": 48.0,
            "turbidity_ntu": 101.0,
        },
    },
    "input_limits_minimum": {
        "label": "Input limits · minimum",
        "description": "Lower legal temperature, salinity, depth, pH, range, noise, and turbidity values.",
        "environment": {
            "temperature_c": -2.0,
            "salinity_psu": 0.0,
            "depth_m": 0.0,
            "ph": 6.0,
            "range_m": 1.0,
            "ambient_noise_db": 0.0,
            "turbidity_ntu": 0.0,
        },
    },
    "input_limits_maximum": {
        "label": "Input limits · maximum",
        "description": "Upper legal temperature, salinity, depth, pH, range, noise, and turbidity values.",
        "environment": {
            "temperature_c": 40.0,
            "salinity_psu": 45.0,
            "depth_m": 11000.0,
            "ph": 10.0,
            "range_m": 20000.0,
            "ambient_noise_db": 90.0,
            "turbidity_ntu": 1000.0,
        },
    },
}

SUPPORTED_MODULATIONS = ("lfm", "geom", "bpsk")
SUPPORTED_WINDOWS = ("rect", "hamming", "hann", "blackman")
BARKER13 = (1, 1, 1, 1, 1, -1, -1, 1, 1, -1, 1, -1, 1)
F_LO = 100_000.0
F_HI = 500_000.0

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


def _waveform_settings(modulation: Any, window: Any) -> tuple[str, str, str, str]:
    mode = str(modulation or "lfm").strip().lower()
    if mode not in SUPPORTED_MODULATIONS:
        raise ValueError(f"unsupported modulation: {mode}")
    requested_window = str(window or ("rect" if mode == "bpsk" else "hann")).strip().lower()
    if requested_window not in SUPPORTED_WINDOWS:
        raise ValueError(f"unsupported window: {requested_window}")
    if mode == "bpsk" and requested_window != "rect":
        return mode, requested_window, "rect", "phase-coded pulses keep a rectangular envelope to preserve chip correlation"
    return mode, requested_window, requested_window, "window applied to pulse envelope"


def adapt_transmit_plan(
    environment: dict[str, float],
    previous_class: str | None = None,
    modulation: str = "lfm",
    window: str | None = None,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
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

    mode, requested_window, effective_window, windowing_note = _waveform_settings(modulation, window)
    requested = overrides if isinstance(overrides, dict) else {}
    base_center = (start_hz + end_hz) / 2.0
    if "center_frequency_hz" in requested or "bandwidth_hz" in requested:
        center_hz = _clamp(_number(requested.get("center_frequency_hz"), base_center), F_LO, F_HI)
        bandwidth_hz = _clamp(_number(requested.get("bandwidth_hz"), end_hz - start_hz), 1_000.0, F_HI - F_LO)
        start_hz = center_hz - bandwidth_hz / 2.0
        end_hz = center_hz + bandwidth_hz / 2.0
        if start_hz < F_LO:
            end_hz += F_LO - start_hz
            start_hz = F_LO
        if end_hz > F_HI:
            start_hz -= end_hz - F_HI
            end_hz = F_HI
            start_hz = max(start_hz, F_LO)
    else:
        start_hz = _clamp(_number(requested.get("start_frequency_hz"), start_hz), F_LO, F_HI)
        end_hz = _clamp(_number(requested.get("end_frequency_hz"), end_hz), F_LO, F_HI)
    if mode != "bpsk" and end_hz <= start_hz:
        start_hz, end_hz = max(F_LO, start_hz - 500.0), min(F_HI, end_hz + 500.0)
    duration_ms = _clamp(_number(requested.get("pulse_duration_ms"), duration_ms), 0.1, 20.0)
    amplitude = _clamp(_number(requested.get("amplitude"), amplitude), 0.05, 1.0)
    bandwidth_hz = max(end_hz - start_hz, 1_000.0 if mode != "bpsk" else 1.0)

    return {
        "controller": "median-of-three ADC filter → fixed-point lookup → hysteresis",
        "policy": "shrike_lite_environment_lookup",
        "classification": classification,
        "mud_score": round(score_q15 / Q15_SCALE, 4),
        "mud_score_q15": score_q15,
        "modulation": mode,
        "window": effective_window,
        "window_requested": requested_window,
        "windowing_note": windowing_note,
        "start_frequency_hz": start_hz,
        "end_frequency_hz": end_hz,
        "center_frequency_hz": (start_hz + end_hz) / 2.0,
        "bandwidth_hz": bandwidth_hz,
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
    modulation = str(plan.get("modulation") or "lfm").strip().lower()
    if modulation not in SUPPORTED_MODULATIONS:
        raise ValueError(f"unsupported modulation: {modulation}")
    start_hz = float(plan["start_frequency_hz"])
    end_hz = float(plan["end_frequency_hz"])
    center_hz = float(plan.get("center_frequency_hz", (start_hz + end_hz) / 2.0))
    duration_s = max(float(plan["pulse_duration_ms"]) / 1000.0, 1e-9)
    sweep_rate = (end_hz - start_hz) / duration_s
    log_ratio = math.log(max(end_hz, 1.0) / max(start_hz, 1.0)) if modulation == "geom" else 0.0
    values: list[float] = []
    for index in range(count):
        fraction = index / (count - 1)
        time_s = fraction * duration_s
        if modulation == "bpsk":
            cycles = center_hz * time_s
            chip = min(len(BARKER13) - 1, int(fraction * len(BARKER13)))
            phase_code = BARKER13[chip]
            envelope = 1.0
        elif modulation == "geom" and abs(log_ratio) > 1e-12:
            cycles = start_hz * duration_s * math.expm1(log_ratio * fraction) / log_ratio
            phase_code = 1
            envelope = _window_value(str(plan["window"]), fraction)
        else:
            cycles = start_hz * time_s + 0.5 * sweep_rate * time_s**2
            phase_code = 1
            envelope = _window_value(str(plan["window"]), fraction)
        values.append(round(float(plan["amplitude"]) * envelope * phase_code * math.sin(2.0 * math.pi * cycles), 6))
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
