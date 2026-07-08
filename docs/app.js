/* Bank Nifty Predictor — plain-JS front end for the Today + Calendar tabs. */

const DATA_LATEST = "../data/latest.json";
const DATA_BACKTEST = "../data/backtest_log.json";
const DATA_TECH = "../data/technical.json";
let techLoaded = false;

let backtestByDate = {};   // "YYYY-MM-DD" -> row
let calMonth = null;       // Date pointing at the 1st of the shown month

// ---------------------------------------------------------------------------
// utilities
// ---------------------------------------------------------------------------
function fmt(n) {
  if (n === null || n === undefined) return "—";
  return Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}
function fmt2(n) {
  if (n === null || n === undefined) return "—";
  return Number(n).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}
function el(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstChild;
}
function badgeClass(rec) {
  if (rec === "Buy Zone") return "buy";
  if (rec === "Sell Zone") return "sell";
  return "neutral";
}

// ---------------------------------------------------------------------------
// tab switching
// ---------------------------------------------------------------------------
function showTab(name) {
  ["today", "technical", "calendar"].forEach((t) => {
    document.getElementById("view-" + t).classList.toggle("hidden", name !== t);
    document.getElementById("tab-" + t).classList.toggle("active", name === t);
  });
  if (name === "calendar" && !calMonth) loadCalendar();
  if (name === "technical" && !techLoaded) loadTechnical();
}

// ---------------------------------------------------------------------------
// Today tab
// ---------------------------------------------------------------------------
async function loadToday() {
  try {
    const res = await fetch(DATA_LATEST, { cache: "no-store" });
    if (!res.ok) throw new Error(res.status);
    const d = await res.json();
    renderToday(d);
  } catch (e) {
    document.getElementById("today-loading").textContent =
      "Could not load latest recommendation. Pull to refresh once data is published.";
  }
}

// Re-pull the latest published data (busts the cache). Does NOT contact Kite —
// it reloads whatever was last committed/pushed to the repo.
async function refreshData() {
  const btn = document.getElementById("refresh-btn");
  btn.classList.add("spin");
  try {
    await loadToday();
    calMonth = null;            // force calendar reload next time it's opened
    techLoaded = false;         // force technical reload next time it's opened
    if (!document.getElementById("view-calendar").classList.contains("hidden")) {
      await loadCalendar();
    }
    if (!document.getElementById("view-technical").classList.contains("hidden")) {
      await loadTechnical();
    }
  } finally {
    setTimeout(() => btn.classList.remove("spin"), 400);
  }
}

function shortDate(iso) {
  if (!iso) return "";
  const [y, m, d] = iso.split("-");
  const mon = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][+m - 1] || m;
  return `${d} ${mon}`;
}

// A single driver's day-over-day move and what it implies for Bank Nifty.
function relRow(r) {
  const up = r.change_pct > 0, down = r.change_pct < 0;
  const arrow = up ? "▲" : (down ? "▼" : "▬");
  const chip = r.implication === "bullish" ? "buy" : (r.implication === "bearish" ? "sell" : "neutral");
  const chipTxt = r.implication === "bullish" ? "Supports Bank Nifty"
               : (r.implication === "bearish" ? "Pressures Bank Nifty" : "Neutral");
  const moved = up ? "rose" : (down ? "fell" : "flat");
  const note = r.implication === "neutral"
    ? `${r.name} ${moved} — weak/unclear link right now`
    : `${r.name} ${moved} — ${r.implication === "bullish" ? "supportive for" : "pressure on"} Bank Nifty`;
  const c = r.corr_20d;
  let bar = `<div class="corr-track slim"><div class="corr-zero"></div></div>`;
  if (c !== null && c !== undefined) {
    const mag = Math.min(Math.abs(c), 1) * 50, neg = c < 0;
    const style = neg ? `left:${(50 - mag).toFixed(1)}%;width:${mag.toFixed(1)}%` : `left:50%;width:${mag.toFixed(1)}%`;
    bar = `<div class="corr-track slim"><div class="corr-zero"></div><div class="corr-bar ${neg ? "neg" : "pos"}" style="${style}"></div></div>`;
  }
  return `<div class="rel">
    <div class="rel-top">
      <span class="rel-name">${r.name}</span>
      <span class="rel-vals">${fmt2(r.prev)} <small>${shortDate(r.prev_date)}</small> → ${fmt2(r.value)} <small>${shortDate(r.date)}</small> <b>${arrow}${Math.abs(r.change_pct)}%</b></span>
    </div>
    <div class="rel-mid">${bar}<span class="badge-sm ${chip}">${chipTxt}</span></div>
    <div class="rel-note">${note} · ${r.relationship === "inverse" ? "moves opposite" : "moves with"} BN (${c ?? "—"})</div>
  </div>`;
}

