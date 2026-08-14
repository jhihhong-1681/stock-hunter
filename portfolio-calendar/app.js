// 讀取 data.js 提供的 window.PORTFOLIO_HISTORY，換算成「每日損益」並畫成月曆。

const rawHistory = [...(window.PORTFOLIO_HISTORY || [])].sort((a, b) =>
  a.date < b.date ? -1 : a.date > b.date ? 1 : 0
);

// 算出某個日期「應該」對應的前一個交易日（週一往前推到上週五，其他日子推一天）。
// 用來偵測快照之間有沒有漏掉交易日 —— 例如排程某天失敗漏跑，資料就會跳過一天。
function expectedPrevBusinessDate(dateStr) {
  const [y, m, d] = dateStr.split("-").map(Number);
  const date = new Date(y, m - 1, d);
  const daysBack = date.getDay() === 1 ? 3 : 1; // 週一(1) -> 往前3天到週五，其他往前1天
  date.setDate(date.getDate() - daysBack);
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
}

// dateStr(YYYY-MM-DD) -> { total, delta, pct, basisChange, gap }
// basis 不同代表統計口徑換了（例如從「只算美股」換成「總資產」），
// 或者中間漏了一個交易日的快照，這兩種情況都不能拿來算漲跌，
// 跟資料的第一天一樣當作沒有前一天可比較，避免把漏掉那幾天的漲跌全部算到下一筆頭上。
const dailyMap = new Map();
for (let i = 0; i < rawHistory.length; i++) {
  const { date, total, basis } = rawHistory[i];
  const prev = i > 0 ? rawHistory[i - 1] : null;
  const basisChanged = !!prev && !!prev.basis && !!basis && prev.basis !== basis;
  const hasGap = !!prev && !basisChanged && prev.date !== expectedPrevBusinessDate(date);
  if (!prev || basisChanged || hasGap) {
    dailyMap.set(date, { total, delta: null, pct: null, basisChange: basisChanged, gap: hasGap });
  } else {
    const prevTotal = prev.total;
    const delta = total - prevTotal;
    const pct = prevTotal !== 0 ? (delta / prevTotal) * 100 : null;
    dailyMap.set(date, { total, delta, pct, basisChange: false, gap: false });
  }
}

// dateStr -> { taiex, sp500, nasdaq, sox } 當天漲跌幅(%)
const indexMap = new Map();
for (const row of window.INDEX_HISTORY || []) {
  indexMap.set(row.date, row);
}

const INDEX_SERIES = [
  { key: "taiex", label: "台股加權", color: "#4da3ff" },
  { key: "sp500", label: "S&P 500", color: "#2fbf6a" },
  { key: "nasdaq", label: "那斯達克", color: "#ff8a3d" },
  { key: "sox", label: "費城半導體", color: "#b96bff" }
];
const PORTFOLIO_SERIES = { key: "portfolio", label: "我的資產", color: "#f5c518" };

function fmtAmount(n) {
  if (n === null || n === undefined) return "";
  const sign = n > 0 ? "+" : n < 0 ? "-" : "";
  return sign + "NT$" + Math.abs(Math.round(n)).toLocaleString("en-US");
}

// 日曆格子空間小，省略 NT$ 只留正負號跟數字
function fmtAmountShort(n) {
  if (n === null || n === undefined) return "";
  const sign = n > 0 ? "+" : n < 0 ? "-" : "";
  return sign + Math.abs(Math.round(n)).toLocaleString("en-US");
}

function fmtPct(p) {
  if (p === null || p === undefined) return "";
  const sign = p > 0 ? "+" : p < 0 ? "-" : "";
  return sign + Math.abs(p).toFixed(2) + "%";
}

function levelClass(pct) {
  if (pct === null || pct === undefined || pct === 0) return "";
  const abs = Math.abs(pct);
  const dir = pct > 0 ? "gain" : "loss";
  let lvl = 1;
  if (abs >= 3) lvl = 4;
  else if (abs >= 1.5) lvl = 3;
  else if (abs >= 0.5) lvl = 2;
  return `lvl-${dir}-${lvl}`;
}

// 找出資料中最新的年月，作為預設顯示月份
let [viewYear, viewMonth] = (() => {
  if (rawHistory.length === 0) {
    const now = new Date();
    return [now.getFullYear(), now.getMonth() + 1];
  }
  const [y, m] = rawHistory[rawHistory.length - 1].date.split("-").map(Number);
  return [y, m];
})();

const gridEl = document.getElementById("grid");
const monthLabelEl = document.getElementById("monthLabel");
const monthAmountEl = document.getElementById("monthAmount");
const monthPctEl = document.getElementById("monthPct");
const footerEl = document.getElementById("footer");

function pad2(n) {
  return String(n).padStart(2, "0");
}

function render() {
  monthLabelEl.textContent = `${viewYear}/${pad2(viewMonth)} 報酬`;

  const daysInMonth = new Date(viewYear, viewMonth, 0).getDate();
  const firstWeekday = new Date(viewYear, viewMonth - 1, 1).getDay();

  gridEl.innerHTML = "";

  // 前面補空白格，對齊星期
  for (let i = 0; i < firstWeekday; i++) {
    const empty = document.createElement("div");
    empty.className = "cell empty";
    gridEl.appendChild(empty);
  }

  let monthDelta = 0;
  let monthStartTotal = null;
  let hasAnyData = false;

  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = `${viewYear}-${pad2(viewMonth)}-${pad2(d)}`;
    const info = dailyMap.get(dateStr);

    const cell = document.createElement("div");
    cell.className = "cell";

    const dayNum = document.createElement("div");
    dayNum.className = "day-num";
    dayNum.textContent = d;
    cell.appendChild(dayNum);

    const amountEl = document.createElement("div");
    amountEl.className = "amount";
    const pctEl = document.createElement("div");
    pctEl.className = "pct";
    const totalEl = document.createElement("div");
    totalEl.className = "day-total";

    if (info && info.delta !== null) {
      hasAnyData = true;
      monthDelta += info.delta;
      if (monthStartTotal === null) {
        monthStartTotal = info.total - info.delta;
      }
      amountEl.textContent = fmtAmountShort(info.delta);
      pctEl.textContent = fmtPct(info.pct);
      totalEl.textContent = Math.round(info.total).toLocaleString("en-US");
      const cls = levelClass(info.pct);
      if (cls) cell.classList.add(cls);
    } else {
      cell.classList.add("no-data");
      amountEl.textContent = info ? (info.basisChange ? "基準變更" : info.gap ? "資料缺漏" : "首筆") : "";
      pctEl.textContent = "";
      totalEl.textContent = info ? Math.round(info.total).toLocaleString("en-US") : "";
    }

    cell.appendChild(amountEl);
    cell.appendChild(pctEl);
    cell.appendChild(totalEl);
    gridEl.appendChild(cell);
  }

  if (hasAnyData && monthStartTotal) {
    const monthPct = (monthDelta / monthStartTotal) * 100;
    monthAmountEl.textContent = fmtAmount(monthDelta);
    monthAmountEl.className = "summary-amount " + (monthDelta > 0 ? "gain" : monthDelta < 0 ? "loss" : "flat");
    monthPctEl.textContent = fmtPct(monthPct);
    monthPctEl.className = "summary-pct " + (monthPct > 0 ? "gain" : monthPct < 0 ? "loss" : "flat");
  } else {
    monthAmountEl.textContent = "尚無資料";
    monthAmountEl.className = "summary-amount flat";
    monthPctEl.textContent = "--";
    monthPctEl.className = "summary-pct flat";
  }

  const lastRecord = rawHistory[rawHistory.length - 1];
  footerEl.textContent = lastRecord
    ? `最後更新：${lastRecord.date}　總資產：${fmtAmount(lastRecord.total).replace(/^[+-]/, "")}`
    : "尚無任何紀錄";

  renderCompareChart(viewYear, viewMonth);
  renderAssetChart();
}

