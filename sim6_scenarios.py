"""SIM-6 -- PS scenarios through sensor adaptation and a sonar link preview.

This is a comparison model, not a substitute for tank/sea data. It exercises
the same sensor payload used by the GUI, selects the Shrike-Lite policy, then
validates the selected LFM pulse with the exact SIM-0 integer waveform path.
"""

from __future__ import annotations

import json
import math

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import params as P
import sim0_reference as s0
from gui.simulation import run_simulation
from gui.realtime import run_realtime
from gui.sonar import (
    SCENARIO_PRESETS,
    SUPPORTED_MODULATIONS,
    SUPPORTED_WINDOWS,
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


def exact_pulse_metrics(plan: dict[str, object], full: bool = True) -> dict[str, object]:
    sample_count = max(2, round(float(plan["pulse_duration_ms"]) / 1000.0 * P.FS))
    window = s0.make_window(str(plan["window"]), sample_count)
    modulation = str(plan["modulation"])
    if modulation == "lfm":
        codes, _ = s0.gen_lfm(float(plan["start_frequency_hz"]), float(plan["end_frequency_hz"]), sample_count, window)
    elif modulation == "geom":
        codes, _ = s0.gen_geom(float(plan["start_frequency_hz"]), float(plan["end_frequency_hz"]), sample_count, window)
    elif modulation == "bpsk":
        codes, _ = s0.gen_bpsk(float(plan["center_frequency_hz"]), sample_count, window)
    else:
        raise ValueError(f"unsupported modulation: {modulation}")
    frequencies, spectrum = s0.spectrum(codes, nfft=1 << 16)
    peak = int(spectrum.argmax())
    metrics: dict[str, object] = {
        "modulation": modulation,
        "sample_count": sample_count,
        "sample_rate_hz": P.FS,
        "spectrum_peak_hz": round(float(frequencies[peak]), 4),
        "peak_sidelobe_db": round(float(s0.peak_sidelobe_db(codes)), 4) if full else None,
    }
    if full:
        preview_indices = np.linspace(0, sample_count - 1, 256, dtype=int)
        metrics["pulse_preview"] = [round(float((int(codes[index]) - 127.5) / 127.5), 6) for index in preview_indices]
    return metrics


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


def _expected_failure(payload: dict[str, object]) -> dict[str, object]:
    try:
        run_simulation(payload)
    except (ValueError, TypeError) as error:
        return {"status": "expected_failure", "error": str(error)}
    return {"status": "unexpected_pass", "error": "invalid input was accepted"}


def run_coverage_matrix() -> dict[str, object]:
    """Exercise the PS requirements and deployment boundaries, not anecdotes."""
    waveform_cases: list[dict[str, object]] = []
    for scenario_id in SCENARIO_PRESETS:
        environment = scenario_environment(scenario_id)
        for modulation in SUPPORTED_MODULATIONS:
            for requested_window in SUPPORTED_WINDOWS:
                plan = adapt_transmit_plan(environment, modulation=modulation, window=requested_window)
                exact = exact_pulse_metrics(plan, full=False)
                result = run_simulation(
                    {
                        "preview_samples": 128,
                        "output_mode": "adaptive_pulse",
                        "transmit": {"modulation": modulation, "window": requested_window},
                        "sensors": [{"frequency_hz": plan["center_frequency_hz"], "enabled": True}],
                        "environment": environment,
                    }
                )
                assert result["hardware"]["waveform"] == f"adaptive {modulation.upper()} pulse"
                assert result["sonar"]["window"] == ("rect" if modulation == "bpsk" else requested_window)
                assert math.isfinite(float(exact["spectrum_peak_hz"]))
                waveform_cases.append(
                    {
                        "scenario": scenario_id,
                        "modulation": modulation,
                        "window_requested": requested_window,
                        "window_effective": plan["window"],
                        "sample_count": exact["sample_count"],
                        "spectrum_peak_hz": exact["spectrum_peak_hz"],
                        "detection_margin_db": result["sonar"]["detection_margin_db"],
                    }
                )

    behavior_cases = 0
    for behavior in ("tone", "chirp_up", "chirp_down", "burst", "dropout"):
        for algorithm in ("weighted_fusion", "median_vote", "peak_pick", "coherent_mean"):
            result = run_simulation(
                {
                    "algorithm": algorithm,
                    "preview_samples": 128,
                    "sensors": [{"frequency_hz": 220_000, "enabled": True, "behavior": behavior}],
                }
            )
            assert result["sensor_rows"][0]["behavior"] == behavior
            assert 100_000 <= result["hardware"]["actual_frequency_hz"] <= 500_000
            behavior_cases += 1

    hardware_cases = 0
    for hardware in (
        {"clock_hz": 1_000_000, "phase_bits": 12, "dac_bits": 4, "vref_v": 0.5, "filter_cutoff_hz": 100_000, "filter_order": 1, "resistor_tolerance_pct": 0},
        {"clock_hz": 100_000_000, "phase_bits": 48, "dac_bits": 16, "vref_v": 5, "filter_cutoff_hz": 5_000_000, "filter_order": 4, "resistor_tolerance_pct": 5},
    ):
        result = run_simulation(
            {
                "preview_samples": 128,
                "output_mode": "adaptive_pulse",
                "transmit": {"modulation": "lfm", "window": "hann"},
                "hardware": hardware,
                "sensors": [{"frequency_hz": 350_000, "enabled": True}],
            }
        )
        assert result["hardware"]["phase_bits"] in (12, 48)
        assert 4 <= result["hardware"]["dac_bits"] <= 16
        hardware_cases += 1

    fault_payloads = [
        {"sensors": [{"enabled": False}]},
        {"transmit": {"modulation": "ask"}, "sensors": [{"enabled": True}]},
        {"transmit": {"window": "kaiser"}, "sensors": [{"enabled": True}]},
        {
            "sensors": [{"enabled": True}],
            "connections": [
                {"from": "algorithm", "to": "dds"},
                {"from": "dds", "to": "r2r"},
                {"from": "r2r", "to": "filter"},
                {"from": "filter", "to": "probe"},
            ],
        },
    ]
    fault_results = [_expected_failure(payload) for payload in fault_payloads]
    assert all(result["status"] == "expected_failure" for result in fault_results)

    realtime: dict[str, object] = {}
    stream_frames = [
        {"label": "clear", "environment": scenario_environment("clear_shallow_reef"), "transmit": {"window": "rect"}},
        {"label": "boundary muddy input while clear", "environment": scenario_environment("boundary_muddy"), "transmit": {"window": "hamming"}},
        {"label": "muddy", "environment": scenario_environment("muddy_estuary"), "transmit": {"window": "hann"}},
        {"label": "boundary clear side", "environment": scenario_environment("boundary_clear"), "transmit": {"window": "blackman"}},
        {"label": "invalid waveform frame", "transmit": {"modulation": "unsupported"}},
        {"label": "sensor dropout", "dropout_indices": [0]},
        {"label": "recovered", "environment": scenario_environment("clear_shallow_reef")},
    ]
    for modulation in SUPPORTED_MODULATIONS:
        stream = run_realtime(
            {
                "frame_period_ms": 100,
                "base": {
                    "preview_samples": 128,
                    "transmit": {"modulation": modulation, "window": "hann"},
                    "sensors": [{"frequency_hz": 200_000, "enabled": True}],
                    "environment": scenario_environment("clear_shallow_reef"),
                },
                "frames": stream_frames,
            }
        )
        assert stream["transitions"]
        assert stream["faults"]
        assert stream["frames"][0]["status"] == "ok"
        assert stream["frames"][1]["classification"] == "clear_shallow_reef"
        assert stream["frames"][3]["classification"] == "muddy_estuary"
        assert {stream["frames"][index]["window_requested"] for index in range(4)} == set(SUPPORTED_WINDOWS)
        realtime[modulation] = {
            "frames": stream["frame_count"],
            "transitions": len(stream["transitions"]),
            "faults": len(stream["faults"]),
            "all_deadlines_met": stream["all_deadlines_met"],
        }

    return {
        "scenario_ids": list(SCENARIO_PRESETS),
        "scenario_count": len(SCENARIO_PRESETS),
        "waveform_modes": list(SUPPORTED_MODULATIONS),
        "window_modes": list(SUPPORTED_WINDOWS),
        "waveform_cases": len(waveform_cases),
        "waveform_case_examples": waveform_cases[:6],
        "sensor_behavior_cases": behavior_cases,
        "hardware_boundary_cases": hardware_cases,
        "fault_cases": len(fault_results),
        "realtime": realtime,
    }


def main() -> dict[str, object]:
    scenarios = [run_scenario(scenario_id) for scenario_id in SCENARIO_PRESETS]
    report = {
        "problem_statement": "SIH26058",
        "controller": "RP2040 filters/median-fuses environmental ADC readings; fixed-point lookup with hysteresis selects the profile; SLG47910 FPGA performs deterministic DDS pulse synthesis.",
        "scenarios": scenarios,
        "coverage": run_coverage_matrix(),
    }
    (P.OUT / "sim6_scenario_report.json").write_text(json.dumps(report, indent=2))

    fig, axes = plt.subplots(2, 2, figsize=(14, 8.5))
    labels = [scenario["label"].replace("Entering ", "") for scenario in scenarios]
    x = np.arange(len(labels))
    margins = [[scenario["comparison"][key]["detection_margin_db"] for scenario in scenarios] for key in ("fixed_low_band", "fixed_high_band", "adaptive")]
    resolutions = [[scenario["comparison"][key]["range_resolution_m"] * 100 for scenario in scenarios] for key in ("fixed_low_band", "fixed_high_band", "adaptive")]
    width = 0.24
    for offset, (name, values) in enumerate(zip(("fixed low", "fixed high", "adaptive"), margins)):
        axes[0, 0].bar(x + (offset - 1) * width, values, width, label=name)
    axes[0, 0].axhline(0, color="black", lw=.8)
    axes[0, 0].set_ylabel("dB"); axes[0, 0].set_title("Predicted detection margin at scenario range", loc="left", fontsize=10); axes[0, 0].set_xticks(x, labels, rotation=35, ha="right"); axes[0, 0].legend(fontsize=8); axes[0, 0].grid(axis="y", alpha=.25)
    for offset, (name, values) in enumerate(zip(("fixed low", "fixed high", "adaptive"), resolutions)):
        axes[0, 1].bar(x + (offset - 1) * width, values, width, label=name)
    axes[0, 1].set_ylabel("cm"); axes[0, 1].set_title("Range resolution (lower is finer)", loc="left", fontsize=10); axes[0, 1].set_xticks(x, labels, rotation=35, ha="right"); axes[0, 1].grid(axis="y", alpha=.25)
    for scenario in scenarios:
        pulse = scenario["exact_waveform"]["pulse_preview"]
        time_ms = np.linspace(0, scenario["shrike_lite_adaptation"]["pulse_duration_ms"], len(pulse))
        axes[1, 0].plot(time_ms, pulse, label=scenario["label"].replace("Entering ", ""))
    axes[1, 0].set_xlabel("pulse time [ms]"); axes[1, 0].set_ylabel("normalised DAC"); axes[1, 0].set_title("Exact selected LFM pulse preview", loc="left", fontsize=10); axes[1, 0].legend(fontsize=8, ncol=2); axes[1, 0].grid(alpha=.25)
    centers = [scenario["shrike_lite_adaptation"]["center_frequency_hz"] / 1000 for scenario in scenarios]
    axes[1, 1].bar(labels, centers, color="tab:blue")
    axes[1, 1].set_ylabel("kHz"); axes[1, 1].set_title("Selected centre frequency", loc="left", fontsize=10); axes[1, 1].tick_params(axis="x", labelrotation=35); axes[1, 1].grid(axis="y", alpha=.25)
    fig.suptitle("SIM-6 · SIH26058 adaptive sonar scenarios", x=.06, ha="left", fontsize=12)
    fig.tight_layout(); fig.savefig(P.OUT / "sim6_scenario_comparison.png", dpi=115); plt.close(fig)
    return report


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