function renderToday(d) {
  document.getElementById("subhead").textContent = "Last updated " + (d.date || "—");
  const corr = d.correlations || {};
  const macro = (d.macro_today || []);
  const o = d.ohlc || {};
  const proj = d.projection || {};
  const chgUp = (d.change || 0) >= 0;
  const scorePos = Math.max(0, Math.min(100, d.score));

  const macroHtml = macro.length
    ? `<div class="card macro"><h3>Scheduled event today</h3>${macro.map(m => `<div>${m.label}</div>`).join("")}</div>`
    : "";

  const html = `
    <div class="card" style="text-align:center">
      <span class="badge ${badgeClass(d.recommendation)}">${d.recommendation}</span>
      <div class="gauge">
        <div class="gauge-track"><div class="gauge-mark" style="left:calc(${scorePos}% - 1.5px)"></div></div>
        <div class="gauge-scale"><span>0 · Sell</span><span>35</span><span>65</span><span>Buy · 100</span></div>
        <div class="gauge-label">Score <b>${d.score}</b>/100 — ${d.score_label || ""}</div>
      </div>
    </div>
    ${macroHtml}
    <div class="card">
      <div class="price-date">Bank Nifty · ${d.date || "—"}</div>
      <div class="price-big">${fmt(d.banknifty_close)}<span class="chg ${chgUp ? "up" : "down"}">${chgUp ? "▲" : "▼"} ${fmt2(Math.abs(d.change))} (${d.change_pct}%)</span></div>
      <div class="ohlc">
        <div class="box"><div class="k">Open</div><div class="v">${fmt(o.open)}</div></div>
        <div class="box"><div class="k">High</div><div class="v">${fmt(o.high)}</div></div>
        <div class="box"><div class="k">Low</div><div class="v">${fmt(o.low)}</div></div>
      </div>
    </div>
    <div class="card">
      <h3>Zones &amp; next-day projection</h3>
      <div class="zones">
        <div class="zone buy"><div class="lbl">Buy zone</div><div class="val">${fmt(d.buy_zone?.[0])}–${fmt(d.buy_zone?.[1])}</div>
          <div class="proj">↑ next-day target <b>${fmt(proj.next_day_upside)}</b></div></div>
        <div class="zone sell"><div class="lbl">Sell zone</div><div class="val">${fmt(d.sell_zone?.[0])}–${fmt(d.sell_zone?.[1])}</div>
          <div class="proj">↓ next-day target <b>${fmt(proj.next_day_downside)}</b></div></div>
      </div>
      <div class="internals">
        <div class="chip"><div class="k">Next-day pivot</div><div class="v">${fmt(proj.next_day_pivot)}</div></div>
        <div class="chip"><div class="k">PCR (ATM ±5)</div><div class="v">${d.pcr ?? "—"}</div></div>
      </div>
      <div class="caption">Projected levels are classic pivot points from today's range — a reference for tomorrow, not a forecast of where price will trade.</div>
    </div>
    <div class="card">
      <h3>Why</h3>
      <ul class="reasons">${(d.reasons || []).map(r => `<li>${r}</li>`).join("")}</ul>
    </div>
    <div class="card">
      <h3>Bank Nifty vs its drivers — yesterday → today</h3>
      ${(d.relationships || []).map(relRow).join("") || '<div class="caption">Not enough data yet.</div>'}
      <div class="caption">Direction is inferred from each driver's 20-day correlation with Bank Nifty (blue bar = moves opposite, amber = moves with). E.g. VIX moves opposite, so VIX <b>falling</b> is supportive. Educational only — a tendency, not a guarantee.</div>
    </div>`;
  const c = document.getElementById("today-content");
  c.innerHTML = html;
  c.classList.remove("hidden");
  document.getElementById("today-loading").classList.add("hidden");
}

// ---------------------------------------------------------------------------
// Technical tab
// ---------------------------------------------------------------------------
const MA_COLOR = { 20: "var(--ma20)", 50: "var(--ma50)", 100: "var(--ma100)", 200: "var(--ma200)" };