// 幫圖表的 <svg> 加上滑鼠/觸控 hover：移到圖上會顯示垂直參考線、對應的點、跟一個顯示日期+數值的浮動提示框。
// dims: { width, height, padL, padR }；n: 資料點個數；updatePoints(idx) 負責把 hover-line/dot 移到對應位置；
// renderTooltipHtml(idx) 回傳提示框內容的 HTML。
function setupChartHover(svgEl, containerEl, tooltipEl, dims, n, updatePoints, renderTooltipHtml) {
  if (n < 1) return;
  const { width, height, padL, padR } = dims;
  const captureEl = svgEl.querySelector(".hover-capture");
  if (!captureEl) return;

  function idxFromClientX(clientX) {
    const rect = svgEl.getBoundingClientRect();
    const scaleX = rect.width / width;
    const mx = (clientX - rect.left) / scaleX;
    if (n === 1) return 0;
    const ratio = (mx - padL) / (width - padL - padR);
    return Math.max(0, Math.min(n - 1, Math.round(ratio * (n - 1))));
  }

  function handleMove(evt) {
    const idx = idxFromClientX(evt.clientX);
    updatePoints(idx);
    tooltipEl.innerHTML = renderTooltipHtml(idx);
    tooltipEl.style.display = "block";

    const contRect = containerEl.getBoundingClientRect();
    const tw = tooltipEl.offsetWidth;
    const th = tooltipEl.offsetHeight;
    let left = evt.clientX - contRect.left + 14;
    let top = evt.clientY - contRect.top - th - 10;
    if (left + tw > contRect.width) left = evt.clientX - contRect.left - tw - 14;
    if (left < 0) left = 4;
    if (top < 0) top = evt.clientY - contRect.top + 14;
    tooltipEl.style.left = left + "px";
    tooltipEl.style.top = top + "px";
  }

  function handleLeave() {
    tooltipEl.style.display = "none";
    svgEl.querySelectorAll(".hover-guide").forEach((g) => g.setAttribute("opacity", "0"));
  }

  captureEl.addEventListener("pointermove", handleMove);
  captureEl.addEventListener("pointerleave", handleLeave);
}

const assetChartEl = document.getElementById("assetChart");
const assetChartWrapEl = document.getElementById("assetChartWrap");
const assetTooltipEl = document.getElementById("assetTooltip");

