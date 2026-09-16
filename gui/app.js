const STORAGE_KEY = "presilicon-bench-gui-v1";

const DEFAULT_SENSORS = [
  { name: "Sensor 1", frequency_hz: 180000, amplitude: 0.92, phase_deg: 0, noise_db: 48, enabled: true, color: "#67d7ce" },
  { name: "Sensor 2", frequency_hz: 205000, amplitude: 0.76, phase_deg: 28, noise_db: 48, enabled: true, color: "#6d9fff" },
  { name: "Sensor 3", frequency_hz: 198000, amplitude: 0.64, phase_deg: -18, noise_db: 48, enabled: true, color: "#b98ff7" },
  { name: "Sensor 4", frequency_hz: 350000, amplitude: 0.28, phase_deg: 55, noise_db: 42, enabled: true, color: "#ef826c" },
];

const DEFAULT_POSITIONS = {
  "sensor-1": { left: 4, top: 5 },
  "sensor-2": { left: 4, top: 53 },
  "sensor-3": { left: 23, top: 5 },
  "sensor-4": { left: 23, top: 53 },
  algorithm: { left: 47, top: 33 },
  hardware: { left: 75, top: 33 },
};

const ALGORITHM_LABELS = {
  weighted_fusion: "Weighted fusion",
  median_vote: "Median vote",
  peak_pick: "Peak pick",
  coherent_mean: "Coherent mean",
};

const DEFAULT_HARDWARE = {
  clock_hz: 10000000,
  phase_bits: 32,
  dac_bits: 8,
  vref_v: 3.3,
  filter_cutoff_hz: 700000,
  filter_order: 3,
  resistor_tolerance_pct: 0.1,
};

const DEFAULT_SOFTWARE = {
  plugin_name: "Signal fusion adapter",
  language: "c",
  entrypoint: "on_measurement",
  test_scenario: "nominal",
  code: `// bench-v1 software adapter
void on_measurement(struct bench_frame *frame) {
    bench_set_algorithm_from_config(frame);
    bench_write_frequency(frame->estimated_hz);
}`,
};

const HARDWARE_STAGES = [
  { id: "dds", label: "32-bit DDS", meta: "synthesise", accent: "coral" },
  { id: "r2r", label: "8-bit R-2R", meta: "convert", accent: "amber" },
  { id: "filter", label: "Reconstruction filter", meta: "condition", accent: "blue" },
  { id: "probe", label: "Output probe", meta: "observe", accent: "aqua" },
];

const DEFAULT_CONNECTIONS = [
  { from: "sensor-1", to: "algorithm" },
  { from: "sensor-2", to: "algorithm" },
  { from: "sensor-3", to: "algorithm" },
  { from: "sensor-4", to: "algorithm" },
  { from: "algorithm", to: "dds" },
  { from: "dds", to: "r2r" },
  { from: "r2r", to: "filter" },
  { from: "filter", to: "probe" },
];

const state = {
  sensors: DEFAULT_SENSORS.map((sensor) => ({ ...sensor })),
  nodes: ["sensor-1", "sensor-2", "sensor-3", "sensor-4", "algorithm", "hardware"],
  positions: structuredClone(DEFAULT_POSITIONS),
  algorithm: "weighted_fusion",
  hardware: { ...DEFAULT_HARDWARE },
  software: { ...DEFAULT_SOFTWARE },
  connections: DEFAULT_CONNECTIONS.map((connection) => ({ ...connection })),
};

function isAllowedConnection(from, to) {
  return (typeof from === "string" && from.startsWith("sensor-") && to === "algorithm")
    || (from === "algorithm" && to === "dds")
    || (from === "dds" && to === "r2r")
    || (from === "r2r" && to === "filter")
    || (from === "filter" && to === "probe");
}

const board = document.querySelector("#board");
const nodes = document.querySelector("#nodes");
const wireLayer = document.querySelector("#wire-layer");
const dropHint = document.querySelector("#drop-hint");
const status = document.querySelector("#run-status");
const runButton = document.querySelector("#run-button");
const deploymentChip = document.querySelector("#deployment-chip");
const circuitChain = document.querySelector("#circuit-chain");
const connectionFrom = document.querySelector("#connection-from");
const connectionTo = document.querySelector("#connection-to");
const connectionList = document.querySelector("#connection-list");

function setDeploymentStatus() {
  if (!deploymentChip) return;
  const localHosts = new Set(["localhost", "127.0.0.1", "::1"]);
  deploymentChip.lastChild.textContent = localHosts.has(window.location.hostname)
    ? " LOCAL / NO EXTERNAL UPLOAD"
    : " TEAM / API INPUTS";
}

