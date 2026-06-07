"use strict";

// Palette mirrored from render2.py so the web viewer matches the PNG renderer.
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
// type -> [color, core width, dashed]
const ROAD = {
  arterial: ["#c8ccd2", 0.9, false], brt: ["#2aa0dc", 2.2, false],
  rail: ["#8a8f98", 1.8, true], freight_rail: ["#9c7b5a", 1.8, true],
  highway: ["#ffffff", 3.0, false], subway: ["#1f2430", 2.6, false],
};
const FAC = {
  airport: ["A", "#3a7bd5"], port: ["P", "#2a6f97"],
  freight_terminal: ["F", "#9c6b3f"], power: ["E", "#e0a020"],
  water_treatment: ["W", "#3aa0c0"], waste: ["X", "#7a8a5a"],
};
const EVENT_VIS = {
  mineral_deposit: ["M", "opportunity"], deep_harbor: ["H", "opportunity"],
  oil_field: ["O", "mixed"], fault_line: ["!", "hazard"],
  floodplain: ["F", "mixed"], heritage_site: ["G", "mixed"],
  natural_reserve: ["N", "mixed"], landslide_zone: ["L", "hazard"],
  typhoon_corridor: ["T", "hazard"], wind_corridor: ["W", "opportunity"],
  aquifer_recharge: ["A", "mixed"], scenic_viewpoint: ["V", "opportunity"],
  geothermal_spring: ["S", "opportunity"], fertile_soil: ["Y", "mixed"],
  subsidence_zone: ["D", "hazard"], bridge_chokepoint: ["B", "opportunity"],
};
const EVENT_KR = {
  mineral_deposit: "광맥", deep_harbor: "심해항", oil_field: "유전", fault_line: "단층",
  floodplain: "범람원", heritage_site: "유산지", natural_reserve: "보호구역",
  landslide_zone: "산사태", typhoon_corridor: "태풍", wind_corridor: "풍력",
  aquifer_recharge: "대수층", scenic_viewpoint: "경관", geothermal_spring: "온천",
  fertile_soil: "비옥토", subsidence_zone: "침하", bridge_chokepoint: "교량지점",
};
const RING = { opportunity: "#3fae54", hazard: "#e05050", mixed: "#e0a020" };
const AXES = ["economy", "transport", "environment", "housing", "urban_form"];
const AXIS_KR = {
  economy: "경제", transport: "교통", environment: "환경",
  housing: "주거", urban_form: "도시구조",
};

const state = { terrain: null, terrainFile: null, submission: null };

const $ = (id) => document.getElementById(id);
const canvas = $("map");
const ctx = canvas.getContext("2d");

function setStatus(msg, kind = "") {
  const el = $("status");
  el.textContent = msg;
  el.className = "status" + (kind ? " " + kind : "");
}

// --- data loading ---------------------------------------------------------
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
  state.submission = null;
  $("btn-score").disabled = true;
  resetPanel();
  draw();
  setStatus("지형 로드됨. 기준 제출물을 불러오거나 JSON을 업로드하세요.");
}

async function loadReference() {
  if (!state.terrainFile) return;
  setStatus("기준 제출물 생성 중…");
  const res = await fetch("/api/reference?file=" + encodeURIComponent(state.terrainFile));
  const sub = await res.json();
  if (sub.error) { setStatus(sub.error, "err"); return; }
  state.submission = sub;
  draw();
  await scoreNow();
}

function loadSubmissionFile(file) {
  const reader = new FileReader();
  reader.onload = () => {
    try {
      state.submission = JSON.parse(reader.result);
      $("btn-score").disabled = false;
      draw();
      setStatus("제출물 로드됨. ‘채점’을 누르세요.", "ok");
    } catch (e) {
      setStatus("JSON 파싱 실패: " + e.message, "err");
    }
  };
  reader.readAsText(file);
}

async function scoreNow() {
  if (!state.submission || !state.terrainFile) return;
  setStatus("채점 중…");
  const res = await fetch("/api/score", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ terrain_file: state.terrainFile, submission: state.submission }),
  });
  const result = await res.json();
  if (result.error) { setStatus(result.error, "err"); return; }
  renderPanel(result);
  setStatus(result.status === "OK" ? `채점 완료 — ${result.score} (${result.grade})`
                                   : "게이트 실패", result.status === "OK" ? "ok" : "err");
}

