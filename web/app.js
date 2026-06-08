const ZONE_TYPES = [
  "CBD", "COMMERCIAL", "RES_HIGH", "RES_MED", "RES_LOW", "SUBURB",
  "UNIVERSITY", "MEDICAL", "INDUSTRIAL", "LOGISTICS", "PUBLIC", "PARK", "GREENBELT"
];
const FACILITY_TYPES = ["airport", "port", "freight_terminal", "power", "water_treatment", "waste"];
const TRANSIT_TYPES = ["subway", "brt", "rail", "freight_rail", "highway", "arterial"];
const AXES = ["economy", "transport", "environment", "housing", "urban_form"];

const ZONE_COLORS = {
  CBD: "#d62839",
  COMMERCIAL: "#f08c28",
  RES_HIGH: "#f3cf2a",
  RES_MED: "#ecd982",
  RES_LOW: "#bcd77a",
  SUBURB: "#d3e1ac",
  UNIVERSITY: "#a878d2",
  MEDICAL: "#cda0dc",
  INDUSTRIAL: "#8c8073",
  LOGISTICS: "#a89a86",
  PUBLIC: "#4f74cf",
  PARK: "#5aa54f",
  GREENBELT: "#79b95f"
};

const TERRAIN_COLORS = {
  ".": [219, 214, 190],
  T: [93, 133, 78],
  F: [211, 194, 105],
  w: [107, 161, 139],
  "^": [178, 172, 161],
  "~": [93, 157, 199]
};

const EVENT_VIS = {
  mineral_deposit: ["M", "#2f974e"],
  deep_harbor: ["H", "#2f974e"],
  oil_field: ["O", "#d69626"],
  fault_line: ["!", "#d24040"],
  floodplain: ["F", "#d69626"],
  heritage_site: ["G", "#d69626"],
  natural_reserve: ["N", "#d69626"],
  landslide_zone: ["L", "#d24040"],
  typhoon_corridor: ["T", "#d24040"],
  wind_corridor: ["W", "#2f974e"],
  aquifer_recharge: ["A", "#d69626"],
  scenic_viewpoint: ["V", "#2f974e"],
  geothermal_spring: ["S", "#2f974e"],
  fertile_soil: ["Y", "#d69626"],
  subsidence_zone: ["D", "#d24040"]
};

const state = {
  terrain: null,
  submission: emptySubmission(),
  mode: "select",
  draft: [],
  selected: null,
  drag: null,
  scale: 1,
  offsetX: 0,
  offsetY: 0,
  leaderboardRows: [],
  balanceRows: []
};

function emptySubmission() {
  return { zones: [], facilities: [], transit: [], stations: [], hubs: [] };
}

function $(id) {
  return document.getElementById(id);
}

function fillSelect(id, values) {
  const el = $(id);
  el.innerHTML = values.map((v) => `<option value="${v}">${v}</option>`).join("");
}

function setup() {
  fillSelect("zoneType", ZONE_TYPES);
  fillSelect("facilityType", FACILITY_TYPES);
  fillSelect("transitType", TRANSIT_TYPES);

  document.querySelectorAll(".tab").forEach((btn) => {
    btn.addEventListener("click", () => switchView(btn.dataset.view));
  });
  document.querySelectorAll("#modeButtons button").forEach((btn) => {
    btn.addEventListener("click", () => setMode(btn.dataset.mode));
  });

  $("loadBundled").addEventListener("click", loadBundledEditor);
  $("loadDashboardBundled").addEventListener("click", loadBundledDashboard);
  $("terrainFile").addEventListener("change", (e) => readJsonFile(e, loadTerrain));
  $("submissionFile").addEventListener("change", (e) => readJsonFile(e, loadSubmission));
  $("leaderboardFile").addEventListener("change", (e) => readTextFile(e, loadLeaderboardCsv));
  $("balanceFile").addEventListener("change", (e) => readTextFile(e, loadBalanceCsv));
  $("finishShape").addEventListener("click", finishDraft);
  $("undoPoint").addEventListener("click", () => {
    state.draft.pop();
    drawMap();
  });
  $("deleteSelected").addEventListener("click", deleteSelected);
  $("downloadSubmission").addEventListener("click", downloadSubmission);
  ["layerTerrain", "layerZones", "layerTransit", "layerEvents", "layerGrid"].forEach((id) => {
    $(id).addEventListener("change", drawMap);
  });

  $("compareA").addEventListener("change", drawDashboard);
  $("compareB").addEventListener("change", drawDashboard);

  const canvas = $("mapCanvas");
  canvas.addEventListener("pointerdown", canvasDown);
  canvas.addEventListener("pointermove", canvasMove);
  canvas.addEventListener("pointerup", canvasUp);
  canvas.addEventListener("pointerleave", canvasUp);
  canvas.addEventListener("dblclick", finishDraft);
  window.addEventListener("resize", drawMap);

  loadBundledEditor();
  loadBundledDashboard();
}

