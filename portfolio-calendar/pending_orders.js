// 未成交訂單追蹤（歷史累積，不會被覆蓋）。
// Firstrade 的當日有效單沒成交，隔天就會從「訂單現況」頁消失；每日快照排程會在執行時讀取訂單現況，
// 把「快照對應日期」那天沒有成交的訂單（已過期/已取消/已駁回/部分成交）逐筆新增到這裡，
// 代表阿紘想買（或想賣）這檔、只是價位沒碰到，要持續追蹤。
//
// 每筆欄位：
//   date        下單日期 YYYY-MM-DD（Firstrade「更新時間」欄的美東日期）
//   time        更新時間 HH:MM:SS（美東時間）
//   side        訂單類別，照抄 Firstrade（買進 / 賣出 / Buy Open / Sell Close ...）
//   symbol      標的代號（期權取標的股票代號，例如 SRPT）
//   type        "stock" 或 "option"
//   description 期權完整合約名稱（例如 "SRPT 12/18/2026 17.50 Call"），股票為 null
//   qty         數量（股票是股數，期權是口數）
//   priceType   價格類型（限價 / 市價 / 停損 / 停損限價 ...）
//   limitPrice  委託價格（USD，期權是每股權利金；市價單為 null）
//   validity    有效期（當日有效 / 取消前有效 ...）
//   conditions  其他條件（沒有就 null）
//   status      Firstrade 顯示的現況（例如 已過期、已取消、部分成交 20/50）
//   filled      （選填）之後同方向、同標的的訂單成交時，排程會把這筆追蹤單結案，補上
//               { date, time, price, qty, description, match }；match 是 "exact"（同一個期權合約/同一檔股票）
//               或 "underlying"（期權同標的但履約價/到期日不同）。沒有這個欄位代表還在追蹤中。
window.PENDING_ORDERS = [
];
