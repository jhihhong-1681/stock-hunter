// 「資產淨值」頁面：唯讀呈現 networth_data.js 裡的月結歷史。
// 這份資料不像 holdings.js 是每日排程寫入，是阿紘在 Google Sheet 更新完月結數字、口頭要求 Claude
// 「同步資產淨值」時才會更新，所以這裡不提供網頁編輯功能（之前用 Firestore 做的線上編輯已經移除，
// 跟持股資料一樣改成靜態檔案 + 手動同步，同一份資料只有 Sheet 跟這個檔案兩個地方，不會對不起來）。

const rows = window.NETWORTH_HISTORY || [];

const nwBody = document.getElementById("nwBody");
const sheetFooterEl = document.getElementById("sheetFooter");
const nwChartEl = document.getElementById("nwChart");
const nwChartWrapEl = document.getElementById("nwChartWrap");
const nwChartTooltipEl = document.getElementById("nwChartTooltip");
const nwLegendEl = document.getElementById("nwLegend");

function num(v) {
  return v === null || v === undefined ? "" : v;
}

function fmtMoney(n) {
  if (n === null || n === undefined || n === "") return "";
  return Number(n).toLocaleString("en-US", { maximumFractionDigits: 0 });
}

function fmtPct(n) {
  if (n === null || n === undefined || n === "") return "";
  return Number(n).toFixed(2) + "%";
}

// 美股總資產/報酬率/MOM/期貨+台幣+加密/總資產都是公式：照日期排序後逐月往前抓上一筆算 MOM。
function recompute(sorted) {
  let prevUsTotal = null;
  for (const r of sorted) {
    const usTotal = (r.usStockValue || 0) + (r.usStockCash || 0);
    r.usStockTotal = usTotal;
    r.returnPct = r.principal ? ((usTotal - r.principal) / r.principal) * 100 : null;
    r.mom = prevUsTotal !== null && prevUsTotal !== 0 ? ((usTotal - prevUsTotal) / prevUsTotal) * 100 : null;
    const otherTotal = (r.cathay || 0) + (r.ctbc || 0) + (r.esun || 0) + (r.esunFutures || 0) + (r.crypto || 0);
    r.otherTotal = otherTotal;
    r.grandTotal = usTotal + otherTotal;
    prevUsTotal = usTotal;
  }
}