function scrollChartToEnd(tries) {
  tries = tries || 0;
  const sc = document.getElementById("chart-scroll");
  if (sc && sc.scrollWidth > sc.clientWidth) {
    sc.scrollLeft = sc.scrollWidth;
  } else if (tries < 10) {
    setTimeout(() => scrollChartToEnd(tries + 1), 60);
  }
}

async function loadTechnical() {
  try {
    const res = await fetch(DATA_TECH, { cache: "no-store" });
    if (!res.ok) throw new Error(res.status);
    renderTechnical(await res.json());
    techLoaded = true;
  } catch (e) {
    document.getElementById("tech-loading").textContent = "Chart data not available yet.";
  }
}

function renderTechnical(t) {
  const c = t.candles, s = t.ma_summary;
  const step = 9, bodyW = 6, top = 8, plotH = 270, H = 320, padX = 4;
  const plotW = padX * 2 + c.length * step;
  let minP = Infinity, maxP = -Infinity;
  c.forEach((d) => { minP = Math.min(minP, d.l); maxP = Math.max(maxP, d.h); });
  const gap = (maxP - minP) * 0.04; minP -= gap; maxP += gap;
  const y = (v) => top + (maxP - v) / (maxP - minP) * plotH;
  const x = (i) => padX + i * step + step / 2;

  let grid = "", yaxis = "";
  for (let g = 0; g <= 5; g++) {
    const val = minP + (maxP - minP) * g / 5, yy = y(val);
    grid += `<line x1="0" y1="${yy.toFixed(1)}" x2="${plotW}" y2="${yy.toFixed(1)}" stroke="var(--line)" stroke-width="1"/>`;
    yaxis += `<text x="44" y="${(yy + 3).toFixed(1)}" text-anchor="end" font-size="9" fill="var(--muted)">${Math.round(val).toLocaleString("en-IN")}</text>`;
  }
  let candles = "";
  c.forEach((d, i) => {
    const cx = x(i), col = d.c >= d.o ? "var(--up)" : "var(--down)";
    const bt = Math.min(y(d.o), y(d.c)), bh = Math.max(1, Math.abs(y(d.c) - y(d.o)));
    candles += `<line x1="${cx}" y1="${y(d.h).toFixed(1)}" x2="${cx}" y2="${y(d.l).toFixed(1)}" stroke="${col}" stroke-width="1"/>`;
    candles += `<rect x="${(cx - bodyW / 2).toFixed(1)}" y="${bt.toFixed(1)}" width="${bodyW}" height="${bh.toFixed(1)}" fill="${col}"/>`;
  });
  let mas = "";
  [20, 50, 100, 200].forEach((n) => {
    const pts = [];
    c.forEach((d, i) => { const v = d["ma" + n]; if (v != null) pts.push(`${x(i).toFixed(1)},${y(v).toFixed(1)}`); });
    if (pts.length > 1) mas += `<polyline points="${pts.join(" ")}" fill="none" stroke="${MA_COLOR[n]}" stroke-width="1.6"/>`;
  });
  let srlines = "";
  (t.levels || []).forEach((lv) => {
    const yy = y(lv.price); if (yy < top || yy > top + plotH) return;
    const col = lv.type === "support" ? "var(--up)" : "var(--down)";
    srlines += `<line x1="0" y1="${yy.toFixed(1)}" x2="${plotW}" y2="${yy.toFixed(1)}" stroke="${col}" stroke-width="1" stroke-dasharray="4 4" opacity="0.55"/>`;
  });
  const idx = {}; c.forEach((d, i) => { idx[d.date] = i; });
  let pmark = "";
  (t.patterns || []).forEach((p) => {
    const i = idx[p.date]; if (i == null) return;
    const col = p.dir === "bull" ? "var(--up)" : (p.dir === "bear" ? "var(--down)" : "var(--neutral)");
    const yy = p.dir === "bear" ? y(c[i].h) - 6 : y(c[i].l) + 6;
    pmark += `<circle cx="${x(i)}" cy="${yy.toFixed(1)}" r="3" fill="${col}"><title>${p.date} ${p.type}</title></circle>`;
  });
  let cross = "";
  (t.crosses || []).forEach((cr) => {
    const i = idx[cr.date]; if (i == null) return;
    const col = cr.type === "golden" ? "var(--up)" : "var(--down)";
    cross += `<line x1="${x(i)}" y1="${top}" x2="${x(i)}" y2="${top + plotH}" stroke="${col}" stroke-width="1" stroke-dasharray="2 3" opacity="0.7"/>`;
    cross += `<text x="${x(i) + 2}" y="${top + 12}" font-size="9" fill="${col}">${cr.type === "golden" ? "GC" : "DC"}</text>`;
  });
  let dax = "";
  for (let k = 0; k < 6; k++) {
    const i = Math.round((c.length - 1) * k / 5);
    dax += `<text x="${x(i)}" y="${top + plotH + 16}" text-anchor="middle" font-size="9" fill="var(--muted)">${shortDate(c[i].date)}</text>`;
  }
  const scrollSvg = `<svg width="${plotW}" height="${H}">${grid}${srlines}${mas}${candles}${pmark}${cross}${dax}</svg>`;
  const yaxisSvg = `<svg width="48" height="${H}">${yaxis}</svg>`;

  const maBoxes = [20, 50, 100, 200].map((n) => {
    const v = s["ma" + n], cls = v == null ? "" : (s.price >= v ? "above" : "below");
    return `<div class="box ${cls}"><div class="k" style="color:${MA_COLOR[n]}">${n} DMA</div><div class="v">${v == null ? "—" : fmt(v)}</div></div>`;
  }).join("");
  const legend = [20, 50, 100, 200].map((n) => `<span><i style="background:${MA_COLOR[n]}"></i>${n} DMA</span>`).join("");
  const plist = (t.patterns || []).slice().reverse().slice(0, 8).map((p) =>
    `<div class="prow"><span class="pdate">${shortDate(p.date)}</span><span class="pdot ${p.dir}"></span><span>${p.type}</span></div>`
  ).join("") || '<div class="caption">No notable candlestick patterns in the recent window.</div>';
  const lchips = (t.levels || []).slice().reverse().map((lv) =>
    `<span class="lvl-chip ${lv.type}">${fmt(lv.price)}</span>`).join("");

  document.getElementById("tech-content").innerHTML = `
    <div class="card">
      <div class="tech-trend">${s.trend}</div>
      <div class="tech-summary">Bank Nifty <b>${fmt(s.price)}</b> · as of ${t.as_of}</div>
      <div class="maval">${maBoxes}</div>
    </div>
    <div class="card">
      <h3>Price &amp; moving averages</h3>
      <div class="ma-legend">${legend}</div>
      <div style="display:flex">${yaxisSvg}<div class="chart-scroll" id="chart-scroll">${scrollSvg}</div></div>
      <div class="chart-hint">scroll ↔ for more history · dashed = support/resistance · GC/DC = golden/death cross · dots = candlestick patterns</div>
    </div>
    <div class="card">
      <h3>Support &amp; resistance</h3>
      <div class="lvl-list">${lchips}</div>
      <div class="caption">Clustered swing highs/lows. Green = support (below price), red = resistance (above).</div>
    </div>
    <div class="card">
      <h3>Recent candlestick patterns</h3>
      <div class="plist">${plist}</div>
      <div class="caption">Detected on daily candles — educational signals, not guarantees.</div>
    </div>`;
  document.getElementById("tech-content").classList.remove("hidden");
  document.getElementById("tech-loading").classList.add("hidden");
  // start scrolled to the most recent candles (retry until layout settles)
  scrollChartToEnd();
}

