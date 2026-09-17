"""Small, deterministic sensor/software -> algorithm -> hardware simulation.

The existing bench proves one fixed transmitter chain. This module adds the
interactive boundary without hiding the hardware model: sensor streams are
generated at the configured clock or resampled from a recorded trace, the
software adapter is contract-checked, the selected algorithm estimates a
frequency, and the output passes through a configurable DDS, R-2R, and
reconstruction-filter preview.
"""

from __future__ import annotations

import math
import random
import re
import statistics
from typing import Any

try:
    import params as bench_params
except ImportError:  # pragma: no cover - makes the module easy to run alone
    bench_params = None


FS = float(getattr(bench_params, "FS", 10_000_000.0))
F_LO = float(getattr(bench_params, "F_LO", 100_000.0))
F_HI = float(getattr(bench_params, "F_HI", 500_000.0))
VREF = float(getattr(bench_params, "VREF", 3.3))
PHASE_BITS = int(getattr(bench_params, "PHASE_BITS", 32))
DAC_BITS = int(getattr(bench_params, "DAC_BITS", 8))
PHASE_SCALE = 1 << PHASE_BITS
DAC_LEVELS = 1 << DAC_BITS
MASK32 = PHASE_SCALE - 1

MAX_ANALYSIS_SAMPLES = 2048
MAX_PREVIEW_SAMPLES = 512
MAX_TRACE_SAMPLES = 4096
ALGORITHMS = {"weighted_fusion", "median_vote", "peak_pick", "coherent_mean"}
BEHAVIORS = {"tone", "chirp_up", "chirp_down", "burst", "dropout"}
HARDWARE_NODES = ("algorithm", "dds", "r2r", "filter", "probe")
ENVIRONMENT_DEFAULTS = {
    "temperature_c": 15.0,
    "salinity_psu": 35.0,
    "depth_m": 10.0,
    "ph": 8.0,
    "range_m": 100.0,
    "ambient_noise_db": 48.0,
}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _number(value: Any, default: float) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    return value if math.isfinite(value) else default


