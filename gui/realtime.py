"""Dependency-free frame runner for the deployed adaptation contract.

The physical firmware will own the timer/DMA deadline.  This module exercises
the same frame contract at host speed, including transitions, hysteresis, and
recoverable sensor faults, so a hosted preview cannot be mistaken for a live
hardware loop.
"""

from __future__ import annotations

import time
from typing import Any

try:
    from .simulation import run_simulation
except ImportError:  # pragma: no cover - supports python gui/realtime.py
    from simulation import run_simulation  # type: ignore[no-redef]


MAX_REALTIME_FRAMES = 128
DEFAULT_FRAME_PERIOD_MS = 100.0


def _number(value: Any, default: float) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    return value if value == value and abs(value) != float("inf") else default


def _frame_sensors(base_sensors: Any, frame: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(base_sensors, list) or not base_sensors:
        raise ValueError("realtime base.sensors must contain at least one sensor")
    sensors = [dict(sensor) for sensor in base_sensors if isinstance(sensor, dict)]
    if len(sensors) != len(base_sensors):
        raise ValueError("realtime sensors must be objects")
    overrides = frame.get("sensor_overrides", [])
    if overrides is not None:
        if not isinstance(overrides, list) or len(overrides) > len(sensors):
            raise ValueError("sensor_overrides must be a list no longer than base.sensors")
        for index, override in enumerate(overrides):
            if override is not None:
                if not isinstance(override, dict):
                    raise ValueError("each sensor override must be an object")
                sensors[index].update(override)
    for index in frame.get("dropout_indices", []) or []:
        if not isinstance(index, int) or not 0 <= index < len(sensors):
            raise ValueError("dropout_indices contains an invalid sensor index")
        sensors[index]["enabled"] = False
    return sensors


def run_realtime(payload: dict[str, Any]) -> dict[str, Any]:
    """Run a bounded stream of environmental frames through the bench.

    The endpoint is deliberately request-scoped: Vercel and other stateless
    hosts cannot provide a durable WebSocket or hardware timer.  A physical
    adapter can send the same one-frame shape to its own controller loop.
    """
    if not isinstance(payload, dict):
        raise ValueError("realtime payload must be an object")
    frames = payload.get("frames")
    if not isinstance(frames, list) or not frames:
        raise ValueError("realtime.frames must contain at least one frame")
    if len(frames) > MAX_REALTIME_FRAMES:
        raise ValueError(f"realtime supports at most {MAX_REALTIME_FRAMES} frames per request")
    base = payload.get("base") or {}
    if not isinstance(base, dict):
        raise ValueError("realtime.base must be an object")
    frame_period_ms = max(1.0, min(1000.0, _number(payload.get("frame_period_ms"), DEFAULT_FRAME_PERIOD_MS)))
    deadline_ms = max(0.1, min(frame_period_ms, _number(payload.get("deadline_ms"), frame_period_ms)))
    previous_class: str | None = None
    results: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    faults: list[dict[str, Any]] = []
    last_plan: dict[str, Any] | None = None

    for index, raw_frame in enumerate(frames):
        started = time.perf_counter()
        try:
            if not isinstance(raw_frame, dict):
                raise ValueError(f"realtime frame {index + 1} must be an object")
            environment = base.get("environment") or {}
            if not isinstance(environment, dict):
                raise ValueError("realtime base.environment must be an object")
            frame_environment = raw_frame.get("environment") or {}
            if not isinstance(frame_environment, dict):
                raise ValueError(f"realtime frame {index + 1}.environment must be an object")
            frame_payload = dict(base)
            frame_payload["environment"] = {**environment, **frame_environment}
            frame_payload["sensors"] = _frame_sensors(base.get("sensors"), raw_frame)
            frame_payload["scenario"] = "custom"
            frame_payload["output_mode"] = "adaptive_pulse"
            frame_payload["previous_class"] = previous_class
            transmit = base.get("transmit") or {}
            if not isinstance(transmit, dict):
                raise ValueError("realtime base.transmit must be an object")
            frame_transmit = raw_frame.get("transmit") or {}
            if not isinstance(frame_transmit, dict):
                raise ValueError(f"realtime frame {index + 1}.transmit must be an object")
            frame_payload["transmit"] = {**transmit, **frame_transmit}
            frame_payload["preview_samples"] = min(int(_number(base.get("preview_samples"), 128)), 256)
            result = run_simulation(frame_payload)
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            plan = result["sonar"]
            classification = str(plan["classification"])
            if previous_class and classification != previous_class:
                transitions.append({"frame": index, "from": previous_class, "to": classification})
            previous_class = classification
            last_plan = plan
            results.append(
                {
                    "frame": index,
                    "time_ms": round(index * frame_period_ms, 3),
                    "label": str(raw_frame.get("label") or f"frame {index + 1}"),
                    "status": "ok",
                    "classification": classification,
                    "modulation": plan["modulation"],
                    "window": plan["window"],
                    "window_requested": plan.get("window_requested"),
                    "start_frequency_hz": plan["start_frequency_hz"],
                    "end_frequency_hz": plan["end_frequency_hz"],
                    "pulse_duration_ms": plan["pulse_duration_ms"],
                    "amplitude": plan["amplitude"],
                    "output_frequency_hz": result["hardware"]["actual_frequency_hz"],
                    "detection_margin_db": plan["detection_margin_db"],
                    "detected_at_range": plan["detected_at_range"],
                    "coherence": result["coherence"],
                    "latency_ms": round(elapsed_ms, 3),
                    "deadline_ms": deadline_ms,
                    "deadline_met": elapsed_ms <= deadline_ms,
                }
            )
        except (ValueError, TypeError) as error:
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            fault = {
                "frame": index,
                "time_ms": round(index * frame_period_ms, 3),
                "label": str(raw_frame.get("label") or f"frame {index + 1}") if isinstance(raw_frame, dict) else f"frame {index + 1}",
                "status": "fault",
                "error": str(error),
                "failsafe": "hold_last_plan" if last_plan else "output_disabled",
                "latency_ms": round(elapsed_ms, 3),
                "deadline_ms": deadline_ms,
                "deadline_met": elapsed_ms <= deadline_ms,
            }
            faults.append(fault)
            results.append(fault)

    return {
        "mode": "realtime_frame_stream",
        "frame_count": len(frames),
        "frame_period_ms": frame_period_ms,
        "deadline_ms": deadline_ms,
        "frames": results,
        "transitions": transitions,
        "faults": faults,
        "all_deadlines_met": all(frame["deadline_met"] for frame in results),
        "last_plan": last_plan,
        "physical_timing_note": "host latency is a preview; hardware timer/DMA timing must be measured on the target board",
    }


def self_check() -> None:
    base = {
        "sensors": [{"frequency_hz": 200_000, "enabled": True}],
        "environment": {"temperature_c": 24, "salinity_psu": 35, "depth_m": 10, "ph": 8, "range_m": 100, "ambient_noise_db": 48, "turbidity_ntu": 2},
    }
    result = run_realtime(
        {
            "base": base,
            "frame_period_ms": 100,
            "frames": [
                {"label": "clear", "environment": {"turbidity_ntu": 2}},
                {"label": "muddy", "environment": {"turbidity_ntu": 250}},
                {"label": "sensor dropout", "dropout_indices": [0]},
                {"label": "recovered", "environment": {"turbidity_ntu": 2}},
            ],
        }
    )
    assert result["frame_count"] == 4
    assert result["transitions"]
    assert result["faults"] and result["faults"][0]["failsafe"] == "hold_last_plan"
    assert result["frames"][0]["classification"] == "clear_shallow_reef"
    assert result["frames"][1]["classification"] == "muddy_estuary"
    continued = run_realtime(
        {
            "base": base,
            "frames": [
                {"label": "valid", "environment": {"turbidity_ntu": 2}},
                {"label": "bad modulation", "transmit": {"modulation": "ask"}},
                {"label": "bad dropout index", "dropout_indices": [3]},
                {"label": "continued", "environment": {"turbidity_ntu": 250}},
            ],
        }
    )
    assert [frame["status"] for frame in continued["frames"]] == ["ok", "fault", "fault", "ok"]
    assert continued["frames"][-1]["classification"] == "muddy_estuary"
    print("realtime frame self-check: ok")


if __name__ == "__main__":
    self_check()