// ---------------------------------------------------------------------------
// Calendar tab
// ---------------------------------------------------------------------------
async function loadCalendar() {
  try {
    const res = await fetch(DATA_BACKTEST, { cache: "no-store" });
    if (!res.ok) throw new Error(res.status);
    const d = await res.json();
    backtestByDate = {};
    (d.days || []).forEach(r => { backtestByDate[r.date] = r; });
    // default to the most recent month with data
    const dates = Object.keys(backtestByDate).sort();
    const anchor = dates.length ? new Date(dates[dates.length - 1] + "T00:00:00") : new Date();
    calMonth = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
    renderCalendar(d.summary || {});
  } catch (e) {
    document.getElementById("cal-loading").textContent =
      "No accuracy history yet. It appears after the backtest has run for a few days.";
  }
}

function monthHitRate(year, month) {
  let hit = 0, scored = 0;
  for (const [date, r] of Object.entries(backtestByDate)) {
    const dt = new Date(date + "T00:00:00");
    if (dt.getFullYear() === year && dt.getMonth() === month && !r.outlier_flag) {
      scored++;
      if (r.zone_hit) hit++;
    }
  }
  return scored ? Math.round((hit / scored) * 100) : null;
}

function renderCalendar(summary) {
  const year = calMonth.getFullYear();
  const month = calMonth.getMonth();
  const monthName = calMonth.toLocaleString("en-US", { month: "long", year: "numeric" });
  const overall = summary.overall_hit_rate != null ? Math.round(summary.overall_hit_rate * 100) + "%" : "—";
  const dir = summary.directional_accuracy != null ? Math.round(summary.directional_accuracy * 100) + "%" : "—";
  const monthRate = monthHitRate(year, month);

  const firstDow = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const dows = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];

  let cells = dows.map(d => `<div class="dow">${d}</div>`).join("");
  for (let i = 0; i < firstDow; i++) cells += `<div class="cell empty"></div>`;

  for (let day = 1; day <= daysInMonth; day++) {
    const iso = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    const r = backtestByDate[iso];
    if (!r) { cells += `<div class="cell empty"><div class="d">${day}</div></div>`; continue; }
    let cls = "clickable", pct = "";
    if (r.outlier_flag) { cls += " outlier"; pct = "excl"; }
    else if (r.zone_hit) { cls += " hit"; pct = `${Math.round(r.zone_accuracy_pct)}%`; }
    else { cls += " miss"; pct = "miss"; }
    cells += `<div class="cell ${cls}" onclick="showDay('${iso}')"><div class="d">${day}</div><div class="p">${pct}</div></div>`;
  }

  document.getElementById("cal-content").innerHTML = `
    <div class="cal-summary">
      <div class="stat"><div class="n">${overall}</div><div class="l">Overall hit</div></div>
      <div class="stat"><div class="n">${monthRate != null ? monthRate + "%" : "—"}</div><div class="l">This month</div></div>
      <div class="stat"><div class="n">${dir}</div><div class="l">Direction</div></div>
      <div class="stat"><div class="n">${summary.outliers ?? 0}</div><div class="l">Outliers</div></div>
    </div>
    <div class="cal-nav">
      <button onclick="changeMonth(-1)">‹</button>
      <span class="month">${monthName}</span>
      <button onclick="changeMonth(1)">›</button>
    </div>
    <div class="cal-grid">${cells}</div>
    <div style="margin-top:10px;font-size:11px;color:var(--muted)">
      Green = price entered predicted zone · Red = missed · Gray = excluded outlier
    </div>`;
  document.getElementById("cal-content").classList.remove("hidden");
  document.getElementById("cal-loading").classList.add("hidden");
  window._calSummary = summary;
}