// 總資產走勢：畫出 rawHistory 裡「全部」快照日期的總資產金額折線圖（不分月份，看長期走勢）
function renderAssetChart() {
  if (rawHistory.length < 2) {
    assetChartEl.innerHTML = '<div class="flat" style="font-size:12px;padding:10px 0;">累積兩天以上的資料才能畫出走勢</div>';
    return;
  }

  const width = 380;
  const height = 130;
  const padL = 4;
  const padR = 4;
  const padT = 10;
  const padBottom = 10;

  const values = rawHistory.map((r) => r.total);
  let min = Math.min(...values);
  let max = Math.max(...values);
  if (min === max) {
    min -= 1;
    max += 1;
  }

  const n = values.length;
  const xFor = (i) => (n === 1 ? padL : padL + (i / (n - 1)) * (width - padL - padR));
  const yFor = (v) => padT + (1 - (v - min) / (max - min)) * (height - padT - padBottom);

  const points = values.map((v, i) => `${xFor(i).toFixed(1)},${yFor(v).toFixed(1)}`).join(" ");
  const areaPoints = `${xFor(0).toFixed(1)},${(height - padBottom).toFixed(1)} ${points} ${xFor(n - 1).toFixed(1)},${(height - padBottom).toFixed(1)}`;

  const lastValue = values[n - 1];
  const firstValue = values[0];
  const trendCls = lastValue >= firstValue ? "gain" : "loss";
  const trendColor = lastValue >= firstValue ? "#ff5c5c" : "#2fbf6a"; // 台股慣例：漲=紅, 跌=綠

  // 找出統計口徑改變的那一天（例如從「只算美股」換成「總資產」），畫一條虛線標記，
  // 提醒這條線左右兩段的數字基準不一樣，不是真的跳漲/跳跌。
  let basisChangeIndex = -1;
  for (let i = 1; i < rawHistory.length; i++) {
    if (rawHistory[i].basis && rawHistory[i - 1].basis && rawHistory[i].basis !== rawHistory[i - 1].basis) {
      basisChangeIndex = i;
      break;
    }
  }

  let svg = `<svg viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg">`;
  svg += `<polygon points="${areaPoints}" fill="${trendColor}" fill-opacity="0.12" />`;
  svg += `<polyline points="${points}" fill="none" stroke="${trendColor}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" />`;
  if (basisChangeIndex >= 0) {
    const bx = xFor(basisChangeIndex).toFixed(1);
    svg += `<line x1="${bx}" y1="${padT}" x2="${bx}" y2="${height - padBottom}" stroke="#9aa0a8" stroke-width="1" stroke-dasharray="3,3" />`;
  }
  svg += `<circle cx="${xFor(n - 1).toFixed(1)}" cy="${yFor(lastValue).toFixed(1)}" r="3.5" fill="${trendColor}" />`;
  svg += `<rect x="0" y="0" width="${width}" height="${height}" fill="transparent" class="hover-capture" style="cursor:crosshair;" />`;
  svg += `<g class="hover-guide" opacity="0" style="pointer-events:none;">`;
  svg += `<line class="hg-line" x1="0" y1="${padT}" x2="0" y2="${height - padBottom}" stroke="#8a8f98" stroke-width="1" stroke-dasharray="2,2" />`;
  svg += `<circle class="hg-dot" r="4" fill="${trendColor}" stroke="#0d1117" stroke-width="1.5" />`;
  svg += `</g>`;
  svg += `</svg>`;

  assetChartEl.innerHTML = svg;
  assetChartEl.innerHTML += `
    <div class="compare-legend">
      <div class="legend-item">期間最高 <span class="legend-value">${fmtAmount(max).replace(/^[+-]/, "")}</span></div>
      <div class="legend-item">期間最低 <span class="legend-value">${fmtAmount(min).replace(/^[+-]/, "")}</span></div>
      <div class="legend-item">目前 <span class="legend-value ${trendCls}">${fmtAmount(lastValue).replace(/^[+-]/, "")}</span></div>
    </div>
  `;
  if (basisChangeIndex >= 0) {
    assetChartEl.innerHTML += `<div class="footer" style="margin-top:6px;">虛線左側是用交易紀錄推算的美股部位（不含台幣現金/期貨/加密貨幣），右側才是完整總資產</div>`;
  }

  const svgEl = assetChartEl.querySelector("svg");
  const hoverGuide = svgEl.querySelector(".hover-guide");
  const hgLine = svgEl.querySelector(".hg-line");
  const hgDot = svgEl.querySelector(".hg-dot");
  setupChartHover(
    svgEl,
    assetChartWrapEl,
    assetTooltipEl,
    { width, height, padL, padR },
    n,
    (idx) => {
      hoverGuide.setAttribute("opacity", "1");
      const x = xFor(idx).toFixed(1);
      hgLine.setAttribute("x1", x);
      hgLine.setAttribute("x2", x);
      hgDot.setAttribute("cx", x);
      hgDot.setAttribute("cy", yFor(values[idx]).toFixed(1));
    },
    (idx) => {
      const r = rawHistory[idx];
      return `<div class="tt-date">${r.date}</div><div class="tt-row"><span class="tt-dot" style="background:${trendColor}"></span><span class="tt-value">${fmtAmount(r.total).replace(/^[+-]/, "")}</span></div>`;
    }
  );
}

const compareChartEl = document.getElementById("compareChart");
const compareChartWrapEl = document.getElementById("compareChartWrap");
const compareTooltipEl = document.getElementById("compareTooltip");
const compareLegendEl = document.getElementById("compareLegend");

function renderCompareChart(year, month) {
  const daysInMonth = new Date(year, month, 0).getDate();
  const dateStrs = [];
  for (let d = 1; d <= daysInMonth; d++) dateStrs.push(`${year}-${pad2(month)}-${pad2(d)}`);

  // 只保留這個月裡「有任一資料」的日期，依序建立每個序列的累積報酬曲線
  const relevantDates = dateStrs.filter(
    (ds) => (dailyMap.get(ds) && dailyMap.get(ds).pct !== null) || indexMap.has(ds)
  );

  const allSeries = [PORTFOLIO_SERIES, ...INDEX_SERIES];

  if (relevantDates.length === 0) {
    compareChartEl.innerHTML = '<div class="flat" style="font-size:12px;padding:10px 0;">本月尚無可比較的資料</div>';
    compareLegendEl.innerHTML = "";
    return;
  }

  const cumSeries = {};
  for (const s of allSeries) {
    let cum = 1;
    cumSeries[s.key] = relevantDates.map((ds) => {
      let pct = null;
      if (s.key === "portfolio") {
        const info = dailyMap.get(ds);
        pct = info ? info.pct : null;
      } else {
        const row = indexMap.get(ds);
        pct = row ? row[s.key] : null;
      }
      if (pct !== null && pct !== undefined) cum *= 1 + pct / 100;
      return (cum - 1) * 100;
    });
  }

  const width = 380;
  const height = 130;
  const padL = 4;
  const padR = 4;
  const padT = 8;
  const padBottom = 8;

  let min = 0;
  let max = 0;
  for (const s of allSeries) {
    for (const v of cumSeries[s.key]) {
      if (v < min) min = v;
      if (v > max) max = v;
    }
  }
  if (min === max) {
    min -= 1;
    max += 1;
  }

  const n = relevantDates.length;
  const xFor = (i) => (n === 1 ? padL : padL + (i / (n - 1)) * (width - padL - padR));
  const yFor = (v) => padT + (1 - (v - min) / (max - min)) * (height - padT - padBottom);

  const zeroY = yFor(0);

  let svg = `<svg viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg">`;
  svg += `<line x1="${padL}" y1="${zeroY}" x2="${width - padR}" y2="${zeroY}" stroke="#33394a" stroke-width="1" stroke-dasharray="3,3" />`;

  for (const s of allSeries) {
    const points = cumSeries[s.key]
      .map((v, i) => `${xFor(i).toFixed(1)},${yFor(v).toFixed(1)}`)
      .join(" ");
    svg += `<polyline points="${points}" fill="none" stroke="${s.color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />`;
  }
  svg += `<rect x="0" y="0" width="${width}" height="${height}" fill="transparent" class="hover-capture" style="cursor:crosshair;" />`;
  svg += `<g class="hover-guide" opacity="0" style="pointer-events:none;">`;
  svg += `<line class="hg-line" x1="0" y1="${padT}" x2="0" y2="${height - padBottom}" stroke="#8a8f98" stroke-width="1" stroke-dasharray="2,2" />`;
  for (const s of allSeries) {
    svg += `<circle class="hg-dot" data-key="${s.key}" r="3.5" fill="${s.color}" stroke="#0d1117" stroke-width="1.2" />`;
  }
  svg += `</g>`;
  svg += `</svg>`;

  compareChartEl.innerHTML = svg;

  compareLegendEl.innerHTML = allSeries
    .map((s) => {
      const last = cumSeries[s.key][cumSeries[s.key].length - 1];
      const cls = last > 0 ? "gain" : last < 0 ? "loss" : "flat";
      return `<div class="legend-item"><span class="legend-dot" style="background:${s.color}"></span>${s.label} <span class="legend-value ${cls}">${fmtPct(last)}</span></div>`;
    })
    .join("");

  const svgEl = compareChartEl.querySelector("svg");
  const hoverGuide = svgEl.querySelector(".hover-guide");
  const hgLine = svgEl.querySelector(".hg-line");
  const hgDots = svgEl.querySelectorAll(".hg-dot");
  setupChartHover(
    svgEl,
    compareChartWrapEl,
    compareTooltipEl,
    { width, height, padL, padR },
    n,
    (idx) => {
      hoverGuide.setAttribute("opacity", "1");
      const x = xFor(idx).toFixed(1);
      hgLine.setAttribute("x1", x);
      hgLine.setAttribute("x2", x);
      hgDots.forEach((dot) => {
        const key = dot.getAttribute("data-key");
        dot.setAttribute("cx", x);
        dot.setAttribute("cy", yFor(cumSeries[key][idx]).toFixed(1));
      });
    },
    (idx) => {
      const rows = allSeries
        .map((s) => {
          const v = cumSeries[s.key][idx];
          const cls = v > 0 ? "gain" : v < 0 ? "loss" : "flat";
          return `<div class="tt-row"><span class="tt-dot" style="background:${s.color}"></span>${s.label} <span class="tt-value ${cls}">${fmtPct(v)}</span></div>`;
        })
        .join("");
      return `<div class="tt-date">${relevantDates[idx]}</div>${rows}`;
    }
  );
}

