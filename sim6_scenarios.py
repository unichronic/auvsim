"""SIM-6 -- PS scenarios through sensor adaptation and a sonar link preview.

This is a comparison model, not a substitute for tank/sea data. It exercises
the same sensor payload used by the GUI, selects the Shrike-Lite policy, then
validates the selected LFM pulse with the exact SIM-0 integer waveform path.
"""

from __future__ import annotations

import json

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import params as P
import sim0_reference as s0
from gui.simulation import run_simulation
from gui.sonar import (
    SCENARIO_PRESETS,
    adapt_transmit_plan,
    evaluate_sonar,
    median_of_three,
    scenario_environment,
)


def fixed_lfm_plan(start_hz: float, end_hz: float, duration_ms: float, amplitude: float) -> dict[str, object]:
    return {
        "controller": "comparison baseline",
        "policy": "fixed_lfm_baseline",
        "classification": "comparison",
        "mud_score": 0.0,
        "modulation": "lfm",
        "window": "hann",
        "start_frequency_hz": start_hz,
        "end_frequency_hz": end_hz,
        "center_frequency_hz": (start_hz + end_hz) / 2.0,
        "bandwidth_hz": end_hz - start_hz,
        "pulse_duration_ms": duration_ms,
        "amplitude": amplitude,
        "rationale": "fixed comparison profile",
    }


def sensor_inputs(plan: dict[str, object]) -> list[dict[str, object]]:
    center_hz = float(plan["center_frequency_hz"])
    return [
        {"name": "Acoustic channel 1", "frequency_hz": center_hz, "amplitude": 0.92, "phase_deg": 0, "noise_db": 55, "enabled": True, "behavior": "tone"},
        {"name": "Acoustic channel 2", "frequency_hz": center_hz, "amplitude": 0.78, "phase_deg": 27, "noise_db": 52, "enabled": True, "behavior": "tone"},
        {"name": "Acoustic channel 3", "frequency_hz": center_hz, "amplitude": 0.64, "phase_deg": -19, "noise_db": 50, "enabled": True, "behavior": "tone"},
    ]


def environment_sensor_inputs(environment: dict[str, float]) -> list[dict[str, object]]:
    """Make three noisy ADC readings for each scenario discriminator.

    These are repeated samples of a temperature, depth/pressure, and optical
    turbidity input—not three sensors required by the PS. The median filter is
    deliberately visible in the report so the proposed RP2040 controller can
    be replaced by real ADC data later.
    """
    return [
        {
            "name": "water temperature probe",
            "parameter": "temperature_c",
            "unit": "°C",
            "samples": [round(environment["temperature_c"] - 0.2, 2), round(environment["temperature_c"] + 0.3, 2), round(environment["temperature_c"], 2)],
        },
        {
            "name": "pressure/depth input",
            "parameter": "depth_m",
            "unit": "m",
            "samples": [round(environment["depth_m"] + 0.4, 2), round(environment["depth_m"], 2), round(max(environment["depth_m"] - 0.3, 0.0), 2)],
        },
        {
            "name": "optical turbidity input",
            "parameter": "turbidity_ntu",
            "unit": "NTU",
            "samples": [round(environment["turbidity_ntu"], 2), round(environment["turbidity_ntu"] + 0.8, 2), round(max(environment["turbidity_ntu"] - 0.5, 0.0), 2)],
        },
    ]


def fuse_environment_sensor_inputs(
    environment: dict[str, float],
    readings: list[dict[str, object]],
) -> tuple[dict[str, float], list[dict[str, object]]]:
    conditioned = dict(environment)
    report_rows: list[dict[str, object]] = []
    for reading in readings:
        parameter = str(reading["parameter"])
        samples = [float(value) for value in reading["samples"]]  # type: ignore[index]
        filtered = median_of_three(samples)
        conditioned[parameter] = filtered
        report_rows.append({**reading, "filtered_value": filtered, "filter": "median-of-three"})
    return conditioned, report_rows


def exact_pulse_metrics(plan: dict[str, object]) -> dict[str, object]:
    sample_count = max(2, round(float(plan["pulse_duration_ms"]) / 1000.0 * P.FS))
    window = s0.make_window(str(plan["window"]), sample_count)
    codes, _ = s0.gen_lfm(float(plan["start_frequency_hz"]), float(plan["end_frequency_hz"]), sample_count, window)
    frequencies, spectrum = s0.spectrum(codes, nfft=1 << 16)
    peak = int(spectrum.argmax())
    preview_indices = np.linspace(0, sample_count - 1, 256, dtype=int)
    return {
        "sample_count": sample_count,
        "sample_rate_hz": P.FS,
        "spectrum_peak_hz": round(float(frequencies[peak]), 4),
        "peak_sidelobe_db": round(float(s0.peak_sidelobe_db(codes)), 4),
        "pulse_preview": [round(float((int(codes[index]) - 127.5) / 127.5), 6) for index in preview_indices],
    }


def compact_sonar(result: dict[str, object]) -> dict[str, object]:
    keys = (
        "controller",
        "policy",
        "classification",
        "mud_score",
        "mud_score_q15",
        "modulation",
        "window",
        "start_frequency_hz",
        "end_frequency_hz",
        "center_frequency_hz",
        "bandwidth_hz",
        "pulse_duration_ms",
        "amplitude",
        "rationale",
        "sound_speed_mps",
        "absorption_db_per_km",
        "sediment_scattering_db_per_km",
        "two_way_loss_db",
        "matched_filter_gain_db",
        "ambient_noise_penalty_db",
        "detection_margin_db",
        "detected_at_range",
        "predicted_max_range_m",
        "range_resolution_m",
    )
    return {key: result[key] for key in keys if key in result}