function switchView(view) {
  document.querySelectorAll(".tab").forEach((btn) => btn.classList.toggle("active", btn.dataset.view === view));
  $("editorView").classList.toggle("active", view === "editor");
  $("dashboardView").classList.toggle("active", view === "dashboard");
  if (view === "editor") drawMap();
  if (view === "dashboard") drawDashboard();
}

function setMode(mode) {
  state.mode = mode;
  state.draft = [];
  document.querySelectorAll("#modeButtons button").forEach((btn) => btn.classList.toggle("active", btn.dataset.mode === mode));
  drawMap();
}

async function loadBundledEditor() {
  const terrain = await fetchJson("../terrain_lake_core.json");
  const submission = await fetchJson("../submission_reference_lake_core.json").catch(() => fetchJson("../submission_lakecore3.json"));
  loadTerrain(terrain);
  loadSubmission(submission);
}

async function loadBundledDashboard() {
  const leaderboard = await fetchText("../leaderboard_lakecore.csv");
  const balance = await fetchText("../balance_report.csv");
  loadLeaderboardCsv(leaderboard);
  loadBalanceCsv(balance);
}

async function fetchJson(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(path);
  return res.json();
}

async function fetchText(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(path);
  return res.text();
}

function readJsonFile(event, callback) {
  const file = event.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => callback(JSON.parse(reader.result));
  reader.readAsText(file);
}

function readTextFile(event, callback) {
  const file = event.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => callback(reader.result);
  reader.readAsText(file);
}

function loadTerrain(terrain) {
  state.terrain = terrain;
  $("scenarioLine").textContent = `${terrain.name || "Scenario"} / ${terrain.objective || ""}`;
  drawMap();
}

function loadSubmission(submission) {
  state.submission = {
    zones: submission.zones || [],
    facilities: submission.facilities || [],
    transit: submission.transit || [],
    stations: submission.stations || [],
    hubs: submission.hubs || []
  };
  state.selected = null;
  updateJson();
  drawMap();
}

function fitCanvas(canvas) {
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.max(640, Math.floor(rect.width * dpr));
  canvas.height = Math.max(420, Math.floor(rect.height * dpr));
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { width: rect.width, height: rect.height, ctx };
}

function mapTransform(size) {
  const t = state.terrain;
  if (!t) return;
  const worldW = t.width * t.cell_size_m;
  const worldH = t.height * t.cell_size_m;
  const pad = 18;
  state.scale = Math.min((size.width - pad * 2) / worldW, (size.height - pad * 2) / worldH);
  state.offsetX = (size.width - worldW * state.scale) / 2;
  state.offsetY = (size.height - worldH * state.scale) / 2;
}

function toScreen(pt) {
  return [state.offsetX + pt[0] * state.scale, state.offsetY + pt[1] * state.scale];
}

function toWorld(event) {
  const rect = $("mapCanvas").getBoundingClientRect();
  return [(event.clientX - rect.left - state.offsetX) / state.scale, (event.clientY - rect.top - state.offsetY) / state.scale];
}

