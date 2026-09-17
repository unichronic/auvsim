"""Browser and HTTP edge-case coverage for the local signal-lab GUI."""

import json
import math

from playwright.sync_api import Page, sync_playwright


BASE_URL = "http://127.0.0.1:8765"
STORAGE_KEY = "presilicon-bench-gui-v1"
DEFAULT_PLUGIN = """// bench-v1 software adapter
void on_measurement(struct bench_frame *frame) {
    bench_set_algorithm_from_config(frame);
    bench_write_frequency(frame->estimated_hz);
}"""


def wait_complete(page: Page) -> None:
    page.wait_for_function("document.querySelector('#run-status').textContent.includes('Complete')")


def run_and_expect_error(page: Page, text: str) -> None:
    page.locator("#run-button").click()
    page.wait_for_function("document.querySelector('#run-status').textContent.includes('Simulation error')")
    assert text.lower() in page.locator("#run-status").inner_text().lower()
    assert page.locator("#run-button").is_enabled()


def main() -> None:
    errors: list[str] = []
    capture_console_errors = {"enabled": True}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path="/usr/bin/google-chrome")
        context = browser.new_context(viewport={"width": 1440, "height": 1200})

        def watch(page: Page) -> None:
            def handle_console(message) -> None:
                if capture_console_errors["enabled"] and message.type == "error":
                    errors.append(f"console: {message.text}")

            page.on("console", handle_console)
            page.on("pageerror", lambda error: errors.append(f"page: {error}"))

        page = context.new_page()
        watch(page)
        page.goto(BASE_URL, wait_until="networkidle")
        page.evaluate("localStorage.clear()")
        page.reload(wait_until="networkidle")
        wait_complete(page)

        assert page.locator(".node.sensor").count() == 4
        assert page.locator(".circuit-stage").count() == 4
        assert page.locator(".connection-row").count() == 8
        assert page.locator(".workflow-step").count() == 4
        assert page.locator(".work-area .software-panel").count() == 1
        assert page.locator(".workflow-step").evaluate_all("els => els.map(el => el.getAttribute('href'))") == ["#board", "#program-panel", "#hardware-circuit", "#results-panel"]
        assert page.locator('[data-sensor-field="behavior"]').evaluate_all("els => els.map(el => el.value)") == ["tone", "chirp_up", "burst", "dropout"]
        assert "kHz" in page.locator("#metric-frequency").inner_text()
        assert page.locator("#software-verdict").inner_text() == "Contract passed"
        assert page.locator("#hardware-verdict").inner_text() == "8 connections valid"
        assert page.locator("#probe-voltage").inner_text().endswith("Vpk")
        assert page.locator("#deployment-chip").inner_text() == "LOCAL / NO EXTERNAL UPLOAD"

        # Environmental controls are visible, persist with the bench, and are
        # included in the complete run instead of being decorative settings.
        assert page.locator("#environment-panel").count() == 1
        assert page.locator("#environment-sound-speed").inner_text().endswith("m/s")
        assert page.locator("#mission-scenario").input_value() == "custom"
        assert page.locator("#environment-turbidity").input_value() == "0"
        assert page.locator("#mission-scenario option").count() == 13
        assert page.locator("#transmit-modulation option").count() == 3
        assert page.locator("#transmit-window option").count() == 4

        # Every PS waveform family reaches the full output path. Phase-coded
        # mode reports the safe rectangular-envelope normalization.
        page.locator("#transmit-modulation").select_option("geom")
        page.locator("#transmit-window").select_option("hamming")
        page.locator("#run-button").click()
        wait_complete(page)
        assert "adaptive GEOM pulse" in page.locator("#hardware-checks").inner_text()
        page.locator("#transmit-modulation").select_option("bpsk")
        page.locator("#transmit-window").select_option("blackman")
        page.locator("#run-button").click()
        wait_complete(page)
        assert "adaptive BPSK pulse" in page.locator("#hardware-checks").inner_text()
        assert "BPSK" in page.locator("#sonar-details").inner_text()
        page.locator("#transmit-modulation").select_option("lfm")
        page.locator("#transmit-window").select_option("hann")

        # The hosted-equivalent frame stream covers all environment classes,
        # waveform transitions, and a recoverable dropout.
        page.locator("#realtime-run").click()
        page.wait_for_function("document.querySelector('#realtime-readout').textContent.includes('frames processed')")
        assert "Realtime coverage complete" in page.locator("#run-status").inner_text()
        assert "2 recoverable fault(s)" in page.locator("#realtime-readout").inner_text()
        assert "4 windows" in page.locator("#realtime-readout").inner_text()

        # The two PS scenarios load real environment inputs and select different
        # adaptive transmit profiles. The selected scenario must reach the API.
        page.locator("#mission-scenario").select_option("muddy_estuary")
        page.locator("#load-scenario").click()
        assert page.locator("#environment-turbidity").input_value() == "250"
        assert "High suspended sediment" in page.locator("#scenario-description").inner_text()
        assert "Muddy Estuary" in page.locator("#workflow-input-detail").inner_text()
        page.locator("#run-button").click()
        wait_complete(page)
        assert "adaptive LFM 100–200 kHz output probe" in page.locator("#result-summary").inner_text()
        assert page.locator("#metric-frequency").inner_text() == "150.00 kHz"
        assert page.locator("#sonar-verdict").inner_text().startswith("PASS")
        assert page.locator("#sonar-details").inner_text().startswith("TX · LFM 100.0k–200.0k")
        assert page.locator("#metric-resolution").inner_text().endswith("cm")

        page.locator("#mission-scenario").select_option("clear_shallow_reef")
        page.locator("#load-scenario").click()
        assert page.locator("#environment-turbidity").input_value() == "2"
        page.locator("#run-button").click()
        wait_complete(page)
        assert "adaptive LFM 300–500 kHz output probe" in page.locator("#result-summary").inner_text()
        assert page.locator("#metric-frequency").inner_text() == "400.00 kHz"
        assert page.locator("#sonar-details").inner_text().startswith("TX · LFM 300.0k–500.0k")
        assert page.locator("#metric-resolution").inner_text().endswith("cm")

        page.locator("#environment-temperature").fill("24")
        page.locator("#environment-salinity").fill("30")
        page.locator("#environment-depth").fill("500")
        page.locator("#environment-ph").fill("7.6")
        page.locator("#environment-range").fill("1000")
        page.locator("#environment-noise").fill("40")
        page.locator("#environment-turbidity").fill("90")
        assert page.locator("#mission-scenario").input_value() == "custom"
        changed_speed = page.locator("#environment-sound-speed").inner_text()
        assert changed_speed != "1502.0 m/s"
        page.locator("#run-button").click()
        wait_complete(page)
        assert "m/s water" in page.locator("#probe-details").inner_text()

        # The source file is visible in the main workflow and can replace the example program.
        program = b'''// loaded from the team firmware workspace
void on_measurement(struct bench_frame *frame) {
    bench_set_algorithm("weighted_fusion");
    bench_write_frequency(frame->estimated_hz);
}
'''
        page.locator("#program-file").set_input_files({"name": "fusion_controller.cpp", "mimeType": "text/plain", "buffer": program})
        page.wait_for_function("document.querySelector('#program-file-name').textContent === 'fusion_controller.cpp'")
        assert page.locator("#plugin-language").input_value() == "cpp"
        assert "loaded from the team firmware workspace" in page.locator("#software-code").input_value()
        assert "fusion_controller.cpp" in page.locator("#workflow-program-detail").inner_text()
        page.locator("#run-button").click()
        wait_complete(page)
        assert "fusion_controller.cpp" in page.locator("#software-checks").inner_text()
        page.locator("#program-file").set_input_files({"name": "too-large.c", "mimeType": "text/plain", "buffer": b"x" * 100001})
        page.wait_for_function("document.querySelector('#run-status').textContent.includes('Program file not loaded')")
        assert page.locator("#program-file-name").inner_text() == "fusion_controller.cpp"

        # A modeled behavior can be changed, a recorded trace can be loaded, and the trace can be removed.
        page.locator("#sensor-0-behavior").select_option("chirp_down")
        assert "down-chirp" in page.locator("#sensor-0-source").inner_text().lower()
        page.locator('[data-sensor-file="0"]').set_input_files({"name": "invalid.csv", "mimeType": "text/csv", "buffer": b"time,value\nno data here\n"})
        page.wait_for_function("document.querySelector('#run-status').textContent.includes('Sensor trace not loaded')")
        assert "MODELED" in page.locator("#sensor-0-source").inner_text()
        trace = "time,value\n" + "\n".join(
            f"{index},{math.sin(2 * math.pi * 200000 * index / 10000000):.6f}" for index in range(256)
        )
        page.locator('[data-sensor-file="0"]').set_input_files({"name": "hydrophone_01.csv", "mimeType": "text/csv", "buffer": trace.encode()})
        page.wait_for_function("document.querySelector('#sensor-0-source').textContent.includes('RECORDED')")
        assert "hydrophone_01.csv" in page.locator("#sensor-0-source").inner_text()
        assert "1 recorded" in page.locator("#workflow-input-detail").inner_text()
        page.locator("#run-button").click()
        wait_complete(page)
        assert "recorded" in page.locator("#waveform-caption").inner_text()
        page.locator('[data-clear-sensor-file="0"]').click()
        assert "MODELED" in page.locator("#sensor-0-source").inner_text()

        controls = page.locator("input, select, textarea")
        assert controls.evaluate_all("els => els.every(el => el.labels?.length || el.getAttribute('aria-label'))")
        assert page.locator("button").evaluate_all("els => els.every(el => el.innerText.trim() || el.getAttribute('aria-label'))")

        # Hardware specs, software metadata, and the alternate test scenario all persist into a run.
        page.locator("#hardware-clock").fill("8000000")
        page.locator("#hardware-phase").fill("24")
        page.locator("#hardware-dac").fill("10")
        page.locator("#hardware-vref").fill("2.5")
        page.locator("#hardware-cutoff").fill("600000")
        page.locator("#hardware-order").fill("2")
        page.locator("#hardware-tolerance").fill("0.2")
        page.locator("#plugin-name").fill("Dropout adapter")
        page.locator("#test-scenario").select_option("sensor_dropout")
        page.locator("#run-button").click()
        wait_complete(page)
        assert "3 sensor stream" in page.locator("#result-summary").inner_text()
        assert "24-bit DDS" in page.locator("#hardware-checks").inner_text()
        assert "10-bit DAC" in page.locator("#hardware-checks").inner_text()
        page.reload(wait_until="networkidle")
        wait_complete(page)
        assert float(page.locator("#hardware-clock").input_value()) == 8000000
        assert float(page.locator("#hardware-phase").input_value()) == 24
        assert page.locator("#plugin-name").input_value() == "Dropout adapter"
        assert page.locator("#test-scenario").input_value() == "sensor_dropout"
        assert page.locator("#mission-scenario").input_value() == "custom"
        assert float(page.locator("#environment-temperature").input_value()) == 24
        assert float(page.locator("#environment-depth").input_value()) == 500
        assert float(page.locator("#environment-turbidity").input_value()) == 90
        page.locator('[data-remove-node="sensor-4"]').click()
        assert page.locator(".node.sensor").count() == 3
        assert page.locator(".connection-row").count() == 7
        page.locator('[data-add-kind="sensor"]').click()
        assert page.locator(".node.sensor").count() == 4
        assert page.locator(".connection-row").count() == 8

        capture_console_errors["enabled"] = False
        # Duplicate and self-connections are rejected without changing the graph.
        page.locator("#connection-from").select_option("algorithm")
        page.locator("#connection-to").select_option("dds")
        page.locator("#add-connection").click()
        assert "already exists" in page.locator("#run-status").inner_text()
        page.locator("#connection-from").select_option("algorithm")
        page.locator("#connection-to").select_option("algorithm")
        page.locator("#add-connection").click()
        assert "different endpoints" in page.locator("#run-status").inner_text()
        page.locator("#connection-from").select_option("sensor-1")
        page.locator("#connection-to").select_option("r2r")
        page.locator("#add-connection").click()
        assert "unsupported connection" in page.locator("#run-status").inner_text().lower()
        assert page.locator(".connection-row").count() == 8

        # Keyboard movement updates the saved layout without changing the graph.
        handle = page.locator('[data-node-id="algorithm"] .drag-handle')
        before = handle.evaluate("el => el.closest('.node').style.left")
        handle.focus()
        handle.press("ArrowRight")
        assert handle.evaluate("el => el.closest('.node').style.left") != before
        page.locator("#reset-layout").click()

        # Removing a required physical wire gives a recoverable simulation error.
        page.locator(".connection-row").filter(has_text="Output probe").locator("button").click()
        page.wait_for_function("document.querySelectorAll('#wire-layer .wire').length === 4")
        run_and_expect_error(page, "connect the hardware chain")
        assert page.locator("#metric-frequency").inner_text() == "—"
        page.locator("#connection-from").select_option("filter")
        page.locator("#connection-to").select_option("probe")
        page.locator("#add-connection").click()
        page.wait_for_function("document.querySelectorAll('#wire-layer .wire').length === 5")
        page.locator("#test-scenario").select_option("nominal")
        page.locator("#run-button").click()
        wait_complete(page)

        # Required sensor fields and plugin contract failures never submit stale data.
        page.locator("#sensor-0-frequency").fill("")
        page.locator("#run-button").click()
        page.wait_for_function("document.querySelector('#run-status').textContent.includes('Fix the highlighted')")
        assert page.locator("#sensor-0-frequency").get_attribute("aria-invalid") == "true"
        assert page.locator("#run-button").is_enabled()
        page.locator("#sensor-0-frequency").fill("180000")
        page.locator("#environment-temperature").fill("")
        page.locator("#run-button").click()
        page.wait_for_function("document.querySelector('#run-status').textContent.includes('Fix the highlighted')")
        assert page.locator("#environment-temperature").get_attribute("aria-invalid") == "true"
        assert page.locator("#run-button").is_enabled()
        page.locator("#environment-temperature").fill("24")
        page.locator("#software-code").fill("")
        page.locator("#run-button").click()
        page.wait_for_function("document.querySelector('#run-status').textContent.includes('Fix the highlighted')")
        assert page.locator("#software-code").get_attribute("aria-invalid") == "true"
        assert page.locator("#run-button").is_enabled()
        page.locator("#software-code").fill('void on_measurement(struct bench_frame *frame) { bench_set_algorithm("peak_pick"); }')
        page.locator("#run-button").click()
        wait_complete(page)
        assert "peak pick" in page.locator("#result-summary").inner_text().lower()
        page.locator("#software-code").fill(DEFAULT_PLUGIN)

        # An all-disabled sensor set is an explicit, useful error rather than a blank plot or crash.
        for index in range(page.locator(".toggle-field input").count()):
            page.locator(".toggle-field input").nth(index).uncheck()
        run_and_expect_error(page, "enable at least one sensor")
        page.locator(".toggle-field input").first.check()
        page.locator("#run-button").click()
        wait_complete(page)
        capture_console_errors["enabled"] = True

        # Malformed and hostile saved layouts are sanitized on reload.
        page.evaluate("([key, value]) => localStorage.setItem(key, value)", [STORAGE_KEY, "{"])
        page.reload(wait_until="networkidle")
        wait_complete(page)
        assert page.locator(".node.sensor").count() == 4

        hostile = {
            "sensors": [{"name": "<img src=x onerror=alert(1)>", "frequency_hz": "bad"}, None, {"name": "🙂"}],
            "nodes": ["sensor-1", "sensor-1", "missing"],
            "positions": {"sensor-1": {"left": -999999, "top": 999999}, "algorithm": {"left": "bad", "top": -5}},
            "hardware": {"clock_hz": "bad", "phase_bits": 999, "dac_bits": -4},
            "software": {"plugin_name": "<script>bad</script>", "code": DEFAULT_PLUGIN},
            "connections": [{"from": "sensor-1", "to": "algorithm"}, {"from": "sensor-2", "to": "algorithm"}, {"from": "sensor-3", "to": "algorithm"}, {"from": "algorithm", "to": "dds"}, {"from": "dds", "to": "r2r"}, {"from": "r2r", "to": "filter"}, {"from": "filter", "to": "probe"}],
        }
        page.evaluate("([key, value]) => localStorage.setItem(key, JSON.stringify(value))", [STORAGE_KEY, hostile])
        page.reload(wait_until="networkidle")
        wait_complete(page)
        assert page.locator(".node.sensor").count() == 3
        assert "<img" in page.locator(".node-heading strong").first.inner_text()
        style = page.locator('[data-node-id="algorithm"]').get_attribute("style") or ""
        assert "-" not in style
        assert float(page.locator("#hardware-phase").input_value()) == 48
        assert float(page.locator("#hardware-dac").input_value()) == 4

        # Network failure restores the button and explains that there is no current result.
        page.route("**/api/simulate", lambda route: route.abort())
        capture_console_errors["enabled"] = False
        page.locator("#run-button").click()
        page.wait_for_function("document.querySelector('#run-status').textContent.includes('Simulation error')")
        assert "no current result" in page.locator("#result-summary").inner_text().lower()
        assert page.locator("#run-button").is_enabled()
        page.unroute("**/api/simulate")
        capture_console_errors["enabled"] = True

        # HTTP boundary cases stay 4xx and never leak a server exception.
        assert page.request.get(f"{BASE_URL}/api/status").status == 200
        assert page.request.get(f"{BASE_URL}/missing").status == 404
        headers = {"Content-Type": "application/json"}
        assert page.request.post(f"{BASE_URL}/api/simulate", data="[]", headers=headers).status == 400
        assert page.request.post(f"{BASE_URL}/api/simulate", data=json.dumps({"sensors": list(range(5))}), headers=headers).status == 400
        assert page.request.post(f"{BASE_URL}/api/simulate", data=json.dumps({"sensors": [{"enabled": False}]}), headers=headers).status == 400
        assert page.request.post(f"{BASE_URL}/api/simulate", data=json.dumps({"sensors": [{"enabled": True}], "software": {"code": ""}}), headers=headers).status == 400
        recorded_response = page.request.post(
            f"{BASE_URL}/api/simulate",
            data=json.dumps({
                "sensors": [{
                    "enabled": True,
                    "source": "trace",
                    "source_file": "api_capture.csv",
                    "samples": [math.sin(2 * math.pi * 200000 * index / 10000000) for index in range(256)],
                }]
            }),
            headers=headers,
        )
        assert recorded_response.status == 200
        assert recorded_response.json()["sensor_rows"][0]["source"] == "trace"
        environment_response = page.request.post(
            f"{BASE_URL}/api/simulate",
            data=json.dumps({
                "sensors": [{"enabled": True, "frequency_hz": 200000}],
                "environment": {"temperature_c": 30, "salinity_psu": 30, "depth_m": 500, "ph": 7.5, "range_m": 1000, "ambient_noise_db": 40},
            }),
            headers=headers,
        )
        assert environment_response.status == 200
        environment_result = environment_response.json()
        assert environment_result["environment"]["temperature_c"] == 30
        assert environment_result["environment"]["sound_speed_mps"] > 1500
        assert environment_result["sensor_rows"][0]["environment_applied"] is True
        scenario_response = page.request.post(
            f"{BASE_URL}/api/simulate",
            data=json.dumps({
                "scenario": "muddy_estuary",
                "sensors": [{"enabled": True, "frequency_hz": 150000}],
            }),
            headers=headers,
        )
        assert scenario_response.status == 200
        scenario_result = scenario_response.json()
        assert scenario_result["scenario"] == "muddy_estuary"
        assert scenario_result["environment"]["turbidity_ntu"] == 250
        assert scenario_result["sonar"]["classification"] == "muddy_estuary"
        assert scenario_result["sensor_rows"][0]["environment_applied"] is True
        assert page.request.post(
            f"{BASE_URL}/api/simulate",
            data=json.dumps({"scenario": "not-a-scenario", "sensors": [{"enabled": True}]}),
            headers=headers,
        ).status == 400
        realtime_response = page.request.post(
            f"{BASE_URL}/api/realtime",
            data=json.dumps({
                "frame_period_ms": 100,
                "base": {
                    "sensors": [{"frequency_hz": 200000, "enabled": True}],
                    "environment": {
                        "temperature_c": 24,
                        "salinity_psu": 35,
                        "depth_m": 8,
                        "ph": 8.1,
                        "range_m": 120,
                        "ambient_noise_db": 48,
                        "turbidity_ntu": 2,
                    },
                    "transmit": {"modulation": "bpsk", "window": "hann"},
                },
                "frames": [
                    {"label": "clear", "environment": {"turbidity_ntu": 2}},
                    {"label": "muddy", "environment": {"turbidity_ntu": 250}},
                    {"label": "dropout", "dropout_indices": [0]},
                    {"label": "recovery", "environment": {"turbidity_ntu": 2}},
                ],
            }),
            headers=headers,
        )
        assert realtime_response.status == 200
        realtime_result = realtime_response.json()
        assert realtime_result["mode"] == "realtime_frame_stream"
        assert realtime_result["transitions"]
        assert realtime_result["faults"]
        assert realtime_result["frames"][0]["modulation"] == "bpsk"
        assert realtime_result["frames"][0]["window"] == "rect"
        assert page.request.get(f"{BASE_URL}/api/realtime").status == 405
        unsupported = {"sensors": [{"enabled": True}], "connections": [{"from": "sensor-1", "to": "r2r"}, {"from": "algorithm", "to": "dds"}, {"from": "dds", "to": "r2r"}, {"from": "r2r", "to": "filter"}, {"from": "filter", "to": "probe"}]}
        assert page.request.post(f"{BASE_URL}/api/simulate", data=json.dumps(unsupported), headers=headers).status == 400
        missing_input = {"sensors": [{"enabled": True}], "connections": [{"from": "algorithm", "to": "dds"}, {"from": "dds", "to": "r2r"}, {"from": "r2r", "to": "filter"}, {"from": "filter", "to": "probe"}]}
        assert page.request.post(f"{BASE_URL}/api/simulate", data=json.dumps(missing_input), headers=headers).status == 400
        cyclic = {"sensors": [{"enabled": True}], "connections": [{"from": "sensor-1", "to": "algorithm"}, {"from": "algorithm", "to": "dds"}, {"from": "dds", "to": "r2r"}, {"from": "r2r", "to": "filter"}, {"from": "filter", "to": "probe"}, {"from": "probe", "to": "algorithm"}]}
        assert page.request.post(f"{BASE_URL}/api/simulate", data=json.dumps(cyclic), headers=headers).status == 400

        # Mobile layout keeps the wide circuit board inside its own scroll region.
        mobile_context = browser.new_context(viewport={"width": 390, "height": 844})
        mobile = mobile_context.new_page()
        watch(mobile)
        mobile.goto(BASE_URL, wait_until="networkidle")
        wait_complete(mobile)
        assert mobile.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
        assert mobile.locator(".circuit-stage").count() == 4
        mobile.close()
        mobile_context.close()

        page.close()
        context.close()
        browser.close()
    assert not errors, errors
    print("gui browser and edge-case tests: ok")


if __name__ == "__main__":
    main()