function finiteNumber(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function booleanValue(value, fallback) {
  if (typeof value === "boolean") return value;
  if (typeof value === "string") {
    if (["", "0", "false", "no", "off"].includes(value.trim().toLowerCase())) return false;
    if (["1", "true", "yes", "on"].includes(value.trim().toLowerCase())) return true;
  }
  return value == null ? fallback : Boolean(value);
}

function boundedPosition(nodeId, left, top) {
  const fallback = DEFAULT_POSITIONS[nodeId] || { left: 5, top: 5 };
  const maxTop = nodeId.startsWith("sensor-") ? 75 : 84;
  return {
    left: Math.max(1, Math.min(86, finiteNumber(left, fallback.left))),
    top: Math.max(2, Math.min(maxTop, finiteNumber(top, fallback.top))),
  };
}

function normalizeState() {
  const sensors = Array.isArray(state.sensors) ? state.sensors : [];
  state.sensors = sensors.slice(0, 4).map((sensor, index) => {
    const base = DEFAULT_SENSORS[index];
    const source = sensor && typeof sensor === "object" ? sensor : {};
    return {
      ...base,
      ...source,
      name: typeof source.name === "string" && source.name.trim() ? source.name.trim().slice(0, 32) : base.name,
      frequency_hz: Math.max(100000, Math.min(500000, finiteNumber(source.frequency_hz, base.frequency_hz))),
      amplitude: Math.max(0.05, Math.min(1, finiteNumber(source.amplitude, base.amplitude))),
      phase_deg: Math.max(-180, Math.min(180, finiteNumber(source.phase_deg, base.phase_deg))),
      noise_db: Math.max(0, Math.min(90, finiteNumber(source.noise_db, base.noise_db))),
      enabled: booleanValue(source.enabled, base.enabled),
      color: base.color,
    };
  });
  const sensorIds = state.sensors.map((_, index) => `sensor-${index + 1}`);
  const valid = new Set([...sensorIds, "algorithm", "hardware"]);
  const ordered = [];
  for (const id of Array.isArray(state.nodes) ? state.nodes : []) {
    if (valid.has(id) && !ordered.includes(id)) ordered.push(id);
  }
  for (const id of [...sensorIds, "algorithm", "hardware"]) {
    if (!ordered.includes(id)) ordered.push(id);
  }
  state.nodes = ordered;

  const hardware = state.hardware && typeof state.hardware === "object" ? state.hardware : {};
  state.hardware = {
    clock_hz: Math.max(1000000, Math.min(100000000, finiteNumber(hardware.clock_hz, DEFAULT_HARDWARE.clock_hz))),
    phase_bits: Math.round(Math.max(12, Math.min(48, finiteNumber(hardware.phase_bits, DEFAULT_HARDWARE.phase_bits)))),
    dac_bits: Math.round(Math.max(4, Math.min(16, finiteNumber(hardware.dac_bits, DEFAULT_HARDWARE.dac_bits)))),
    vref_v: Math.max(0.5, Math.min(5, finiteNumber(hardware.vref_v, DEFAULT_HARDWARE.vref_v))),
    filter_cutoff_hz: Math.max(100000, Math.min(5000000, finiteNumber(hardware.filter_cutoff_hz, DEFAULT_HARDWARE.filter_cutoff_hz))),
    filter_order: Math.round(Math.max(1, Math.min(4, finiteNumber(hardware.filter_order, DEFAULT_HARDWARE.filter_order)))),
    resistor_tolerance_pct: Math.max(0, Math.min(5, finiteNumber(hardware.resistor_tolerance_pct, DEFAULT_HARDWARE.resistor_tolerance_pct))),
  };

  const software = state.software && typeof state.software === "object" ? state.software : {};
  state.software = {
    plugin_name: typeof software.plugin_name === "string" && software.plugin_name.trim() ? software.plugin_name.trim().slice(0, 64) : DEFAULT_SOFTWARE.plugin_name,
    language: ["c", "cpp", "python"].includes(software.language) ? software.language : DEFAULT_SOFTWARE.language,
    entrypoint: typeof software.entrypoint === "string" && software.entrypoint.trim() ? software.entrypoint.trim().slice(0, 64) : DEFAULT_SOFTWARE.entrypoint,
    test_scenario: ["nominal", "sensor_dropout", "low_coherence"].includes(software.test_scenario) ? software.test_scenario : DEFAULT_SOFTWARE.test_scenario,
    code: typeof software.code === "string" && software.code.trim() ? software.code.slice(0, 100000) : DEFAULT_SOFTWARE.code,
  };

  const validConnectionIds = new Set([...sensorIds, "algorithm", "dds", "r2r", "filter", "probe"]);
  const connections = Array.isArray(state.connections) ? state.connections : DEFAULT_CONNECTIONS;
  const seen = new Set();
  state.connections = connections.filter((connection) => {
    if (!connection || !validConnectionIds.has(connection.from) || !validConnectionIds.has(connection.to) || connection.from === connection.to || !isAllowedConnection(connection.from, connection.to)) return false;
    const key = `${connection.from}->${connection.to}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  }).map((connection) => ({ from: connection.from, to: connection.to }));
}

function loadLayout() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
    if (!saved) { normalizeState(); return; }
    if (Array.isArray(saved.sensors) && saved.sensors.length) state.sensors = saved.sensors.slice(0, 4);
    if (saved.algorithm && ALGORITHM_LABELS[saved.algorithm]) state.algorithm = saved.algorithm;
    if (saved.hardware && typeof saved.hardware === "object") state.hardware = { ...state.hardware, ...saved.hardware };
    if (saved.software && typeof saved.software === "object") state.software = { ...state.software, ...saved.software };
    if (Array.isArray(saved.connections)) state.connections = saved.connections;
    if (Array.isArray(saved.nodes)) {
      state.nodes = saved.nodes.filter((id) => id === "algorithm" || id === "hardware" || (/^sensor-[1-4]$/.test(id) && Number(id.split("-")[1]) <= state.sensors.length));
    } else if (state.sensors.length < 4) {
      state.nodes = state.nodes.filter((id) => !id.startsWith("sensor-") || Number(id.split("-")[1]) <= state.sensors.length);
    }
    if (saved.positions && typeof saved.positions === "object") {
      const positionIds = new Set([
        ...Array.from({ length: 4 }, (_, index) => `sensor-${index + 1}`),
        "algorithm",
        "hardware",
      ]);
      for (const [id, position] of Object.entries(saved.positions)) {
        if (positionIds.has(id) && position && typeof position === "object") state.positions[id] = boundedPosition(id, position.left, position.top);
      }
    }
  } catch {
    try { localStorage.removeItem(STORAGE_KEY); } catch { /* storage may be disabled */ }
  }
  normalizeState();
}

function saveLayout() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      sensors: state.sensors,
      nodes: state.nodes,
      algorithm: state.algorithm,
      positions: state.positions,
      hardware: state.hardware,
      software: state.software,
      connections: state.connections,
    }));
  } catch {
    // The in-memory bench still works when a browser blocks local storage.
  }
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[character]);
}

function dragGrip() {
  return '<span class="drag-grip" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i></span>';
}

function sensorMarkup(sensor, index) {
  const sensorId = `sensor-${index + 1}`;
  return `
    <article class="node sensor" data-node-id="${sensorId}" data-kind="sensor" aria-label="${escapeHtml(sensor.name)} sensor input">
      <div class="node-top">
        <span class="drag-handle" draggable="true" tabindex="0" role="button" aria-label="Move ${escapeHtml(sensor.name)}">${dragGrip()} drag to move</span>
        <button class="node-remove" type="button" data-remove-node="${sensorId}" aria-label="Remove ${escapeHtml(sensor.name)}" title="Remove sensor">×</button>
      </div>
      <div class="node-heading"><strong>${escapeHtml(sensor.name)}</strong><span>CH ${index + 1}</span></div>
      <div class="node-body">
        <div class="field-grid">
          <div class="field"><label for="sensor-${index}-frequency">frequency / Hz</label><input id="sensor-${index}-frequency" data-sensor-index="${index}" data-sensor-field="frequency_hz" type="number" min="100000" max="500000" step="1000" value="${sensor.frequency_hz}" required></div>
          <div class="field"><label for="sensor-${index}-amplitude">amplitude</label><input id="sensor-${index}-amplitude" data-sensor-index="${index}" data-sensor-field="amplitude" type="number" min="0.05" max="1" step="0.01" value="${sensor.amplitude}" required></div>
          <div class="field"><label for="sensor-${index}-phase">phase / deg</label><input id="sensor-${index}-phase" data-sensor-index="${index}" data-sensor-field="phase_deg" type="number" min="-180" max="180" step="1" value="${sensor.phase_deg}" required></div>
          <div class="field"><label for="sensor-${index}-noise">noise / dBc</label><input id="sensor-${index}-noise" data-sensor-index="${index}" data-sensor-field="noise_db" type="number" min="0" max="90" step="1" value="${sensor.noise_db}" required></div>
        </div>
        <label class="toggle-field"><input data-sensor-index="${index}" data-sensor-field="enabled" type="checkbox" ${sensor.enabled ? "checked" : ""}> include this channel</label>
        <div class="node-foot"><i></i> deterministic input stream</div>
      </div>
    </article>`;
}

function algorithmMarkup() {
  return `
    <article class="node algorithm" data-node-id="algorithm" data-kind="algorithm" aria-label="Algorithm stage">
      <div class="node-top">
        <span class="drag-handle" draggable="true" tabindex="0" role="button" aria-label="Move algorithm stage">${dragGrip()} drag to move</span>
        <button class="node-remove" type="button" disabled aria-label="Algorithm stage is required">×</button>
      </div>
      <div class="node-heading"><strong>Algorithm</strong><span>DECIDE</span></div>
      <div class="node-body">
        <div class="field field-wide"><label for="algorithm-select">selection rule</label><select id="algorithm-select">
          ${Object.entries(ALGORITHM_LABELS).map(([value, label]) => `<option value="${value}" ${state.algorithm === value ? "selected" : ""}>${label}</option>`).join("")}
        </select></div>
        <p class="algorithm-copy"><strong>Input:</strong> estimated frequency + RMS from each enabled sensor.</p>
        <div class="node-foot"><i></i> active decision stage</div>
      </div>
    </article>`;
}

function hardwareMarkup() {
  return `
    <article class="node hardware" data-node-id="hardware" data-kind="hardware" aria-label="Hardware output stage">
      <div class="node-top">
        <span class="drag-handle" draggable="true" tabindex="0" role="button" aria-label="Move hardware output stage">${dragGrip()} drag to move</span>
        <button class="node-remove" type="button" disabled aria-label="Hardware output stage is required">×</button>
      </div>
      <div class="node-heading"><strong>Hardware output</strong><span>EMIT</span></div>
      <div class="node-body">
        <p class="hardware-copy"><strong>32-bit DDS</strong> phase accumulator feeding an <strong>8-bit R-2R</strong> output preview.</p>
        <div class="field-grid">
          <div class="field"><span>clock / Hz</span><input type="text" value="10,000,000" readonly aria-label="Hardware clock frequency, 10 million hertz"></div>
          <div class="field"><span>DAC / bits</span><input type="text" value="8" readonly aria-label="DAC resolution, 8 bits"></div>
        </div>
        <div class="node-foot"><i></i> output frequency probe</div>
      </div>
    </article>`;
}

function componentLabel(id) {
  if (id.startsWith("sensor-")) return `Sensor ${id.split("-")[1]}`;
  if (id === "algorithm") return "Algorithm stage";
  return HARDWARE_STAGES.find((stage) => stage.id === id)?.label || id;
}

function hardwareStageMarkup(stage) {
  const fields = {
    dds: `
      <div class="circuit-fields">
        <div class="field"><label for="hardware-clock">clock / Hz</label><input id="hardware-clock" data-hardware-field="clock_hz" type="number" min="1000000" max="100000000" step="100000" required></div>
        <div class="field"><label for="hardware-phase">phase bits</label><input id="hardware-phase" data-hardware-field="phase_bits" type="number" min="12" max="48" step="1" required></div>
      </div>`,
    r2r: `
      <div class="circuit-fields">
        <div class="field"><label for="hardware-dac">DAC bits</label><input id="hardware-dac" data-hardware-field="dac_bits" type="number" min="4" max="16" step="1" required></div>
        <div class="field"><label for="hardware-vref">Vref / V</label><input id="hardware-vref" data-hardware-field="vref_v" type="number" min="0.5" max="5" step="0.1" required></div>
        <div class="field field-wide"><label for="hardware-tolerance">resistor tolerance / %</label><input id="hardware-tolerance" data-hardware-field="resistor_tolerance_pct" type="number" min="0" max="5" step="0.1" required></div>
      </div>`,
    filter: `
      <div class="circuit-fields">
        <div class="field"><label for="hardware-cutoff">cutoff / Hz</label><input id="hardware-cutoff" data-hardware-field="filter_cutoff_hz" type="number" min="100000" max="5000000" step="10000" required></div>
        <div class="field"><label for="hardware-order">order</label><input id="hardware-order" data-hardware-field="filter_order" type="number" min="1" max="4" step="1" required></div>
      </div>`,
    probe: '<p class="circuit-copy">Reads the post-filter analogue output and exposes frequency, voltage, and quantisation error to the test report.</p>',
  };
  return `<article class="circuit-stage ${stage.accent}" data-circuit-stage="${stage.id}">
    <div class="circuit-stage-top"><span class="stage-mark" aria-hidden="true"></span><span>${stage.meta}</span></div>
    <strong>${stage.label}</strong>
    ${fields[stage.id]}
  </article>`;
}

function renderCircuit() {
  if (!circuitChain) return;
  circuitChain.innerHTML = HARDWARE_STAGES.map(hardwareStageMarkup).join('<span class="circuit-arrow" aria-hidden="true">→</span>');
  document.querySelectorAll("[data-hardware-field]").forEach((input) => {
    const field = input.dataset.hardwareField;
    input.value = state.hardware[field];
    input.addEventListener("input", () => {
      if (!input.checkValidity()) {
        input.setAttribute("aria-invalid", "true");
        input.setAttribute("aria-describedby", "run-status");
        status.textContent = "Fix the highlighted hardware specification before running.";
        return;
      }
      input.removeAttribute("aria-invalid");
      input.removeAttribute("aria-describedby");
      state.hardware[field] = Number(input.value);
      saveLayout();
      status.textContent = "Hardware specification changed. Run the co-simulation to apply it.";
    });
  });
  renderConnectionControls();
}

function renderConnectionControls() {
  if (!connectionFrom || !connectionTo || !connectionList) return;
  const sensorIds = state.sensors.map((_, index) => `sensor-${index + 1}`);
  const ids = [...sensorIds, "algorithm", ...HARDWARE_STAGES.map((stage) => stage.id)];
  const options = ids.map((id) => `<option value="${id}">${escapeHtml(componentLabel(id))}</option>`).join("");
  const previousFrom = connectionFrom.value;
  const previousTo = connectionTo.value;
  connectionFrom.innerHTML = options;
  connectionTo.innerHTML = options;
  connectionFrom.value = ids.includes(previousFrom) ? previousFrom : ids[0];
  connectionTo.value = ids.includes(previousTo) ? previousTo : (ids.includes("algorithm") ? "algorithm" : ids[0]);
  connectionList.innerHTML = state.connections.length
    ? state.connections.map((connection, index) => `<div class="connection-row" role="listitem"><span>${escapeHtml(componentLabel(connection.from))}</span><i aria-hidden="true">→</i><span>${escapeHtml(componentLabel(connection.to))}</span><button type="button" data-remove-connection="${index}" aria-label="Remove ${escapeHtml(componentLabel(connection.from))} to ${escapeHtml(componentLabel(connection.to))} connection">×</button></div>`).join("")
    : '<p class="empty-readout">No wires yet. Add the first connection above.</p>';
  connectionList.querySelectorAll("[data-remove-connection]").forEach((button) => button.addEventListener("click", () => {
    state.connections.splice(Number(button.dataset.removeConnection), 1);
    saveLayout();
    renderConnectionControls();
    status.textContent = "Connection removed. Run the co-simulation to validate the circuit.";
  }));
  requestAnimationFrame(updateWires);
}

function renderSoftwareEditor() {
  const fields = {
    "plugin-name": state.software.plugin_name,
    "plugin-language": state.software.language,
    "plugin-entrypoint": state.software.entrypoint,
    "test-scenario": state.software.test_scenario,
    "software-code": state.software.code,
  };
  Object.entries(fields).forEach(([id, value]) => {
    const element = document.querySelector(`#${id}`);
    if (element) element.value = value;
  });
}

function readHardwareState() {
  let valid = true;
  document.querySelectorAll("[data-hardware-field]").forEach((input) => {
    if (!input.checkValidity()) {
      input.setAttribute("aria-invalid", "true");
      input.setAttribute("aria-describedby", "run-status");
      valid = false;
      return;
    }
    input.removeAttribute("aria-invalid");
    input.removeAttribute("aria-describedby");
    state.hardware[input.dataset.hardwareField] = Number(input.value);
  });
  return valid;
}

function readSoftwareState() {
  const code = document.querySelector("#software-code");
  state.software.plugin_name = document.querySelector("#plugin-name")?.value.trim() || DEFAULT_SOFTWARE.plugin_name;
  state.software.language = document.querySelector("#plugin-language")?.value || DEFAULT_SOFTWARE.language;
  state.software.entrypoint = document.querySelector("#plugin-entrypoint")?.value.trim() || DEFAULT_SOFTWARE.entrypoint;
  state.software.test_scenario = document.querySelector("#test-scenario")?.value || DEFAULT_SOFTWARE.test_scenario;
  state.software.code = code?.value || "";
  if (code && !code.checkValidity()) {
    code.setAttribute("aria-invalid", "true");
    code.setAttribute("aria-describedby", "run-status");
    return false;
  }
  if (code) {
    code.removeAttribute("aria-invalid");
    code.setAttribute("aria-describedby", "software-hint");
  }
  return true;
}

function readEditorState() {
  let valid = true;
  document.querySelectorAll("[data-sensor-index][data-sensor-field]").forEach((input) => {
    const index = Number(input.dataset.sensorIndex);
    const field = input.dataset.sensorField;
    if (!state.sensors[index]) return;
    if (input.type === "checkbox") {
      state.sensors[index][field] = input.checked;
      return;
    }
    if (!input.checkValidity()) {
      input.setAttribute("aria-invalid", "true");
      input.setAttribute("aria-describedby", "run-status");
      valid = false;
      return;
    }
    input.removeAttribute("aria-invalid");
    input.removeAttribute("aria-describedby");
    state.sensors[index][field] = Number(input.value);
  });
  const select = document.querySelector("#algorithm-select");
  if (select) state.algorithm = select.value;
  return valid;
}

function positionNode(nodeId, left, top) {
  state.positions[nodeId] = boundedPosition(nodeId, left, top);
  const node = document.querySelector(`[data-node-id="${nodeId}"]`);
  if (node) {
    node.style.left = `${state.positions[nodeId].left}%`;
    node.style.top = `${state.positions[nodeId].top}%`;
  }
  updateWires();
  saveLayout();
}

function makeNodeDraggable(handle) {
  const node = handle.closest(".node");
  handle.addEventListener("dragstart", (event) => {
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", `node:${node.dataset.nodeId}`);
    node.classList.add("dragging");
  });
  handle.addEventListener("dragend", () => node.classList.remove("dragging"));
  handle.addEventListener("keydown", (event) => {
    const step = event.shiftKey ? 5 : 2;
    const position = state.positions[node.dataset.nodeId] || { left: 5, top: 5 };
    const changes = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[event.key];
    if (!changes) return;
    event.preventDefault();
    positionNode(node.dataset.nodeId, position.left + changes[0], position.top + changes[1]);
    status.textContent = `${node.dataset.nodeId} moved. Run the pipeline to refresh the readout.`;
  });
}

function renderBoard() {
  readEditorState();
  nodes.innerHTML = "";
  const sensorCount = state.nodes.filter((id) => id.startsWith("sensor-")).length;
  dropHint.hidden = sensorCount >= 4;
  for (const nodeId of state.nodes) {
    if (nodeId.startsWith("sensor-")) {
      const index = Number(nodeId.split("-")[1]) - 1;
      if (!state.sensors[index]) continue;
      nodes.insertAdjacentHTML("beforeend", sensorMarkup(state.sensors[index], index));
    } else if (nodeId === "algorithm") {
      nodes.insertAdjacentHTML("beforeend", algorithmMarkup());
    } else if (nodeId === "hardware") {
      nodes.insertAdjacentHTML("beforeend", hardwareMarkup());
    }
  }
  document.querySelectorAll(".node").forEach((node) => {
    const position = state.positions[node.dataset.nodeId] || { left: 5, top: 5 };
    node.style.left = `${position.left}%`;
    node.style.top = `${position.top}%`;
  });
  document.querySelectorAll(".drag-handle").forEach(makeNodeDraggable);
  document.querySelectorAll("[data-remove-node]").forEach((button) => button.addEventListener("click", () => removeNode(button.dataset.removeNode)));
  document.querySelectorAll("[data-sensor-field]").forEach((input) => input.addEventListener("input", () => {
    const valid = readEditorState();
    if (valid) {
      saveLayout();
      status.textContent = "Input changed. Run the pipeline to apply it.";
    } else {
      status.textContent = "Fix the highlighted sensor field before running the pipeline.";
    }
  }));
  const select = document.querySelector("#algorithm-select");
  if (select) select.addEventListener("change", () => {
    state.algorithm = select.value;
    saveLayout();
    status.textContent = `${ALGORITHM_LABELS[state.algorithm]} selected. Run the pipeline.`;
  });
  requestAnimationFrame(updateWires);
  renderCircuit();
  saveLayout();
}

function removeNode(nodeId) {
  if (nodeId === "algorithm" || nodeId === "hardware") return;
  if (state.nodes.filter((id) => id.startsWith("sensor-")).length <= 1) {
    status.textContent = "Keep at least one sensor input on the board.";
    return;
  }
  const index = Number(nodeId.split("-")[1]);
  state.connections = state.connections.filter((connection) => connection.from !== nodeId && connection.to !== nodeId).map((connection) => {
    const shift = (id) => {
      if (!id.startsWith("sensor-")) return id;
      const sensorIndex = Number(id.split("-")[1]);
      return sensorIndex > index ? `sensor-${sensorIndex - 1}` : id;
    };
    return { from: shift(connection.from), to: shift(connection.to) };
  });
  state.nodes = state.nodes.filter((id) => id !== nodeId);
  state.sensors.splice(index, 1);
  state.nodes = state.nodes.map((id) => {
    if (!id.startsWith("sensor-")) return id;
    const oldIndex = Number(id.split("-")[1]);
    return oldIndex > index ? `sensor-${oldIndex - 1}` : id;
  });
  const moved = {};
  state.nodes.forEach((id) => { moved[id] = state.positions[id] || DEFAULT_POSITIONS[id] || { left: 4, top: 10 }; });
  state.positions = { ...state.positions, ...moved };
  renderBoard();
  status.textContent = "Sensor removed. Add another from the palette to return to four channels.";
}

function addComponent(kind, clientX, clientY) {
  readEditorState();
  if (kind === "sensor") {
    const sensorCount = state.nodes.filter((id) => id.startsWith("sensor-")).length;
    if (sensorCount >= 4) {
      status.textContent = "The board already has four sensor inputs.";
      return;
    }
    const index = sensorCount;
    state.sensors[index] = { ...DEFAULT_SENSORS[index], name: `Sensor ${index + 1}` };
    const id = `sensor-${index + 1}`;
    state.nodes.unshift(id);
    state.connections.push({ from: id, to: "algorithm" });
    state.positions[id] = index < 2
      ? { left: 4, top: 5 + index * 48 }
      : { left: 23, top: 5 + (index - 2) * 48 };
    renderBoard();
    status.textContent = `${state.sensors[index].name} added. Tune it, then run the pipeline.`;
  } else if (kind === "algorithm") {
    status.textContent = "The live chain already has one algorithm stage; change its selection rule instead.";
  } else if (kind === "hardware") {
    status.textContent = "The live chain already has one hardware output stage.";
  }
  if (clientX !== undefined && clientY !== undefined && kind === "sensor") {
    const boardRect = board.getBoundingClientRect();
    const id = state.nodes.find((nodeId) => nodeId === `sensor-${state.nodes.filter((nodeId) => nodeId.startsWith("sensor-")).length}`);
    if (id) positionNode(id, ((clientX - boardRect.left) / boardRect.width) * 100, ((clientY - boardRect.top) / boardRect.height) * 100);
  }
}

function updateWires() {
  if (!board || !wireLayer) return;
  const boardRect = board.getBoundingClientRect();
  const algorithm = document.querySelector('[data-node-id="algorithm"]');
  const hardware = document.querySelector('[data-node-id="hardware"]');
  if (!algorithm || !hardware || !boardRect.width) return;
  wireLayer.innerHTML = "";
  const centerY = (element) => element.getBoundingClientRect().top - boardRect.top + element.getBoundingClientRect().height / 2;
  const rightX = (element) => element.getBoundingClientRect().right - boardRect.left;
  const leftX = (element) => element.getBoundingClientRect().left - boardRect.left;
  const connections = new Set(state.connections.map((connection) => `${connection.from}->${connection.to}`));
  const draw = (from, to, colour = "") => {
    const x1 = rightX(from);
    const y1 = centerY(from);
    const x2 = leftX(to);
    const y2 = centerY(to);
    const bend = Math.max(26, Math.abs(x2 - x1) * 0.42);
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("class", `wire ${colour}`);
    path.setAttribute("d", `M ${x1} ${y1} C ${x1 + bend} ${y1}, ${x2 - bend} ${y2}, ${x2} ${y2}`);
    wireLayer.appendChild(path);
  };
  const sensorNodes = [...document.querySelectorAll('[data-kind="sensor"]')].sort((a, b) => Number(a.dataset.nodeId.split("-")[1]) - Number(b.dataset.nodeId.split("-")[1]));
  sensorNodes.forEach((sensor) => {
    if (connections.has(`${sensor.dataset.nodeId}->algorithm`)) draw(sensor, algorithm);
  });
  const hardwareChain = ["algorithm->dds", "dds->r2r", "r2r->filter", "filter->probe"];
  if (hardwareChain.every((connection) => connections.has(connection))) draw(algorithm, hardware);
  document.querySelector("#wires").setAttribute("viewBox", `0 0 ${board.clientWidth} ${board.clientHeight}`);
}

function readPayload() {
  const sensorValid = readEditorState();
  const hardwareValid = readHardwareState();
  const softwareValid = readSoftwareState();
  if (!sensorValid || !hardwareValid || !softwareValid) return null;
  const sensors = state.sensors.slice(0, 4).map((sensor) => ({ ...sensor }));
  if (state.software.test_scenario === "sensor_dropout" && sensors.length > 1) sensors[sensors.length - 1].enabled = false;
  if (state.software.test_scenario === "low_coherence" && sensors.length > 1) sensors[sensors.length - 1].frequency_hz = 490000;
  return {
    algorithm: state.algorithm,
    preview_samples: 384,
    sensors,
    hardware: { ...state.hardware },
    software: { ...state.software },
    connections: state.connections.map((connection) => ({ ...connection })),
  };
}

function formatKHz(value) {
  return `${(Number(value) / 1000).toFixed(2)} kHz`;
}

function formatHz(value) {
  return `${(Number(value) / 1000).toFixed(1)}k`;
}

function setMetric(id, value) {
  const element = document.querySelector(`#${id}`);
  if (element) element.textContent = value;
}

function drawWaveform(result) {
  const canvas = document.querySelector("#waveform");
  const context = canvas.getContext("2d");
  const width = canvas.clientWidth || 900;
  const height = canvas.clientHeight || 260;
  const scale = window.devicePixelRatio || 1;
  canvas.width = Math.floor(width * scale);
  canvas.height = Math.floor(height * scale);
  context.setTransform(scale, 0, 0, scale, 0, 0);
  context.clearRect(0, 0, width, height);

  const padding = { top: 13, right: 11, bottom: 22, left: 31 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  context.font = "9px IBM Plex Mono, monospace";
  context.lineWidth = 1;
  context.strokeStyle = "rgba(161, 191, 187, .12)";
  context.fillStyle = "rgba(142, 155, 154, .68)";
  for (let line = 0; line <= 4; line += 1) {
    const y = padding.top + plotHeight * line / 4;
    context.beginPath(); context.moveTo(padding.left, y); context.lineTo(width - padding.right, y); context.stroke();
    context.fillText((1 - line / 2).toFixed(1), 4, y + 3);
  }
  const time = result.series.time_us;
  const x = (index) => padding.left + index / Math.max(time.length - 1, 1) * plotWidth;
  context.fillText(`${time[0].toFixed(0)}μs`, padding.left, height - 5);
  context.fillText(`${time[time.length - 1].toFixed(0)}μs`, width - 40, height - 5);
  const y = (value) => padding.top + (1 - (value + 1) / 2) * plotHeight;

  const series = [
    ["sensor_1", "#67d7ce", 1.1], ["sensor_2", "#6d9fff", 1.1], ["sensor_3", "#b98ff7", 1.1], ["sensor_4", "#ef826c", 1.1],
    ["fused", "#f2b95d", 1.7], ["output", "#f7f3e6", 1.2],
  ];
  for (const [key, colour, lineWidth] of series) {
    const values = result.series[key];
    if (!values) continue;
    context.strokeStyle = colour;
    context.lineWidth = lineWidth;
    context.globalAlpha = key.startsWith("sensor") ? 0.54 : 0.92;
    context.beginPath();
    values.forEach((value, index) => index ? context.lineTo(x(index), y(value)) : context.moveTo(x(index), y(value)));
    context.stroke();
  }
  context.globalAlpha = 1;
  document.querySelector("#waveform-caption").textContent = `${result.active_sensor_names.join(", ")} → ${ALGORITHM_LABELS[result.algorithm]} → ${formatKHz(result.hardware.actual_frequency_hz)} output probe.`;
}

function renderFrequencyBars(result) {
  const container = document.querySelector("#frequency-bars");
  const rows = result.sensor_rows.map((row) => ({ label: row.name, estimate: row.estimated_hz, requested: row.requested_hz, kind: "sensor", enabled: row.enabled }));
  rows.push({ label: "algorithm", estimate: result.algorithm_estimate_hz, requested: result.algorithm_estimate_hz, kind: "algorithm", enabled: true });
  rows.push({ label: "output probe", estimate: result.hardware.actual_frequency_hz, requested: result.algorithm_estimate_hz, kind: "output", enabled: true });
  const max = 500000;
  container.innerHTML = rows.map((row) => {
    const opacity = row.enabled ? "" : " style=\"opacity:.28\"";
    const fill = Math.max(0, Math.min(100, row.estimate / max * 100));
    const requested = Math.max(0, Math.min(100, row.requested / max * 100));
    return `<div class="bar-row ${row.kind}-row"${opacity}>
      <span class="bar-label">${escapeHtml(row.label)}</span>
      <span class="bar-track"><i class="bar-fill" style="width:${fill}%"></i><i class="bar-requested" style="left:${requested}%"></i></span>
      <span class="bar-value">${formatHz(row.estimate)}</span>
    </div>`;
  }).join("");
}

function renderResults(result) {
  setMetric("metric-frequency", formatKHz(result.hardware.actual_frequency_hz));
  setMetric("metric-coherence", `${Math.round(result.coherence * 100)}%`);
  setMetric("metric-ftw", `0x${result.hardware.ftw.toString(16).toUpperCase().padStart(8, "0")}`);
  setMetric("metric-error", `${result.hardware.quantization_error_hz.toFixed(3)} Hz`);
  document.querySelector("#result-summary").textContent = result.summary;
  const softwareVerdict = document.querySelector("#software-verdict");
  if (softwareVerdict) softwareVerdict.textContent = result.software.passed ? "Contract passed" : "Contract failed";
  const softwareChecks = document.querySelector("#software-checks");
  if (softwareChecks) softwareChecks.textContent = `${result.software.plugin_name} · ${result.software.checks.join(" · ")}`;
  const hardwareVerdict = document.querySelector("#hardware-verdict");
  if (hardwareVerdict) hardwareVerdict.textContent = `${result.connections.length} connections valid`;
  const hardwareChecks = document.querySelector("#hardware-checks");
  if (hardwareChecks) hardwareChecks.textContent = `${result.hardware.phase_bits}-bit DDS · ${result.hardware.dac_bits}-bit DAC · ${result.hardware.filter_order}P filter`;
  const probeVoltage = document.querySelector("#probe-voltage");
  if (probeVoltage) probeVoltage.textContent = `${result.hardware.peak_voltage_v.toFixed(3)} Vpk`;
  const probeDetails = document.querySelector("#probe-details");
  if (probeDetails) probeDetails.textContent = `${result.hardware.filter_gain_db.toFixed(2)} dB filter gain · ${result.hardware.resistor_tolerance_pct.toFixed(1)}% tolerance`;
  const pluginStatus = document.querySelector("#plugin-status");
  if (pluginStatus) pluginStatus.textContent = result.software.passed ? "BENCH-V1 CONTRACT PASSED" : "BENCH-V1 CONTRACT FAILED";
  renderFrequencyBars(result);
  drawWaveform(result);
}

function clearResults(message) {
  ["metric-frequency", "metric-coherence", "metric-ftw", "metric-error", "probe-voltage"].forEach((id) => setMetric(id, "—"));
  const summary = document.querySelector("#result-summary");
  if (summary) summary.textContent = message;
  const bars = document.querySelector("#frequency-bars");
  if (bars) bars.innerHTML = `<p class="empty-readout">${escapeHtml(message)}</p>`;
  const caption = document.querySelector("#waveform-caption");
  if (caption) caption.textContent = "The chart will return after a successful co-simulation.";
  const canvas = document.querySelector("#waveform");
  if (canvas) canvas.getContext("2d")?.clearRect(0, 0, canvas.width, canvas.height);
  ["software-verdict", "hardware-verdict"].forEach((id) => setMetric(id, "Not run"));
  const pluginStatus = document.querySelector("#plugin-status");
  if (pluginStatus) pluginStatus.textContent = "BENCH-V1 CONTRACT NOT RUN";
  const softwareChecks = document.querySelector("#software-checks");
  if (softwareChecks) softwareChecks.textContent = "Resolve the error and run again.";
  const hardwareChecks = document.querySelector("#hardware-checks");
  if (hardwareChecks) hardwareChecks.textContent = "Resolve the circuit error and run again.";
  const probeDetails = document.querySelector("#probe-details");
  if (probeDetails) probeDetails.textContent = "No current output probe result";
}

async function runPipeline() {
  runButton.disabled = true;
  status.textContent = "Running sensor estimation, algorithm, and output quantisation…";
  try {
    const payload = readPayload();
    if (!payload) {
      clearResults("No current result. Fix the highlighted specification first.");
      status.textContent = "Fix the highlighted field before running the co-simulation.";
      return;
    }
    saveLayout();
    const response = await fetch("/api/simulate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "The simulation returned an error.");
    renderResults(result);
    status.textContent = `Complete. ${result.summary}.`;
  } catch (error) {
    clearResults(`No current result. ${error.message}`);
    status.textContent = `Simulation error: ${error.message}`;
  } finally {
    runButton.disabled = false;
  }
}

function handleDrop(event) {
  event.preventDefault();
  board.classList.remove("drop-target");
  const value = event.dataTransfer.getData("text/plain");
  if (!value) return;
  const boardRect = board.getBoundingClientRect();
  if (value.startsWith("palette:")) {
    addComponent(value.slice("palette:".length), event.clientX, event.clientY);
    return;
  }
  if (value.startsWith("node:")) {
    const nodeId = value.slice("node:".length);
    positionNode(nodeId, ((event.clientX - boardRect.left) / boardRect.width) * 100 - 7, ((event.clientY - boardRect.top) / boardRect.height) * 100 - 4);
    status.textContent = `${nodeId} moved. The signal connections updated automatically.`;
  }
}

function wirePalette() {
  document.querySelectorAll("[data-add-kind]").forEach((button) => {
    button.addEventListener("click", () => addComponent(button.dataset.addKind));
    button.addEventListener("dragstart", (event) => {
      event.dataTransfer.effectAllowed = "copy";
      event.dataTransfer.setData("text/plain", `palette:${button.dataset.addKind}`);
    });
  });
  board.addEventListener("dragover", (event) => { event.preventDefault(); board.classList.add("drop-target"); });
  board.addEventListener("dragleave", (event) => { if (!board.contains(event.relatedTarget)) board.classList.remove("drop-target"); });
  board.addEventListener("drop", handleDrop);
  runButton.addEventListener("click", runPipeline);
  document.querySelector("#add-connection").addEventListener("click", () => {
    const from = connectionFrom.value;
    const to = connectionTo.value;
    if (from === to) {
      status.textContent = "Choose two different endpoints for a connection.";
      return;
    }
    if (state.connections.some((connection) => connection.from === from && connection.to === to)) {
      status.textContent = "That connection already exists.";
      return;
    }
    if (!isAllowedConnection(from, to)) {
      status.textContent = "Unsupported connection. Use sensor → algorithm → DDS → R-2R → filter → probe.";
      return;
    }
    state.connections.push({ from, to });
    saveLayout();
    renderConnectionControls();
    status.textContent = `${componentLabel(from)} connected to ${componentLabel(to)}. Run the co-simulation to validate it.`;
  });
  document.querySelectorAll("#plugin-name, #plugin-language, #plugin-entrypoint, #test-scenario, #software-code").forEach((input) => input.addEventListener("input", () => {
    readSoftwareState();
    saveLayout();
    document.querySelector("#plugin-status").textContent = "BENCH-V1 CONTRACT NOT RUN";
  }));
  document.querySelector("#reset-layout").addEventListener("click", () => {
    state.positions = structuredClone(DEFAULT_POSITIONS);
    renderBoard();
    status.textContent = "Board layout reset. Input values were kept.";
  });
  window.addEventListener("resize", updateWires);
}

loadLayout();
setDeploymentStatus();
renderSoftwareEditor();
renderBoard();
wirePalette();
setTimeout(runPipeline, 180);