def _enabled(value: Any, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.strip().lower() in {"", "0", "false", "no", "off"}:
            return False
        if value.strip().lower() in {"1", "true", "yes", "on"}:
            return True
    return bool(value) if value is not None else default


def _sensor_behavior(sensor: dict[str, Any]) -> str:
    behavior = str(sensor.get("behavior") or "tone").strip().lower()
    return behavior if behavior in BEHAVIORS else "tone"


def _trace_samples(sensor: dict[str, Any]) -> list[float]:
    if sensor.get("source") != "trace" or not isinstance(sensor.get("samples"), list):
        return []
    samples: list[float] = []
    for raw_sample in sensor["samples"][:MAX_TRACE_SAMPLES]:
        sample = _number(raw_sample, math.nan)
        if math.isfinite(sample):
            samples.append(_clamp(sample, -1.5, 1.5))
    return samples


def _trace_wave(sensor: dict[str, Any], sample_count: int) -> list[float] | None:
    samples = _trace_samples(sensor)
    if len(samples) < 2:
        return None
    return [
        samples[
            min(
                int(round(index * (len(samples) - 1) / max(sample_count - 1, 1))),
                len(samples) - 1,
            )
        ]
        for index in range(sample_count)
    ]


def _environment_config(raw: Any) -> dict[str, float]:
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError("environment must be an object")
    return {
        "temperature_c": _clamp(_number(raw.get("temperature_c"), ENVIRONMENT_DEFAULTS["temperature_c"]), -2.0, 40.0),
        "salinity_psu": _clamp(_number(raw.get("salinity_psu"), ENVIRONMENT_DEFAULTS["salinity_psu"]), 0.0, 45.0),
        "depth_m": _clamp(_number(raw.get("depth_m"), ENVIRONMENT_DEFAULTS["depth_m"]), 0.0, 11_000.0),
        "ph": _clamp(_number(raw.get("ph"), ENVIRONMENT_DEFAULTS["ph"]), 6.0, 10.0),
        "range_m": _clamp(_number(raw.get("range_m"), ENVIRONMENT_DEFAULTS["range_m"]), 1.0, 20_000.0),
        "ambient_noise_db": _clamp(_number(raw.get("ambient_noise_db"), ENVIRONMENT_DEFAULTS["ambient_noise_db"]), 0.0, 90.0),
    }


def _sound_speed(environment: dict[str, float]) -> float:
    """Mackenzie-style sound speed fit used by the propagation model."""
    return (
        1412.0
        + 3.21 * environment["temperature_c"]
        + 1.19 * environment["salinity_psu"]
        + 0.0167 * environment["depth_m"]
    )


def _absorption_db_per_km(frequency_hz: float, environment: dict[str, float]) -> float:
    """Scalar Ainslie-McColl absorption preview, matching sim5_propagation.py."""
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


def _environment_effects(frequency_hz: float, environment: dict[str, float]) -> dict[str, float]:
    speed = _sound_speed(environment)
    delay_s = environment["range_m"] / max(speed, 1.0)
    absorption = _absorption_db_per_km(frequency_hz, environment)
    attenuation_db = absorption * environment["range_m"] / 1000.0
    gain = 10.0 ** (-attenuation_db / 20.0)
    return {
        "sound_speed_mps": speed,
        "propagation_delay_s": delay_s,
        "absorption_db_per_km": absorption,
        "attenuation_db": attenuation_db,
        "gain": gain,
    }


def _sensor_wave(
    sensor: dict[str, Any],
    sample_count: int,
    seed: int,
    sample_rate: float = FS,
    environment: dict[str, float] | None = None,
) -> list[float]:
    """Generate one reproducible modeled or recorded sensor stream."""
    recorded = _trace_wave(sensor, sample_count)
    if recorded is not None:
        return recorded

    environment = environment or _environment_config(None)

    frequency = _clamp(_number(sensor.get("frequency_hz"), 250_000.0), F_LO, F_HI)
    effects = _environment_effects(frequency, environment)
    amplitude = _clamp(_number(sensor.get("amplitude"), 0.8), 0.05, 1.0) * effects["gain"]
    phase = math.radians(_clamp(_number(sensor.get("phase_deg"), 0.0), -180.0, 180.0))
    phase += 2.0 * math.pi * frequency * effects["propagation_delay_s"]
    noise_below_carrier_db = min(
        _clamp(_number(sensor.get("noise_db"), 48.0), 0.0, 90.0),
        environment["ambient_noise_db"],
    )
    noise_rms = amplitude * (10.0 ** (-noise_below_carrier_db / 20.0))
    behavior = _sensor_behavior(sensor)
    sweep_hz = _clamp(_number(sensor.get("sweep_hz"), 50_000.0), 0.0, 400_000.0)
    duration = max(sample_count / max(sample_rate, 1.0), 1.0 / max(sample_rate, 1.0))
    start_frequency = frequency
    end_frequency = frequency
    if behavior in {"chirp_up", "chirp_down"}:
        direction = 1.0 if behavior == "chirp_up" else -1.0
        start_frequency = _clamp(frequency - direction * sweep_hz / 2.0, F_LO, F_HI)
        end_frequency = _clamp(frequency + direction * sweep_hz / 2.0, F_LO, F_HI)
    sweep_rate = (end_frequency - start_frequency) / duration

    def envelope(index: int) -> float:
        if behavior == "burst":
            period = max(64, min(2048, int(sample_rate / max(frequency, F_LO) * 16.0)))
            return 1.0 if index % period < int(period * 0.62) else 0.0
        if behavior == "dropout":
            period = max(256, min(2048, int(sample_rate / max(frequency, F_LO) * 24.0)))
            return 1.0 if index % period < int(period * 0.76) else 0.0
        return 1.0

    rng = random.Random(seed)
    waveform: list[float] = []
    for index in range(sample_count):
        time = index / max(sample_rate, 1.0)
        cycles = start_frequency * time + 0.5 * sweep_rate * time * time
        waveform.append(amplitude * envelope(index) * math.sin(2.0 * math.pi * cycles + phase) + rng.gauss(0.0, noise_rms))
    return waveform


def _estimate_frequency(samples: list[float], sample_rate: float = FS) -> float:
    """Estimate a clean synthetic sensor's frequency from upward crossings."""
    # A crossing itself is close to zero; a high threshold makes the estimate
    # depend on propagation phase and can discard every valid crossing when a
    # wave happens to cross between two nearby samples.
    crossing_floor = max((max(abs(sample) for sample in samples) if samples else 0.0) * 0.01, 0.0)
    crossings: list[float] = []
    for index in range(1, len(samples)):
        before, after = samples[index - 1], samples[index]
        if before <= 0.0 < after and max(abs(before), abs(after)) >= crossing_floor:
            delta = after - before
            fraction = (-before / delta) if delta else 0.0
            crossings.append(index - 1 + fraction)

    if len(crossings) < 2:
        return 0.0
    periods = [b - a for a, b in zip(crossings, crossings[1:]) if b > a]
    if not periods:
        return 0.0
    # Gated inputs skip complete carrier cycles while they are off. Keep the
    # tightest cluster of periods so a dropout does not look like a slower tone.
    shortest = min(periods)
    stable_periods = [period for period in periods if period <= shortest * 1.35]
    return sample_rate / statistics.median(stable_periods or periods)


def _rms(samples: list[float]) -> float:
    return math.sqrt(sum(sample * sample for sample in samples) / max(len(samples), 1))


def _algorithm(sensor_rows: list[dict[str, Any]], algorithm: str) -> tuple[float, int | None]:
    active = [row for row in sensor_rows if row["enabled"] and row["estimated_hz"] > 0.0]
    if not active:
        raise ValueError("Enable at least one sensor with a detectable signal.")

    frequencies = [row["estimated_hz"] for row in active]
    if algorithm == "median_vote":
        return statistics.median(frequencies), None
    if algorithm == "peak_pick":
        chosen = max(active, key=lambda row: row["rms"])
        return chosen["estimated_hz"], chosen["index"]
    if algorithm == "coherent_mean":
        # Treat the median cluster as the coherent set; outliers are rejected.
        centre = statistics.median(frequencies)
        coherent = [row for row in active if abs(row["estimated_hz"] - centre) <= 35_000]
        return statistics.fmean(row["estimated_hz"] for row in coherent), None

    # weighted_fusion is the default: a stronger sensor gets more influence.
    weight_sum = sum(max(row["rms"], 1e-6) for row in active)
    estimate = sum(row["estimated_hz"] * max(row["rms"], 1e-6) for row in active) / weight_sum
    return estimate, None


def _dds_preview(
    frequency_hz: float,
    sample_count: int,
    sample_rate: float = FS,
    phase_bits: int = PHASE_BITS,
    dac_bits: int = DAC_BITS,
) -> tuple[list[float], int, float, list[int]]:
    """Return normalized DAC values using an integer phase accumulator."""
    phase_scale = 1 << phase_bits
    phase_mask = phase_scale - 1
    dac_levels = 1 << dac_bits
    midpoint = (dac_levels - 1) / 2.0
    ftw = int(round(frequency_hz / sample_rate * phase_scale)) & phase_mask
    actual_frequency = ftw * sample_rate / phase_scale
    phase = 0
    normalized: list[float] = []
    codes: list[int] = []
    for _ in range(sample_count):
        address = (phase >> (phase_bits - 12)) & 0xFFF
        raw = math.floor(midpoint + midpoint * math.sin(2.0 * math.pi * address / 4096.0) + 0.5)
        raw = max(0, min(dac_levels - 1, raw))
        codes.append(raw)
        normalized.append((raw - midpoint) / max(midpoint, 1.0))
        phase = (phase + ftw) & phase_mask
    return normalized, ftw, actual_frequency, codes


def _hardware_config(raw: Any) -> dict[str, float | int]:
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError("hardware must be an object")
    return {
        "clock_hz": _clamp(_number(raw.get("clock_hz"), FS), 1_000_000.0, 100_000_000.0),
        "phase_bits": int(_clamp(_number(raw.get("phase_bits"), PHASE_BITS), 12, 48)),
        "dac_bits": int(_clamp(_number(raw.get("dac_bits"), DAC_BITS), 4, 16)),
        "vref_v": _clamp(_number(raw.get("vref_v"), VREF), 0.5, 5.0),
        "filter_cutoff_hz": _clamp(_number(raw.get("filter_cutoff_hz"), 700_000.0), 100_000.0, 5_000_000.0),
        "filter_order": int(_clamp(_number(raw.get("filter_order"), 3), 1, 4)),
        "resistor_tolerance_pct": _clamp(_number(raw.get("resistor_tolerance_pct"), 0.1), 0.0, 5.0),
    }


def _default_connections(sensor_count: int) -> list[dict[str, str]]:
    return (
        [{"from": f"sensor-{index + 1}", "to": "algorithm"} for index in range(sensor_count)]
        + [
            {"from": "algorithm", "to": "dds"},
            {"from": "dds", "to": "r2r"},
            {"from": "r2r", "to": "filter"},
            {"from": "filter", "to": "probe"},
        ]
    )


def _allowed_connection(source: str, target: str) -> bool:
    return (
        (source.startswith("sensor-") and target == "algorithm")
        or (source == "algorithm" and target == "dds")
        or (source == "dds" and target == "r2r")
        or (source == "r2r" and target == "filter")
        or (source == "filter" and target == "probe")
    )


def _connections(raw: Any, sensor_count: int) -> list[dict[str, str]]:
    if raw is None:
        return _default_connections(sensor_count)
    if not isinstance(raw, list):
        raise ValueError("connections must be an array")
    valid = {f"sensor-{index + 1}" for index in range(sensor_count)} | set(HARDWARE_NODES)
    cleaned: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for connection in raw:
        if not isinstance(connection, dict):
            raise ValueError("each connection must be an object")
        source = connection.get("from")
        target = connection.get("to")
        if not isinstance(source, str) or not isinstance(target, str) or source not in valid or target not in valid:
            raise ValueError("connections reference an unknown component")
        if source == target:
            raise ValueError("a component cannot connect to itself")
        if not _allowed_connection(source, target):
            raise ValueError("unsupported connection; use sensor → algorithm → DDS → R-2R → filter → output probe")
        pair = (source, target)
        if pair not in seen:
            cleaned.append({"from": source, "to": target})
            seen.add(pair)
    required = [("algorithm", "dds"), ("dds", "r2r"), ("r2r", "filter"), ("filter", "probe")]
    if any(pair not in seen for pair in required):
        raise ValueError("connect the hardware chain: algorithm → DDS → R-2R → filter → output probe")
    graph = {node: [] for node in valid}
    for source, target in seen:
        graph[source].append(target)
    visited: set[str] = set()
    active: set[str] = set()

    def visit(node: str) -> None:
        if node in active:
            raise ValueError("connections must form an acyclic signal graph")
        if node in visited:
            return
        active.add(node)
        for target in graph[node]:
            visit(target)
        active.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)
    return cleaned