// ---- Hero 摘要卡：淨資產大數字 + MoM/YTD/現金水位 + 持股分佈甜甜圈圖 + YTD 走勢圖 ----

// 從 dailyMap 依日期區間(含頭尾)複利串起每天的漲跌幅，算出區間累積報酬%。
// 遇到 basis 變更或資料缺漏的那天 pct 是 null，直接跳過不計入(累積值維持不變)，
// 跟 compareChart 的邏輯一致：不硬把不同基準的區間橋接在一起。
function computeCumulativeReturn(fromDate, toDate) {
  let cum = 1;
  let count = 0;
  const sortedDates = [...dailyMap.keys()].sort();
  for (const date of sortedDates) {
    if (date < fromDate || date > toDate) continue;
    const info = dailyMap.get(date);
    if (info.pct !== null && info.pct !== undefined) {
      cum *= 1 + info.pct / 100;
      count++;
    }
  }
  return { pct: (cum - 1) * 100, count };
}

function computeMonthReturn(year, month) {
  const from = `${year}-${pad2(month)}-01`;
  const to = `${year}-${pad2(month)}-31`;
  return computeCumulativeReturn(from, to);
}

const heroDateEl = document.getElementById("heroDate");
const heroTotalAssetsEl = document.getElementById("heroTotalAssets");
const heroUnrealizedEl = document.getElementById("heroUnrealized");
const heroRealizedEl = document.getElementById("heroRealized");
const statMomEl = document.getElementById("statMom");
const statYtdEl = document.getElementById("statYtd");
const statCashEl = document.getElementById("statCash");

function gainLossClass(n) {
  return n > 0 ? "gain" : n < 0 ? "loss" : "flat";
}

function renderHeroSummary() {
  const today = new Date();
  heroDateEl.textContent = `${today.getFullYear()}年${today.getMonth() + 1}月${today.getDate()}日`;

  if (rawHistory.length === 0) {
    heroTotalAssetsEl.textContent = "尚無資料";
    return;
  }

  const last = rawHistory[rawHistory.length - 1];
  heroTotalAssetsEl.textContent = fmtAmount(last.total).replace(/^[+-]/, "");

  const h = window.HOLDINGS;
  const t = (h && h.totals) || {};
  heroUnrealizedEl.textContent = fmtAmount(t.unrealizedPL);
  heroUnrealizedEl.className = "breakdown-value " + gainLossClass(t.unrealizedPL);
  heroRealizedEl.textContent = fmtAmount(t.realizedPL);
  heroRealizedEl.className = "breakdown-value " + gainLossClass(t.realizedPL);

  const [ly, lm] = last.date.split("-").map(Number);

  const mom = computeMonthReturn(ly, lm);
  statMomEl.textContent = mom.count ? fmtPct(mom.pct) : "--";
  statMomEl.className = "stat-value " + (mom.count ? gainLossClass(mom.pct) : "flat");

  const ytd = computeCumulativeReturn(`${ly}-01-01`, last.date);
  statYtdEl.textContent = ytd.count ? fmtPct(ytd.pct) : "--";
  statYtdEl.className = "stat-value " + (ytd.count ? gainLossClass(ytd.pct) : "flat");

  const cashRatio = t.totalAssets ? (t.cash / t.totalAssets) * 100 : null;
  statCashEl.textContent = cashRatio !== null ? cashRatio.toFixed(1) + "%" : "--";
  statCashEl.className = "stat-value flat";
}

const donutChartEl = document.getElementById("donutChart");
const donutLegendEl = document.getElementById("donutLegend");

