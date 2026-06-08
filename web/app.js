"use strict";

/* ===========================================================================
 * Palette — mirrored from render2.py so the editor matches the PNG renderer.
 * ======================================================================== */
const TERRAIN_COLORS = {
  ".": "#eef0ea", "T": "#cfe3c4", "F": "#e9dfaa",
  "w": "#b9d8c8", "^": "#cfcdc9", "~": "#a9d2ee",
};
const ZONE = {
  CBD: "#d62839", COMMERCIAL: "#f08c28", RES_HIGH: "#f3cf2a",
  RES_MED: "#ecd982", RES_LOW: "#bcd77a", SUBURB: "#d3e1ac",
  UNIVERSITY: "#a878d2", MEDICAL: "#cda0dc", INDUSTRIAL: "#8c8073",
  LOGISTICS: "#a89a86", PUBLIC: "#4f74cf", PARK: "#5aa54f",
  GREENBELT: "#79b95f",
};
const ZONE_KR = {
  CBD: "CBD", COMMERCIAL: "상업/업무", RES_HIGH: "고밀주거", RES_MED: "중밀주거",
  RES_LOW: "저밀주거", SUBURB: "교외", UNIVERSITY: "대학", MEDICAL: "의료",
  INDUSTRIAL: "산업", LOGISTICS: "물류", PUBLIC: "공공", PARK: "공원",
  GREENBELT: "그린벨트",
};
// Zone categories for a clearer, grouped palette + legend.
const ZONE_CATS = [
  ["중심·상업", ["CBD", "COMMERCIAL"]],
  ["주거", ["RES_HIGH", "RES_MED", "RES_LOW", "SUBURB"]],
  ["산업·물류", ["INDUSTRIAL", "LOGISTICS"]],
  ["공공·교육·의료", ["UNIVERSITY", "MEDICAL", "PUBLIC"]],
  ["녹지", ["PARK", "GREENBELT"]],
];
const ROAD = { // type -> [color, core width, dashed]
  arterial: ["#c8ccd2", 0.9, false], brt: ["#2aa0dc", 2.2, false],
  rail: ["#8a8f98", 1.8, true], freight_rail: ["#9c7b5a", 1.8, true],
  highway: ["#ffffff", 3.0, false], subway: ["#1f2430", 2.6, false],
};
const TRANSIT_KR = {
  subway: "지하철", brt: "BRT", rail: "철도", freight_rail: "화물철도",
  highway: "고속도로", arterial: "간선도로",
};
// Station kinds (a subset of transit modes that have platforms).
const STATION_KR = { subway: "지하철역", rail: "철도역", brt: "BRT 정류장" };
const FAC = {
  airport: ["A", "#3a7bd5"], port: ["P", "#2a6f97"],
  freight_terminal: ["F", "#9c6b3f"], power: ["E", "#e0a020"],
  water_treatment: ["W", "#3aa0c0"], waste: ["X", "#7a8a5a"],
};
const FAC_KR = {
  airport: "공항", port: "항만", freight_terminal: "화물터미널",
  power: "발전소", water_treatment: "정수장", waste: "폐기물",
};
const RING = { opportunity: "#3fae54", hazard: "#e05050", mixed: "#e0a020" };
const CLASS_KR = { opportunity: "기회(보너스)", hazard: "재난(페널티)", mixed: "양면" };

// Event metadata: letter, class, Korean name, and a plain effect description.
const EVENT_INFO = {
  mineral_deposit:  ["M", "opportunity", "광맥(자원 발견)", "반경 내 산업·물류를 배치하면 +점수"],
  deep_harbor:      ["H", "opportunity", "심해항", "항만 시설 + 인근 산업 배치 시 +점수"],
  wind_corridor:    ["W", "opportunity", "풍력회랑", "발전소 배치 시 +, 고밀·CBD는 -"],
  scenic_viewpoint: ["V", "opportunity", "경관 명소", "저밀·녹지·공공은 +, 산업·고밀은 -"],
  geothermal_spring:["S", "opportunity", "온천", "대학·의료·공공·공원은 +, 산업은 -"],
  bridge_chokepoint:["B", "opportunity", "교량 요충", "도로망·허브가 인접하면 +"],
  oil_field:        ["O", "mixed", "유전", "산업 배치 시 +경제 / -환경(오염)"],
  floodplain:       ["F", "mixed", "범람원(침수 위험)", "녹지는 +(완충), 주거는 -(침수)"],
  heritage_site:    ["G", "mixed", "유산지", "공원·저밀은 +, 산업·고밀은 -"],
  natural_reserve:  ["N", "mixed", "보호구역", "녹지는 +, 개발은 강한 -"],
  aquifer_recharge: ["A", "mixed", "대수층", "정수장·녹지는 +, 오염·인구는 -"],
  fertile_soil:     ["Y", "mixed", "비옥토", "저밀·녹지는 +, 산업·고밀은 -"],
  fault_line:       ["!", "hazard", "단층", "주거·산업을 올리면 -(붕괴 위험)"],
  landslide_zone:   ["L", "hazard", "산사태 위험", "개발하면 -"],
  typhoon_corridor: ["T", "hazard", "태풍 통로", "개발은 -, 녹지 완충은 +"],
  subsidence_zone:  ["D", "hazard", "침하 위험", "개발은 강한 -, 녹지 완충은 +"],
};
const AXES = ["economy", "transport", "environment", "housing", "urban_form"];
const AXIS_KR = {
  economy: "경제", transport: "교통", environment: "환경",
  housing: "주거", urban_form: "도시구조",
};

const EMPTY_SUB = () => ({ zones: [], facilities: [], transit: [], stations: [], hubs: [] });