def _software_contract(raw: Any, requested_algorithm: str) -> dict[str, Any]:
    if raw is None:
        return {
            "enabled": False,
            "plugin_name": "No software plugin",
            "language": "none",
            "entrypoint": "",
            "source_file": "",
            "contract": "bench-v1",
            "passed": True,
            "checks": ["hardware-only run"],
            "algorithm": requested_algorithm,
        }
    if not isinstance(raw, dict):
        raise ValueError("software must be an object")
    code = str(raw.get("code") or "")
    if len(code) > 100_000:
        raise ValueError("software plugin code is too large")
    if not code.strip():
        raise ValueError("software plugin code is required")
    entrypoint = str(raw.get("entrypoint") or "on_measurement")[:64]
    if entrypoint not in code:
        raise ValueError(f"software plugin must define {entrypoint}(...)")
    if "bench_set_algorithm" not in code:
        raise ValueError("software plugin must call bench_set_algorithm(...)")
    match = re.search(r"bench_set_algorithm\s*\(\s*['\"](weighted_fusion|median_vote|peak_pick|coherent_mean)['\"]", code)
    algorithm = match.group(1) if match else requested_algorithm
    return {
        "enabled": True,
        "plugin_name": str(raw.get("plugin_name") or "Local bench plugin")[:64],
        "language": str(raw.get("language") or "c")[:16],
        "entrypoint": entrypoint,
        "source_file": str(raw.get("source_file") or "")[:128],
        "contract": "bench-v1",
        "passed": True,
        "checks": ["entrypoint found", "algorithm handoff found", "hardware frame accepted"],
        "algorithm": algorithm,
    }


