# 每日報酬日曆快照（雲端排程指令）

這份檔案是雲端排程（Claude Code Routine「daily-portfolio-snapshot (雲端)」）每次執行時照做的完整指令。
排程本身的 prompt 只寫「照 portfolio-calendar/SNAPSHOT_TASK.md 執行」，所以**要改規則就改這個檔案、push 到 main**，下一次排程就會照新規則跑，在哪台電腦改都可以。

背景：幫用戶（阿紘）更新「報酬日曆」網站的每日快照資料，推上 GitHub 讓網站（GitHub Pages：https://jhihhong-1681.github.io/stock-hunter/portfolio-calendar/ ，阿紘平常從 https://jhihhong-stock-hunter-v2.streamlit.app/報酬日曆 看）自動同步。

執行環境：雲端，排程在台北時間平日 13:30 觸發。工作目錄就是 `stock-hunter` repo 根目錄（已經 clone 好），下面的路徑都相對於 repo 根目錄。**雲端系統時間是 UTC，日期一律換算成 Asia/Taipei 再判斷。** 這是無人值守的排程，阿紘不在線上，不要問問題，遇到不確定的狀況照下面的規則處理並在結果摘要裡說明。

Firstrade 未成交訂單（`portfolio-calendar/pending_orders.js`）**不歸這個排程管**——它需要阿紘本機已登入的 Chrome，由本機排程照 `portfolio-calendar/FIRSTRADE_TASK.md` 另外處理。這個排程不要讀也不要改 `pending_orders.js`。

---

## 步驟

### 1. 算出「快照對應日期」（YYYY-MM-DD）

下面所有步驟寫入的 date 都用這個日期，不是「今天」。

排程在台北 13:30 執行，美股還沒開盤，能抓到的美股資料（總資產、持股、S&P500/那斯達克/SOX）一定是「前一個已收盤交易日」的。台股加權指數 13:30 收盤、跟執行時間重疊，但快照仍然標成前一個交易日，所以第 5 步台股要明確查「快照對應日期」當天的收盤，不能用最新收盤。

算法：先取得今天的 Asia/Taipei 日期（例如 `TZ=Asia/Taipei date +%F` 跟 `TZ=Asia/Taipei date +%u`）：
- 今天是星期一 → 快照對應日期 = 上週五
- 今天是星期二～五 → 快照對應日期 = 昨天

（排程只在週一到週五執行。）如果 `portfolio-calendar/data.js` 裡已經有這個日期，代表今天已經跑過（例如手動重跑），照樣用最新 Sheet 數字更新同一天即可。

### 2. 讀取試算表

用 Google Drive 連接器的 `read_file_content` 讀 file id `1eaUErkLJUOH7aaIKhDWM5vQwAbE2Zrl0w9jI3KK-9yU`（「輸輸贏贏 那也沒辦法」），第一個分頁「美股持有庫存(每日更新)」。
欄位：市場, 股票代號, 股票名稱, 股數, 第一筆建倉, 成本均價, 幣別, 現價, 總投入, 現值, 損益, 報酬率, 平倉, 已實現損益。右側 P/Q/R 欄是摘要區：現金水位、總資產、Total總投入、（現金金額，標籤欄可能是空白）、未實現損益（金額＋%）、Total總現值、已實現損益。

- **總資產**：「總資產」那格的金額，去掉 NT$ 和逗號轉數字。
- **持股明細（positions）**：只保留「總投入」和「現值」都有值的列。每列整理成
  `{ symbol, name, shares, avgCost, price, invested, value, pl, pct, realized }`（數字去掉 $、NT$、逗號、%；抓不到填 null），市場欄是「期權」的加 `type: "option"`。保持表格原本順序。
  - 股票的 name：沿用上一份 `holdings.js` 裡同 symbol 的名稱寫法（例如 Sheet 寫 "FIVERR INTERNATIONAL"，holdings.js 一直用 "Fiverr International"），新代號才用你知道的正確公司名稱。名稱寫法不一致會讓 positions_history 的逐日比對失效。
  - **期權的 avgCost/price**：Sheet 上期權的成本均價永遠是空的，用換匯反推每股 USD 權利金：`avgCost = 總投入 ÷ 31 ÷ shares`、`price = 現值 ÷ 31 ÷ shares`，取到小數點後 4 位（31 是阿紘固定用的匯率，他說換了再改這裡）。
  - **期權的 underlyingPrice**：期權列的「現價」欄記的是**標的股票的現價**（阿紘手動維護、確認正確），直接去掉 $ 轉數字當 underlyingPrice，空白才留 null，不用上網查證。
