// 目前持股快照（不是歷史紀錄，每天會被最新資料整個覆蓋掉）。
// 只列「目前還有部位」的股票/期權（總投入、現值有值的），已經全部賣光的舊部位不會出現在這裡，
// 但它們的已實現損益仍計入 totals.realizedPL。
window.HOLDINGS = {
  asOf: "2026-08-10",
  totals: {
    invested: 982665,
    value: 910576.34,
    unrealizedPL: -72088.66,
    unrealizedPct: -7.34,
    realizedPL: 358073.03,
    cash: 187055,
    totalAssets: 1097631.34
  },
  positions: [
    { symbol: "ASTS", name: "AST Spacemobile", shares: 53, avgCost: 74.2, price: 68.8, invested: 121861, value: 112973, pl: -8888.32, pct: -7.29, realized: null },
    { symbol: "MP", name: "MP Materials", shares: 50, avgCost: 54.5, price: 54.7, invested: 84508, value: 84723, pl: 215.25, pct: 0.25, realized: -8137.50 },
    { symbol: "SMR", name: "NuScale Power", shares: 95, avgCost: 27.8, price: 9.2, invested: 81945, value: 27035, pl: -54909.46, pct: -67.01, realized: -106338.51 },
    { symbol: "UGL", name: "2x Long Gold", shares: 35, avgCost: 68.2, price: 51.7, invested: 73961, value: 56105, pl: -17855.48, pct: -24.14, realized: -31372.00 },
    { symbol: "RKLB", name: "Rocket Lab Corporation", shares: 25, avgCost: 85.6, price: 80.0, invested: 66340, value: 62031, pl: -4309.00, pct: -6.50, realized: 28585.10 },
    { symbol: "VPG", name: "Vishay Precision Group", shares: 20, avgCost: 94.0, price: 64.9, invested: 58280, value: 40226, pl: -18054.40, pct: -30.98, realized: null },
    { symbol: "VRT", name: "Vertiv Holding", shares: 6, avgCost: 250.7, price: 270.1, invested: 46624, value: 50239, pl: 3614.60, pct: 7.75, realized: 75717.50 },
    { symbol: "FVRR", name: "Fiverr International", shares: 140, avgCost: 9.7, price: 9.1, invested: 42098, value: 39451, pl: -2647.40, pct: -6.29, realized: null },
    { symbol: "PLTR", name: "Palantir", shares: 9, avgCost: 128.1, price: 175.2, invested: 35743, value: 48889, pl: 13146.17, pct: 36.78, realized: 5541.56 },
    { symbol: "VOYG", name: "Voyager Technologies", shares: 40, avgCost: 28.0, price: 43.0, invested: 34720, value: 53320, pl: 18600.00, pct: 53.57, realized: null },
    { symbol: "UUUU", name: "Energy Fuels", shares: 55, avgCost: 20.3, price: 14.3, invested: 34646, value: 24364, pl: -10281.15, pct: -29.68, realized: -12827.80 },
    { symbol: "IBM", name: "IBM", shares: 5, avgCost: 218.0, price: 236.3, invested: 33790, value: 36628, pl: 2838.05, pct: 8.40, realized: null },
    { symbol: "MU", name: "Micron", shares: 1, avgCost: 930.0, price: 861.0, invested: 28830, value: 26691, pl: -2139.00, pct: -7.42, realized: null },
    { symbol: "ALGM", name: "Allegro MicroSystems", shares: 20, avgCost: 45.2, price: 42.5, invested: 28024, value: 26325, pl: -1698.80, pct: -6.06, realized: null },
    { symbol: "CAG", name: "ConAgra Brands", shares: 50, avgCost: 15.5, price: 14.8, invested: 24025, value: 22894, pl: -1131.50, pct: -4.71, realized: null },
    { symbol: "MRCY", name: "Mercury Systems", shares: 2, avgCost: 112.0, price: 108.6, invested: 6944, value: 6736, pl: -208.32, pct: -3.00, realized: null },
    { symbol: "HOOD", name: "HOOD 09/18/26 100 Call", type: "option", shares: 100, avgCost: null, price: null, invested: 57350, value: 65937, pl: 8587.00, pct: 14.97, realized: -41850.00 },
    { symbol: "XOM", name: "XOM 09/18/26 145 Call", type: "option", shares: 100, avgCost: null, price: 15.75, invested: 39370, value: 48824.23, pl: 9454.23, pct: 24.01, realized: null },
    { symbol: "HAL", name: "HAL 10/16/26 32 Call", type: "option", shares: 300, avgCost: null, price: 2.94, invested: 32147, value: 27340.41, pl: -4806.59, pct: -14.95, realized: null },
    { symbol: "GSK", name: "GSK 11/20/26 45 Call", type: "option", shares: null, avgCost: null, price: 7.69, invested: 23870, value: 23838.38, pl: -31.62, pct: -0.13, realized: null },
    { symbol: "SBET", name: "SBET 01/15/27 5 Call", type: "option", shares: 200, avgCost: null, price: 1.85, invested: 13640, value: 11468.96, pl: -2171.04, pct: -15.92, realized: null },
    { symbol: "BMNR", name: "BMNR 09/18/26 14 Call", type: "option", shares: 100, avgCost: null, price: 4.69, invested: 13950, value: 14538.36, pl: 588.36, pct: 4.22, realized: null }
  ]
};
