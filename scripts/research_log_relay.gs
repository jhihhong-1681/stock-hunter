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

// 標的總表的「狀態」（未處理／已進場／已出場／忽略）存在同一個資料夾的 _status.json，
// 檔名不是日期開頭，所以不會被當成監控紀錄讀進來。內容：{ "<紀錄id>": { status, updatedAtUtc }, ... }
const STATUS_FILE = '_status.json';
const STATUS_VALUES = ['未處理', '已進場', '已出場', '忽略'];

function statusFile_() {
  const folder = DriveApp.getFolderById(FOLDER_ID);
  const it = folder.getFilesByName(STATUS_FILE);
  return it.hasNext() ? it.next() : folder.createFile(STATUS_FILE, '{}', 'application/json');
}

// 在編輯器手動執行一次，觸發「編輯 Drive 檔案」的授權（底線結尾的函式不會出現在執行選單裡）。
function authorize() {
  statusFile_();
}

function readStatuses_() {
  try { return JSON.parse(statusFile_().getBlob().getDataAsString('UTF-8')) || {}; } catch (err) { return {}; }
}

// POST ?key=...&action=setStatus&id=<紀錄id>&status=已進場 → { ok: true }
// （參數放網址或 JSON body 都可以；網址參數比較穩，body 當備援）
function doPost(e) {
  const p = e.parameter || {};
  if (!authorized_(p.key)) return json_({ error: 'unauthorized' });
  let body = {};
  try { body = JSON.parse((e.postData && e.postData.contents) || '{}') || {}; } catch (err) { body = {}; }
  const action = p.action || body.action, id = p.id || body.id, status = p.status || body.status;
  if (action !== 'setStatus') return json_({ error: 'bad action', got: String(action) });
  if (!/^[\w-]{1,64}$/.test(id || '')) return json_({ error: 'bad id', got: String(id) });
  if (STATUS_VALUES.indexOf(status) < 0) return json_({ error: 'bad status', got: String(status) });
  body = { id: id, status: status };
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const file = statusFile_();
    const all = readStatuses_();
    all[body.id] = { status: body.status, updatedAtUtc: new Date().toISOString() };
    file.setContent(JSON.stringify(all));
  } finally {
    lock.releaseLock();
  }
  return json_({ ok: true });
}

// GET ?key=...&action=list          → { dates: ["2026-09-24", ...] }（新到舊）
// GET ?key=...&action=get&dates=a,b → { days: { "2026-09-24": [檔案內容, ...], ... } }
// GET ?key=...&action=status        → { statuses: { "<紀錄id>": { status, updatedAtUtc }, ... } }
function doGet(e) {
  const p = e.parameter || {};
  if (!authorized_(p.key)) return json_({ error: 'unauthorized' });
  if (p.action === 'status') return json_({ statuses: readStatuses_() });
  const byDate = filesByDate_();
  if (p.action === 'list') {
    return json_({ dates: Object.keys(byDate).sort().reverse() });
  }
  const wanted = (p.dates || '').split(',').filter(Boolean).slice(0, 31);
  const files = [];
  wanted.forEach(function (d) { (byDate[d] || []).forEach(function (f) { files.push(f); }); });
  const texts = readCached_(files);
  const days = {};
  wanted.forEach(function (d) {
    days[d] = (byDate[d] || []).map(function (f) {
      try { return JSON.parse(texts[f.getId()]); } catch (err) { return null; }
    }).filter(Boolean);
  });
  return json_({ days: days });
}

// 每個檔案寫入後就不會再改，所以把內容放進 CacheService（最多 6 小時）。
// 逐一 getBlob() 每個檔案要好幾百毫秒，一週約 50 個檔就要十幾二十秒，快取後只剩新檔案要讀。
function readCached_(files) {
  const cache = CacheService.getScriptCache();
  const keyOf = function (f) { return 'f_' + f.getId() + '_' + f.getLastUpdated().getTime(); };
  const hit = files.length ? cache.getAll(files.map(keyOf)) : {};
  const out = {}, fresh = {};
  files.forEach(function (f) {
    const k = keyOf(f);
    let text = hit[k];
    if (text == null) {
      text = f.getBlob().getDataAsString('UTF-8');
      if (text.length < 90000) fresh[k] = text;  // 單筆快取上限 100KB
    }
    out[f.getId()] = text;
  });
  if (Object.keys(fresh).length) cache.putAll(fresh, 21600);
  return out;
}