/* ===========================================================================
 * State
 * ======================================================================== */
const state = {
  terrain: null, terrainFile: null,
  submission: EMPTY_SUB(),
  events: [],                 // editable working copy of terrain events
  mode: "select",
  drawUse: "CBD", drawTransit: "subway", drawFacility: "airport",
  drawStation: "subway", drawEvent: "mineral_deposit",
  draft: null,                // in-progress {kind:'zone'|'transit', pts:[[m,m]...]}
  sel: null,                  // {kind, index}
  drag: null,                 // {kind, index, vi?}
  history: [], redo: [],
  snap: false, gridStep: 500,   // grid spacing in meters
  lastResult: null,
  g: null,                    // current geometry (set in draw)
  mouse: null,                // last mouse [m,m]
};

const $ = (id) => document.getElementById(id);
const canvas = $("map");
const ctx = canvas.getContext("2d");

function setStatus(msg, kind = "") {
  $("status").textContent = msg;
  $("status").className = "status" + (kind ? " " + kind : "");
}

/* ===========================================================================
 * Geometry / coordinate conversion
 * ======================================================================== */
function geom() {
  const t = state.terrain;
  const cell = t.cell_size_m;
  const w = t.width || t.rows[0].length;
  const h = t.height || t.rows.length;
  const cpx = Math.max(3, Math.round(900 / w));
  return { cell, w, h, cpx, mx: (m) => (m / cell) * cpx, my: (m) => (m / cell) * cpx };
}
function evtPx(e) {
  const r = canvas.getBoundingClientRect();
  return [(e.clientX - r.left) * (canvas.width / r.width),
          (e.clientY - r.top) * (canvas.height / r.height)];
}
function evtMeters(e) {
  const [px, py] = evtPx(e);
  const g = state.g;
  return [px / g.cpx * g.cell, py / g.cpx * g.cell];
}
function polyAreaKm2(poly) {
  let a = 0;
  for (let i = 0; i < poly.length; i++) {
    const [x1, y1] = poly[i], [x2, y2] = poly[(i + 1) % poly.length];
    a += x1 * y2 - x2 * y1;
  }
  return Math.abs(a) / 2 / 1e6;
}
function polylineKm(pts) {
  let d = 0;
  for (let i = 1; i < pts.length; i++)
    d += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
  return d / 1000;
}
function pointInPoly(pt, poly) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i], [xj, yj] = poly[j];
    if (((yi > pt[1]) !== (yj > pt[1])) &&
        (pt[0] < ((xj - xi) * (pt[1] - yi)) / (yj - yi) + xi)) inside = !inside;
  }
  return inside;
}
function segInt(a, b, c, d) {
  const cc = (p, q, r) => Math.sign((q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]));
  return cc(a, b, c) !== cc(a, b, d) && cc(c, d, a) !== cc(c, d, b);
}
function polysOverlap(p, q) {
  if (p.some((v) => pointInPoly(v, q)) || q.some((v) => pointInPoly(v, p))) return true;
  for (let i = 0; i < p.length; i++)
    for (let j = 0; j < q.length; j++)
      if (segInt(p[i], p[(i + 1) % p.length], q[j], q[(j + 1) % q.length])) return true;
  return false;
}

/* ===========================================================================
 * Data loading / export
 * ======================================================================== */