function drawMap() {
  const canvas = $("mapCanvas");
  const size = fitCanvas(canvas);
  const ctx = size.ctx;
  ctx.clearRect(0, 0, size.width, size.height);
  ctx.fillStyle = "#d9d4c6";
  ctx.fillRect(0, 0, size.width, size.height);
  if (!state.terrain) return;
  mapTransform(size);

  if ($("layerTerrain").checked) drawTerrain(ctx);
  if ($("layerGrid").checked) drawGrid(ctx);
  if ($("layerZones").checked) drawZones(ctx);
  if ($("layerTransit").checked) drawTransit(ctx);
  if ($("layerEvents").checked) drawEvents(ctx);
  drawDraft(ctx);
  drawSelection(ctx);
  updateStats();
  updateSelectionDetails();
}

function drawTerrain(ctx) {
  const t = state.terrain;
  const rows = t.rows || [];
  const cell = t.cell_size_m;
  const elev = Array.isArray(t.elevation_m) ? t.elevation_m : null;
  for (let y = 0; y < rows.length; y++) {
    for (let x = 0; x < rows[y].length; x++) {
      const key = rows[y][x];
      const base = TERRAIN_COLORS[key] || TERRAIN_COLORS["."];
      const shade = elev && elev[y] ? elevationShade(elev[y][x], t) : 1;
      ctx.fillStyle = `rgb(${clamp(base[0] * shade)}, ${clamp(base[1] * shade)}, ${clamp(base[2] * shade)})`;
      const sx = state.offsetX + x * cell * state.scale;
      const sy = state.offsetY + y * cell * state.scale;
      const s = Math.ceil(cell * state.scale) + 0.5;
      ctx.fillRect(sx, sy, s, s);
    }
  }
}

function elevationShade(value, terrain) {
  const stats = terrain.layer_stats && terrain.layer_stats.elevation_m;
  if (!stats) return 1;
  const span = Math.max(1, stats.max - stats.min);
  return 0.84 + ((value - stats.min) / span) * 0.28;
}

function clamp(value) {
  return Math.max(0, Math.min(255, Math.round(value)));
}

function drawGrid(ctx) {
  const t = state.terrain;
  const cell = t.cell_size_m;
  const worldW = t.width * cell;
  const worldH = t.height * cell;
  ctx.strokeStyle = "rgba(80, 85, 90, 0.18)";
  ctx.lineWidth = 1;
  for (let x = 0; x <= t.width; x += 5) {
    const sx = state.offsetX + x * cell * state.scale;
    ctx.beginPath();
    ctx.moveTo(sx, state.offsetY);
    ctx.lineTo(sx, state.offsetY + worldH * state.scale);
    ctx.stroke();
  }
  for (let y = 0; y <= t.height; y += 5) {
    const sy = state.offsetY + y * cell * state.scale;
    ctx.beginPath();
    ctx.moveTo(state.offsetX, sy);
    ctx.lineTo(state.offsetX + worldW * state.scale, sy);
    ctx.stroke();
  }
}

function drawZones(ctx) {
  state.submission.zones.forEach((zone, index) => {
    if (!zone.polygon || zone.polygon.length < 3) return;
    const selected = state.selected && state.selected.kind === "zones" && state.selected.index === index;
    drawPolygon(ctx, zone.polygon, ZONE_COLORS[zone.use] || "#888", selected);
    drawLabel(ctx, centroid(zone.polygon), zone.use || "ZONE");
  });
}