// 持股現值由大到小排序，取前 7 筆各畫一段甜甜圈，其餘併成「其他」，
// 顏色沿用 THEME_COLORS（跟主題曝險那組色票一致，整站配色統一）。
function renderDonutChart() {
  const h = window.HOLDINGS;
  const positions = ((h && h.positions) || []).filter((p) => !p.closed && p.value);
  if (!positions.length) {
    donutChartEl.innerHTML = "";
    donutLegendEl.innerHTML = '<div class="flat" style="font-size:12px;">尚無持股資料</div>';
    return;
  }

  const sorted = [...positions].sort((a, b) => b.value - a.value);
  const TOP_N = 7; // 甜甜圈本身只有畫面能承受的色塊數，超過這個數的部位彙總成一段灰色「其他」
  const top = sorted.slice(0, TOP_N);
  const rest = sorted.slice(TOP_N);
  const restValue = rest.reduce((s, p) => s + p.value, 0);
  const grandTotal = sorted.reduce((s, p) => s + p.value, 0);

  if (grandTotal <= 0) {
    donutChartEl.innerHTML = "";
    donutLegendEl.innerHTML = "";
    return;
  }

  const OTHER_COLOR = "#4a5162";

  const chartSlices = top.map((p, i) => ({
    pct: (p.value / grandTotal) * 100,
    color: THEME_COLORS[i % THEME_COLORS.length]
  }));
  if (restValue > 0) {
    chartSlices.push({ pct: (restValue / grandTotal) * 100, color: OTHER_COLOR });
  }

  const size = 200;
  const cx = size / 2;
  const cy = size / 2;
  const r = 76;
  const strokeWidth = 32;
  const circumference = 2 * Math.PI * r;
  const gapDeg = chartSlices.length > 1 ? 1.4 : 0; // 每段之間留一點視覺間隙，避免色塊糊在一起

  let offset = 0;
  let svg = `<svg viewBox="0 0 ${size} ${size}" xmlns="http://www.w3.org/2000/svg">`;
  svg += `<g transform="rotate(-90 ${cx} ${cy})">`;
  svg += `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="#1b2029" stroke-width="${strokeWidth}" />`;
  for (const s of chartSlices) {
    const gap = (gapDeg / 360) * circumference;
    const len = Math.max((s.pct / 100) * circumference - gap, 0);
    svg += `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${s.color}" stroke-width="${strokeWidth}" stroke-linecap="round" stroke-dasharray="${len.toFixed(2)} ${(circumference - len).toFixed(2)}" stroke-dashoffset="${(-offset).toFixed(2)}" />`;
    offset += (s.pct / 100) * circumference;
  }
  svg += `</g>`;
  svg += `<text x="${cx}" y="${cy - 4}" text-anchor="middle" font-size="12" fill="#8a8f98">持股現值</text>`;
  svg += `<text x="${cx}" y="${cy + 16}" text-anchor="middle" font-size="15" font-weight="700" fill="#e6e6e6">${fmtAmount(grandTotal).replace(/^[+-]/, "")}</text>`;
  svg += `</svg>`;
  donutChartEl.innerHTML = svg;

  // 圖例列出「每一檔」持股（不再彙總），前 N 大沿用甜甜圈上的色塊顏色，
  // 其餘部位在圖上被併成一段灰色「其他」，圖例裡則統一用同一個灰點標示，方便對照。
  const legendRow = (label, pct, color) => `
    <div class="donut-legend-row">
      <span class="legend-dot" style="background:${color}"></span>
      <span class="donut-legend-label">${label}</span>
      <span class="donut-legend-value">${pct.toFixed(1)}%</span>
    </div>
  `;

  let legendHtml = top
    .map((p, i) => legendRow(p.symbol, (p.value / grandTotal) * 100, THEME_COLORS[i % THEME_COLORS.length]))
    .join("");

  if (rest.length) {
    legendHtml += `<div class="donut-legend-divider">其他持股（${rest.length} 檔，甜甜圈圖中歸為同一色）</div>`;
    legendHtml += rest.map((p) => legendRow(p.symbol, (p.value / grandTotal) * 100, OTHER_COLOR)).join("");
  }

  donutLegendEl.innerHTML = legendHtml;
}

const ytdChartEl = document.getElementById("ytdChart");
const ytdChartWrapEl = document.getElementById("ytdChartWrap");
const ytdTooltipEl = document.getElementById("ytdTooltip");
const ytdStatsRowEl = document.getElementById("ytdStatsRow");
const ytdYearBadgeEl = document.getElementById("ytdYearBadge");