- **總計（totals）**：invested=Total總投入、value=Total總現值、unrealizedPL/unrealizedPct=未實現損益金額/%、realizedPL=已實現損益（這格是 Sheet 公式 `=SUM(N…)` 的結果，直接照抄，不要自己重新加總去「修正」它）、cash=現金金額（= 總資產 − 總現值，可用來核對）、totalAssets=總資產。
- **已平倉紀錄（closedPositions）**：總投入和現值都空白、但有已實現損益的列，整理成 `{ symbol, name, note: 平倉欄文字或 null, realized }`，name 是亂碼/純數字時換成正確名稱（例如 ALAB → "Astera Labs"）。保持表格順序。
  - **⚠ 截斷防呆（重要）**：`read_file_content` 會在 Sheet 變大時**靜默截斷已平倉區塊的尾端**（沒有任何警告，已發生多次）。所以：先讀上一份 `portfolio-calendar/holdings.js` 的 closedPositions；這次讀到的清單只要比上一份少，或上一份裡有 symbol+name 這次沒讀到，**一律視為截斷，不是阿紘刪除**——把這次讀到的放前面（新平倉的部位通常出現在已平倉區塊最上方），後面接上一份裡這次沒讀到的項目（沿用上一份的 realized 值）。
  - 核對：positions 的 realized 加總 + closedPositions 的 realized 加總，應該等於 totals.realizedPL（差 1 元以內是四捨五入）。對不上就在結果摘要裡說明差額，但 realizedPL 仍然照抄 Sheet。
- **新代號檢查**：positions 裡每個 symbol 對照 `portfolio-calendar/app.js` 的 `THEME_MAP` key，不在裡面的記下來（給第 14 步）。不要自己改 app.js。

### 3. 期權價格

直接信任 Sheet 的數字（阿紘手動更新期權報價），不用另外查證或修正。

### 4. 期權報價更新警示（priceUnchangedDays）

覆蓋 holdings.js 之前，讀上一份 holdings.js 裡每筆 `type: "option"` 的 symbol、name、value、priceUnchangedDays（沒有視為 0）。
對這次每一筆期權用 symbol+name 完全相同去對上一份：
- value 完全相等 → priceUnchangedDays = 上一份 + 1
- 不相等，或對不到（新開倉/滾倉）→ 0

寫進這次的期權物件。任何一筆 ≥ 1（現值連續 2 個交易日沒變）就記下來（給第 14 步）。
排程只在平日跑，比的是「連續幾次排程」，週末自然跳過。
如果最近 git log 顯示上一份 holdings.js 是排程漏跑後補跑、或被手動修正過的，比對基準可能被污染，在結果摘要裡註明。

### 5. 大盤指數（每個都要兩個來源交叉比對）

- **台股加權指數**（要查「快照對應日期」那天，不是最新收盤）
  - 來源A：WebFetch https://finance.yahoo.com/quote/%5ETWII/history ，取快照對應日期的收盤與前一交易日收盤，算漲跌幅% =（當日−前日）÷前日×100
  - 來源B：WebSearch「台股 加權指數 <快照對應日期> 收盤 漲跌幅」
- **S&P 500**：來源A WebFetch https://finance.yahoo.com/quote/%5EGSPC/ ；來源B WebSearch「S&P 500 close today percent change」
- **那斯達克綜合指數**：來源A https://finance.yahoo.com/quote/%5EIXIC/ ；來源B「Nasdaq Composite close today percent change」
- **費城半導體 SOX**：來源A https://finance.yahoo.com/quote/%5ESOX/ ；來源B「Philadelphia Semiconductor Index SOX close today percent change」

確認來源A的收盤日期就是快照對應日期。比對規則：正負號一致且差距 ≤ 0.3 個百分點才算成功，用來源A數字。不一致時以來源A為準寫入（不要留 null），並記錄哪個指數、兩邊數字、採用值（給第 14 步）。只有來源A抓不到時才留 null。

### 6. （保留編號，不用動作）

### 7. 寫入 `portfolio-calendar/data.js`

`window.PORTFOLIO_HISTORY = [ { date, total, basis: "total_assets" }, ... ]`。該日期已存在就更新 total（= totals.totalAssets），否則依日期順序新增。

### 8. 寫入 `portfolio-calendar/indices.js`

`window.INDEX_HISTORY = [ { date, taiex, sp500, nasdaq, sox }, ... ]`。該日期已存在就更新，否則依日期順序新增。照檔案裡既有格式，每個欄位後面用註解寫兩個來源的數字與比對結果。

### 9. 寫入 `portfolio-calendar/positions_history.js`

