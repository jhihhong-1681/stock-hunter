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
//               或 "underlying"（期權同標的但履約價/到期日不同）。沒有這個欄位代表還在追蹤中；
//               有這個欄位的網站就不再顯示（資料保留備查，拿掉 filled 就會恢復追蹤）。
window.PENDING_ORDERS = [
  { date: "2026-09-28", time: "16:05:02", side: "Buy Open", symbol: "GRAB", type: "option", description: "GRAB 01/15/2027 3.00 Call", qty: 3, priceType: "限價", limitPrice: 0.4, validity: "當日有效", conditions: null, status: "已取消" },
  { date: "2026-09-29", time: "16:05:02", side: "Buy Open", symbol: "SMCI", type: "option", description: "SMCI 10/16/2026 45.00 Call", qty: 1, priceType: "限價", limitPrice: 1, validity: "當日有效", conditions: null, status: "已取消" },
  { date: "2026-09-29", time: "11:57:46", side: "Sell Close", symbol: "CCL", type: "option", description: "CCL 11/20/2026 20.00 Call", qty: 1, priceType: "限價", limitPrice: 5.3, validity: "當日有效", conditions: null, status: "原訂單已取消，變更為新訂單", filled: { date: "2026-09-29", time: "12:21:16", price: 5.2, qty: 1, description: "CCL 11/20/2026 20.00 Call", match: "exact" } },
  { date: "2026-10-01", time: "14:06:03", side: "Buy Open", symbol: "SDGR", type: "option", description: "SDGR 11/20/2026 35.00 Call", qty: 2, priceType: "限價", limitPrice: 3.2, validity: "當日有效", conditions: null, status: "原訂單已取消，變更為新訂單", filled: { date: "2026-10-01", time: "14:06:31", price: 3.3, qty: 2, description: "SDGR 11/20/2026 35.00 Call", match: "exact" } },
  { date: "2026-10-01", time: "14:05:52", side: "買進", symbol: "ET", type: "stock", description: null, qty: 30, priceType: "限價", limitPrice: 19.9, validity: "當日有效", conditions: null, status: "原訂單已取消，變更為新訂單", filled: { date: "2026-10-01", time: "14:42:46", price: 20, qty: 30, description: null, match: "exact" } }
];