// 今年以來每個有資料的交易日，複利累加成「今年累積報酬%」走勢圖（面積圖 + 格線 + hover）。
function renderYtdChart() {
  if (rawHistory.length === 0) {
    ytdChartEl.innerHTML = '<div class="flat" style="font-size:12px;padding:10px 0;">尚無資料</div>';
    ytdStatsRowEl.innerHTML = "";
    return;
  }

  const last = rawHistory[rawHistory.length - 1];
  const [year] = last.date.split("-").map(Number);
  ytdYearBadgeEl.textContent = `${year} 年至今`;

  const yearDates = [...dailyMap.keys()].filter((d) => d.startsWith(String(year))).sort();
  if (yearDates.length === 0) {
    ytdChartEl.innerHTML = '<div class="flat" style="font-size:12px;padding:10px 0;">今年尚無資料</div>';
    ytdStatsRowEl.innerHTML = "";
    return;
  }

  let cum = 1;
  const series = [];
  for (const d of yearDates) {
    const info = dailyMap.get(d);
    if (info.pct !== null && info.pct !== undefined) cum *= 1 + info.pct / 100;
    series.push({ date: d, pct: (cum - 1) * 100 });
  }

  const width = 640;
  const height = 190;
  const padL = 38;
  const padR = 8;
  const padT = 14;
  const padBottom = 10;

  const values = series.map((s) => s.pct);
  let min = Math.min(0, ...values);
  let max = Math.max(0, ...values);
  if (min === max) {
    min -= 1;
    max += 1;
  }
  const spread = max - min;
  min -= spread * 0.08;
  max += spread * 0.08;

  const n = series.length;
  const xFor = (i) => (n === 1 ? padL : padL + (i / (n - 1)) * (width - padL - padR));
  const yFor = (v) => padT + (1 - (v - min) / (max - min)) * (height - padT - padBottom);

  const zeroY = yFor(0);
  const points = series.map((s, i) => `${xFor(i).toFixed(1)},${yFor(s.pct).toFixed(1)}`).join(" ");
  const areaPoints = `${xFor(0).toFixed(1)},${zeroY.toFixed(1)} ${points} ${xFor(n - 1).toFixed(1)},${zeroY.toFixed(1)}`;

  const lastPct = values[n - 1];
  // 台股慣例：紅 = 賺錢(正), 綠 = 賠錢(負)，跟其他圖表統一
  const lineColor = lastPct >= 0 ? "#ff5c5c" : "#2fbf6a";

  let gridSvg = "";
  const gridCount = 4;
  for (let i = 0; i <= gridCount; i++) {
    const v = min + ((max - min) * i) / gridCount;
    const y = yFor(v).toFixed(1);
    gridSvg += `<line x1="${padL}" y1="${y}" x2="${width - padR}" y2="${y}" stroke="#1e2430" stroke-width="1" />`;
    gridSvg += `<text x="${(padL - 8).toFixed(1)}" y="${(parseFloat(y) + 3.5).toFixed(1)}" text-anchor="end" font-size="10" fill="#6b7078">${v > 0 ? "+" : ""}${v.toFixed(0)}%</text>`;
  }

  let svg = `<svg viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg">`;
  svg += `<defs><linearGradient id="ytdGrad" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="${lineColor}" stop-opacity="0.32" />
    <stop offset="100%" stop-color="${lineColor}" stop-opacity="0" />
  </linearGradient></defs>`;
  svg += gridSvg;
  svg += `<line x1="${padL}" y1="${zeroY.toFixed(1)}" x2="${width - padR}" y2="${zeroY.toFixed(1)}" stroke="#3a3f4a" stroke-width="1" stroke-dasharray="3,3" />`;
  svg += `<polygon points="${areaPoints}" fill="url(#ytdGrad)" />`;
  svg += `<polyline points="${points}" fill="none" stroke="${lineColor}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" />`;
  svg += `<circle cx="${xFor(n - 1).toFixed(1)}" cy="${yFor(lastPct).toFixed(1)}" r="4" fill="${lineColor}" stroke="#0d1117" stroke-width="1.5"/>`;
  svg += `<rect x="0" y="0" width="${width}" height="${height}" fill="transparent" class="hover-capture" style="cursor:crosshair;" />`;
  svg += `<g class="hover-guide" opacity="0" style="pointer-events:none;">`;
  svg += `<line class="hg-line" x1="0" y1="${padT}" x2="0" y2="${height - padBottom}" stroke="#8a8f98" stroke-width="1" stroke-dasharray="2,2" />`;
  svg += `<circle class="hg-dot" r="4" fill="${lineColor}" stroke="#0d1117" stroke-width="1.5" />`;
  svg += `</g>`;
  svg += `</svg>`;

  ytdChartEl.innerHTML = svg;

  const trackedDays = Math.round((new Date(yearDates[yearDates.length - 1]) - new Date(yearDates[0])) / 86400000) + 1;
  ytdStatsRowEl.innerHTML = `
    <div class="ytd-stat">
      <div class="ytd-stat-label">YTD 增幅</div>
      <div class="ytd-stat-value ${gainLossClass(lastPct)}">${fmtPct(lastPct)}</div>
    </div>
    <div class="ytd-stat">
      <div class="ytd-stat-label">資料點數</div>
      <div class="ytd-stat-value stat-blue">${n}</div>
    </div>
    <div class="ytd-stat">
      <div class="ytd-stat-label">追蹤天數</div>
      <div class="ytd-stat-value stat-yellow">${trackedDays}</div>
    </div>
  `;

  const svgEl = ytdChartEl.querySelector("svg");
  const hoverGuide = svgEl.querySelector(".hover-guide");
  const hgLine = svgEl.querySelector(".hg-line");
  const hgDot = svgEl.querySelector(".hg-dot");
  setupChartHover(
    svgEl,
    ytdChartWrapEl,
    ytdTooltipEl,
    { width, height, padL, padR },
    n,
    (idx) => {
      hoverGuide.setAttribute("opacity", "1");
      const x = xFor(idx).toFixed(1);
      hgLine.setAttribute("x1", x);
      hgLine.setAttribute("x2", x);
      hgDot.setAttribute("cx", x);
      hgDot.setAttribute("cy", yFor(series[idx].pct).toFixed(1));
    },
    (idx) => {
      const s = series[idx];
      return `<div class="tt-date">${s.date}</div><div class="tt-row"><span class="tt-dot" style="background:${lineColor}"></span><span class="tt-value ${gainLossClass(s.pct)}">${fmtPct(s.pct)}</span></div>`;
    }
  );
}

const holdingsSummaryEl = document.getElementById("holdingsSummary");
const themeExposureEl = document.getElementById("themeExposure");
const expiryListEl = document.getElementById("expiryList");
const holdingsListEl = document.getElementById("holdingsList");
const holdingsFooterEl = document.getElementById("holdingsFooter");

// 股票代號 -> 主題分類，手動維護。新增持股時要記得補上對照，不然會被歸到「未分類」。
const THEME_MAP = {
  MU: "AI基建/半導體",
  AVGO: "AI基建/半導體",
  IBM: "AI基建/半導體",
  NBIL: "AI基建/半導體",
  VRT: "AI基建/半導體",
  ALGM: "AI基建/半導體",
  NET: "資安/軟體",
  PLTR: "資安/軟體",
  MSFL: "資安/軟體",
  SMR: "核能",
  UUUU: "核能",
  ASTS: "國防太空",
  RKLB: "國防太空",
  VOYG: "國防太空",
  MRCY: "國防太空",
  MP: "稀土關鍵金屬",
  NU: "金融科技",
  HOOD: "金融科技",
  VPG: "機器人",
  BHE: "機器人",
  BMNR: "加密貨幣",
  XOM: "能源/石油",
  CRGY: "能源/石油",
  HAL: "能源/石油",
  GSK: "醫療保健",
  FVRR: "消費網路",
  UGL: "貴金屬避險",
  B: "貴金屬避險",
  CAG: "民生消費",
  SMCI: "AI基建/半導體",
  ONDS: "國防太空",
  SOFI: "金融科技",
  SBET: "加密貨幣",
  AESI: "能源/石油",
  MSTR: "加密貨幣"
};

const THEME_COLORS = [
  "#4da3ff", "#2fbf6a", "#ff8a3d", "#b96bff", "#f5c518",
  "#ff5c5c", "#3ddad7", "#e879b9", "#9aa0a8", "#7ee787", "#ffb454"
];

function fmtUsd(n) {
  if (n === null || n === undefined) return "-";
  return "$" + Number(n).toLocaleString("en-US", { maximumFractionDigits: 1, minimumFractionDigits: 1 });
}

// 依 THEME_MAP 把持股現值分組加總，畫成橫向比例條，看整體主題曝險集中度。
function renderThemeExposure(positions) {
  if (!positions.length) {
    themeExposureEl.innerHTML = "";
    return;
  }

  const totals = new Map();
  const symbolsByTheme = new Map();
  for (const p of positions) {
    const theme = THEME_MAP[p.symbol] || "未分類";
    totals.set(theme, (totals.get(theme) || 0) + (p.value || 0));
    if (!symbolsByTheme.has(theme)) symbolsByTheme.set(theme, []);
    symbolsByTheme.get(theme).push(p.symbol);
  }

  const grandTotal = [...totals.values()].reduce((a, b) => a + b, 0);
  if (grandTotal <= 0) {
    themeExposureEl.innerHTML = "";
    return;
  }

  const rows = [...totals.entries()].sort((a, b) => b[1] - a[1]);

  themeExposureEl.innerHTML = rows
    .map(([theme, value], i) => {
      const pct = (value / grandTotal) * 100;
      const color = THEME_COLORS[i % THEME_COLORS.length];
      const symbols = symbolsByTheme.get(theme).join("、");
      return `
        <div class="theme-row">
          <div class="theme-row-label">
            <span class="legend-dot" style="background:${color}"></span>${theme}
            <span class="theme-row-value">${fmtAmount(value).replace(/^[+-]/, "")}（${pct.toFixed(1)}%）</span>
          </div>
          <div class="theme-row-symbols" style="color:${color}">${symbols}</div>
          <div class="theme-bar-track">
            <div class="theme-bar-fill" style="width:${pct.toFixed(2)}%;background:${color};"></div>
          </div>
        </div>
      `;
    })
    .join("");
}

