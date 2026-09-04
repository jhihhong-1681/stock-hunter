// 「資產淨值」頁面的月結歷史資料，複製自 Google Sheet「輸輸贏贏 那也沒辦法」試算表最下面那張月結表。
// 這份資料不是每天排程自動更新的：阿紘在 Sheet 更新完當月數字後，跟 Claude 說一聲「同步資產淨值」，
// 才會由 Claude 讀 Sheet、手動整理成這個陣列的格式、整批覆蓋寫入這個檔案（同一個月份重跑就直接覆蓋那一列）。
// usStockTotal／returnPct／mom／otherTotal／grandTotal 這幾欄是 Sheet 裡的公式欄位，這裡不重複存，
// 由 networth.js 的 recompute() 用同樣公式在前端算出來；yoy／cashRatio 是 Sheet 裡的手動輸入欄位，照抄數字，
// yoy 這欄 Sheet 裡目前每一列都是空的，所以都是 null。
window.NETWORTH_HISTORY = [
  { date: "2025/07/30", usStockValue: 338816, usStockCash: 109509, principal: 419104, yoy: null, cashRatio: 32.32, cathay: null, ctbc: null, esun: null, esunFutures: null, crypto: null },
  { date: "2025/08/30", usStockValue: 366557, usStockCash: 209507, principal: 511872, yoy: null, cashRatio: 35.23, cathay: null, ctbc: null, esun: null, esunFutures: null, crypto: null },
  { date: "2025/09/30", usStockValue: 548257, usStockCash: 164303, principal: 511872, yoy: null, cashRatio: 25.65, cathay: 126445, ctbc: 11897, esun: null, esunFutures: 74217, crypto: null },
  { date: "2025/10/31", usStockValue: 748224, usStockCash: 108656, principal: 562750, yoy: null, cashRatio: 14.79, cathay: 123333, ctbc: 13820, esun: null, esunFutures: 74217, crypto: null },
  { date: "2025/11/29", usStockValue: 459535, usStockCash: 206762, principal: 562750, yoy: null, cashRatio: 28.83, cathay: 171380, ctbc: 22225, esun: null, esunFutures: 64721, crypto: null },
  { date: "2025/12/31", usStockValue: 590200, usStockCash: 131491, principal: 612053, yoy: null, cashRatio: 16.67, cathay: 32993, ctbc: 11511, esun: null, esunFutures: 132929, crypto: null },
  { date: "2026/01/31", usStockValue: 710930, usStockCash: 27891, principal: 612053, yoy: null, cashRatio: 3.47, cathay: 59365, ctbc: 9442, esun: null, esunFutures: 73999, crypto: 35222 },
  { date: "2026/02/28", usStockValue: 764754, usStockCash: 197613, principal: 807698, yoy: null, cashRatio: 18.27, cathay: 80892, ctbc: 69340, esun: null, esunFutures: 73999, crypto: 23788 },
  { date: "2026/03/31", usStockValue: 826366, usStockCash: 48482, principal: 807698, yoy: null, cashRatio: 4.43, cathay: 68249, ctbc: 9636, esun: 45866, esunFutures: 119787, crypto: 33199 },
  { date: "2026/04/30", usStockValue: 791055, usStockCash: 210669, principal: 807698, yoy: null, cashRatio: 19.36, cathay: 78230, ctbc: 4119, esun: 29443, esunFutures: 68899, crypto: 31788 },
  { date: "2026/05/30", usStockValue: 930789, usStockCash: 217086, principal: 807698, yoy: null, cashRatio: 18.97, cathay: 55287, ctbc: 22786, esun: 46850, esunFutures: 86425, crypto: 21549 },
  { date: "2026/06/30", usStockValue: 855998, usStockCash: 206673, principal: 807698, yoy: null, cashRatio: 16.06, cathay: 8350, ctbc: 46095, esun: 49776, esunFutures: 86425, crypto: 29756 },
  { date: "2026/07/31", usStockValue: 840410, usStockCash: 109564, principal: 807698, yoy: null, cashRatio: 9.30, cathay: 3998, ctbc: 41941, esun: 81635, esunFutures: 84197, crypto: 43438 },
  { date: "2026/08/30", usStockValue: 1037449, usStockCash: 46009, principal: 807698, yoy: null, cashRatio: 4.43, cathay: 1682, ctbc: 41014, esun: 99819, esunFutures: 88553, crypto: 117651 }
];
