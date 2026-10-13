/**
 * 交易紀錄 → Google Sheet 的讀寫中繼 API（Google Apps Script 網頁應用程式）。
 *
 * 「交易紀錄」頁（portfolio-calendar/journal.html，Streamlit 的 pages/11_交易紀錄.py 用 iframe 嵌入）
 * 手動輸入的紀錄存在這支程式綁定的那份 Google Sheet 的「Journal」分頁，所以不同電腦、不同瀏覽器都看得到同一份。
 *
 * 一次性設定：
 *   1. 在自己的 Google Drive 建一份新的試算表（名稱隨意，例如「交易紀錄」）。
 *   2. 試算表選單 → 擴充功能 → Apps Script → 把這個檔案的內容整份貼上取代 → 儲存。
 *   3. 專案設定（齒輪）→ 指令碼屬性 → 新增 API_KEY（自己取一串很長的亂碼）。
 *   4. 部署 → 新增部署作業 → 類型「網頁應用程式」→ 執行身分「我」、存取權「所有人」→ 部署，複製網址。
 *   5. Streamlit Cloud → App → Settings → Secrets 新增（放最上層，不要放在 [區段] 底下）：
 *        JOURNAL_API_URL = "<步驟 4 的網址>"
 *        JOURNAL_API_KEY = "<步驟 3 的亂碼>"
 *        JOURNAL_PASSWORD = "<打開交易紀錄頁要輸入的密碼>"
 *
 * 之後如果修改了這支程式，要「部署 → 管理部署作業 → 編輯 → 新版本」才會生效。
 * 沒有 API_KEY 的請求一律拿不到資料，也寫不進去。
 */
const SHEET_NAME = 'Journal';
const COLS = ['id', 'date', 'sym', 'con', 'cls', 'S', 'P', 'n', 'stop', 'tgt', 'by', 'why', 'exitDate', 'exitP', 'mae'];

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function authorized_(key) {
  const expected = PropertiesService.getScriptProperties().getProperty('API_KEY');
  return !!expected && key === expected;
}

function sheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh = ss.getSheetByName(SHEET_NAME);
  if (!sh) {
    sh = ss.insertSheet(SHEET_NAME);
    sh.appendRow(COLS);
    sh.setFrozenRows(1);
  }
  return sh;
}

function readRows_(sh) {
  const values = sh.getDataRange().getValues();
  const tz = Session.getScriptTimeZone();
  return values.slice(1).filter((r) => r[0] !== '').map((r) => {
    const o = {};
    COLS.forEach((c, i) => {
      let v = r[i];
      if (v instanceof Date) v = Utilities.formatDate(v, tz, 'yyyy-MM-dd');
      o[c] = v;
    });
    return o;
  });
}

function doGet(e) {
  if (!authorized_(e && e.parameter && e.parameter.key)) return json_({ ok: false, error: 'unauthorized' });
  return json_({ ok: true, rows: readRows_(sheet_()) });
}

// 瀏覽器用 text/plain 送 JSON（避免跨網域預檢請求）：{ key, action: 'upsert'|'delete', row | id }
function doPost(e) {
  let body;
  try { body = JSON.parse(e.postData.contents); } catch (err) { return json_({ ok: false, error: 'bad request' }); }
  if (!authorized_(body.key)) return json_({ ok: false, error: 'unauthorized' });

  const lock = LockService.getScriptLock();
  lock.waitLock(15000);
  try {
    const sh = sheet_();
    const ids = sh.getRange(1, 1, Math.max(sh.getLastRow(), 1), 1).getValues().map((r) => String(r[0]));
    if (body.action === 'upsert' && body.row && body.row.id != null) {
      const rowValues = COLS.map((c) => (body.row[c] == null ? '' : body.row[c]));
      const idx = ids.indexOf(String(body.row.id));
      if (idx > 0) sh.getRange(idx + 1, 1, 1, COLS.length).setValues([rowValues]);
      else sh.appendRow(rowValues);
      return json_({ ok: true });
    }
    if (body.action === 'delete' && body.id != null) {
      const idx = ids.indexOf(String(body.id));
      if (idx > 0) sh.deleteRow(idx + 1);
      return json_({ ok: true });
    }
    return json_({ ok: false, error: 'unknown action' });
  } finally {
    lock.releaseLock();
  }
}
