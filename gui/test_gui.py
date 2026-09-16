"""Browser and HTTP edge-case coverage for the local signal-lab GUI."""

import json

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
        assert "kHz" in page.locator("#metric-frequency").inner_text()
        assert page.locator("#software-verdict").inner_text() == "Contract passed"
        assert page.locator("#hardware-verdict").inner_text() == "8 connections valid"
        assert page.locator("#probe-voltage").inner_text().endswith("Vpk")
        assert page.locator("#deployment-chip").inner_text() == "LOCAL / NO EXTERNAL UPLOAD"

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