async function loadTerrainList() {
  const list = await (await fetch("/api/terrains")).json();
  const sel = $("terrain-select");
  sel.innerHTML = "";
  list.forEach((t) => {
    const o = document.createElement("option");
    o.value = t.file;
    o.textContent = `${t.name} — ${t.objective} (×${t.difficulty})`;
    sel.appendChild(o);
  });
  if (list.length) await selectTerrain(list[0].file);
}
async function selectTerrain(file) {
  state.terrainFile = file;
  state.terrain = await (await fetch("/api/terrain?file=" + encodeURIComponent(file))).json();
  state.submission = EMPTY_SUB();
  state.events = JSON.parse(JSON.stringify(state.terrain.events || []));
  state.history = []; state.redo = []; state.sel = null; state.draft = null; state.lastResult = null;
  state.g = geom();
  refreshButtons(); resetPanel(); hideInspector(); draw();
  setStatus("지형 로드됨. 도구로 그리거나 기준 제출물을 불러오세요.");
}
async function loadReference() {
  if (!state.terrainFile) return;
  setStatus("기준 제출물 생성 중…");
  const sub = await (await fetch("/api/reference?file=" + encodeURIComponent(state.terrainFile))).json();
  if (sub.error) return setStatus(sub.error, "err");
  delete sub.metadata;
  state.submission = Object.assign(EMPTY_SUB(), sub);
  state.history = []; state.redo = []; refreshButtons();
  draw(); await scoreNow();
}
function loadSubmissionFile(file) {
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const obj = JSON.parse(reader.result);
      state.submission = Object.assign(EMPTY_SUB(), obj);
      if (Array.isArray(obj.events)) state.events = obj.events;
      state.history = []; state.redo = []; refreshButtons();
      $("btn-score").disabled = false;
      draw();
      setStatus("제출물 로드됨. ‘채점’을 누르세요.", "ok");
    } catch (e) { setStatus("JSON 파싱 실패: " + e.message, "err"); }
  };
  reader.readAsText(file);
}
function exportJSON() {
  const out = Object.assign({}, state.submission, { events: state.events });
  const blob = new Blob([JSON.stringify(out, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = (state.terrainFile || "submission").replace(/^terrain_/, "sub_");
  a.click();
  URL.revokeObjectURL(a.href);
}

/* ===========================================================================
 * History (undo / redo)
 * ======================================================================== */
function snapshot() {
  return JSON.stringify({ sub: state.submission, events: state.events });
}
function restore(snap) {
  const o = JSON.parse(snap);
  state.submission = o.sub; state.events = o.events;
  state.sel = null; state.draft = null;
}
function pushHistory() { state.history.push(snapshot()); state.redo = []; refreshButtons(); }
function undo() {
  if (!state.history.length) return;
  state.redo.push(snapshot());
  restore(state.history.pop());
  refreshButtons(); hideInspector(); draw();
}
function redo() {
  if (!state.redo.length) return;
  state.history.push(snapshot());
  restore(state.redo.pop());
  refreshButtons(); hideInspector(); draw();
}
function refreshButtons() {
  $("btn-undo").disabled = !state.history.length;
  $("btn-redo").disabled = !state.redo.length;
  $("btn-delete").disabled = !state.sel;
  $("btn-score").disabled = !state.terrainFile;
}

/* ===========================================================================
 * Drawing
 * ======================================================================== */
function draw() {
  if (!state.terrain) return;
  const g = state.g = geom();
  canvas.width = g.w * g.cpx;
  canvas.height = g.h * g.cpx;

  drawTerrain(g);
  drawGrid(g);
  drawZones(g);
  drawTransit(g);
  drawFacilities(g);
  drawStations(g);
  drawHubs(g);
  drawEvents(g);
  drawDraft(g);
  drawSelection(g);
  drawZoneLabels(g);
  buildLegend();
}
function drawTerrain(g) {
  const rows = state.terrain.rows;
  const off = document.createElement("canvas");
  off.width = g.w; off.height = g.h;
  const octx = off.getContext("2d");
  const img = octx.createImageData(g.w, g.h);
  for (let y = 0; y < g.h; y++) {
    const row = rows[y];
    for (let x = 0; x < g.w; x++) {
      const [r, gr, b] = hexRgb(TERRAIN_COLORS[row[x]] || TERRAIN_COLORS["."]);
      const i = (y * g.w + x) * 4;
      img.data[i] = r; img.data[i + 1] = gr; img.data[i + 2] = b; img.data[i + 3] = 255;
    }
  }
  octx.putImageData(img, 0, 0);
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(off, 0, 0, canvas.width, canvas.height);
  ctx.imageSmoothingEnabled = true;
}
function drawGrid(g) {
  if (!state.snap) return;
  let sp = state.gridStep / g.cell * g.cpx;          // px per grid step
  const k = Math.max(1, Math.ceil(12 / sp));         // keep lines >=~12px apart
  sp *= k;                                            // still a multiple of the snap step
  ctx.lineWidth = 1; ctx.strokeStyle = "#1f242b55";
  ctx.beginPath();
  for (let x = 0; x <= canvas.width + 0.5; x += sp) { ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height); }
  for (let y = 0; y <= canvas.height + 0.5; y += sp) { ctx.moveTo(0, y); ctx.lineTo(canvas.width, y); }
  ctx.stroke();
}
function tracePoly(g, poly) {
  ctx.beginPath();
  poly.forEach(([x, y], i) => { const px = g.mx(x), py = g.my(y); i ? ctx.lineTo(px, py) : ctx.moveTo(px, py); });
  ctx.closePath();
}
function drawZones(g) {
  (state.submission.zones || []).forEach((z, i) => {
    const col = ZONE[z.use] || "#999999";
    tracePoly(g, z.polygon);
    ctx.fillStyle = col + "8c";
    ctx.fill();
    ctx.lineWidth = state.sel && state.sel.kind === "zone" && state.sel.index === i ? 2.5 : 1.2;
    ctx.strokeStyle = state.sel && state.sel.kind === "zone" && state.sel.index === i ? "#ffffff" : shade(col, 0.65);
    ctx.stroke();
  });
}
function drawZoneLabels(g) {
  ctx.font = "700 11px system-ui, sans-serif";
  ctx.textAlign = "center"; ctx.textBaseline = "middle";
  (state.submission.zones || []).forEach((z) => {
    let cx = 0, cy = 0;
    z.polygon.forEach(([x, y]) => { cx += x; cy += y; });
    cx /= z.polygon.length; cy /= z.polygon.length;
    const px = g.mx(cx), py = g.my(cy);
    const label = ZONE_KR[z.use] || z.use;
    const col = ZONE[z.use] || "#999";
    const w = ctx.measureText(label).width + 10;
    roundRect(px - w / 2, py - 9, w, 18, 5);
    ctx.fillStyle = col; ctx.fill();
    ctx.fillStyle = luminance(col) > 0.6 ? "#1a1c20" : "#ffffff";
    ctx.fillText(label, px, py + 0.5);
  });
}
function drawTransit(g) {
  (state.submission.transit || []).forEach((line, i) => {
    const [col, core, dashed] = ROAD[line.type] || ["#bbbbbb", 1.0, false];
    ctx.beginPath();
    line.path.forEach(([x, y], k) => { const px = g.mx(x), py = g.my(y); k ? ctx.lineTo(px, py) : ctx.moveTo(px, py); });
    ctx.setLineDash(dashed ? [6, 5] : []);
    ctx.lineWidth = Math.max(1.4, core * g.cpx * 0.5);
    ctx.lineJoin = ctx.lineCap = "round";
    ctx.strokeStyle = state.sel && state.sel.kind === "transit" && state.sel.index === i ? "#ffffff" : col;
    ctx.stroke();
  });
  ctx.setLineDash([]);
}
function drawFacilities(g) {
  (state.submission.facilities || []).forEach((f, i) => {
    const [letter, col] = FAC[f.type] || ["?", "#888888"];
    const px = g.mx(f.x), py = g.my(f.y), r = 9;
    roundRect(px - r, py - r, 2 * r, 2 * r, 3);
    ctx.fillStyle = "#ffffff"; ctx.fill();
    ctx.lineWidth = state.sel && state.sel.kind === "facility" && state.sel.index === i ? 3 : 2;
    ctx.strokeStyle = col; ctx.stroke();
    ctx.fillStyle = col; ctx.font = "700 11px system-ui, sans-serif";
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText(letter, px, py + 0.5);
  });
}
function drawStations(g) {
  (state.submission.stations || []).forEach((s, i) => {
    const sel = state.sel && state.sel.kind === "station" && state.sel.index === i;
    ctx.beginPath(); ctx.arc(g.mx(s.x), g.my(s.y), sel ? 5 : 3.5, 0, Math.PI * 2);
    ctx.fillStyle = "#ffffff"; ctx.fill();
    ctx.lineWidth = sel ? 2.5 : 1; ctx.strokeStyle = sel ? "#ffd95a" : "#222428"; ctx.stroke();
  });
}
function drawHubs(g) {
  (state.submission.hubs || []).forEach((hb, i) => {
    const sel = state.sel && state.sel.kind === "hub" && state.sel.index === i;
    const px = g.mx(hb.x), py = g.my(hb.y);
    ctx.beginPath(); ctx.arc(px, py, sel ? 9 : 7, 0, Math.PI * 2);
    ctx.fillStyle = "#1f2430"; ctx.fill();
    ctx.lineWidth = sel ? 3 : 2; ctx.strokeStyle = sel ? "#ffd95a" : "#ffffff"; ctx.stroke();
  });
}
function drawEvents(g) {
  state.events.forEach((e, i) => {
    const [letter, defk] = EVENT_INFO[e.type] || [(e.type || "?")[0].toUpperCase(), "mixed"];
    const klass = e.class || defk;
    const col = RING[klass] || RING.mixed;
    const px = g.mx(e.x), py = g.my(e.y);
    const rr = (e.radius || 0) / g.cell * g.cpx;
    const selected = state.sel && state.sel.kind === "event" && state.sel.index === i;
    if (rr > 2) {
      ctx.beginPath(); ctx.arc(px, py, rr, 0, Math.PI * 2);
      ctx.fillStyle = col + (selected ? "22" : "12");
      ctx.fill();
      ctx.setLineDash([4, 4]); ctx.lineWidth = selected ? 2 : 1.5; ctx.strokeStyle = col; ctx.stroke();
      ctx.setLineDash([]);
    }
    ctx.beginPath(); ctx.arc(px, py, 9, 0, Math.PI * 2);
    ctx.fillStyle = "#ffffff"; ctx.fill();
    ctx.lineWidth = selected ? 3 : 2; ctx.strokeStyle = col; ctx.stroke();
    ctx.fillStyle = col; ctx.font = "700 11px system-ui, sans-serif";
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText(letter, px, py + 0.5);
  });
}
function drawDraft(g) {
  if (!state.draft) return;
  const pts = state.draft.pts;
  const isZone = state.draft.kind === "zone";
  const col = isZone ? (ZONE[state.drawUse] || "#fff") : (ROAD[state.drawTransit] || ["#fff"])[0];
  ctx.beginPath();
  pts.forEach(([x, y], i) => { const px = g.mx(x), py = g.my(y); i ? ctx.lineTo(px, py) : ctx.moveTo(px, py); });
  if (state.mouse) { const mm = snap(state.mouse); ctx.lineTo(g.mx(mm[0]), g.my(mm[1])); }
  ctx.setLineDash([5, 4]); ctx.lineWidth = 2; ctx.strokeStyle = col; ctx.stroke();
  ctx.setLineDash([]);
  pts.forEach(([x, y], i) => {
    const px = g.mx(x), py = g.my(y);
    ctx.beginPath(); ctx.arc(px, py, i === 0 ? 6 : 4, 0, Math.PI * 2);
    ctx.fillStyle = i === 0 ? "#ffd95a" : "#ffffff"; ctx.fill();
    ctx.lineWidth = 1.5; ctx.strokeStyle = "#1a1c20"; ctx.stroke();
  });
}
function drawSelection(g) {
  if (!state.sel || state.sel.kind !== "zone") return;
  const z = state.submission.zones[state.sel.index];
  if (!z) return;
  z.polygon.forEach(([x, y]) => {
    const px = g.mx(x), py = g.my(y);
    ctx.beginPath(); ctx.rect(px - 4, py - 4, 8, 8);
    ctx.fillStyle = "#ffffff"; ctx.fill();
    ctx.lineWidth = 1.5; ctx.strokeStyle = "#1a1c20"; ctx.stroke();
  });
}
function buildLegend() {
  const used = new Set((state.submission.zones || []).map((z) => z.use));
  const parts = ZONE_CATS.map(([cat, uses]) => {
    const chips = uses.map((u) =>
      `<span class="item${used.has(u) ? " on" : ""}"><span class="sw" style="background:${ZONE[u]}"></span>${ZONE_KR[u]}</span>`).join("");
    return `<div class="legrow"><b>${cat}</b>${chips}</div>`;
  }).join("");
  const terr = `<div class="legrow"><b>지형</b>` +
    [["~", "수면"], ["^", "급경사"], ["T", "숲"], ["w", "습지"], ["F", "농지"]]
      .map(([k, n]) => `<span class="item"><span class="sw" style="background:${TERRAIN_COLORS[k]}"></span>${n}</span>`).join("") + `</div>`;
  $("legend").innerHTML = terr + parts;
}

/* ===========================================================================
 * Interaction
 * ======================================================================== */
function setMode(mode) {
  state.mode = mode;
  state.draft = null;
  document.querySelectorAll(".tool").forEach((b) => b.classList.toggle("active", b.dataset.mode === mode));
  ["zone", "transit", "facility", "station", "event"].forEach((m) =>
    $("palette-" + m).classList.toggle("hidden", m !== mode));
  canvas.style.cursor = mode === "select" ? "default" : "crosshair";
  draw();
}
function hitVertex(px, py, poly) {
  for (let i = 0; i < poly.length; i++) {
    if (Math.hypot(state.g.mx(poly[i][0]) - px, state.g.my(poly[i][1]) - py) <= 7) return i;
  }
  return -1;
}
function hitPoint(px, py, arr, radius = 10) {
  for (let i = arr.length - 1; i >= 0; i--)
    if (Math.hypot(state.g.mx(arr[i].x) - px, state.g.my(arr[i].y) - py) <= radius) return i;
  return -1;
}
function hitZone(m) {
  for (let i = state.submission.zones.length - 1; i >= 0; i--)
    if (pointInPoly(m, state.submission.zones[i].polygon)) return i;
  return -1;
}

canvas.addEventListener("mousedown", (e) => {
  if (!state.terrain) return;
  const m = evtMeters(e), [px, py] = evtPx(e);

  if (state.mode === "select") {
    // 1) dragging a vertex of the selected zone
    if (state.sel && state.sel.kind === "zone") {
      const vi = hitVertex(px, py, state.submission.zones[state.sel.index].polygon);
      if (vi >= 0) { pushHistory(); state.drag = { kind: "zonevtx", index: state.sel.index, vi }; return; }
    }
    // 2) events (also draggable)
    const ei = hitPoint(px, py, state.events, 11);
    if (ei >= 0) { state.sel = { kind: "event", index: ei }; showEventInspector(ei); pushHistory(); state.drag = { kind: "event", index: ei }; refreshButtons(); draw(); return; }
    // 3) facilities (draggable)
    const fi = hitPoint(px, py, state.submission.facilities);
    if (fi >= 0) { state.sel = { kind: "facility", index: fi }; hideInspector(); pushHistory(); state.drag = { kind: "facility", index: fi }; refreshButtons(); draw(); return; }
    // 3b) hubs then stations (draggable)
    const hi = hitPoint(px, py, state.submission.hubs, 10);
    if (hi >= 0) { state.sel = { kind: "hub", index: hi }; hideInspector(); pushHistory(); state.drag = { kind: "hub", index: hi }; refreshButtons(); draw(); return; }
    const si = hitPoint(px, py, state.submission.stations, 8);
    if (si >= 0) { state.sel = { kind: "station", index: si }; hideInspector(); pushHistory(); state.drag = { kind: "station", index: si }; refreshButtons(); draw(); return; }
    // 4) select a zone
    const zi = hitZone(m);
    state.sel = zi >= 0 ? { kind: "zone", index: zi } : null;
    hideInspector(); refreshButtons(); draw();
    return;
  }

  if (state.mode === "zone") {
    if (!state.draft) state.draft = { kind: "zone", pts: [] };
    const pts = state.draft.pts;
    if (pts.length >= 3 && Math.hypot(state.g.mx(pts[0][0]) - px, state.g.my(pts[0][1]) - py) <= 8) {
      commitDraft();                 // auto-close: clicked near first vertex
    } else { pts.push(snap(m)); draw(); }
    return;
  }
  if (state.mode === "transit") {
    if (!state.draft) state.draft = { kind: "transit", pts: [] };
    state.draft.pts.push(snap(m)); draw();
    return;
  }
  if (state.mode === "facility") {
    pushHistory();
    const p = snap(m);
    state.submission.facilities.push({ type: state.drawFacility, x: p[0], y: p[1] });
    state.sel = { kind: "facility", index: state.submission.facilities.length - 1 };
    refreshButtons(); draw(); return;
  }
  if (state.mode === "station") {
    pushHistory();
    const p = snap(m);
    state.submission.stations.push({ type: state.drawStation, x: p[0], y: p[1] });
    state.sel = { kind: "station", index: state.submission.stations.length - 1 };
    refreshButtons(); draw(); return;
  }
  if (state.mode === "hub") {
    pushHistory();
    const p = snap(m);
    state.submission.hubs.push({ x: p[0], y: p[1] });
    state.sel = { kind: "hub", index: state.submission.hubs.length - 1 };
    refreshButtons(); draw(); return;
  }
  if (state.mode === "event") {
    pushHistory();
    const info = EVENT_INFO[state.drawEvent];
    const p = snap(m);
    state.events.push({
      type: state.drawEvent, x: p[0], y: p[1],
      radius: Math.max(500, parseInt($("event-radius").value, 10) || 4000),
      class: info ? info[1] : "mixed", name: info ? info[2] : state.drawEvent,
    });
    state.sel = { kind: "event", index: state.events.length - 1 };
    showEventInspector(state.sel.index); refreshButtons(); draw();
  }
});

canvas.addEventListener("mousemove", (e) => {
  if (!state.terrain) return;
  const m = evtMeters(e);
  state.mouse = m;
  if (state.drag) {
    const p = snap(m);
    if (state.drag.kind === "zonevtx") {
      state.submission.zones[state.drag.index].polygon[state.drag.vi] = p;
    } else if (state.drag.kind === "event") {
      const ev = state.events[state.drag.index]; ev.x = p[0]; ev.y = p[1];
    } else if (state.drag.kind === "facility") {
      const f = state.submission.facilities[state.drag.index]; f.x = p[0]; f.y = p[1];
    } else if (state.drag.kind === "station") {
      const s = state.submission.stations[state.drag.index]; s.x = p[0]; s.y = p[1];
    } else if (state.drag.kind === "hub") {
      const hb = state.submission.hubs[state.drag.index]; hb.x = p[0]; hb.y = p[1];
    }
    draw();
  } else if (state.draft) {
    draw();
  }
  updateReadout(m);
});

canvas.addEventListener("mouseup", () => { state.drag = null; });
canvas.addEventListener("dblclick", (e) => { e.preventDefault(); if (state.draft) commitDraft(); });
canvas.addEventListener("mouseleave", () => { state.mouse = null; if (!state.drag) updateReadout(null); });

function updateReadout(m) {
  const out = $("readout");
  if (!m) { out.textContent = state.terrain ? `${state.g.w}×${state.g.h} 셀 · ${state.g.cell}m/셀` : ""; return; }
  const p = snap(m);
  let txt = `x ${p[0]} · y ${p[1]} m${state.snap ? " ⊞" : ""}`;
  if (state.draft && state.draft.kind === "zone" && state.draft.pts.length >= 2) {
    txt += ` · 면적 ${polyAreaKm2([...state.draft.pts, m]).toFixed(2)} km²`;
  } else if (state.draft && state.draft.kind === "transit" && state.draft.pts.length >= 1) {
    txt += ` · 길이 ${polylineKm([...state.draft.pts, m]).toFixed(2)} km`;
  } else if (state.drag && state.drag.kind === "zonevtx") {
    txt += ` · 면적 ${polyAreaKm2(state.submission.zones[state.drag.index].polygon).toFixed(2)} km²`;
  }
  out.textContent = txt;
}

function commitDraft() {
  const d = state.draft; state.draft = null;
  if (!d) return;
  if (d.kind === "zone") {
    if (d.pts.length < 3) { draw(); return; }
    pushHistory();
    const poly = d.pts.map((p) => [round(p[0]), round(p[1])]);
    state.submission.zones.push({ use: state.drawUse, polygon: poly });
    checkOverlap(poly);
  } else {
    if (d.pts.length < 2) { draw(); return; }
    pushHistory();
    state.submission.transit.push({ type: state.drawTransit, path: d.pts.map((p) => [round(p[0]), round(p[1])]) });
  }
  draw();
}
function checkOverlap(poly) {
  const others = state.submission.zones.slice(0, -1);
  const hit = others.some((z) => polysOverlap(poly, z.polygon));
  const warn = $("warn");
  if (hit) {
    warn.textContent = "⚠ 새 구역이 기존 구역과 겹칩니다. 채점 시 나중에 그린 구역이 우선합니다.";
    warn.classList.remove("hidden");
    clearTimeout(checkOverlap._t);
    checkOverlap._t = setTimeout(() => warn.classList.add("hidden"), 4000);
  } else warn.classList.add("hidden");
}
function deleteSelected() {
  if (!state.sel) return;
  pushHistory();
  const { kind, index } = state.sel;
  if (kind === "zone") state.submission.zones.splice(index, 1);
  else if (kind === "transit") state.submission.transit.splice(index, 1);
  else if (kind === "facility") state.submission.facilities.splice(index, 1);
  else if (kind === "station") state.submission.stations.splice(index, 1);
  else if (kind === "hub") state.submission.hubs.splice(index, 1);
  else if (kind === "event") state.events.splice(index, 1);
  state.sel = null; hideInspector(); refreshButtons(); draw();
}

document.addEventListener("keydown", (e) => {
  if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return;
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") { e.preventDefault(); return e.shiftKey ? redo() : undo(); }
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "y") { e.preventDefault(); return redo(); }
  if (e.key === "Enter") { if (state.draft) commitDraft(); return; }
  if (e.key === "Escape") { state.draft = null; state.sel = null; hideInspector(); draw(); return; }
  if (e.key === "Delete" || e.key === "Backspace") { deleteSelected(); return; }
  const map = { v: "select", z: "zone", t: "transit", f: "facility", s: "station", h: "hub", e: "event" };
  if (map[e.key.toLowerCase()]) setMode(map[e.key.toLowerCase()]);
});

/* ===========================================================================
 * Inspector (event details + score impact)
 * ======================================================================== */
function eventResultFor(idx) {
  if (!state.lastResult || !state.lastResult.events) return null;
  const ev = state.events[idx];
  // match by type + nearest coordinate among results of same type
  const same = state.lastResult.events.filter((r) => r.type === ev.type);
  return same.length ? same[Math.min(idx, same.length - 1)] : null;
}
function showEventInspector(idx) {
  const ev = state.events[idx];
  if (!ev) return hideInspector();
  const info = EVENT_INFO[ev.type] || ["?", "mixed", ev.type, ""];
  const col = RING[info[1]] || RING.mixed;
  const r = eventResultFor(idx);
  let impact = `<div class="imp muted">채점하면 점수 반영이 표시됩니다.</div>`;
  if (r) {
    const cls = r.net > 0 ? "pos" : r.net < 0 ? "neg" : "";
    impact = `<div class="imp">점수 반영 <span class="net ${cls}">${r.net > 0 ? "+" : ""}${r.net}</span>
      <span class="muted">(+${r.gain} / −${r.loss})</span></div>`;
  }
  $("inspector").innerHTML = `
    <div class="ins-head"><span class="dot" style="background:${col}"></span>
      <b>${info[2]}</b><span class="chip" style="border-color:${col};color:${col}">${CLASS_KR[info[1]]}</span></div>
    <div class="muted desc">${info[3]}</div>
    <div class="ins-kv"><span>좌표</span><span>${round(ev.x)}, ${round(ev.y)} m</span></div>
    <div class="ins-kv"><span>반경</span><span>${ev.radius} m</span></div>
    ${impact}
    <div class="ins-actions"><button id="ins-del">이 이벤트 삭제</button></div>`;
  $("inspector").classList.remove("hidden");
  $("ins-del").addEventListener("click", () => { state.sel = { kind: "event", index: idx }; deleteSelected(); });
}
function hideInspector() { $("inspector").classList.add("hidden"); }

/* ===========================================================================
 * Scoring + panel
 * ======================================================================== */
async function scoreNow() {
  if (!state.terrainFile) return;
  setStatus("채점 중…");
  const res = await fetch("/api/score", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ terrain_file: state.terrainFile, submission: state.submission, events: state.events }),
  });
  const result = await res.json();
  if (result.error) return setStatus(result.error, "err");
  state.lastResult = result;
  renderPanel(result);
  if (state.sel && state.sel.kind === "event") showEventInspector(state.sel.index);
  setStatus(result.status === "OK" ? `채점 완료 — ${result.score} (${result.grade})` : "게이트 실패",
            result.status === "OK" ? "ok" : "err");
}
function resetPanel() {
  $("panel").innerHTML = '<div class="placeholder">도구로 그리거나 제출물을 불러온 뒤 ‘채점’을 누르세요.</div>';
}
function renderPanel(r) {
  const panel = $("panel");
  if (r.status !== "OK") {
    panel.innerHTML = `<div class="fail-box"><div class="title">FAILED — 하드 게이트 위반</div>
      <ul>${(r.reasons || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>`;
    return;
  }
  const axes = AXES.map((a) => {
    const v = r.axes[a] || 0;
    return `<div class="axis"><div class="row"><span>${AXIS_KR[a]}</span><span>${v.toFixed(0)} / 200</span></div>
      <div class="bar"><span style="width:${Math.min(100, v / 2)}%"></span></div></div>`;
  }).join("");
  const events = (r.events || []).map((e) => {
    const info = EVENT_INFO[e.type] || ["?", "mixed", e.type, ""];
    const net = e.net || 0, cls = net > 0 ? "pos" : net < 0 ? "neg" : "";
    return `<div class="event" title="${esc(info[3])}"><span class="nm"><span class="dot" style="background:${RING[info[1]] || RING.mixed}"></span>${info[2]}</span>
      <span class="net ${cls}">${net > 0 ? "+" : ""}${net}</span></div>`;
  }).join("");
  const kv = (k, v) => `<div class="kv"><span class="k">${k}</span><span>${v}</span></div>`;
  const s = r.stats || {};
  panel.innerHTML = `
    <div class="score-head"><span class="score">${r.score}</span><span class="grade ${r.grade}">${r.grade}</span></div>
    <div class="objective">${esc(r.objective || "")}</div>
    <div class="axes">${axes}</div>
    ${kv("기본 점수(1000)", r.base_1000)}
    ${kv("목적 적합 보너스", `${r.fit_bonus} (${r.objective_fit})`)}
    ${kv("이벤트 점수", r.event_score)}
    ${kv("난이도", `${r.difficulty}${r.effective_difficulty ? " → ×" + r.effective_difficulty : ""}`)}
    ${kv("인구 / 일자리", `${fmt(s.residents)} / ${fmt(s.jobs)}`)}
    ${kv("예산 사용", `${fmt(s.spent)} / ${fmt(s.budget)}`)}
    ${events ? `<h3>이벤트 점수 반영</h3><div class="events">${events}</div>` : ""}`;
}