// --- canvas drawing -------------------------------------------------------
function geom() {
  const t = state.terrain;
  const cell = t.cell_size_m;
  const w = t.width || t.rows[0].length;
  const h = t.height || t.rows.length;
  const cpx = Math.max(3, Math.round(900 / w)); // pixels per cell
  return { cell, w, h, cpx, mx: (m) => (m / cell) * cpx, my: (m) => (m / cell) * cpx };
}

function draw() {
  if (!state.terrain) return;
  const g = geom();
  canvas.width = g.w * g.cpx;
  canvas.height = g.h * g.cpx;

  drawTerrain(g);
  if (state.submission) {
    drawZones(g);
    drawTransit(g);
    drawFacilities(g);
    drawStations(g);
    drawHubs(g);
  }
  drawEvents(g);
  if (state.submission) drawZoneLabels(g);
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

function drawZones(g) {
  (state.submission.zones || []).forEach((z) => {
    const col = ZONE[z.use] || "#999999";
    ctx.beginPath();
    z.polygon.forEach(([x, y], i) => {
      const px = g.mx(x), py = g.my(y);
      i ? ctx.lineTo(px, py) : ctx.moveTo(px, py);
    });
    ctx.closePath();
    ctx.fillStyle = col + "8c"; // ~55% alpha
    ctx.fill();
    ctx.strokeStyle = shade(col, 0.7);
    ctx.lineWidth = 1;
    ctx.stroke();
  });
}

function drawZoneLabels(g) {
  ctx.font = "600 11px system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  (state.submission.zones || []).forEach((z) => {
    let cx = 0, cy = 0;
    z.polygon.forEach(([x, y]) => { cx += x; cy += y; });
    cx /= z.polygon.length; cy /= z.polygon.length;
    const label = ZONE_KR[z.use] || z.use;
    const px = g.mx(cx), py = g.my(cy);
    ctx.lineWidth = 3; ctx.strokeStyle = "#ffffffcc";
    ctx.strokeText(label, px, py);
    ctx.fillStyle = "#222428";
    ctx.fillText(label, px, py);
  });
}

function drawTransit(g) {
  (state.submission.transit || []).forEach((line) => {
    const spec = ROAD[line.type] || ["#bbbbbb", 1.0, false];
    const [col, core, dashed] = spec;
    ctx.beginPath();
    line.path.forEach(([x, y], i) => {
      const px = g.mx(x), py = g.my(y);
      i ? ctx.lineTo(px, py) : ctx.moveTo(px, py);
    });
    ctx.setLineDash(dashed ? [6, 5] : []);
    ctx.lineWidth = Math.max(1.4, core * g.cpx * 0.5);
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    ctx.strokeStyle = col;
    ctx.stroke();
  });
  ctx.setLineDash([]);
}

function drawFacilities(g) {
  (state.submission.facilities || []).forEach((f) => {
    const [letter, col] = FAC[f.type] || ["?", "#888888"];
    const px = g.mx(f.x), py = g.my(f.y), r = 9;
    roundRect(px - r, py - r, 2 * r, 2 * r, 3);
    ctx.fillStyle = "#ffffff"; ctx.fill();
    ctx.lineWidth = 2; ctx.strokeStyle = col; ctx.stroke();
    ctx.fillStyle = col;
    ctx.font = "700 11px system-ui, sans-serif";
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText(letter, px, py + 0.5);
  });
}

function drawStations(g) {
  ctx.fillStyle = "#ffffff"; ctx.strokeStyle = "#222428"; ctx.lineWidth = 1;
  (state.submission.stations || []).forEach((s) => {
    ctx.beginPath();
    ctx.arc(g.mx(s.x), g.my(s.y), 3, 0, Math.PI * 2);
    ctx.fill(); ctx.stroke();
  });
}

function drawHubs(g) {
  (state.submission.hubs || []).forEach((hb) => {
    const px = g.mx(hb.x), py = g.my(hb.y);
    ctx.beginPath(); ctx.arc(px, py, 7, 0, Math.PI * 2);
    ctx.fillStyle = "#1f2430"; ctx.fill();
    ctx.lineWidth = 2; ctx.strokeStyle = "#ffffff"; ctx.stroke();
  });
}

