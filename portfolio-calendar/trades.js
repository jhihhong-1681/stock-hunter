// Firstrade 成交紀錄（歷史累積，不會被覆蓋）。
// 桌機的本機排程（FIRSTRADE_TASK.md 第 4 步）每天把「訂單現況」裡已成交的每一筆抄到這裡，
// 交易紀錄頁的「新建倉位待補紀錄」用它預填真正的成交日期、價格和數量（Sheet 的成本均價只是加碼平均後的數字）。
//
// 每筆欄位：
//   date        成交日期 YYYY-MM-DD（Firstrade「更新時間」欄的美東日期）
//   time        更新時間 HH:MM:SS（美東時間）
//   side        訂單類別，照抄 Firstrade（買進 / 賣出 / Buy Open / Sell Close ...）
//   symbol      標的代號（期權取標的股票代號）
//   type        "stock" 或 "option"
//   description 期權完整合約名稱（例如 "INTC 10/23/2026 100.00 Call"），股票為 null
//   qty         成交數量（股票是股數，期權是口數）；部分成交填實際成交的數量
//   price       成交價（USD，期權是每股權利金）
window.TRADES = [
];