// holdings.js 的 name 欄位對選擇權是純文字，例如 "XOM 08/21/26 125 Call"，
// 到期日/履約價只能從這個字串解析，沒有結構化欄位。
function parseOptionExpiry(name) {
  if (!name) return null;
  const m = name.match(/(\d{1,2})\/(\d{1,2})\/(\d{2})\s+([\d.]+)\s+(Call|Put)/i);
  if (!m) return null;
  const [, mm, dd, yy, strike, optType] = m;
  const year = 2000 + parseInt(yy, 10);
  const date = new Date(year, parseInt(mm, 10) - 1, parseInt(dd, 10));
  const dateStr = `${year}-${mm.padStart(2, "0")}-${dd.padStart(2, "0")}`;
  return { date, dateStr, strike: parseFloat(strike), optType: optType[0].toUpperCase() + optType.slice(1).toLowerCase() };
}

function daysUntil(date) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const target = new Date(date);
  target.setHours(0, 0, 0, 0);
  return Math.round((target - today) / 86400000);
}

// 選擇權部位依到期日由近到遠排序，30天內標黃、7天內標紅提醒。
function renderOptionExpiry(positions) {
  const options = (positions || [])
    .filter((p) => p.type === "option")
    .map((p) => ({ ...p, parsed: parseOptionExpiry(p.name) }))
    .sort((a, b) => {
      if (!a.parsed && !b.parsed) return 0;
      if (!a.parsed) return 1;
      if (!b.parsed) return -1;
      return a.parsed.date - b.parsed.date;
    });

  if (!options.length) {
    expiryListEl.innerHTML = '<div class="flat" style="font-size:12px;">目前沒有選擇權部位</div>';
    return;
  }

  expiryListEl.innerHTML = options
    .map((p) => {
      const plCls = p.pl > 0 ? "gain" : p.pl < 0 ? "loss" : "flat";
      const borderCls = p.pl > 0 ? "gain-border" : p.pl < 0 ? "loss-border" : "";
      const sharesTxt = p.shares !== null && p.shares !== undefined ? `${p.shares} 股` : "";
      const investTxt = `投入 ${fmtAmount(p.invested).replace(/^[+-]/, "")} → 現值 ${fmtAmount(p.value).replace(/^[+-]/, "")}`;
      const plHtml = `${fmtAmount(p.pl)} <span class="expiry-pct">(${fmtPct(p.pct)})</span>`;
      if (!p.parsed) {
        return `
          <div class="expiry-row ${borderCls}">
            <div class="expiry-main">
              <div class="expiry-symbol-row"><span class="expiry-symbol">${p.symbol}</span><span class="expiry-shares">${sharesTxt}</span></div>
              <span class="expiry-name">${p.name || ""}</span>
              <span class="expiry-invest">${investTxt}</span>
            </div>
            <div class="expiry-right">
              <div class="expiry-days flat">到期日未知</div>
              <div class="expiry-pl ${plCls}">${plHtml}</div>
            </div>
          </div>
        `;
      }
      const days = daysUntil(p.parsed.date);
      let urgencyCls = "";
      if (days <= 7) urgencyCls = "expiry-urgent";
      else if (days <= 30) urgencyCls = "expiry-soon";
      const daysTxt = days < 0 ? "已到期" : days === 0 ? "今天到期" : `${days} 天`;
      return `
        <div class="expiry-row ${borderCls}">
          <div class="expiry-main">
            <div class="expiry-symbol-row"><span class="expiry-symbol">${p.symbol}</span><span class="expiry-shares">${sharesTxt}</span></div>
            <span class="expiry-name">${p.parsed.strike} ${p.parsed.optType} · ${p.parsed.dateStr}</span>
            <span class="expiry-invest">${investTxt}</span>
          </div>
          <div class="expiry-right">
            <div class="expiry-days ${urgencyCls}">${daysTxt}</div>
            <div class="expiry-pl ${plCls}">${plHtml}</div>
          </div>
        </div>
      `;
    })
    .join("");
}

// 目前持股卡片一多就要滾很久，預設只顯示前 N 檔，其餘收在「顯示全部」按鈕後面。
const HOLDINGS_COLLAPSE_COUNT = 8;
let holdingsExpanded = false;
const holdingsExpandBtnEl = document.getElementById("holdingsExpandBtn");

function renderHoldingRow(p) {
  const borderCls = p.pl > 0 ? "gain-border" : p.pl < 0 ? "loss-border" : "";
  const plCls = p.pl > 0 ? "gain" : p.pl < 0 ? "loss" : "flat";
  const isOption = p.type === "option";
  const sharesTxt = p.shares !== null && p.shares !== undefined ? `${p.shares} 股` : "";
  const optionTag = isOption ? '<span class="h-tag">期權</span>' : "";
  const nameTxt = p.name && p.name !== p.symbol ? `<div class="h-name">${p.name}</div>` : "";
  const costLine = p.avgCost !== null && p.avgCost !== undefined
    ? `成本 ${fmtUsd(p.avgCost)} → 現價 ${fmtUsd(p.price)}`
    : "";
  const investLine = `投入 ${fmtAmount(p.invested).replace(/^[+-]/, "")} → 現值 ${fmtAmount(p.value).replace(/^[+-]/, "")}`;
  const realizedLine = p.realized !== null && p.realized !== undefined
    ? `<div class="h-line3">已實現：<span class="${p.realized > 0 ? "gain" : p.realized < 0 ? "loss" : "flat"}">${fmtAmount(p.realized)}</span></div>`
    : "";
  return `
    <div class="holding-row ${borderCls}">
      <div class="h-line1">
        <span><span class="h-symbol">${p.symbol}</span><span class="h-shares">${sharesTxt}</span>${optionTag}</span>
        <span class="h-pl ${plCls}">${fmtAmount(p.pl)} <span style="font-size:10.5px;">(${fmtPct(p.pct)})</span></span>
      </div>
      ${nameTxt}
      <div class="h-line2">
        <span>${costLine}</span>
        <span>${investLine}</span>
      </div>
      ${realizedLine}
    </div>
  `;
}

