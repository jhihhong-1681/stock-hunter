// 目前持股快照（不是歷史紀錄，每天會被最新資料整個覆蓋掉）。
// 只列「目前還有部位」的股票/期權（總投入、現值有值的），已經全部賣光的舊部位不會出現在這裡，
// 但它們的已實現損益仍計入 totals.realizedPL。
window.HOLDINGS = {
  asOf: "2026-08-11",
  totals: {
    invested: 1015060,
    value: 959355.80,
    unrealizedPL: -55704.20,
    unrealizedPct: -5.49,
    realizedPL: 361328,
    cash: 157855,
    totalAssets: 1117210.80
  },
  positions: [
    { symbol: "ASTS", name: "AST Spacemobile", shares: 53, avgCost: 74.2, price: 71.6, invested: 121861, value: 117688, pl: -4172.91, pct: -3.42, realized: null },
    { symbol: "MP", name: "MP Materials", shares: 50, avgCost: 54.5, price: 55.2, invested: 84508, value: 85622, pl: 1114.25, pct: 1.32, realized: -8137.50 },
    { symbol: "SMR", name: "NuScale Power", shares: 95, avgCost: 27.8, price: 9.9, invested: 81945, value: 29126, pl: -52818.51, pct: -64.46, realized: -106338.51 },
    { symbol: "UGL", name: "2x Long Gold", shares: 35, avgCost: 68.2, price: 51.3, invested: 73961, value: 55682, pl: -18278.63, pct: -24.71, realized: -31372.00 },
    { symbol: "RKLB", name: "Rocket Lab Corporation", shares: 25, avgCost: 85.6, price: 80.0, invested: 66340, value: 62008, pl: -4332.25, pct: -6.53, realized: 28585.10 },
    { symbol: "VPG", name: "Vishay Precision Group", shares: 20, avgCost: 94.0, price: 67.1, invested: 58280, value: 41627, pl: -16653.20, pct: -28.57, realized: null },
    { symbol: "VRT", name: "Vertiv Holding", shares: 6, avgCost: 250.7, price: 281.8, invested: 46624, value: 52417, pl: 5792.66, pct: 12.42, realized: 75717.50 },
    { symbol: "FVRR", name: "Fiverr International", shares: 140, avgCost: 9.7, price: 8.8, invested: 42098, value: 37975, pl: -4123.00, pct: -9.79, realized: null },
    { symbol: "PLTR", name: "Palantir", shares: 9, avgCost: 128.1, price: 174.9, invested: 35743, value: 48808, pl: 13065.26, pct: 36.55, realized: 5541.56 },
    { symbol: "VOYG", name: "Voyager Technologies", shares: 40, avgCost: 28.0, price: 42.9, invested: 34720, value: 53196, pl: 18476.00, pct: 53.21, realized: null },
    { symbol: "UUUU", name: "Energy Fuels", shares: 55, avgCost: 20.3, price: 14.8, invested: 34646, value: 25200, pl: -9445.70, pct: -27.26, realized: -12827.80 },
    { symbol: "MU", name: "Micron", shares: 1, avgCost: 930.0, price: 868.5, invested: 28830, value: 26924, pl: -1905.88, pct: -6.61, realized: null },
    { symbol: "ALGM", name: "Allegro MicroSystems", shares: 20, avgCost: 45.2, price: 42.5, invested: 28024, value: 26362, pl: -1661.60, pct: -5.93, realized: null },
    { symbol: "CAG", name: "ConAgra Brands", shares: 50, avgCost: 15.5, price: 14.9, invested: 24025, value: 23142, pl: -883.50, pct: -3.68, realized: null },
    { symbol: "MRCY", name: "Mercury Systems", shares: 2, avgCost: 112.0, price: 109.2, invested: 6944, value: 6767, pl: -176.70, pct: -2.54, realized: null },
    { symbol: "HOOD", name: "HOOD 09/18/26 75 Call", type: "option", shares: 100, avgCost: null, price: 20.12, invested: 57350, value: 62371.34, pl: 5021.34, pct: 8.76, realized: -41850.00 },
    { symbol: "XOM", name: "XOM 09/18/26 145 Call", type: "option", shares: 100, avgCost: null, price: 15.54, invested: 39370, value: 48173.27, pl: 8803.27, pct: 22.36, realized: null },
    { symbol: "HAL", name: "HAL 10/16/26 32 Call", type: "option", shares: 300, avgCost: null, price: 3.07, invested: 32147, value: 28549.36, pl: -3597.64, pct: -11.19, realized: null },
    { symbol: "SMCI", name: "SMCI 08/14/26 40 Call", type: "option", shares: 3000, avgCost: null, price: 0.49, invested: 29760, value: 45570.00, pl: 15810.00, pct: 53.13, realized: null },
    { symbol: "GSK", name: "GSK 11/20/26 45 Call", type: "option", shares: 100, avgCost: null, price: 6.70, invested: 23870, value: 20769.46, pl: -3100.54, pct: -12.99, realized: null },
    { symbol: "ONDS", name: "ONDS 09/18/26 13 Call", type: "option", shares: 1500, avgCost: null, price: 0.49, invested: 20925, value: 22785.00, pl: 1860.00, pct: 8.89, realized: null },
    { symbol: "SOFI", name: "SOFI 08/21/26 20 Call", type: "option", shares: 5000, avgCost: null, price: 0.09, invested: 15500, value: 13950.00, pl: -1550.00, pct: -10.00, realized: null },
    { symbol: "BMNR", name: "BMNR 09/18/26 14 Call", type: "option", shares: 100, avgCost: null, price: 4.25, invested: 13950, value: 13174.41, pl: -775.59, pct: -5.56, realized: null },
    { symbol: "SBET", name: "SBET 01/15/27 5 Call", type: "option", shares: 200, avgCost: null, price: 1.85, invested: 13640, value: 11468.96, pl: -2171.04, pct: -15.92, realized: null }
  ]
};
