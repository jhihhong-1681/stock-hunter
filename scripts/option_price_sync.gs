/**
 * 期權現價權利金自動同步（Google Apps Script，綁在「輸輸贏贏 那也沒辦法」這份 Sheet 上）
 *
 * 每天自動讀 GitHub 上 GitHub Actions 抓好的 data/option_prices.json（公開檔，不需要任何帳密），
 * 把「美股持有庫存(每日更新)」分頁裡每筆期權的 I 欄（現值）改成 `=最新權利金*股數*31`，
 * 並把 J 欄（損益）、K 欄（報酬率）一起更新成對應的數字。H 欄（總投入）、其他欄位都不動。
 *
 * 安裝：擴充功能 → Apps Script → 貼上這份程式 → 先手動執行 syncOptionPrices() 一次（會要求授權）
 *       → 執行 installTrigger() 建立每天自動執行（台北 08:00 左右）。
 * 停用（阿紘回來後要自己更新時）：執行 removeTrigger()。
 * 紀錄：每次執行會在「期權補價紀錄」分頁（沒有會自動建立）追加每一筆更新前後的數字，想還原可以照著改回去。
 */
var JSON_URL = 'https://raw.githubusercontent.com/jhihhong-1681/stock-hunter/main/data/option_prices.json';
var SHEET_NAME = '美股持有庫存(每日更新)';
var LOG_SHEET = '期權補價紀錄';
var FX = 31;               // 阿紘固定匯率
var DRY_RUN = false;       // true：只寫紀錄、不改 I/J/K 欄

function parseName_(name) {
  var m = /^([A-Z.]+)\s+(\d{1,2})\/(\d{1,2})\/(\d{2,4})\s+([\d.]+)\s+(C|P)/i.exec(String(name).trim());
  if (!m) return null;
  var y = parseInt(m[4], 10); if (y < 100) y += 2000;
  return m[1].toUpperCase() + '|' + y + '-' + ('0' + m[2]).slice(-2) + '-' + ('0' + m[3]).slice(-2) + '|' + parseFloat(m[5]) + '|' + m[6].toUpperCase();
}

function syncOptionPrices() {
  var resp = UrlFetchApp.fetch(JSON_URL + '?t=' + Date.now(), { muteHttpExceptions: true });
  if (resp.getResponseCode() !== 200) throw new Error('讀不到 option_prices.json：HTTP ' + resp.getResponseCode());
  var data = JSON.parse(resp.getContentText());
  var asof = data.asof;
  var day = data.by_date && data.by_date[asof];
  if (!day) throw new Error('option_prices.json 沒有 ' + asof + ' 的資料');

  // JSON key 是 "SYMBOL|name"，轉成「代號|到期日|履約價|C/P」好跟 Sheet 的名稱對上（寫法不同也能對）
  var prices = {};
  Object.keys(day).forEach(function (k) {
    var v = day[k];
    if (!v || v.price === undefined) return;
    var key = parseName_(k.split('|').slice(1).join('|'));
    if (key) prices[key] = v;
  });

  var ss = SpreadsheetApp.getActive();
  var sh = ss.getSheetByName(SHEET_NAME);
  var log = ss.getSheetByName(LOG_SHEET) || ss.insertSheet(LOG_SHEET);
  if (log.getLastRow() === 0) log.appendRow(['執行時間', '資料日', '代號', '名稱', '股數', '舊權利金(I欄公式)', '新權利金', '來源', '舊現值', '新現值', '備註']);

  var last = sh.getLastRow();
  var rows = sh.getRange(1, 1, last, 13).getValues();       // A..M
  var formulas = sh.getRange(1, 9, last, 1).getFormulas();  // I 欄公式
  var now = new Date(), updated = 0, skipped = [];
  for (var i = 1; i < rows.length; i++) {
    var r = rows[i];
    if (r[0] !== '期權') continue;
    var shares = Number(r[3]), cost = Number(r[7]);
    if (!shares || !cost) continue;                           // 只處理還持有（有總投入）的列
    var key = parseName_(r[2]);
    var p = key && prices[key];
    if (!p) { skipped.push(r[2]); continue; }
    var oldVal = Number(r[8]) || 0;
    var newVal = Math.round(p.price * shares * FX);
    var pl = newVal - cost;
    if (!DRY_RUN) {
      var row = i + 1;
      sh.getRange(row, 9).setFormula('=' + p.price + '*' + shares + '*' + FX);
      sh.getRange(row, 10).setValue(pl);
      sh.getRange(row, 11).setValue(pl / cost);
    }
    log.appendRow([now, asof, r[1], r[2], shares, formulas[i][0] || oldVal, p.price, p.source + (p.stale ? '（過時）' : ''), oldVal, newVal, DRY_RUN ? 'DRY_RUN' : '']);
    updated++;
  }
  if (skipped.length) log.appendRow([now, asof, '', '未更新（JSON 沒有或已到期）', '', '', '', '', '', '', skipped.join('、')]);
  Logger.log('更新 ' + updated + ' 筆；略過：' + skipped.join('、'));
}

function installTrigger() {
  removeTrigger();
  ScriptApp.newTrigger('syncOptionPrices').timeBased().everyDays(1).atHour(8).nearMinute(0).inTimezone('Asia/Taipei').create();
}

function removeTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'syncOptionPrices') ScriptApp.deleteTrigger(t);
  });
}
