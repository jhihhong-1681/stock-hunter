/**
 * 研究監控日誌 → Streamlit 的中繼 API（Google Apps Script 網頁應用程式）。
 *
 * Cowork 的每小時監控排程用 Google Drive 連接器，每跑一次就在下面這個資料夾新增一個小 JSON 檔：
 *   檔名：YYYY-MM-DD__<執行時間或 backfill>.json
 *   內容：{ date, runs: [這次的執行紀錄], articles: [這次新抓到的文章] }
 * Streamlit 的「研究監控日誌」頁透過這支程式讀資料（要帶 API_KEY），同一天的多個檔案由 Streamlit 合併。
 *
 * 部署方式：
 *   1. 專案設定 → 指令碼屬性 → 新增 API_KEY（自己取一串長亂碼，跟 Streamlit secrets 的 RESEARCH_API_KEY 一樣）。
 *   2. 部署 → 新增部署作業 → 類型「網頁應用程式」→ 執行身分「我」、存取權「所有人」→ 部署，複製網址。
 *
 * 付費內容只在你的私人 Drive 資料夾裡；沒有 API_KEY 的請求一律拿不到資料。
 */
const FOLDER_ID = '1ppA4DCou6edHRsTvnluQO3wF3ei6uUJQ';

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function authorized_(key) {
  const expected = PropertiesService.getScriptProperties().getProperty('API_KEY');
  return !!expected && key === expected;
}

function filesByDate_() {
  const byDate = {};
  const it = DriveApp.getFolderById(FOLDER_ID).getFiles();
  while (it.hasNext()) {
    const f = it.next();
    const m = f.getName().match(/^(\d{4}-\d{2}-\d{2})__/);
    if (!m) continue;
    (byDate[m[1]] = byDate[m[1]] || []).push(f);
  }
  return byDate;
}

// GET ?key=...&action=list          → { dates: ["2026-09-24", ...] }（新到舊）
// GET ?key=...&action=get&dates=a,b → { days: { "2026-09-24": [檔案內容, ...], ... } }
function doGet(e) {
  const p = e.parameter || {};
  if (!authorized_(p.key)) return json_({ error: 'unauthorized' });
  const byDate = filesByDate_();
  if (p.action === 'list') {
    return json_({ dates: Object.keys(byDate).sort().reverse() });
  }
  const days = {};
  (p.dates || '').split(',').filter(Boolean).slice(0, 31).forEach(function (d) {
    days[d] = (byDate[d] || []).map(function (f) {
      try { return JSON.parse(f.getBlob().getDataAsString('UTF-8')); } catch (err) { return null; }
    }).filter(Boolean);
  });
  return json_({ days: days });
}