function drawPolygon(ctx, polygon, color, selected) {
  ctx.beginPath();
  polygon.forEach((pt, i) => {
    const [x, y] = toScreen(pt);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.closePath();
  ctx.fillStyle = `${color}dd`;
  ctx.strokeStyle = selected ? "#10151b" : "#ffffff";
  ctx.lineWidth = selected ? 3 : 1;
  ctx.fill();
  ctx.stroke();
  if (selected) {
    polygon.forEach((pt) => {
      const [x, y] = toScreen(pt);
      ctx.fillStyle = "#ffffff";
      ctx.strokeStyle = "#10151b";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(x, y, 5, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
    });
  }
}

function drawTransit(ctx) {
  const colors = { subway: "#1f2430", brt: "#2aa0dc", rail: "#777f8a", freight_rail: "#9c7b5a", highway: "#ffffff", arterial: "#c8ccd2" };
  state.submission.transit.forEach((line, index) => {
    const selected = state.selected && state.selected.kind === "transit" && state.selected.index === index;
    drawPath(ctx, line.path || [], colors[line.type] || "#222", selected ? 5 : 3, selected);
  });
  state.submission.stations.forEach((station, index) => drawPoint(ctx, [station.x, station.y], "S", "#ffffff", "#20242a", state.selected?.kind === "stations" && state.selected.index === index));
  state.submission.hubs.forEach((hub, index) => drawPoint(ctx, [hub.x, hub.y], "H", "#20242a", "#ffffff", state.selected?.kind === "hubs" && state.selected.index === index));
  state.submission.facilities.forEach((facility, index) => drawPoint(ctx, [facility.x, facility.y], facility.type.slice(0, 1).toUpperCase(), "#ffffff", "#2f6f9f", state.selected?.kind === "facilities" && state.selected.index === index));
}

function drawPath(ctx, path, color, width, selected) {
  if (!path || path.length < 2) return;
  ctx.strokeStyle = selected ? "#10151b" : color;
  ctx.lineWidth = width;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.beginPath();
  path.forEach((pt, i) => {
    const [x, y] = toScreen(pt);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();
}

function drawPoint(ctx, pt, label, fill, stroke, selected) {
  const [x, y] = toScreen(pt);
  ctx.fillStyle = fill;
  ctx.strokeStyle = selected ? "#d48736" : stroke;
  ctx.lineWidth = selected ? 4 : 2;
  ctx.beginPath();
  ctx.arc(x, y, selected ? 9 : 7, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = stroke === "#ffffff" ? "#ffffff" : "#20242a";
  ctx.font = "700 10px Arial";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(label, x, y + 0.5);
}

function drawEvents(ctx) {
  const t = state.terrain;
  (t.events || []).forEach((event) => {
    const vis = EVENT_VIS[event.type] || [event.type.slice(0, 1).toUpperCase(), "#d69626"];
    const [x, y] = toScreen([event.x, event.y]);
    const radius = event.radius * state.scale;
    ctx.strokeStyle = vis[1];
    ctx.lineWidth = 2;
    ctx.setLineDash([6, 4]);
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);
    drawPoint(ctx, [event.x, event.y], vis[0], "#ffffff", vis[1], false);
  });
}

function drawDraft(ctx) {
  if (!state.draft.length) return;
  const color = state.mode === "transit" ? "#1f2430" : ZONE_COLORS[$("zoneType").value] || "#2f6f9f";
  if (state.mode === "zone") {
    ctx.beginPath();
    state.draft.forEach((pt, i) => {
      const [x, y] = toScreen(pt);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.strokeStyle = color;
    ctx.lineWidth = 3;
    ctx.stroke();
  } else if (state.mode === "transit") {
    drawPath(ctx, state.draft, color, 4, false);
  }
  state.draft.forEach((pt) => drawPoint(ctx, pt, "", "#ffffff", color, false));
}

function drawSelection(ctx) {
  if (!state.selected) return;
}

function drawLabel(ctx, pt, text) {
  const [x, y] = toScreen(pt);
  ctx.font = "700 11px Arial";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.lineWidth = 3;
  ctx.strokeStyle = "rgba(255,255,255,0.86)";
  ctx.fillStyle = "#20242a";
  ctx.strokeText(text, x, y);
  ctx.fillText(text, x, y);
}

function centroid(poly) {
  const sum = poly.reduce((acc, pt) => [acc[0] + pt[0], acc[1] + pt[1]], [0, 0]);
  return [sum[0] / poly.length, sum[1] / poly.length];
}

function canvasDown(event) {
  if (!state.terrain) return;
  const pt = toWorld(event);
  if (state.mode === "zone" || state.mode === "transit") {
    state.draft.push(pt);
    drawMap();
    return;
  }
  if (state.mode === "facility") {
    state.submission.facilities.push({ type: $("facilityType").value, x: pt[0], y: pt[1] });
    updateJson();
    drawMap();
    return;
  }
  if (state.mode === "station") {
    state.submission.stations.push({ type: $("transitType").value, x: pt[0], y: pt[1] });
    updateJson();
    drawMap();
    return;
  }
  if (state.mode === "hub") {
    state.submission.hubs.push({ x: pt[0], y: pt[1] });
    updateJson();
    drawMap();
    return;
  }
  selectAt(pt);
}

function canvasMove(event) {
  if (!state.drag) return;
  const pt = toWorld(event);
  const { kind, index, vertex } = state.drag;
  if (kind === "zones") state.submission.zones[index].polygon[vertex] = pt;
  if (kind === "transit") state.submission.transit[index].path[vertex] = pt;
  updateJson(false);
  drawMap();
}

function canvasUp() {
  state.drag = null;
}

function selectAt(pt) {
  state.selected = null;
  state.drag = null;
  const threshold = 1200 / Math.max(0.1, state.scale);

  for (let i = 0; i < state.submission.zones.length; i++) {
    const zone = state.submission.zones[i];
    const vertex = nearestVertex(zone.polygon || [], pt, threshold);
    if (vertex >= 0) {
      state.selected = { kind: "zones", index: i };
      state.drag = { kind: "zones", index: i, vertex };
      drawMap();
      return;
    }
  }
  for (let i = 0; i < state.submission.transit.length; i++) {
    const line = state.submission.transit[i];
    const vertex = nearestVertex(line.path || [], pt, threshold);
    if (vertex >= 0) {
      state.selected = { kind: "transit", index: i };
      state.drag = { kind: "transit", index: i, vertex };
      drawMap();
      return;
    }
  }
  for (const kind of ["facilities", "stations", "hubs"]) {
    const list = state.submission[kind];
    for (let i = 0; i < list.length; i++) {
      const item = list[i];
      const target = [item.x, item.y];
      if (distance(target, pt) < threshold * 1.6) {
        state.selected = { kind, index: i };
        drawMap();
        return;
      }
    }
  }
  for (let i = 0; i < state.submission.zones.length; i++) {
    if (pointInPolygon(pt, state.submission.zones[i].polygon || [])) {
      state.selected = { kind: "zones", index: i };
      drawMap();
      return;
    }
  }
  drawMap();
}

function nearestVertex(points, pt, threshold) {
  let best = -1;
  let bestD = threshold;
  points.forEach((candidate, index) => {
    const d = distance(candidate, pt);
    if (d < bestD) {
      best = index;
      bestD = d;
    }
  });
  return best;
}

function distance(a, b) {
  return Math.hypot(a[0] - b[0], a[1] - b[1]);
}

function pointInPolygon(pt, poly) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const xi = poly[i][0], yi = poly[i][1];
    const xj = poly[j][0], yj = poly[j][1];
    const intersect = yi > pt[1] !== yj > pt[1] && pt[0] < ((xj - xi) * (pt[1] - yi)) / (yj - yi) + xi;
    if (intersect) inside = !inside;
  }
  return inside;
}

function finishDraft() {
  if (state.mode === "zone" && state.draft.length >= 3) {
    state.submission.zones.push({ use: $("zoneType").value, polygon: state.draft.slice() });
    state.draft = [];
    updateJson();
    drawMap();
  } else if (state.mode === "transit" && state.draft.length >= 2) {
    state.submission.transit.push({ type: $("transitType").value, path: state.draft.slice() });
    state.draft = [];
    updateJson();
    drawMap();
  }
}

function deleteSelected() {
  if (!state.selected) return;
  const list = state.submission[state.selected.kind];
  if (list) list.splice(state.selected.index, 1);
  state.selected = null;
  updateJson();
  drawMap();
}

function updateStats() {
  $("editorStats").innerHTML = `
    <div><span>Zones</span><strong>${state.submission.zones.length}</strong></div>
    <div><span>Facilities</span><strong>${state.submission.facilities.length}</strong></div>
    <div><span>Transit</span><strong>${state.submission.transit.length}</strong></div>
    <div><span>Events</span><strong>${state.terrain?.events?.length || 0}</strong></div>
  `;
}

function updateSelectionDetails() {
  const el = $("selectionDetails");
  if (!state.selected) {
    el.textContent = "None";
    return;
  }
  const item = state.submission[state.selected.kind][state.selected.index];
  el.innerHTML = `<strong>${state.selected.kind} #${state.selected.index + 1}</strong><br>${escapeHtml(JSON.stringify(item, null, 2))}`;
}

function updateJson(redraw = true) {
  $("jsonPreview").value = JSON.stringify(state.submission, null, 2);
  if (redraw) drawMap();
}

function downloadSubmission() {
  const blob = new Blob([JSON.stringify(state.submission, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "submission_edited.json";
  a.click();
  URL.revokeObjectURL(url);
}

function escapeHtml(text) {
  return text.replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
}

function loadLeaderboardCsv(text) {
  state.leaderboardRows = parseCsv(text);
  populateCompareSelects();
  drawDashboard();
}

function loadBalanceCsv(text) {
  state.balanceRows = parseCsv(text);
  drawDashboard();
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = "";
  let quote = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (quote) {
      if (ch === '"' && text[i + 1] === '"') {
        cell += '"';
        i++;
      } else if (ch === '"') {
        quote = false;
      } else {
        cell += ch;
      }
    } else if (ch === '"') {
      quote = true;
    } else if (ch === ",") {
      row.push(cell);
      cell = "";
    } else if (ch === "\n") {
      row.push(cell);
      rows.push(row);
      row = [];
      cell = "";
    } else if (ch !== "\r") {
      cell += ch;
    }
  }
  if (cell || row.length) {
    row.push(cell);
    rows.push(row);
  }
  const headers = rows.shift() || [];
  return rows.filter((r) => r.length && r.some(Boolean)).map((r) => Object.fromEntries(headers.map((h, i) => [h, r[i] ?? ""])));
}

function populateCompareSelects() {
  const options = state.leaderboardRows.map((row, i) => `<option value="${i}">${row.submission || row.objective || i + 1}</option>`).join("");
  $("compareA").innerHTML = options;
  $("compareB").innerHTML = options;
  if (state.leaderboardRows.length > 1) $("compareB").value = "1";
}

function drawDashboard() {
  drawLeaderboardTable();
  drawAxisChart();
  drawGradeChart();
  drawMatrixChart();
}

function drawLeaderboardTable() {
  const rows = state.leaderboardRows;
  if (!rows.length) {
    $("leaderboardTable").innerHTML = "";
    return;
  }
  $("leaderboardTable").innerHTML = `
    <table>
      <thead><tr><th>Rank</th><th>Submission</th><th>Score</th><th>Grade</th><th>Status</th><th>Axes</th></tr></thead>
      <tbody>
        ${rows.map((row, i) => `
          <tr>
            <td>${i + 1}</td>
            <td>${escapeHtml(row.submission || "")}</td>
            <td>${row.score}</td>
            <td>${row.grade}</td>
            <td>${row.status}</td>
            <td><div class="axis-pill">${AXES.map((axis) => `<span style="flex-basis:${Number(row[axis] || 0) / 2}px"></span>`).join("")}</div></td>
          </tr>
        `).join("")}
      </tbody>
    </table>`;
}

function clearChart(id) {
  const canvas = $(id);
  const { ctx, width, height } = fitCanvas(canvas);
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, width, height);
  return { ctx, width, height };
}

function drawAxisChart() {
  const { ctx, width, height } = clearChart("axisChart");
  const a = state.leaderboardRows[Number($("compareA").value || 0)];
  const b = state.leaderboardRows[Number($("compareB").value || 0)];
  if (!a) return;
  const colors = ["#4472c4", "#70ad47"];
  AXES.forEach((axis, i) => {
    const y = 42 + i * 48;
    ctx.fillStyle = "#59616b";
    ctx.font = "12px Arial";
    ctx.fillText(axis, 20, y + 14);
    [a, b].forEach((row, j) => {
      if (!row) return;
      const value = Number(row[axis] || 0);
      ctx.fillStyle = colors[j];
      ctx.fillRect(140, y + j * 16, Math.max(1, value / 200 * (width - 190)), 12);
      ctx.fillStyle = "#20242a";
      ctx.fillText(value.toFixed(0), width - 42, y + j * 16 + 11);
    });
  });
}

function drawGradeChart() {
  const { ctx, width, height } = clearChart("gradeChart");
  const source = state.balanceRows.length ? state.balanceRows : state.leaderboardRows;
  const counts = {};
  source.forEach((row) => counts[row.grade] = (counts[row.grade] || 0) + 1);
  const grades = ["S", "A", "B", "C", "D"];
  const max = Math.max(1, ...grades.map((g) => counts[g] || 0));
  grades.forEach((grade, i) => {
    const barH = ((counts[grade] || 0) / max) * (height - 90);
    const x = 44 + i * 72;
    const y = height - 42 - barH;
    ctx.fillStyle = ["#2f6f9f", "#4f8f62", "#d48736", "#a878d2", "#c94f4f"][i];
    ctx.fillRect(x, y, 44, barH);
    ctx.fillStyle = "#20242a";
    ctx.font = "13px Arial";
    ctx.textAlign = "center";
    ctx.fillText(grade, x + 22, height - 20);
    ctx.fillText(counts[grade] || 0, x + 22, y - 8);
  });
  ctx.textAlign = "left";
}

function drawMatrixChart() {
  const { ctx, width, height } = clearChart("matrixChart");
  const rows = state.balanceRows;
  if (!rows.length) return;
  const terrains = [...new Set(rows.map((r) => r.terrain_key || r.terrain))];
  const objectives = [...new Set(rows.map((r) => r.objective))];
  const left = 150;
  const top = 48;
  const cellW = Math.max(95, (width - left - 30) / objectives.length);
  const cellH = Math.max(48, (height - top - 30) / terrains.length);
  ctx.font = "12px Arial";
  ctx.fillStyle = "#59616b";
  objectives.forEach((obj, i) => ctx.fillText(shortObjective(obj), left + i * cellW + 6, 26));
  terrains.forEach((terrain, r) => {
    ctx.fillStyle = "#59616b";
    ctx.fillText(terrain, 18, top + r * cellH + cellH / 2 + 4);
    objectives.forEach((obj, c) => {
      const row = rows.find((item) => (item.terrain_key || item.terrain) === terrain && item.objective === obj);
      const score = Number(row?.score || 0);
      const intensity = Math.max(0, Math.min(1, (score - 560) / 430));
      const color = heatColor(intensity);
      const x = left + c * cellW;
      const y = top + r * cellH;
      ctx.fillStyle = color;
      ctx.fillRect(x, y, cellW - 4, cellH - 4);
      ctx.fillStyle = "#20242a";
      ctx.font = "700 13px Arial";
      ctx.fillText(score ? score.toFixed(0) : "-", x + 10, y + 24);
      ctx.font = "12px Arial";
      ctx.fillText(row?.grade || "", x + 10, y + 42);
    });
  });
}

function shortObjective(value) {
  return (value || "").replace("Financial Capital", "Finance").replace("Logistics Hub", "Logistics").replace("Innovation City", "Innovation").replace("Tourism Capital", "Tourism").replace("Eco Metropolis", "Eco");
}

function heatColor(t) {
  const r = Math.round(210 - t * 92);
  const g = Math.round(90 + t * 120);
  const b = Math.round(80 + t * 58);
  return `rgb(${r}, ${g}, ${b})`;
}

setup();