function drawEvents(g) {
  (state.terrain.events || []).forEach((e) => {
    const [letter, defClass] = EVENT_VIS[e.type] || [(e.type || "?")[0].toUpperCase(), "mixed"];
    const klass = e.class || defClass;
    const col = RING[klass] || RING.mixed;
    const px = g.mx(e.x), py = g.my(e.y);
    const rr = (e.radius || 0) / g.cell * g.cpx;
    if (rr > 2) {
      ctx.beginPath(); ctx.arc(px, py, rr, 0, Math.PI * 2);
      ctx.setLineDash([4, 4]); ctx.lineWidth = 1.5; ctx.strokeStyle = col; ctx.stroke();
      ctx.setLineDash([]);
    }
    ctx.beginPath(); ctx.arc(px, py, 9, 0, Math.PI * 2);
    ctx.fillStyle = "#ffffff"; ctx.fill();
    ctx.lineWidth = 2; ctx.strokeStyle = col; ctx.stroke();
    ctx.fillStyle = col; ctx.font = "700 11px system-ui, sans-serif";
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText(letter, px, py + 0.5);
  });
}

function buildLegend() {
  const items = [];
  const used = new Set((state.submission?.zones || []).map((z) => z.use));
  if (used.size === 0) Object.keys(ZONE).forEach((k) => used.add(k));
  used.forEach((u) => items.push([ZONE[u] || "#999", ZONE_KR[u] || u]));
  const html = items.map(([c, label]) =>
    `<span class="item"><span class="sw" style="background:${c}"></span>${label}</span>`).join("");
  const terr = `<span class="item"><span class="sw" style="background:${TERRAIN_COLORS["~"]}"></span>수면</span>` +
               `<span class="item"><span class="sw" style="background:${TERRAIN_COLORS["^"]}"></span>급경사</span>` +
               `<span class="item"><span class="sw" style="background:${TERRAIN_COLORS["T"]}"></span>숲</span>`;
  $("legend").innerHTML = terr + html;
}

// --- score panel ----------------------------------------------------------
function resetPanel() {
  $("panel").innerHTML = '<div class="placeholder">제출물을 불러오면 점수가 표시됩니다.</div>';
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
    const klass = e.class || (EVENT_VIS[e.type] || [null, "mixed"])[1];
    const name = EVENT_KR[e.type] || e.type;
    const net = e.net || 0;
    const cls = net > 0 ? "pos" : net < 0 ? "neg" : "";
    const sign = net > 0 ? "+" : "";
    return `<div class="event"><span class="nm"><span class="dot" style="background:${RING[klass] || RING.mixed}"></span>${name}</span>
      <span class="net ${cls}">${sign}${net}</span></div>`;
  }).join("");
  const kv = (k, v) => `<div class="kv"><span class="k">${k}</span><span>${v}</span></div>`;
  const s = r.stats || {};
  panel.innerHTML = `
    <div class="score-head"><span class="score">${r.score}</span>
      <span class="grade ${r.grade}">${r.grade}</span></div>
    <div class="objective">${esc(r.objective || "")}</div>
    <div class="axes">${axes}</div>
    ${kv("기본 점수(1000)", r.base_1000)}
    ${kv("목적 적합 보너스", `${r.fit_bonus} (${r.objective_fit})`)}
    ${kv("이벤트 점수", r.event_score)}
    ${kv("난이도", `${r.difficulty}${r.effective_difficulty ? " → ×" + r.effective_difficulty : ""}`)}
    ${kv("인구 / 일자리", `${fmt(s.residents)} / ${fmt(s.jobs)}`)}
    ${kv("예산 사용", `${fmt(s.spent)} / ${fmt(s.budget)}`)}
    ${events ? `<h3>이벤트</h3><div class="events">${events}</div>` : ""}`;
}

// --- small utilities ------------------------------------------------------
function hexRgb(hex) {
  const h = hex.replace("#", "");
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
}
function shade(hex, f) {
  const [r, g, b] = hexRgb(hex);
  const c = (v) => ("0" + Math.round(v * f).toString(16)).slice(-2);
  return "#" + c(r) + c(g) + c(b);
}
function roundRect(x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}
function fmt(n) { return (n || 0).toLocaleString(); }
function esc(s) { return String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c])); }

// --- wire up --------------------------------------------------------------
$("terrain-select").addEventListener("change", (e) => selectTerrain(e.target.value));
$("btn-reference").addEventListener("click", loadReference);
$("btn-score").addEventListener("click", scoreNow);
$("file-input").addEventListener("change", (e) => {
  if (e.target.files[0]) loadSubmissionFile(e.target.files[0]);
});

loadTerrainList().catch((e) => setStatus("초기화 실패: " + e.message, "err"));
