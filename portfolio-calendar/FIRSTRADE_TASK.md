# Firstrade 未成交訂單追蹤（本機排程指令）

這份檔案是**阿紘桌機上的本機排程**（Claude 桌面 app 的 scheduled task `firstrade-pending-orders`，平日台北 13:45）照做的指令。
只有這一段留在本機，因為它要用阿紘本機 Chrome 裡已登入的 Firstrade；其他每日快照資料由雲端排程照 `SNAPSHOT_TASK.md` 處理，電腦沒開也會跑。
電腦沒開、或 Firstrade 登入逾時，這一段就跳過，不影響快照。要改規則就改這個檔案、push 到 main（本機排程每次執行會先 `git pull`）。

背景：阿紘在 Firstrade 下了單沒成交，代表他想買/賣這檔，只是價位沒碰到，要持續追蹤；但 Firstrade 的「訂單現況」頁隔天就會清掉，所以每天要抄下來，累積在 `portfolio-calendar/pending_orders.js`（格式跟欄位說明在該檔檔頭註解）：
`window.PENDING_ORDERS = [ { date, time, side, symbol, type, description, qty, priceType, limitPrice, validity, conditions, status, filled? }, ... ];`

repo 在 `C:\Users\user1\Desktop\stock-hunter`（remote https://github.com/jhihhong-1681/stock-hunter.git）。

## 步驟

0. 在 repo 根目錄 `git pull --rebase origin main`，確保拿到雲端排程剛推的最新檔案。

1. **快照對應日期**（Asia/Taipei）：今天星期一 → 上週五；星期二～五 → 昨天。

2. **讀訂單現況**：用 Claude in Chrome（先用 ToolSearch 一次載入 tabs_context_mcp、tabs_create_mcp、navigate、get_page_text、computer、find、tabs_close_mcp），開新分頁到 https://invest.firstrade.com/cgi-bin/main#/cgi-bin/orderstatus 。
   - **只讀，不准操作**：不要點「取消」「改單」或任何下單/送出按鈕，也不要進交易頁面。
   - **沒登入就放棄**：出現登入頁（例如「登入已逾時失效，請重新登入」）、驗證碼、或要求密碼，不要嘗試登入（不能代打密碼/驗證碼），pending_orders.js 不動，記錄給第 6 步。Chrome 沒連線/讀不到頁面也一樣。
   - 確認篩選列「未成交訂單」「已成交訂單」「已駁回或取消訂單」三個勾選框都有勾、下拉選單是「全部」（只能勾這些篩選框，這是唯一允許的點擊）。
   - 用 get_page_text 讀表格（讀不到內容再用 screenshot/zoom）：更新時間、訂單類別、股數、代號、價格類型、價格、有效期、其他條件、現況。

3. **挑出要追蹤的單**：「更新時間的日期 = 快照對應日期」而且「現況不是完全成交（不是『已成交 @ 價格』）」——例如已過期、已取消、已駁回、未成交、部分成交、「原訂單已取消，變更為新訂單」。買賣都記。
   - 表格完全沒有快照對應日期的訂單（全是別天的或空表）→ 這一步什麼都不寫；但如果有別天的單卻沒有快照對應日期的，記錄給第 6 步（可能 Firstrade 已先清掉）。
   - 每筆整理成：`{ date: 快照對應日期, time: "HH:MM:SS"（美東）, side: 訂單類別原文, symbol: 標的代號（期權取合約名稱開頭的代號，例如 "SRPT 12/18/2026 17.50 Call" → "SRPT"）, type: "option" 或 "stock", description: 期權完整合約名稱／股票 null, qty: 數字, priceType: 原文, limitPrice: 數字或 null, validity: 原文, conditions: 原文或 null, status: 現況原文 }`
   - 附加到陣列尾端（舊資料原封不動）。用 date+time+symbol+side+description+limitPrice 檢查重複，已存在就不新增。

4. **成交後結案（e2）**：把同一張表裡「更新時間的日期 = 快照對應日期」且「現況是已成交（含部分成交）」的每一筆，拿去對 PENDING_ORDERS 裡**還沒有 filled 欄位**的舊紀錄：
   - 方向一樣：買方（買進 / Buy Open / Buy to Open / Buy Close）只對買方，賣方（賣出 / Sell Close / Sell Open）只對賣方。
   - 商品一樣：股票只對股票（symbol 相同）；期權只對期權——合約名稱完全相同 → `match: "exact"`；只有標的相同、履約價或到期日不同 → `match: "underlying"`。股票成交不對期權追蹤單，反之亦然。
   - 追蹤單的 date+time 必須早於成交時間。
   - 同代號＋方向的多筆追蹤單都算同一個意圖，一次全部結案；但同時有 exact 跟 underlying 候選時，只結案 exact 的，underlying 的繼續追蹤。
   - 結案就加上 `filled: { date: 快照對應日期, time: 成交更新時間, price: 成交價, qty: 成交數量, description: 成交那筆的期權合約名稱（股票 null）, match }`，其他欄位不動。同一天先掛沒成交、改價後成交的，也照這個規則（第 3 步剛新增的那筆馬上標 filled）。
   - 有 filled 的網站就不顯示，但資料保留，不要刪（判斷錯了只要拿掉 filled 就恢復追蹤）。每一筆結案都記錄給第 6 步。

5. **推上 GitHub**：做完關掉自己開的分頁。用 node 驗證 pending_orders.js 能正常執行，然後在 repo 根目錄：
   ```
   git add portfolio-calendar/pending_orders.js
   git commit -m "Firstrade 未成交訂單 <快照對應日期>"
   git push
   ```
   push 被拒就 `git pull --rebase origin main` 再 push（不要 --force）；跟 pending_orders.js 衝突就 `git rebase --abort` 放棄並回報。沒有任何變動就不用 commit。只改 pending_orders.js，不要動其他檔案。

6. **回報**：預設安靜結束。符合下列情況才簡短用繁體中文說明，並同時呼叫 PushNotification（status: "proactive"，200 字元內純文字，多項合併成一則）：
   - (f) 訂單沒抄到（沒登入、Chrome 沒連線、讀不到頁面、或表格只剩別天的單），說明原因，例如「Firstrade 未登入，昨天的未成交訂單沒抄到，請登入後手動檢查訂單現況」。
   - 有新增追蹤單：列出代號、買賣類型、數量、限價、狀態。
   - (g) 有追蹤單因成交被結案：每一筆寫清楚 ①移除哪一筆（原掛單日期、代號/合約、買賣類型、數量、原掛價）②哪一筆成交造成的（成交日期時間(美東)、訂單類別、合約、數量、成交價、比原掛價差幾%）③判定依據是同合約還是同標的不同合約（後者提醒阿紘確認，判斷錯了跟 Claude 說就會恢復追蹤）。例：「移除 SRPT 12/18/2026 17.50 Call Buy Open 1口 限價$3.50（9/22 掛單）← 9/23 14:43 同合約 1口 以 $3.80 成交（+8.6%）」。
   - push 失敗。