/* ===========================================================================
 * Leaderboard · comparison
 * ======================================================================== */
const LB_DIR = "submissions_demo";
function axisMiniBars(axes) {
  return AXES.map((a) => {
    const v = axes[a] || 0;
    return `<span class="mini" title="${AXIS_KR[a]} ${v.toFixed(0)}"><span style="height:${Math.min(100, v / 2)}%"></span></span>`;
  }).join("");
}
function lbRow(rank, r, current) {
  const cls = current ? "lbrow current" : "lbrow" + (r.status !== "OK" ? " failed" : "");
  const score = r.status === "OK" ? r.score : "—";
  const grade = r.status === "OK" ? `<span class="grade ${r.grade}">${r.grade}</span>` : `<span class="gx">FAIL</span>`;
  const name = current ? "▶ 현재 작업" : esc(r.name || r.file);
  const action = current ? "" : `<button class="lb-load" data-file="${esc(r.file)}">불러오기</button>`;
  return `<tr class="${cls}">
    <td class="rk">${rank}</td><td class="nm">${name}</td>
    <td class="sc">${score}</td><td>${grade}</td>
    <td class="bars">${r.axes ? axisMiniBars(r.axes) : ""}</td>
    <td class="ac">${action}</td></tr>`;
}
async function openLeaderboard() {
  if (!state.terrainFile) return;
  const modal = $("lb-modal"), body = $("lb-body");
  modal.classList.remove("hidden");
  body.innerHTML = '<div class="placeholder">채점 중…</div>';
  const data = await (await fetch(`/api/leaderboard?file=${encodeURIComponent(state.terrainFile)}&dir=${LB_DIR}`)).json();
  if (data.error) { body.innerHTML = `<div class="placeholder">${data.error}</div>`; return; }
  $("lb-sub").textContent = `${data.terrain} · ${data.objective} · ${LB_DIR}/`;

  // Merge in the current working submission (if scored) and rank everything.
  const rows = data.rows.map((r) => ({ r, current: false }));
  if (state.lastResult && state.lastResult.status) {
    rows.push({ current: true, r: {
      file: "__current__", name: "현재 작업",
      status: state.lastResult.status, score: state.lastResult.score || 0,
      grade: state.lastResult.grade, axes: state.lastResult.axes || {},
    }});
  }
  rows.sort((a, b) => (a.r.status !== "OK") - (b.r.status !== "OK") || b.r.score - a.r.score);

  const head = `<table class="lb"><thead><tr>
    <th>#</th><th>이름</th><th>점수</th><th>등급</th><th>축(경·교·환·주·도)</th><th></th>
    </tr></thead><tbody>`;
  body.innerHTML = head + rows.map((x, i) => lbRow(i + 1, x.r, x.current)).join("") + "</tbody></table>";
  body.querySelectorAll(".lb-load").forEach((b) =>
    b.addEventListener("click", () => loadFromLeaderboard(b.dataset.file)));
}
async function loadFromLeaderboard(file) {
  const sub = await (await fetch(`/api/submission?dir=${LB_DIR}&file=${encodeURIComponent(file)}`)).json();
  if (sub.error) return setStatus(sub.error, "err");
  state.submission = Object.assign(EMPTY_SUB(), sub);
  delete state.submission.metadata;
  if (Array.isArray(sub.events)) state.events = sub.events;
  state.history = []; state.redo = []; state.sel = null; refreshButtons();
  $("lb-modal").classList.add("hidden");
  draw(); scoreNow();
  setStatus(`'${file}' 불러옴`, "ok");
}

