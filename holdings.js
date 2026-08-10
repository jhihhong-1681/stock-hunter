// 目前持股快照（不是歷史紀錄，每天會被最新資料整個覆蓋掉）。
// 只列「目前還有部位」的股票/期權（總投入、現值有值的），已經全部賣光的舊部位不會出現在這裡，
// 但它們的已實現損益仍計入 totals.realizedPL。
window.HOLDINGS = {
  asOf: "2026-08-07",
  totals: {
    invested: 982665,
    value: 892151,
    unrealizedPL: -90513.88,
    unrealizedPct: -9.21,
    realizedPL: 358073.03,
    cash: 187055,
    totalAssets: 1079206
  },
  positions: [
    { symbol: "ASTS", name: "AST Spacemobile", shares: 53, avgCost: 74.2, price: 71.9, invested: 121861, value: 118197, pl: -3663.58, pct: -3.01, realized: null },
    { symbol: "MP", name: "MP Materials", shares: 50, avgCost: 54.5, price: 51.1, invested: 84508, value: 79221, pl: -5287.25, pct: -6.26, realized: -8137.50 },
    { symbol: "SMR", name: "NuScale Power", shares: 95, avgCost: 27.8, price: 9.8, invested: 81945, value: 28920, pl: -53024.66, pct: -64.71, realized: -106338.51 },
    { symbol: "UGL", name: "2x Long Gold", shares: 35, avgCost: 68.2, price: 50.7, invested: 73961, value: 54999, pl: -18962.18, pct: -25.64, realized: -31372.00 },
    { symbol: "RKLB", name: "Rocket Lab Corporation", shares: 25, avgCost: 85.6, price: 82.8, invested: 66340, value: 64193, pl: -2146.75, pct: -3.24, realized: 28585.10 },
    { symbol: "VPG", name: "Vishay Precision Group", shares: 20, avgCost: 94.0, price: 68.6, invested: 58280, value: 42526, pl: -15754.20, pct: -27.03, realized: null },
    { symbol: "VRT", name: "Vertiv Holding", shares: 6, avgCost: 250.7, price: 272.4, invested: 46624, value: 50666, pl: 4042.40, pct: 8.67, realized: 75717.50 },
    { symbol: "FVRR", name: "Fiverr International", shares: 140, avgCost: 9.7, price: 9.4, invested: 42098, value: 40883, pl: -1215.20, pct: -2.89, realized: null },
    { symbol: "PLTR", name: "Palantir", shares: 9, avgCost: 128.1, price: 172.0, invested: 35743, value: 47991, pl: 12247.79, pct: 34.27, realized: 5541.56 },
    { symbol: "VOYG", name: "Voyager Technologies", shares: 40, avgCost: 28.0, price: 41.9, invested: 34720, value: 51894, pl: 17174.00, pct: 49.46, realized: null },
    { symbol: "UUUU", name: "Energy Fuels", shares: 55, avgCost: 20.3, price: 14.1, invested: 34646, value: 24109, pl: -10536.90, pct: -30.41, realized: -12827.80 },
    { symbol: "IBM", name: "IBM", shares: 5, avgCost: 218.0, price: 237.3, invested: 33790, value: 36778, pl: 2988.40, pct: 8.84, realized: null },
    { symbol: "MU", name: "Micron", shares: 1, avgCost: 930.0, price: 877.6, invested: 28830, value: 27205, pl: -1625.33, pct: -5.64, realized: null },
    { symbol: "ALGM", name: "Allegro MicroSystems", shares: 20, avgCost: 45.2, price: 43.8, invested: 28024, value: 27137, pl: -886.60, pct: -3.16, realized: null },
    { symbol: "CAG", name: "ConAgra Brands", shares: 50, avgCost: 15.5, price: 15.1, invested: 24025, value: 23421, pl: -604.50, pct: -2.52, realized: null },
    { symbol: "MRCY", name: "Mercury Systems", shares: 2, avgCost: 112.0, price: 108.6, invested: 6944, value: 6736, pl: -208.32, pct: -3.00, realized: null },
    { symbol: "HOOD", name: "HOOD 09/18/26 100 Call", type: "option", shares: 100, avgCost: null, price: null, invested: 57350, value: 62093, pl: 4743.00, pct: 8.27, realized: -41850.00 },
    { symbol: "XOM", name: "XOM 09/18/26 145 Call", type: "option", shares: 100, avgCost: null, price: null, invested: 39370, value: 30845, pl: -8525.00, pct: -21.65, realized: null },
    { symbol: "HAL", name: "HAL 10/16/26 32 Call", type: "option", shares: 300, avgCost: null, price: null, invested: 32147, value: 17856, pl: -14291.00, pct: -44.46, realized: null },
    { symbol: "GSK", name: "GSK 11/20/26 45 Call", type: "option", shares: null, avgCost: null, price: null, invested: 23870, value: 26970, pl: 3100.00, pct: 12.99, realized: null },
    { symbol: "SBET", name: "SBET 01/15/27 5 Call", type: "option", shares: 200, avgCost: null, price: null, invested: 13640, value: 13392, pl: -248.00, pct: -1.82, realized: null },
    { symbol: "BMNR", name: "BMNR 09/18/26 14 Call", type: "option", shares: 100, avgCost: null, price: null, invested: 13950, value: 16120, pl: 2170.00, pct: 15.56, realized: null }
  ]
};