`window.POSITIONS_HISTORY = { "YYYY-MM-DD": { positions: [ { symbol, name, pl, realized } ], totals: { cash, invested, realizedPL } }, ... }`（逐日累積，不是覆蓋）。要在覆蓋 holdings.js 之前做：
a. 上一份 holdings.js 的 positions 裡、這次用 symbol+name 對不到的（今天平倉），去這次的 closedPositions 找同 symbol+name 的 realized，組成 `{ symbol, name, pl: 0, realized }`。
b. 這次 positions 每一筆組成 `{ symbol, name, pl, realized（沒有就 null） }`。
c. a + b 合併成 positions 陣列；totals 抄這次的 cash、invested、realizedPL。
d. 只新增/更新快照對應日期這個 key，其他日期原封不動。

### 10. 覆蓋 `portfolio-calendar/holdings.js`（目前狀態快照，整個換掉）

保留檔頭註解，內容換成：
```
window.HOLDINGS = {
  asOf: "快照對應日期",
  totals: { invested, value, unrealizedPL, unrealizedPct, realizedPL, cash, totalAssets },
  positions: [ ...第2步的持股，期權要有 avgCost/price（權利金）、underlyingPrice、priceUnchangedDays ],
  closedPositions: [ ...第2步（含截斷防呆）的已平倉清單，每天都要整批寫入，不能漏 ]
};
```

寫完後用 node 驗證四個檔案都能正常執行，例如：
`node -e "const w={};new Function('window',require('fs').readFileSync('portfolio-calendar/holdings.js','utf8'))(w);console.log(Object.keys(w))"`

### 11. 只改這四個資料檔

`data.js`、`indices.js`、`holdings.js`、`positions_history.js`。不要改 `index.html`、`style.css`、`app.js`、`pending_orders.js`，也不要改這份 SNAPSHOT_TASK.md。

### 12. 推上 GitHub（直接推 main，不要開 PR、不要開新分支）

```
git add portfolio-calendar/data.js portfolio-calendar/indices.js portfolio-calendar/holdings.js portfolio-calendar/positions_history.js
git commit -m "每日快照 <快照對應日期>"
git push origin HEAD:main
```
如果 git 還沒設定身分，用 `git -c user.name="jhihhong-1681" -c user.email="jhihhong0810@gmail.com" commit ...`。

push 被拒（remote 有新 commit，例如 ETF 持股、法人資料、本機 Firstrade 排程的自動 commit）：`git fetch origin`，確認遠端新 commit 沒動到這四個檔案，就 `git pull --rebase origin main` 再 push，不要用 --force。rebase 真的衝突到這四個檔案就 `git rebase --abort`，放棄這次 push 並在結果摘要說明。驗證/權限類錯誤不要嘗試繞過，直接在結果摘要說明。

### 13. 讀不到資料就放棄

第 2 步讀不到總資產/持股就不要寫入任何猜測數字，直接結束（下一個交易日會再試），但最後的結果摘要要說明讀取失敗。指數只是改用來源A、或少數期權 underlyingPrice 留 null，都不影響照常寫入。

### 14. 結果摘要（會推播到阿紘的 Claude App）

這個排程設定成「執行完成就推播到 Claude App」（跟 Cowork 的研究監控一樣），**你最後一則回覆就是推播內容**，阿紘會在手機/電腦的 Claude App 收到。不要寄信、不要用其他通知管道。最後一則回覆用繁體中文、精簡條列，第一行是重點：

- 沒狀況：一行就好，例如「✅ 10/02 快照完成｜總資產 NT$918,856（較前日 −0.4%）｜已推上 GitHub」。
- 有狀況：第一行寫「⚠️ 10/02 快照完成，有 N 件事要看」（失敗就寫「❌ 10/02 快照失敗：原因」），下面逐項列出：
- (a) 有指數因來源B不可靠改採 Yahoo Finance（指數、兩來源數字、採用值）
- (b) git push 失敗（原因）
- (c) 有新代號不在 THEME_MAP（列出 symbol 跟名稱，請阿紘決定主題，或請 Claude 研究後分類）
- (d) 有期權 priceUnchangedDays ≥ 1（列出名稱與連續天數，請阿紘檢查 Sheet 現價是否忘記更新）
- (e) 有期權的 Sheet 現價欄空白、underlyingPrice 留 null（列出 symbol）
- (f) positions + closedPositions 的 realized 加總跟 Sheet 已實現損益對不上（差額多少；截斷本身已經是常態，補回後對得上就不用通知）
- (g) 第 2 步整個讀取失敗、這次沒有寫入

- 有新平倉或新開倉的部位，用一行帶過（例如「新平倉：MU、LPG；新部位：ET、SDGR 11/20 35C」）。
- 最後一行附網站連結 https://jhihhong-stock-hunter-v2.streamlit.app/報酬日曆 。
