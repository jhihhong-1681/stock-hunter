// 「資產淨值」頁面：複製 Sheet 裡「資產淨值」那個分頁的月結表 —— 美股總現值/現金、
// 各帳戶現金(國泰/中信/玉山/期貨/加密貨幣)都是手動輸入的原始欄位，
// 美股總資產／報酬率／MOM／期貨+台幣+加密／總資產這幾欄跟 Sheet 一樣是公式算出來的，不能直接編輯。
//
// 「現金水位」「YOY」這兩欄在原本 Sheet 裡看不出明確公式（試算過幾種常見算法都對不起來），
// 所以先當成手動欄位保留，不自動計算，避免呈現假的數字。
//
// 任何失敗（初始化、登入、讀寫）都只印 console + 更新狀態文字，絕不讓整頁壞掉。

import { initializeApp } from "https://www.gstatic.com/firebasejs/12.17.1/firebase-app.js";
import {
  getAuth,
  GoogleAuthProvider,
  signInWithPopup,
  signOut,
  onAuthStateChanged
} from "https://www.gstatic.com/firebasejs/12.17.1/firebase-auth.js";
import {
  getFirestore,
  doc,
  onSnapshot,
  setDoc
} from "https://www.gstatic.com/firebasejs/12.17.1/firebase-firestore.js";
import { FIREBASE_CONFIG, OWNER_EMAIL, NETWORTH_DOC_PATH } from "./firebase-config.js";

// 從 Google Sheet「資產淨值」分頁原封不動搬過來的歷史資料，只在 Firestore 還沒有這份文件時拿來當起點。
const SEED_ROWS = [
  { date: "2025/07/30", usStockValue: 338816, usStockCash: 109509, principal: 419104, yoy: null, cashRatio: 32.32, cathay: null, ctbc: null, esun: null, esunFutures: null, crypto: null },
  { date: "2025/08/30", usStockValue: 366557, usStockCash: 209507, principal: 511872, yoy: null, cashRatio: 35.23, cathay: null, ctbc: null, esun: null, esunFutures: null, crypto: null },
  { date: "2025/09/30", usStockValue: 548257, usStockCash: 164303, principal: 511872, yoy: null, cashRatio: 25.65, cathay: 126445, ctbc: 11897, esun: null, esunFutures: 74217, crypto: null },
  { date: "2025/10/31", usStockValue: 748224, usStockCash: 108656, principal: 562750, yoy: null, cashRatio: 14.79, cathay: 123333, ctbc: 13820, esun: null, esunFutures: 74217, crypto: null },
  { date: "2025/11/29", usStockValue: 459535, usStockCash: 206762, principal: 562750, yoy: null, cashRatio: 28.83, cathay: 171380, ctbc: 22225, esun: null, esunFutures: 64721, crypto: null },
  { date: "2025/12/31", usStockValue: 590200, usStockCash: 131491, principal: 612053, yoy: null, cashRatio: 16.67, cathay: 32993, ctbc: 11511, esun: null, esunFutures: 132929, crypto: null },
  { date: "2026/01/31", usStockValue: 710930, usStockCash: 27891, principal: 612053, yoy: null, cashRatio: 3.47, cathay: 59365, ctbc: 9442, esun: null, esunFutures: 73999, crypto: 35222 },
  { date: "2026/02/28", usStockValue: 764754, usStockCash: 197613, principal: 807698, yoy: null, cashRatio: 18.27, cathay: 80892, ctbc: 69340, esun: null, esunFutures: 73999, crypto: 23788 },
  { date: "2026/03/31", usStockValue: 826366, usStockCash: 48482, principal: 807698, yoy: null, cashRatio: 4.43, cathay: 68249, ctbc: 9636, esun: 45866, esunFutures: 119787, crypto: 33199 },
  { date: "2026/04/30", usStockValue: 791055, usStockCash: 210669, principal: 807698, yoy: null, cashRatio: 19.36, cathay: 78230, ctbc: 4119, esun: 29443, esunFutures: 68899, crypto: 31788 },
  { date: "2026/05/30", usStockValue: 930789, usStockCash: 217086, principal: 807698, yoy: null, cashRatio: 18.97, cathay: 55287, ctbc: 22786, esun: 46850, esunFutures: 86425, crypto: 21549 },
  { date: "2026/06/30", usStockValue: 855998, usStockCash: 206673, principal: 807698, yoy: null, cashRatio: 16.06, cathay: 8350, ctbc: 46095, esun: 49776, esunFutures: 86425, crypto: 29756 },
  { date: "2026/07/31", usStockValue: 840410, usStockCash: 109564, principal: 807698, yoy: null, cashRatio: 9.30, cathay: 3998, ctbc: 41941, esun: 81635, esunFutures: 84197, crypto: 43438 }
];