// Y 軸每 20 萬(200,000)畫一條格線；X 軸一個月一個刻度，顯示每一筆的年/月。
function renderChart(sorted) {
  if (sorted.length < 2) {
    nwChartEl.innerHTML = '<div style="font-size:12px;padding:10px 0;color:#80868b;">累積兩筆以上資料才能畫出走勢</div>';
    nwLegendEl.innerHTML = "";
    return;
  }
  const values = sorted.map((r) => r.grandTotal || 0);
  const Y_STEP = 200000;

  const width = 900;
  const height = 220;
  const padL = 64;
  const padR = 10;
  const padT = 12;
  const padBottom = 26;

  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  let min = Math.floor(rawMin / Y_STEP) * Y_STEP;
  let max = Math.ceil(rawMax / Y_STEP) * Y_STEP;
  if (min === max) max = min + Y_STEP;

  const n = values.length;
  const xFor = (i) => (n === 1 ? padL : padL + (i / (n - 1)) * (width - padL - padR));
  const yFor = (v) => padT + (1 - (v - min) / (max - min)) * (height - padT - padBottom);

  const points = values.map((v, i) => `${xFor(i).toFixed(1)},${yFor(v).toFixed(1)}`).join(" ");
  const areaPoints = `${xFor(0).toFixed(1)},${(height - padBottom).toFixed(1)} ${points} ${xFor(n - 1).toFixed(1)},${(height - padBottom).toFixed(1)}`;

  const lastValue = values[n - 1];
  const firstValue = values[0];
  const trendColor = lastValue >= firstValue ? "#d93025" : "#188038"; // 台股慣例：漲=紅, 跌=綠

  // 月份標籤：把 "2026/07/31" 這種格式轉成 "25/07" 這種短格式。
  function monthLabel(dateStr) {
    const parts = dateStr.split(/[\/\-]/);
    if (parts.length < 2) return dateStr;
    return parts[0].slice(2) + "/" + parts[1].padStart(2, "0");
  }

  let svg = `<svg viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg">`;

  // Y 軸格線 + 標籤（每 20 萬一條）
  for (let v = min; v <= max; v += Y_STEP) {
    const y = yFor(v).toFixed(1);
    svg += `<line x1="${padL}" y1="${y}" x2="${width - padR}" y2="${y}" stroke="#e8eaed" stroke-width="1" />`;
    svg += `<text x="${padL - 8}" y="${y}" text-anchor="end" dominant-baseline="middle" font-size="10" fill="#80868b">${(v / 10000).toFixed(0)}萬</text>`;
  }

  // X 軸刻度 + 月份標籤（一個月一個單位，每一筆資料畫一個刻度）
  sorted.forEach((r, i) => {
    const x = xFor(i).toFixed(1);
    svg += `<line x1="${x}" y1="${height - padBottom}" x2="${x}" y2="${height - padBottom + 4}" stroke="#c0c4c9" stroke-width="1" />`;
    svg += `<text x="${x}" y="${height - padBottom + 16}" text-anchor="middle" font-size="10" fill="#80868b">${monthLabel(r.date)}</text>`;
  });

  svg += `<polygon points="${areaPoints}" fill="${trendColor}" fill-opacity="0.10" />`;
  svg += `<polyline points="${points}" fill="none" stroke="${trendColor}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" />`;
  svg += `<circle cx="${xFor(n - 1).toFixed(1)}" cy="${yFor(lastValue).toFixed(1)}" r="3.5" fill="${trendColor}" />`;
  svg += `<rect x="0" y="0" width="${width}" height="${height}" fill="transparent" class="hover-capture" style="cursor:crosshair;" />`;
  svg += `<g class="hover-guide" opacity="0" style="pointer-events:none;">`;
  svg += `<line class="hg-line" x1="0" y1="${padT}" x2="0" y2="${height - padBottom}" stroke="#c0c4c9" stroke-width="1" stroke-dasharray="2,2" />`;
  svg += `<circle class="hg-dot" r="4" fill="${trendColor}" stroke="#fff" stroke-width="1.5" />`;
  svg += `</g>`;
  svg += `</svg>`;

  nwChartEl.innerHTML = svg;

  nwLegendEl.innerHTML = `
    <span>期間最高 <span class="legend-value">NT$${fmtMoney(rawMax)}</span></span>
    <span>期間最低 <span class="legend-value">NT$${fmtMoney(rawMin)}</span></span>
    <span>目前 <span class="legend-value">NT$${fmtMoney(lastValue)}</span></span>
  `;

  const svgEl = nwChartEl.querySelector("svg");
  const captureEl = svgEl.querySelector(".hover-capture");
  const hoverGuide = svgEl.querySelector(".hover-guide");
  const hgLine = svgEl.querySelector(".hg-line");
  const hgDot = svgEl.querySelector(".hg-dot");

  function idxFromClientX(clientX) {
    const rect = svgEl.getBoundingClientRect();
    const scaleX = rect.width / width;
    const mx = (clientX - rect.left) / scaleX;
    if (n === 1) return 0;
    const ratio = (mx - padL) / (width - padL - padR);
    return Math.max(0, Math.min(n - 1, Math.round(ratio * (n - 1))));
  }

  captureEl.addEventListener("pointermove", (evt) => {
    const idx = idxFromClientX(evt.clientX);
    hoverGuide.setAttribute("opacity", "1");
    const x = xFor(idx).toFixed(1);
    hgLine.setAttribute("x1", x);
    hgLine.setAttribute("x2", x);
    hgDot.setAttribute("cx", x);
    hgDot.setAttribute("cy", yFor(values[idx]).toFixed(1));

    nwChartTooltipEl.innerHTML = `<div class="tt-date">${sorted[idx].date}</div><div>NT$${fmtMoney(values[idx])}</div>`;
    nwChartTooltipEl.style.display = "block";
    const contRect = nwChartWrapEl.getBoundingClientRect();
    let left = evt.clientX - contRect.left + 14;
    let top = evt.clientY - contRect.top - 40;
    if (left + 120 > contRect.width) left = evt.clientX - contRect.left - 120;
    nwChartTooltipEl.style.left = left + "px";
    nwChartTooltipEl.style.top = Math.max(0, top) + "px";
  });
  captureEl.addEventListener("pointerleave", () => {
    nwChartTooltipEl.style.display = "none";
    hoverGuide.setAttribute("opacity", "0");
  });
}

function render() {
  const sorted = [...rows].sort((a, b) => new Date(a.date) - new Date(b.date));

  if (!sorted.length) {
    nwBody.innerHTML = `<tr><td colspan="16" style="text-align:center;color:#80868b;padding:24px;">尚無資料</td></tr>`;
    sheetFooterEl.textContent = "";
    nwChartEl.innerHTML = "";
    nwLegendEl.innerHTML = "";
    return;
  }

  recompute(sorted);
  renderChart(sorted);

  nwBody.innerHTML = sorted
    .map((r) => {
      const returnCls = r.returnPct > 0 ? "gain-text" : r.returnPct < 0 ? "loss-text" : "";
      const momCls = r.mom > 0 ? "gain-text" : r.mom < 0 ? "loss-text" : "";
      return `
        <tr>
          <td>${r.date || ""}</td>
          <td>${fmtMoney(r.usStockValue)}</td>
          <td>${fmtMoney(r.usStockCash)}</td>
          <td>${fmtMoney(r.principal)}</td>
          <td class="cell-readonly">${fmtMoney(r.usStockTotal)}</td>
          <td class="cell-readonly ${returnCls}">${fmtPct(r.returnPct)}</td>
          <td>${num(r.yoy)}</td>
          <td class="cell-readonly ${momCls}">${fmtPct(r.mom)}</td>
          <td>${r.cashRatio === null || r.cashRatio === undefined ? "" : fmtPct(r.cashRatio)}</td>
          <td>${fmtMoney(r.cathay)}</td>
          <td>${fmtMoney(r.ctbc)}</td>
          <td>${fmtMoney(r.esun)}</td>
          <td>${fmtMoney(r.esunFutures)}</td>
          <td>${fmtMoney(r.crypto)}</td>
          <td class="cell-readonly">${fmtMoney(r.otherTotal)}</td>
          <td class="cell-readonly">${fmtMoney(r.grandTotal)}</td>
        </tr>
      `;
    })
    .join("");

  sheetFooterEl.textContent = `共 ${sorted.length} 筆月結資料`;
}

render();