def _low_pass(values: list[float], sample_rate: float, cutoff_hz: float, order: int) -> list[float]:
    """Approximate a cascaded RC reconstruction filter for the visible preview."""
    alpha = 1.0 - math.exp(-2.0 * math.pi * cutoff_hz / sample_rate)
    filtered = values[:]
    for _ in range(order):
        previous = 0.0
        next_values: list[float] = []
        for value in filtered:
            previous += alpha * (value - previous)
            next_values.append(previous)
        filtered = next_values
    return filtered


def _coherence(sensor_rows: list[dict[str, Any]]) -> float:
    frequencies = [row["estimated_hz"] for row in sensor_rows if row["enabled"] and row["estimated_hz"]]
    if len(frequencies) < 2:
        return 1.0
    spread = max(frequencies) - min(frequencies)
    return _clamp(1.0 - spread / (F_HI - F_LO), 0.0, 1.0)


def run_simulation(payload: dict[str, Any]) -> dict[str, Any]:
    """Run the interactive pipeline and return JSON-safe results."""
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    sensors = payload.get("sensors") or []
    if not isinstance(sensors, list):
        raise ValueError("sensors must be an array")
    if len(sensors) > 4:
        raise ValueError("a maximum of four sensors is supported")
    if not sensors:
        raise ValueError("At least one sensor is required.")
    for index, sensor in enumerate(sensors):
        if not isinstance(sensor, dict):
            raise ValueError(f"sensor {index + 1} must be an object")

    preview_count = int(_clamp(_number(payload.get("preview_samples"), 384), 128, MAX_PREVIEW_SAMPLES))
    analysis_count = max(preview_count, min(MAX_ANALYSIS_SAMPLES, 1024))
    requested_algorithm = str(payload.get("algorithm") or "weighted_fusion")
    if requested_algorithm not in ALGORITHMS:
        raise ValueError(f"Unknown algorithm: {requested_algorithm}")

    hardware_config = _hardware_config(payload.get("hardware"))
    environment = _environment_config(payload.get("environment"))
    software = _software_contract(payload.get("software"), requested_algorithm)
    algorithm = software["algorithm"]
    connections = _connections(payload.get("connections"), len(sensors))
    clock_hz = float(hardware_config["clock_hz"])
    phase_bits = int(hardware_config["phase_bits"])
    dac_bits = int(hardware_config["dac_bits"])
    vref_v = float(hardware_config["vref_v"])
    filter_cutoff_hz = float(hardware_config["filter_cutoff_hz"])
    filter_order = int(hardware_config["filter_order"])
    resistor_tolerance_pct = float(hardware_config["resistor_tolerance_pct"])

    rows: list[dict[str, Any]] = []
    series: dict[str, list[float]] = {"time_us": [round(i / clock_hz * 1e6, 4) for i in range(preview_count)]}
    active_names: list[str] = []
    for index, sensor in enumerate(sensors):
        enabled = _enabled(sensor.get("enabled", True))
        name = str(sensor.get("name") or f"Sensor {index + 1}")[:32]
        waveform = _sensor_wave(sensor, analysis_count, 0x5EED + index * 97, clock_hz, environment)
        estimated_hz = _estimate_frequency(waveform, clock_hz) if enabled else 0.0
        trace_active = len(_trace_samples(sensor)) >= 2
        effects = _environment_effects(
            _clamp(_number(sensor.get("frequency_hz"), 250_000.0), F_LO, F_HI),
            environment,
        )
        row = {
            "index": index,
            "name": name,
            "enabled": enabled,
            "requested_hz": round(_clamp(_number(sensor.get("frequency_hz"), 250_000.0), F_LO, F_HI), 2),
            "estimated_hz": round(estimated_hz, 2),
            "rms": round(_rms(waveform), 5),
            "phase_deg": round(_number(sensor.get("phase_deg"), 0.0), 2),
            "behavior": _sensor_behavior(sensor),
            "source": "trace" if trace_active else "model",
            "source_file": str(sensor.get("source_file") or "")[:128] if trace_active else "",
            "environment_applied": not trace_active,
            "propagation_gain_db": round(-effects["attenuation_db"], 5) if not trace_active else 0.0,
        }
        rows.append(row)
        series[f"sensor_{index + 1}"] = [round(value, 5) for value in waveform[:preview_count]]
        if enabled:
            active_names.append(name)

    connected = {(connection["from"], connection["to"]) for connection in connections}
    missing_inputs = [row["name"] for row in rows if row["enabled"] and (f"sensor-{row['index'] + 1}", "algorithm") not in connected]
    if missing_inputs:
        raise ValueError(f"connect enabled sensor input(s) to the algorithm: {', '.join(missing_inputs)}")

    estimate_hz, selected_index = _algorithm(rows, algorithm)
    estimate_hz = _clamp(estimate_hz, F_LO, F_HI)
    raw_output, ftw, actual_hz, dac_codes = _dds_preview(estimate_hz, preview_count, clock_hz, phase_bits, dac_bits)
    output = _low_pass(raw_output, clock_hz, filter_cutoff_hz, filter_order)
    fused = [
        round(
            sum(series[f"sensor_{index + 1}"][sample] for index, row in enumerate(rows) if row["enabled"])
            / max(sum(1 for row in rows if row["enabled"]), 1),
            5,
        )
        for sample in range(preview_count)
    ]
    series["fused"] = fused
    series["output"] = output

    tolerance = abs(actual_hz - estimate_hz)
    filter_ratio = actual_hz / max(filter_cutoff_hz, 1.0)
    filter_gain = (1.0 / math.sqrt(1.0 + filter_ratio * filter_ratio)) ** filter_order
    filter_gain_db = 20.0 * math.log10(max(filter_gain, 1e-12))
    ladder_gain = 1.0 - resistor_tolerance_pct / 100.0
    output_environment = _environment_effects(estimate_hz, environment)
    return {
        "sample_rate_hz": clock_hz,
        "sensor_rows": rows,
        "active_sensor_names": active_names,
        "environment": {
            **environment,
            "sound_speed_mps": round(_sound_speed(environment), 4),
            "absorption_db_per_km": round(output_environment["absorption_db_per_km"], 6),
            "one_way_attenuation_db": round(output_environment["attenuation_db"], 6),
            "propagation_delay_ms": round(output_environment["propagation_delay_s"] * 1000.0, 6),
        },
        "algorithm": algorithm,
        "algorithm_estimate_hz": round(estimate_hz, 2),
        "selected_sensor_index": selected_index,
        "coherence": round(_coherence(rows), 4),
        "hardware": {
            "stage": "DDS → R-2R DAC → reconstruction filter → output probe",
            "clock_hz": clock_hz,
            "phase_bits": phase_bits,
            "dac_bits": dac_bits,
            "vref_v": round(vref_v, 4),
            "filter_cutoff_hz": round(filter_cutoff_hz, 2),
            "filter_order": filter_order,
            "filter_gain_db": round(filter_gain_db, 4),
            "resistor_tolerance_pct": round(resistor_tolerance_pct, 4),
            "ladder_gain": round(ladder_gain, 6),
            "ftw": ftw,
            "actual_frequency_hz": round(actual_hz, 4),
            "quantization_error_hz": round(tolerance, 6),
            "peak_voltage_v": round(vref_v * ladder_gain * filter_gain, 4),
            "codes": dac_codes,
        },
        "software": software,
        "connections": connections,
        "series": series,
        "summary": (
            f"{len(active_names)} sensor stream(s) → {algorithm.replace('_', ' ')} "
            f"→ {software['plugin_name']} → {actual_hz / 1000:.3f} kHz output probe"
        ),
    }