function renderOpenPositionsList(positions) {
  const needsCollapse = positions.length > HOLDINGS_COLLAPSE_COUNT;
  const showAll = holdingsExpanded || !needsCollapse;
  const visible = showAll ? positions : positions.slice(0, HOLDINGS_COLLAPSE_COUNT);

  holdingsListEl.innerHTML = visible.map(renderHoldingRow).join("");

  if (!needsCollapse) {
    holdingsExpandBtnEl.textContent = "";
    holdingsExpandBtnEl.onclick = null;
    return;
  }
  holdingsExpandBtnEl.textContent = showAll ? "收起 ▲" : `顯示全部 ${positions.length} 檔 ▾`;
  holdingsExpandBtnEl.onclick = () => {
    holdingsExpanded = !holdingsExpanded;
    renderOpenPositionsList(positions);
  };
}

const closedHeaderEl = document.getElementById("closedHeader");
const closedHeaderTitleEl = document.getElementById("closedHeaderTitle");
const closedListEl = document.getElementById("closedList");
const closedSectionEl = document.querySelector(".closed-section");

// 已平倉紀錄整個區塊預設收起（只顯示標題+筆數+已實現損益合計），點了才展開明細，
// 依已實現損益排序（最賺的排最前面，最賠的排最後面），比照原始 Sheet 順序反而看不出重點。
function renderClosedPositions(closedPositions) {
  if (!closedPositions.length) {
    closedSectionEl.style.display = "none";
    return;
  }
  closedSectionEl.style.display = "";

  const sorted = [...closedPositions].sort((a, b) => b.realized - a.realized);
  const totalRealized = sorted.reduce((s, p) => s + p.realized, 0);
  closedHeaderTitleEl.textContent = `已平倉紀錄（${sorted.length} 筆，合計 ${fmtAmount(totalRealized)}）`;

  closedListEl.innerHTML = sorted
    .map((p) => {
      const cls = p.realized > 0 ? "gain-border" : p.realized < 0 ? "loss-border" : "";
      const plCls = p.realized > 0 ? "gain" : p.realized < 0 ? "loss" : "flat";
      const noteTxt = p.note ? `・${p.note}` : "";
      return `
        <div class="closed-row ${cls}">
          <span class="cr-symbol">${p.symbol}</span>
          <span class="cr-name">${p.name || ""}${noteTxt}</span>
          <span class="cr-pl ${plCls}">${fmtAmount(p.realized)}</span>
        </div>
      `;
    })
    .join("");

  closedHeaderEl.onclick = () => {
    const isOpen = closedListEl.classList.toggle("open");
    closedHeaderEl.classList.toggle("open", isOpen);
  };
}

function renderHoldings() {
  const h = window.HOLDINGS;
  if (!h) {
    holdingsSummaryEl.innerHTML = "";
    holdingsListEl.innerHTML = '<div class="flat" style="font-size:12px;">尚無持股資料</div>';
    holdingsFooterEl.textContent = "";
    renderHeroSummary();
    renderDonutChart();
    return;
  }

  const t = h.totals || {};
  const unrealizedCls = t.unrealizedPL > 0 ? "gain" : t.unrealizedPL < 0 ? "loss" : "flat";
  const realizedCls = t.realizedPL > 0 ? "gain" : t.realizedPL < 0 ? "loss" : "flat";

  holdingsSummaryEl.innerHTML = `
    <div class="metric">
      <div class="metric-label">總投入</div>
      <div class="metric-value">${fmtAmount(t.invested).replace(/^[+-]/, "")}</div>
    </div>
    <div class="metric">
      <div class="metric-label">現值</div>
      <div class="metric-value">${fmtAmount(t.value).replace(/^[+-]/, "")}</div>
    </div>
    <div class="metric">
      <div class="metric-label">現金</div>
      <div class="metric-value">${fmtAmount(t.cash).replace(/^[+-]/, "")}</div>
      <div class="metric-sub flat">水位 ${t.totalAssets ? ((t.cash / t.totalAssets) * 100).toFixed(1) : "0.0"}%</div>
    </div>
    <div class="metric wide">
      <div class="metric-label">總資產（含現金/期貨/加密貨幣）</div>
      <div class="metric-value">${fmtAmount(t.totalAssets).replace(/^[+-]/, "")}</div>
    </div>
    <div class="metric">
      <div class="metric-label">未實現損益</div>
      <div class="metric-value ${unrealizedCls}">${fmtAmount(t.unrealizedPL)}</div>
      <div class="metric-sub ${unrealizedCls}">${fmtPct(t.unrealizedPct)}</div>
    </div>
    <div class="metric">
      <div class="metric-label">已實現損益</div>
      <div class="metric-value ${realizedCls}">${fmtAmount(t.realizedPL)}</div>
    </div>
  `;

  // 目前持股面板只顯示還持有的部位；已經全部賣光的部位改到下面的「已平倉紀錄」手風琴區塊，
  // 它們的已實現損益已經算進上面的 totals.realizedPL 裡了。
  const openPositions = (h.positions || []).filter((p) => !p.closed);

  renderThemeExposure(openPositions);
  renderOptionExpiry(openPositions);
  // 期權已經在報酬日曆卡片的「選擇權到期日」列出完整資訊了，這裡的持股清單只留股票，避免重複。
  renderOpenPositionsList(openPositions.filter((p) => p.type !== "option"));
  renderClosedPositions(h.closedPositions || []);

  holdingsFooterEl.textContent = `快照時間：${h.asOf}`;

  renderHeroSummary();
  renderDonutChart();
}

renderHoldings();
renderYtdChart();

document.getElementById("prevBtn").addEventListener("click", () => {
  viewMonth -= 1;
  if (viewMonth < 1) {
    viewMonth = 12;
    viewYear -= 1;
  }
  render();
});

document.getElementById("nextBtn").addEventListener("click", () => {
  viewMonth += 1;
  if (viewMonth > 12) {
    viewMonth = 1;
    viewYear += 1;
  }
  render();
});

render();