/* ===========================================================================
 * Utilities
 * ======================================================================== */
function hexRgb(hex) { const h = hex.replace("#", ""); return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)]; }
function shade(hex, f) { const [r, g, b] = hexRgb(hex); const c = (v) => ("0" + Math.round(v * f).toString(16)).slice(-2); return "#" + c(r) + c(g) + c(b); }
function luminance(hex) { const [r, g, b] = hexRgb(hex); return (0.299 * r + 0.587 * g + 0.114 * b) / 255; }
function roundRect(x, y, w, h, r) {
  ctx.beginPath(); ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
}
function round(n) { return Math.round(n); }
// Snap a meter point to the grid when snapping is on, else round to integer.
function snap(m) {
  if (state.snap) { const s = state.gridStep; return [Math.round(m[0] / s) * s, Math.round(m[1] / s) * s]; }
  return [round(m[0]), round(m[1])];
}
function fmt(n) { return (n || 0).toLocaleString(); }
function esc(s) { return String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c])); }

/* ===========================================================================
 * Palettes + wiring
 * ======================================================================== */
function fillZonePalette() {
  const sel = $("zone-use"); sel.innerHTML = "";
  ZONE_CATS.forEach(([cat, uses]) => {
    const og = document.createElement("optgroup"); og.label = cat;
    uses.forEach((u) => { const o = document.createElement("option"); o.value = u; o.textContent = ZONE_KR[u]; og.appendChild(o); });
    sel.appendChild(og);
  });
  sel.value = state.drawUse;
}
function fillSimple(id, obj, kr, cur) {
  const sel = $(id); sel.innerHTML = "";
  Object.keys(obj).forEach((k) => { const o = document.createElement("option"); o.value = k; o.textContent = kr[k] || k; sel.appendChild(o); });
  sel.value = cur;
}
function fillEventPalette() {
  const sel = $("event-type"); sel.innerHTML = "";
  [["opportunity", "기회(보너스)"], ["mixed", "양면"], ["hazard", "재난(페널티)"]].forEach(([klass, label]) => {
    const og = document.createElement("optgroup"); og.label = label;
    Object.keys(EVENT_INFO).filter((t) => EVENT_INFO[t][1] === klass).forEach((t) => {
      const o = document.createElement("option"); o.value = t; o.textContent = EVENT_INFO[t][2]; og.appendChild(o);
    });
    sel.appendChild(og);
  });
  sel.value = state.drawEvent;
}