function changeMonth(delta) {
  calMonth = new Date(calMonth.getFullYear(), calMonth.getMonth() + delta, 1);
  renderCalendar(window._calSummary || {});
}

function showDay(iso) {
  const r = backtestByDate[iso];
  if (!r) return;
  const dirTxt = r.directional_correct === null ? "n/a (neutral)"
    : (r.directional_correct ? "correct" : "wrong");
  const status = r.outlier_flag ? "Excluded (outlier)" : (r.zone_hit ? "Hit" : "Miss");
  const reasons = (r.reasons || []).map(x => `<li>${x}</li>`).join("");
  document.getElementById("popover").innerHTML = `
    <button class="close-x" onclick="closePopover()">×</button>
    <h3>${iso}</h3>
    <div class="row"><span class="k">Prediction</span><b>${r.recommendation}</b></div>
    <div class="row"><span class="k">Predicted zone</span><b>${fmt(r.active_zone?.[0])}–${fmt(r.active_zone?.[1])}</b></div>
    <div class="row"><span class="k">Actual close</span><b>${fmt(r.actual_close)}</b></div>
    <div class="row"><span class="k">Day move</span><b>${r.daily_move_pct}%</b></div>
    <div class="row"><span class="k">Zone result</span><b>${status}</b></div>
    <div class="row"><span class="k">Direction</span><b>${dirTxt}</b></div>
    ${r.outlier_flag ? `<div style="font-size:12px;color:var(--muted);margin-top:6px">${r.outlier_reason}</div>` : ""}
    <h3 style="margin-top:12px">Reasoning that day</h3>
    <ul class="reasons">${reasons}</ul>`;
  document.getElementById("overlay").classList.add("show");
}
function closePopover() { document.getElementById("overlay").classList.remove("show"); }

// ---------------------------------------------------------------------------
// boot
// ---------------------------------------------------------------------------
loadToday();
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("service-worker.js").catch(() => {}));
}