const authBtn = document.getElementById("authBtn");
const authStatusEl = document.getElementById("authStatus");
const nwBody = document.getElementById("nwBody");
const addRowBtn = document.getElementById("addRowBtn");
const sheetFooterEl = document.getElementById("sheetFooter");
const nwChartEl = document.getElementById("nwChart");
const nwChartWrapEl = document.getElementById("nwChartWrap");
const nwChartTooltipEl = document.getElementById("nwChartTooltip");
const nwLegendEl = document.getElementById("nwLegend");

let rows = null; // 目前畫面上的資料（陣列），來自 Firestore
let editMode = false;
let db = null;

function setStatus(text) {
  authStatusEl.textContent = text;
}

function num(v) {
  return v === null || v === undefined ? "" : v;
}

// 輸入框失去焦點時顯示的格式：帶千分位逗點。取值時要先把逗點拿掉才能轉數字。
function fmtInputNum(n) {
  if (n === null || n === undefined || n === "") return "";
  return Number(n).toLocaleString("en-US", { maximumFractionDigits: 4 });
}

function getNumOrNull(str) {
  if (str === "" || str === null || str === undefined) return null;
  const n = Number(String(str).replace(/,/g, ""));
  return Number.isNaN(n) ? null : n;
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
function recompute() {
  if (!rows) return;
  const sorted = [...rows].sort((a, b) => new Date(a.date) - new Date(b.date));
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
function renderChart() {
  if (!rows || rows.length < 2) {
    nwChartEl.innerHTML = '<div style="font-size:12px;padding:10px 0;color:#80868b;">累積兩筆以上資料才能畫出走勢</div>';
    nwLegendEl.innerHTML = "";
    return;
  }
  const sorted = [...rows].sort((a, b) => new Date(a.date) - new Date(b.date));
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
  if (!rows) {
    nwBody.innerHTML = `<tr><td colspan="17" style="text-align:center;color:#80868b;padding:24px;">${
      db ? "雲端尚無資料" + (editMode ? "，按下面「＋新增一列」開始建立" : "，登入後可以建立") : "雲端連線中，稍後再試"
    }</td></tr>`;
    addRowBtn.style.display = editMode ? "block" : "none";
    sheetFooterEl.textContent = "";
    nwChartEl.innerHTML = "";
    nwLegendEl.innerHTML = "";
    return;
  }

  recompute();
  renderChart();

  const dis = editMode ? "" : "disabled";
  const sorted = rows
    .map((r, idx) => ({ r, idx }))
    .sort((a, b) => new Date(a.r.date) - new Date(b.r.date));

  nwBody.innerHTML = sorted
    .map(({ r, idx }) => {
      const returnCls = r.returnPct > 0 ? "gain-text" : r.returnPct < 0 ? "loss-text" : "";
      const momCls = r.mom > 0 ? "gain-text" : r.mom < 0 ? "loss-text" : "";
      return `
        <tr data-idx="${idx}">
          <td><input data-field="date" data-idx="${idx}" value="${r.date || ""}" ${dis} placeholder="YYYY/MM/DD" /></td>
          <td><input type="text" inputmode="decimal" class="money-input" data-field="usStockValue" data-idx="${idx}" value="${fmtInputNum(r.usStockValue)}" ${dis} /></td>
          <td><input type="text" inputmode="decimal" class="money-input" data-field="usStockCash" data-idx="${idx}" value="${fmtInputNum(r.usStockCash)}" ${dis} /></td>
          <td><input type="text" inputmode="decimal" class="money-input" data-field="principal" data-idx="${idx}" value="${fmtInputNum(r.principal)}" ${dis} /></td>
          <td><span class="cell-readonly">${fmtMoney(r.usStockTotal)}</span></td>
          <td><span class="cell-readonly ${returnCls}">${fmtPct(r.returnPct)}</span></td>
          <td><input data-field="yoy" data-idx="${idx}" value="${num(r.yoy)}" ${dis} /></td>
          <td><span class="cell-readonly ${momCls}">${fmtPct(r.mom)}</span></td>
          <td><input type="text" inputmode="decimal" class="money-input" data-field="cashRatio" data-idx="${idx}" value="${fmtInputNum(r.cashRatio)}" ${dis} /></td>
          <td><input type="text" inputmode="decimal" class="money-input" data-field="cathay" data-idx="${idx}" value="${fmtInputNum(r.cathay)}" ${dis} /></td>
          <td><input type="text" inputmode="decimal" class="money-input" data-field="ctbc" data-idx="${idx}" value="${fmtInputNum(r.ctbc)}" ${dis} /></td>
          <td><input type="text" inputmode="decimal" class="money-input" data-field="esun" data-idx="${idx}" value="${fmtInputNum(r.esun)}" ${dis} /></td>
          <td><input type="text" inputmode="decimal" class="money-input" data-field="esunFutures" data-idx="${idx}" value="${fmtInputNum(r.esunFutures)}" ${dis} /></td>
          <td><input type="text" inputmode="decimal" class="money-input" data-field="crypto" data-idx="${idx}" value="${fmtInputNum(r.crypto)}" ${dis} /></td>
          <td><span class="cell-readonly">${fmtMoney(r.otherTotal)}</span></td>
          <td><span class="cell-readonly">${fmtMoney(r.grandTotal)}</span></td>
          <td>${editMode ? `<button class="del-cell-btn" type="button" data-del-idx="${idx}">✕</button>` : ""}</td>
        </tr>
      `;
    })
    .join("");

  addRowBtn.style.display = editMode ? "block" : "none";
  sheetFooterEl.textContent = rows.length ? `共 ${rows.length} 筆月結資料` : "";
}

async function persist() {
  render();
  if (!editMode || !db) return;
  try {
    await setDoc(doc(db, ...NETWORTH_DOC_PATH), { rows });
  } catch (err) {
    console.error("寫入雲端失敗，這次修改暫時只留在畫面上", err);
    alert("同步到雲端失敗，請檢查網路連線再試一次（這筆修改還沒存起來，重新整理可能會遺失）");
  }
}

const TEXT_FIELDS = ["date", "yoy"];

// 數字欄位平常顯示千分位逗點；點進去編輯時先拿掉逗點方便打字，離開時再補回去。
nwBody.addEventListener("focusin", (e) => {
  if (e.target.classList.contains("money-input")) {
    e.target.value = e.target.value.replace(/,/g, "");
  }
});
nwBody.addEventListener("focusout", (e) => {
  if (e.target.classList.contains("money-input")) {
    e.target.value = fmtInputNum(getNumOrNull(e.target.value));
  }
});

nwBody.addEventListener("change", (e) => {
  const t = e.target;
  const idx = t.dataset.idx;
  const field = t.dataset.field;
  if (idx === undefined || !field || !rows) return;
  const r = rows[Number(idx)];
  if (!r) return;
  r[field] = TEXT_FIELDS.includes(field) ? t.value : getNumOrNull(t.value);
  persist();
});

nwBody.addEventListener("click", (e) => {
  const delIdx = e.target.dataset.delIdx;
  if (delIdx !== undefined && rows) {
    if (!confirm("確定要刪除這一列嗎？")) return;
    rows.splice(Number(delIdx), 1);
    persist();
  }
});

addRowBtn.addEventListener("click", () => {
  if (!rows) rows = [];
  rows.push({
    date: "", usStockValue: null, usStockCash: null, principal: null,
    yoy: null, cashRatio: null, cathay: null, ctbc: null, esun: null,
    esunFutures: null, crypto: null
  });
  persist();
});

try {
  const app = initializeApp(FIREBASE_CONFIG);
  const auth = getAuth(app);
  db = getFirestore(app);

  onAuthStateChanged(
    auth,
    (user) => {
      const isOwner = !!user && user.email === OWNER_EMAIL;
      editMode = isOwner;
      authBtn.textContent = user ? "登出" : "登入編輯";
      if (!user) setStatus("唯讀模式（登入才能編輯）");
      else if (isOwner) setStatus(`已登入：${user.email}`);
      else setStatus(`${user.email} 沒有編輯權限`);
      render();
    },
    (err) => {
      console.error("登入狀態監聽失敗", err);
      setStatus("登入狀態讀取失敗（唯讀模式）");
    }
  );

  authBtn.addEventListener("click", async () => {
    try {
      if (auth.currentUser) {
        await signOut(auth);
      } else {
        await signInWithPopup(auth, new GoogleAuthProvider());
      }
    } catch (err) {
      console.error("登入/登出失敗", err);
      alert("操作失敗：" + (err && err.message ? err.message : err));
    }
  });

  const nwRef = doc(db, ...NETWORTH_DOC_PATH);
  onSnapshot(
    nwRef,
    (snap) => {
      if (snap.exists()) {
        const data = snap.data();
        rows = data.rows || [];
      } else {
        // 雲端還沒有這份文件：先用畫面顯示 Sheet 搬過來的歷史資料，
        // 登入後按「＋新增一列」或改動任何一格，就會第一次寫進 Firestore。
        rows = JSON.parse(JSON.stringify(SEED_ROWS));
      }
      render();
    },
    (err) => {
      console.error("Firestore 讀取失敗，暫時顯示 Sheet 搬過來的歷史資料（唯讀）", err);
      setStatus("讀取雲端資料失敗，顯示最後已知資料");
      if (!rows) rows = JSON.parse(JSON.stringify(SEED_ROWS));
      editMode = false;
      render();
    }
  );
} catch (err) {
  console.error("Firebase 初始化失敗", err);
  setStatus("雲端連線失敗");
  authBtn.style.display = "none";
  render();
}