def self_check() -> None:
    result = run_simulation(
        {
            "algorithm": "weighted_fusion",
            "preview_samples": 128,
            "sensors": [
                {"name": "A", "frequency_hz": 200_000, "amplitude": 1.0, "noise_db": 60, "enabled": True},
                {"name": "B", "frequency_hz": 200_000, "amplitude": 0.8, "noise_db": 60, "enabled": True},
                {"name": "C", "frequency_hz": 350_000, "amplitude": 0.2, "noise_db": 60, "enabled": False},
                {"name": "D", "frequency_hz": 400_000, "amplitude": 0.2, "noise_db": 60, "enabled": False},
            ],
        }
    )
    assert 190_000 < result["algorithm_estimate_hz"] < 210_000
    assert len(result["series"]["output"]) == 128
    assert 0 <= result["hardware"]["ftw"] <= MASK32
    assert result["environment"]["temperature_c"] == ENVIRONMENT_DEFAULTS["temperature_c"]
    warmer_deeper = run_simulation(
        {
            "sensors": [{"frequency_hz": 200_000, "enabled": True}],
            "environment": {"temperature_c": 30, "salinity_psu": 30, "depth_m": 500, "ph": 7.5, "range_m": 1000, "ambient_noise_db": 48},
        }
    )
    assert warmer_deeper["environment"]["sound_speed_mps"] != result["environment"]["sound_speed_mps"]
    assert warmer_deeper["sensor_rows"][0]["environment_applied"] is True
    recorded_environment = run_simulation(
        {
            "sensors": [{"enabled": True, "source": "trace", "samples": [-1.0, 1.0, -1.0, 1.0, -1.0, 1.0]}],
            "environment": {"temperature_c": -2, "salinity_psu": 0, "depth_m": 11000, "ph": 10, "range_m": 20000, "ambient_noise_db": 0},
        }
    )
    assert recorded_environment["sensor_rows"][0]["environment_applied"] is False
    for behavior in BEHAVIORS:
        alternate = run_simulation({"algorithm": "weighted_fusion", "sensors": [{"frequency_hz": 220000, "enabled": True, "behavior": behavior}]})
        assert F_LO <= alternate["hardware"]["actual_frequency_hz"] <= F_HI
        assert alternate["sensor_rows"][0]["behavior"] == behavior
    trace = [math.sin(2.0 * math.pi * 200_000 * index / FS) for index in range(256)]
    recorded = run_simulation({"sensors": [{"enabled": True, "source": "trace", "source_file": "captured.csv", "samples": trace}]})
    assert recorded["sensor_rows"][0]["source"] == "trace"
    assert recorded["sensor_rows"][0]["source_file"] == "captured.csv"
    for algorithm in ("weighted_fusion", "median_vote", "peak_pick", "coherent_mean"):
        alternate = run_simulation({"algorithm": algorithm, "sensors": [{"frequency_hz": 220000, "enabled": True}]})
        assert F_LO <= alternate["hardware"]["actual_frequency_hz"] <= F_HI
    for invalid in (
        None,
        {"sensors": ["not a sensor"]},
        {"sensors": [{"enabled": False}]},
        {
            "sensors": [{"enabled": True}],
            "connections": [
                {"from": "algorithm", "to": "dds"},
                {"from": "dds", "to": "r2r"},
                {"from": "r2r", "to": "filter"},
                {"from": "filter", "to": "probe"},
            ],
        },
        {"sensors": [{"enabled": True}], "environment": "not an object"},
    ):
        try:
            run_simulation(invalid)  # type: ignore[arg-type]
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid payload unexpectedly accepted: {invalid!r}")
    print("gui simulation self-check: ok")


if __name__ == "__main__":
    self_check()