$("terrain-select").addEventListener("change", (e) => selectTerrain(e.target.value));
$("btn-reference").addEventListener("click", loadReference);
$("btn-export").addEventListener("click", exportJSON);
$("btn-score").addEventListener("click", scoreNow);
$("file-input").addEventListener("change", (e) => { if (e.target.files[0]) loadSubmissionFile(e.target.files[0]); });
$("btn-undo").addEventListener("click", undo);
$("btn-redo").addEventListener("click", redo);
$("btn-delete").addEventListener("click", deleteSelected);
$("btn-finish").addEventListener("click", () => { if (state.draft) commitDraft(); });
document.querySelectorAll(".tool").forEach((b) => b.addEventListener("click", () => setMode(b.dataset.mode)));
$("zone-use").addEventListener("change", (e) => { state.drawUse = e.target.value; });
$("transit-type").addEventListener("change", (e) => { state.drawTransit = e.target.value; });
$("facility-type").addEventListener("change", (e) => { state.drawFacility = e.target.value; });
$("station-type").addEventListener("change", (e) => { state.drawStation = e.target.value; });
$("event-type").addEventListener("change", (e) => { state.drawEvent = e.target.value; });
$("snap-on").addEventListener("change", (e) => { state.snap = e.target.checked; draw(); });
$("snap-step").addEventListener("change", (e) => { state.gridStep = parseInt(e.target.value, 10); if (state.snap) draw(); });
$("btn-leaderboard").addEventListener("click", openLeaderboard);
$("lb-close").addEventListener("click", () => $("lb-modal").classList.add("hidden"));
$("lb-modal").addEventListener("click", (e) => { if (e.target.id === "lb-modal") $("lb-modal").classList.add("hidden"); });

fillZonePalette();
fillSimple("transit-type", ROAD, TRANSIT_KR, state.drawTransit);
fillSimple("facility-type", FAC, FAC_KR, state.drawFacility);
fillSimple("station-type", STATION_KR, STATION_KR, state.drawStation);
fillEventPalette();
setMode("select");
loadTerrainList().catch((e) => setStatus("초기화 실패: " + e.message, "err"));
