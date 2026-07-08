/* Bank Nifty Predictor — plain-JS front end for the Today + Calendar tabs. */

const DATA_LATEST = "../data/latest.json";
const DATA_BACKTEST = "../data/backtest_log.json";

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
  document.getElementById("view-today").classList.toggle("hidden", name !== "today");
  document.getElementById("view-calendar").classList.toggle("hidden", name !== "calendar");
  document.getElementById("tab-today").classList.toggle("active", name === "today");
  document.getElementById("tab-calendar").classList.toggle("active", name === "calendar");
  if (name === "calendar" && !calMonth) loadCalendar();
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

function corrBar(name, r20, r90) {
  if (r20 === null || r20 === undefined) {
    return `<div class="corr-row"><div class="corr-name">${name}</div>
      <div class="corr-track"><div class="corr-zero"></div></div><div class="corr-val">—</div></div>`;
  }
  const mag = Math.min(Math.abs(r20), 1) * 50;
  const neg = r20 < 0;
  const style = neg ? `left:${(50 - mag).toFixed(1)}%;width:${mag.toFixed(1)}%`
                    : `left:50%;width:${mag.toFixed(1)}%`;
  const r90txt = (r90 === null || r90 === undefined) ? "" : `<small>90d ${r90.toFixed(2)}</small>`;
  return `<div class="corr-row">
    <div class="corr-name">${name}</div>
    <div class="corr-track"><div class="corr-zero"></div>
      <div class="corr-bar ${neg ? "neg" : "pos"}" style="${style}"></div></div>
    <div class="corr-val">${r20.toFixed(2)}${r90txt}</div>
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
      <h3>How Bank Nifty moves with other markets (20-day)</h3>
      <div class="corr-axis"><span>−1 opposite</span><span>0</span><span>same +1</span></div>
      ${corrBar("VIX", corr.vix_20d, corr.vix_90d)}
      ${corrBar("Crude", corr.crude_20d, corr.crude_90d)}
      ${corrBar("USDINR", corr.usdinr_20d, corr.usdinr_90d)}
      <div class="caption">Blue = moves opposite Bank Nifty; amber = moves with it. E.g. VIX at ${corr.vix_20d ?? "—"} means when volatility rises, Bank Nifty tends to fall.</div>
    </div>`;
  const c = document.getElementById("today-content");
  c.innerHTML = html;
  c.classList.remove("hidden");
  document.getElementById("today-loading").classList.add("hidden");
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
