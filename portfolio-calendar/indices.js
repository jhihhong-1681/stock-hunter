// 大盤指數每日漲跌幅紀錄（%）。date 對齊 data.js 的快照日期，
// 數值是當天可取得的最新收盤漲跌幅（台股/美股收盤時間不同，抓取當下能拿到的最新一筆）。
// 這個檔案會由每日自動排程任務持續新增資料，不需要手動編輯。
window.INDEX_HISTORY = [
  {
    date: "2026-07-01",
    taiex: 2.50,    // 台股加權指數
    sp500: 0.79,    // S&P 500
    nasdaq: 1.52,   // 那斯達克綜合指數
    sox: 3.92       // 費城半導體指數
  },
  {
    date: "2026-07-02",
    taiex: 1.94,    // 台股加權指數
    sp500: -0.22,   // S&P 500
    nasdaq: -0.66,  // 那斯達克綜合指數
    sox: -6.27      // 費城半導體指數
  },
  {
    date: "2026-07-03",
    taiex: -0.58,   // 台股加權指數
    sp500: 0.00,    // S&P 500（美股7/3為國慶日觀察假期，休市）
    nasdaq: -0.80,  // 那斯達克綜合指數
    sox: -5.45      // 費城半導體指數
  },
  {
    date: "2026-07-06",
    taiex: 0.08,    // 台股加權指數
    sp500: 0.00,    // S&P 500（美股連續假期後尚無新收盤，沿用上一筆）
    nasdaq: -0.80,  // 那斯達克綜合指數
    sox: -5.45      // 費城半導體指數
  },
  {
    date: "2026-07-07",
    taiex: -0.48,   // 台股加權指數
    sp500: 0.72,    // S&P 500
    nasdaq: 1.12,   // 那斯達克綜合指數
    sox: 2.17       // 費城半導體指數
  },
  {
    date: "2026-07-08",
    taiex: -2.31,   // 台股加權指數
    sp500: -0.45,   // S&P 500
    nasdaq: -1.16,  // 那斯達克綜合指數
    sox: -4.65      // 費城半導體指數
  },
  {
    date: "2026-07-09",
    taiex: 0.56,    // 台股加權指數
    sp500: -0.28,   // S&P 500
    nasdaq: 0.20,   // 那斯達克綜合指數
    sox: 2.23       // 費城半導體指數
  },
  {
    date: "2026-07-10",
    taiex: -0.83,   // 台股加權指數
    sp500: 0.81,    // S&P 500
    nasdaq: 1.30,   // 那斯達克綜合指數
    sox: 3.06       // 費城半導體指數
  },
  {
    date: "2026-07-13",
    taiex: 0.06,    // 台股加權指數
    sp500: 0.42,    // S&P 500
    nasdaq: 0.29,   // 那斯達克綜合指數
    sox: 0.06       // 費城半導體指數
  },
  {
    date: "2026-07-14",
    taiex: -1.42,   // 台股加權指數
    sp500: -0.79,   // S&P 500
    nasdaq: -1.55,  // 那斯達克綜合指數
    sox: -4.78      // 費城半導體指數
  },
  {
    date: "2026-07-15",
    taiex: 2.00,    // 台股加權指數
    sp500: 0.38,    // S&P 500
    nasdaq: 0.90,   // 那斯達克綜合指數
    sox: 2.54       // 費城半導體指數
  },
  {
    date: "2026-07-16",
    taiex: -0.01,   // 台股加權指數
    sp500: 0.38,    // S&P 500
    nasdaq: 0.62,   // 那斯達克綜合指數
    sox: -2.08      // 費城半導體指數
  },
  {
    date: "2026-07-17",
    taiex: -6.47,   // 台股加權指數
    sp500: -0.51,   // S&P 500
    nasdaq: -1.47,  // 那斯達克綜合指數
    sox: -4.29      // 費城半導體指數
  },
  {
    date: "2026-07-18",
    taiex: -6.47,   // 台股加權指數
    sp500: -1.01,   // S&P 500
    nasdaq: -1.40,  // 那斯達克綜合指數
    sox: -1.63      // 費城半導體指數
  },
  {
    date: "2026-07-21",
    taiex: 4.20,    // 台股加權指數
    sp500: -0.19,   // S&P 500
    nasdaq: -0.05,  // 那斯達克綜合指數（次要來源比對失敗，採用Yahoo Finance）
    sox: 0.60       // 費城半導體指數（次要來源比對失敗，採用Yahoo Finance）
  },
  {
    date: "2026-07-22",
    taiex: 1.34,    // 台股加權指數
    sp500: 0.89,    // S&P 500
    nasdaq: 1.29,   // 那斯達克綜合指數
    sox: 5.21       // 費城半導體指數（次要來源比對失敗，採用Yahoo Finance）
  },
  {
    date: "2026-07-23",
    taiex: 0.06,    // 台股加權指數（finance.yahoo.com過期沿用前一日，改用tw.stock.yahoo.com即時收盤數字）
    sp500: -0.14,   // S&P 500
    nasdaq: -0.57,  // 那斯達克綜合指數
    sox: 0.44       // 費城半導體指數（次要來源比對失敗，採用Yahoo Finance）
  },
  {
    date: "2026-07-24",
    taiex: -2.67,   // 台股加權指數
    sp500: 0.05,    // S&P 500
    nasdaq: -0.64,  // 那斯達克綜合指數
    sox: -4.25      // 費城半導體指數
  },
  {
    date: "2026-07-27",
    taiex: -0.05,   // 台股加權指數
    sp500: 0.02,    // S&P 500
    nasdaq: -0.18,  // 那斯達克綜合指數（次要來源比對失敗，抓到盤中即時價，採用Yahoo Finance收盤數字）
    sox: -2.23      // 費城半導體指數（次要來源查無可比對的收盤數字，採用Yahoo Finance）
  },
  {
    date: "2026-07-28",
    taiex: -4.65,   // 台股加權指數
    sp500: 0.21,    // S&P 500（次要來源比對失敗，正負號不一致，採用Yahoo Finance）
    nasdaq: -0.22,  // 那斯達克綜合指數
    sox: -4.49      // 費城半導體指數（次要來源查無可比對的收盤數字，採用Yahoo Finance）
  },
  {
    date: "2026-07-29",
    taiex: -3.76,   // 台股加權指數
    sp500: -1.52,   // S&P 500（次要來源抓到過期舊資料-0.05%，比對失敗，採用Yahoo Finance）
    nasdaq: -1.74,  // 那斯達克綜合指數
    sox: -5.33      // 費城半導體指數（次要來源抓到過期/錯誤數字+1.57%，正負號不一致，採用Yahoo Finance）
  },
  {
    date: "2026-07-30",
    taiex: -0.26,   // 台股加權指數（finance.yahoo.com 503無法取得，改用tw.stock.yahoo.com昨收+WebSearch交叉確認）
    sp500: 1.66,    // S&P 500
    nasdaq: 2.78,   // 那斯達克綜合指數
    sox: 8.16       // 費城半導體指數（Yahoo Finance +8.16%，investing.com +8.19%、Google Finance +8.18% 交叉比對成功）
  },
  {
    date: "2026-07-31",
    taiex: null,    // 台股加權指數（finance.yahoo.com/history 連續503無法取得，僅WebSearch有數字但無法比對，依規則留空）
    sp500: 0.70,    // S&P 500
    nasdaq: 1.00,   // 那斯達克綜合指數
    sox: 1.18       // 費城半導體指數（次要來源查無可比對的收盤數字，採用Yahoo Finance）
  },
  {
    date: "2026-08-03",
    taiex: 0.62,    // 台股加權指數（tw.stock.yahoo.com收盤43,386.41 與 WebSearch +0.62% 交叉比對成功）
    sp500: 1.48,    // S&P 500（Yahoo Finance收盤7,600.50 與 WebSearch +1.48% 交叉比對成功）
    nasdaq: 2.13,   // 那斯達克綜合指數（Yahoo Finance收盤25,913.90 與 WebSearch +2.1% 交叉比對成功）
    sox: 1.05       // 費城半導體指數（Yahoo Finance收盤11,430.35 與 investing.com收盤11,430.4 交叉比對成功）
  },
  {
    date: "2026-08-04",
    taiex: -0.06,   // 台股加權指數（tw.stock.yahoo.com收盤43,360.66 與 WebSearch -0.06% 交叉比對成功）
    sp500: 1.79,    // S&P 500（Yahoo Finance收盤7,736.52 與 WebSearch +1.79% 交叉比對成功）
    nasdaq: 2.59,   // 那斯達克綜合指數（Yahoo Finance收盤26,584.99 與 WebSearch +2.59% 交叉比對成功）
    sox: 6.55       // 費城半導體指數（finance.yahoo.com僅有delayed盤中數字不可用，改用investing.com收盤12,179.3；次要來源WebSearch +6.18%與此差0.37pp比對失敗，採用investing.com數字）
  },
  {
    date: "2026-08-05",
    taiex: 2.88,    // 台股加權指數（tw.stock.yahoo.com收盤44,611.60 與 WebSearch +2.88% 交叉比對成功）
    sp500: -0.17,   // S&P 500（Yahoo Finance收盤7,723.55 與 WebSearch -0.05%~-0.2% 區間交叉比對成功）
    nasdaq: -0.83,  // 那斯達克綜合指數（Yahoo Finance收盤26,363.44 與 WebSearch另一數字-0.8%交叉比對成功）
    sox: -1.40      // 費城半導體指數（finance.yahoo.com連續503無法取得，改用investing.com收盤12,008.9；次要來源WebSearch查無可比對收盤數字，採用investing.com數字）
  },
  {
    date: "2026-08-06",
    taiex: null,    // 台股加權指數（finance.yahoo.com/history連續503、finance.yahoo.com與tw.stock.yahoo.com即時頁互相矛盾且與WebSearch正負號不一致，無法建立可信數字，依規則留空）
    sp500: -0.18,   // S&P 500（Yahoo Finance收盤7,709.96 與 WebSearch -0.17% 交叉比對成功）
    nasdaq: -0.06,  // 那斯達克綜合指數（Yahoo Finance收盤26,348.35 與 WebSearch -0.14% 交叉比對成功）
    sox: -0.98      // 費城半導體指數（次要來源WebSearch查無可比對收盤數字，採用Yahoo Finance數字）
  },
  {
    date: "2026-08-07",
    taiex: -0.38,   // 台股加權指數（tw.stock.yahoo.com「昨收」44,225.91 與 WebSearch 44,225.91/-0.38% 完全吻合）
    sp500: 0.62,    // S&P 500（Yahoo Finance收盤7,757.64 與 WebSearch +0.62% 完全吻合）
    nasdaq: 1.30,   // 那斯達克綜合指數（Yahoo Finance收盤26,690.62 與 WebSearch +1.30% 完全吻合）
    sox: 2.56       // 費城半導體指數（finance.yahoo.com持續回傳與日期無關的舊快取數字不可用，改用investing.com收盤12,356.8；次要來源WebSearch查無可比對的當日收盤數字，採用investing.com數字）
  },
  {
    date: "2026-08-10",
    taiex: 1.59,    // 台股加權指數（finance.yahoo.com/history連續503無法取得，改用tw.stock.yahoo.com昨收44,928.76 與多篇新聞WebSearch「漲702.85點/+1.59%」交叉比對成功）
    sp500: -0.06,   // S&P 500（Yahoo Finance收盤7,753.11/-0.06% 與 WebSearch抓到過期的8/7舊資料+0.62%，正負號不一致，採用Yahoo Finance）
    nasdaq: -0.32,  // 那斯達克綜合指數（Yahoo Finance收盤26,605.36 與 WebSearch -0.32% 完全吻合）
    sox: -2.94      // 費城半導體指數（finance.yahoo.com回傳與日期無關的舊快取數字-0.98%不可用，改用investing.com收盤11,993.9 與 Google Finance 11,993.86 交叉比對成功）
  },
  {
    date: "2026-08-11",
    taiex: 0.43,    // 台股加權指數（tw.stock.yahoo.com「昨收」45,120.72 與 WebSearch新聞「終場收在45,120.72/+0.43%」完全吻合）
    sp500: -0.32,   // S&P 500（Yahoo Finance收盤7,728.20/-0.32% 與 WebSearch抓到8/10舊資料7,753/-0.06%，比對失敗，採用Yahoo Finance）
    nasdaq: -0.60,  // 那斯達克綜合指數（Yahoo Finance收盤26,445.45/-0.60% 與 WebSearch -0.60% 完全吻合）
    sox: 0.87       // 費城半導體指數（Yahoo Finance收盤12,098.47/+0.87%；次要來源查無可比對的當日收盤數字，採用Yahoo Finance）
  },
  {
    date: "2026-08-12",
    taiex: 0.88,    // 台股加權指數（finance.yahoo.com/history 503無法取得，改用tw.stock.yahoo.com昨收45,518.07推算漲跌點+397.35，與WebSearch新聞「收盤45,518.07/+0.88%」完全吻合）
    sp500: 0.26,    // S&P 500（Yahoo Finance收盤7,748.50/+0.26% 與 WebSearch另一數字+0.18%，差0.08pp在容許範圍內，交叉比對成功）
    nasdaq: 0.54,   // 那斯達克綜合指數（Yahoo Finance收盤26,588.49/+0.54% 與 WebSearch +0.54% 完全吻合）
    sox: 2.49       // 費城半導體指數（Yahoo Finance收盤12,399.38/+2.49%；次要來源查無可比對的當日收盤數字，採用Yahoo Finance）
  },
  {
    date: "2026-08-13",
    taiex: 1.11,    // 台股加權指數（finance.yahoo.com/history 503無法取得，改用tw.stock.yahoo.com昨收46,021.48 與 WebSearch「收盤46,021.48/+1.11%(503.41點)」完全吻合）
    sp500: 0.65,    // S&P 500（Yahoo Finance收盤7,798.99/+0.65% 與 WebSearch抓到8/12舊資料+0.26%，比對失敗，採用Yahoo Finance）
    nasdaq: 0.81,   // 那斯達克綜合指數（Yahoo Finance收盤26,803.03/+0.81% 與 WebSearch抓到8/12舊資料+0.54%，比對失敗，採用Yahoo Finance）
    sox: 0.46       // 費城半導體指數（Yahoo Finance收盤12,456.00/+0.46%；次要來源查無可比對的當日收盤數字，採用Yahoo Finance）
  },
  {
    date: "2026-08-14",
    taiex: -0.46,   // 台股加權指數（tw.stock.yahoo.com「昨收」45,811.01 與 WebSearch「收盤45,811.01/-0.46%(-210.47點)」完全吻合）
    sp500: -0.17,   // S&P 500（Yahoo Finance收盤7,785.76/-0.17% 與 WebSearch -0.17% 完全吻合）
    nasdaq: -0.28,  // 那斯達克綜合指數（Yahoo Finance收盤26,729.16/-0.28% 與 WebSearch收盤26,729.16/-0.28% 完全吻合）
    sox: -0.31      // 費城半導體指數（Yahoo Finance收盤12,417.05/-0.31%；次要來源查無可比對的當日收盤數字，採用Yahoo Finance）
  },
  {
    date: "2026-08-17",
    taiex: 0.10,    // 台股加權指數（tw.stock.yahoo.com「昨收」45,857.27 與 WebSearch「收盤45,857.27/+0.10%(+46.26點)」完全吻合；以前一交易日8/14收盤45,811.01反推亦得+0.10%）
    sp500: -0.52,   // S&P 500（Yahoo Finance收盤7,745.06/-0.52% 與 WebSearch -0.52% 完全吻合）
    nasdaq: -0.32,  // 那斯達克綜合指數（Yahoo Finance收盤26,644.91/-0.32% 與 WebSearch -0.32% 完全吻合）
    sox: 1.64       // 費城半導體指數（Yahoo Finance收盤12,621.01/+1.64%；次要來源查無可比對的當日收盤數字，採用Yahoo Finance）
  },
  {
    date: "2026-08-18",
    taiex: -1.20,   // 台股加權指數（finance.yahoo.com/history 503無法取得，改用tw.stock.yahoo.com「昨收」45,308.68反推＝8/17收盤45,857.27下跌548.59點；首次WebSearch誤報+1.20%，正負號不一致，改查證後多篇新聞「收盤下跌548.59點、跌幅1.2%、收45,308.68點」確認為下跌，採用-1.20%）
    sp500: -0.69,   // S&P 500（Yahoo Finance收盤7,691.76/-0.69%；次要來源WebSearch查無當日收盤可比對數字，採用Yahoo Finance）
    nasdaq: -1.33,  // 那斯達克綜合指數（Yahoo Finance收盤26,289.71/-1.33% 與 WebSearch -1.33% 完全吻合）
    sox: -4.98      // 費城半導體指數（Yahoo Finance收盤11,992.46/-4.98%；次要來源WebSearch僅抓到盤中/舊快取數字，無法比對，採用Yahoo Finance）
  },
  {
    date: "2026-08-19",
    taiex: -1.30,   // 台股加權指數（Yahoo Finance收盤44,719.35，較前一日45,308.68下跌589.33點/-1.30%；WebSearch雖然收盤數字44,719.35完全吻合，卻誤標為「漲幅1.30%」，正負號不一致，採用Yahoo Finance）
    sp500: 0.21,    // S&P 500（Yahoo Finance收盤7,707.98/+0.21%；次要來源WebSearch查無當日可比對收盤數字，採用Yahoo Finance）
    nasdaq: 0.16,   // 那斯達克綜合指數（Yahoo Finance收盤26,331.09/+0.16% 與 WebSearch抓到8/18舊資料26,729.16/-0.28%，比對失敗，採用Yahoo Finance）
    sox: -2.12      // 費城半導體指數（Yahoo Finance收盤11,738.23/-2.12%；次要來源WebSearch資料明顯過期/錯誤，採用Yahoo Finance）
  },
  {
    date: "2026-08-20",
    taiex: 0.48,    // 台股加權指數（Yahoo Finance收盤44,933.74，較前一日44,719.35上漲214.39點/+0.48%；次要來源WebSearch只查到「昨收44,933.74」印證收盤數字正確，但未查到8/20當天可比對的漲跌幅，採用Yahoo Finance）
    sp500: -0.87,   // S&P 500（Yahoo Finance收盤7,641.16/-0.87% 與 WebSearch同一數字完全吻合）
    nasdaq: -1.00,  // 那斯達克綜合指數（Yahoo Finance收盤26,067.17/-1.00% 與 WebSearch抓到8/19舊資料26,331.09/+0.16%，比對失敗，採用Yahoo Finance）
    sox: 0.53       // 費城半導體指數（Yahoo Finance收盤11,800.02/+0.53%；次要來源WebSearch查無可比對的當日收盤數字，採用Yahoo Finance）
  },
  {
    date: "2026-08-21",
    taiex: 0.65,    // 台股加權指數（Yahoo Finance收盤45,224.29，較前一日44,933.74上漲290.55點/+0.65% 與 WebSearch同一數字「上漲290.55點/+0.65%」完全吻合）
    sp500: 0.43,    // S&P 500（Yahoo Finance收盤7,674.37/+0.43%；次要來源WebSearch抓到過期舊資料，採用Yahoo Finance）
    nasdaq: 0.43,   // 那斯達克綜合指數（Yahoo Finance收盤26,180.46/+0.43% 與 WebSearch完全吻合）
    sox: -0.51      // 費城半導體指數（Yahoo Finance收盤11,740.37/-0.51%；次要來源WebSearch資料明顯過期/錯誤，採用Yahoo Finance）
  },
  {
    date: "2026-08-24",
    taiex: -1.02,   // 台股加權指數（finance.yahoo.com/history連續503無法取得，改用tw.stock.yahoo.com「昨收」44,762.32，較前一日8/21收盤45,224.29下跌461.97點；WebSearch同一收盤數字44,762.32完全吻合，但誤標為「上漲」，正負號不一致，依內部推算的正確方向採用-1.02%）
    sp500: -0.28,   // S&P 500（Yahoo Finance收盤7,652.86/-0.28% 與 WebSearch同一數字「fell 0.28% to 7,652.86」完全吻合）
    nasdaq: -0.77,  // 那斯達克綜合指數（Yahoo Finance收盤25,980.19/-0.77% 與 WebSearch同一收盤價/-0.76% 差0.01pp在容許範圍內，交叉比對成功）
    sox: -2.70      // 費城半導體指數（Yahoo Finance收盤11,423.17/-2.70%；次要來源WebSearch查無可比對的當日收盤數字，採用Yahoo Finance）
  },
  {
    date: "2026-08-25",
    taiex: 0.91,    // 台股加權指數（Yahoo Finance歷史收盤45,169.46，較前一日44,762.32上漲407.14點/+0.91%；WebSearch把「今日8/26盤中相對昨收上漲1.47%」誤植成8/25當天漲跌，日期搞混，比對失敗，採用Yahoo Finance）
    sp500: 0.32,    // S&P 500（Yahoo Finance收盤7,677.28/+0.32% 與 WebSearch同一數字完全吻合）
    nasdaq: 0.66,   // 那斯達克綜合指數（Yahoo Finance收盤26,151.30/+0.66% 與 WebSearch抓到8/24舊資料25,980.19/-0.76%，比對失敗，採用Yahoo Finance）
    sox: 1.44       // 費城半導體指數（Yahoo Finance收盤11,588.04/+1.44%；次要來源WebSearch只查到8/26盤中即時價，查無可比對的當日收盤漲跌幅，採用Yahoo Finance）
  },
  {
    date: "2026-08-26",
    taiex: 1.47,    // 台股加權指數（Yahoo Finance歷史收盤45,832.62，較前一日45,169.46上漲663.16點/+1.47% 與 WebSearch新聞「終場收在45,832.62/上漲663.16點/+1.46~1.47%」完全吻合）
    sp500: -0.02,   // S&P 500（Yahoo Finance收盤7,675.70/-0.02% 與 WebSearch同一收盤數字完全吻合）
    nasdaq: -0.08,  // 那斯達克綜合指數（Yahoo Finance收盤26,130.20/-0.08% 與 WebSearch同一數字26,130.20完全吻合）
    sox: 0.20       // 費城半導體指數（finance.yahoo.com quote頁回傳的漲跌幅時間戳矛盾（標示盤中卻宣稱收盤）不可信，改用investing.com收盤11,611.2較前一日11,588.0上漲+0.20%；次要來源WebSearch查無可比對的當日收盤數字，採用investing.com數字）
  }
];