def run_scenario(scenario_id: str) -> dict[str, object]:
    base_environment = scenario_environment(scenario_id)
    environment, environment_sensor_report = fuse_environment_sensor_inputs(
        base_environment,
        environment_sensor_inputs(base_environment),
    )
    plan = adapt_transmit_plan(environment)
    sensor_result = run_simulation(
        {
            "scenario": scenario_id,
            "algorithm": "weighted_fusion",
            "sensors": sensor_inputs(plan),
            "environment": environment,
        }
    )
    comparisons = {
        "fixed_low_band": compact_sonar(evaluate_sonar(fixed_lfm_plan(100_000, 200_000, 2.0, 0.95), environment)),
        "fixed_high_band": compact_sonar(evaluate_sonar(fixed_lfm_plan(300_000, 500_000, 1.0, 0.75), environment)),
        "adaptive": compact_sonar(evaluate_sonar(plan, environment)),
    }
    selected_sonar = evaluate_sonar(plan, environment)
    return {
        "scenario": scenario_id,
        "label": SCENARIO_PRESETS[scenario_id]["label"],
        "description": SCENARIO_PRESETS[scenario_id]["description"],
        "environment": environment,
        "environment_sensor_input": environment_sensor_report,
        "acoustic_sensor_input": {
            "channels": len(sensor_result["sensor_rows"]),
            "fusion_algorithm": sensor_result["algorithm"],
            "estimated_frequency_hz": sensor_result["algorithm_estimate_hz"],
            "output_frequency_hz": sensor_result["hardware"]["actual_frequency_hz"],
            "coherence": sensor_result["coherence"],
        },
        "shrike_lite_adaptation": compact_sonar(selected_sonar),
        "exact_waveform": exact_pulse_metrics(plan),
        "comparison": comparisons,
    }


def main() -> dict[str, object]:
    scenarios = [run_scenario(scenario_id) for scenario_id in SCENARIO_PRESETS]
    report = {
        "problem_statement": "SIH26058",
        "controller": "RP2040 filters/median-fuses environmental ADC readings; fixed-point lookup with hysteresis selects the profile; SLG47910 FPGA performs deterministic DDS pulse synthesis.",
        "scenarios": scenarios,
    }
    (P.OUT / "sim6_scenario_report.json").write_text(json.dumps(report, indent=2))

    fig, axes = plt.subplots(2, 2, figsize=(11, 7.5))
    labels = [scenario["label"].replace("Entering ", "") for scenario in scenarios]
    x = np.arange(len(labels))
    margins = [[scenario["comparison"][key]["detection_margin_db"] for scenario in scenarios] for key in ("fixed_low_band", "fixed_high_band", "adaptive")]
    resolutions = [[scenario["comparison"][key]["range_resolution_m"] * 100 for scenario in scenarios] for key in ("fixed_low_band", "fixed_high_band", "adaptive")]
    width = 0.24
    for offset, (name, values) in enumerate(zip(("fixed low", "fixed high", "adaptive"), margins)):
        axes[0, 0].bar(x + (offset - 1) * width, values, width, label=name)
    axes[0, 0].axhline(0, color="black", lw=.8)
    axes[0, 0].set_ylabel("dB"); axes[0, 0].set_title("Predicted detection margin at scenario range", loc="left", fontsize=10); axes[0, 0].set_xticks(x, labels); axes[0, 0].legend(fontsize=8); axes[0, 0].grid(axis="y", alpha=.25)
    for offset, (name, values) in enumerate(zip(("fixed low", "fixed high", "adaptive"), resolutions)):
        axes[0, 1].bar(x + (offset - 1) * width, values, width, label=name)
    axes[0, 1].set_ylabel("cm"); axes[0, 1].set_title("Range resolution (lower is finer)", loc="left", fontsize=10); axes[0, 1].set_xticks(x, labels); axes[0, 1].grid(axis="y", alpha=.25)
    for scenario in scenarios:
        pulse = scenario["exact_waveform"]["pulse_preview"]
        time_ms = np.linspace(0, scenario["shrike_lite_adaptation"]["pulse_duration_ms"], len(pulse))
        axes[1, 0].plot(time_ms, pulse, label=scenario["label"].replace("Entering ", ""))
    axes[1, 0].set_xlabel("pulse time [ms]"); axes[1, 0].set_ylabel("normalised DAC"); axes[1, 0].set_title("Exact selected LFM pulse preview", loc="left", fontsize=10); axes[1, 0].legend(fontsize=8); axes[1, 0].grid(alpha=.25)
    centers = [scenario["shrike_lite_adaptation"]["center_frequency_hz"] / 1000 for scenario in scenarios]
    axes[1, 1].bar(labels, centers, color=("tab:orange", "tab:blue"))
    axes[1, 1].set_ylabel("kHz"); axes[1, 1].set_title("Selected centre frequency", loc="left", fontsize=10); axes[1, 1].grid(axis="y", alpha=.25)
    fig.suptitle("SIM-6 · SIH26058 adaptive sonar scenarios", x=.06, ha="left", fontsize=12)
    fig.tight_layout(); fig.savefig(P.OUT / "sim6_scenario_comparison.png", dpi=115); plt.close(fig)
    return report


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
