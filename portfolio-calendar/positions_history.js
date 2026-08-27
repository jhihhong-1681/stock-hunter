// 每日「持股組成」歷史，用來拆解報酬日曆某一天的漲跌是哪幾檔貢獻的。
// 跟 holdings.js（只留最新一天）不同，這份是逐日累積、不會被覆蓋掉。
//
// 每一天存 { positions: [...], totals: {...} }：
//
// positions：當天還持有的部位 + 當天剛平倉的部位，每筆 { symbol, name, pl, realized }
// - pl：那個部位當下的未實現損益（跟 holdings.js positions[] 裡的 pl 同一個數字）
// - realized：那個部位累積至今的已實現損益（跟 holdings.js positions[]/closedPositions[] 的 realized 同一個數字，沒有就 null）
// 早就平倉、之後也沒再變動的部位不會每天重複列出（反正對後面每一天的貢獻都是 0，列了也只是浪費空間）。
//
// 算某一天(D)某個部位的損益貢獻的公式：
//   (D 的 pl − 前一天的 pl，找不到前一天就當 0) + (D 的 realized − 前一天的 realized，找不到前一天就當 0)
// 用 symbol+"|"+name 當作比對兩天是否為同一個部位的 key（期權滾倉換履約價/到期日會變成新的 key，視為新部位，不算連續）。
//
// totals：{ cash, invested, realizedPL }，直接抄 holdings.js totals 裡同名欄位當天的值。
// 用來算「現金的非交易變動」（存提款、利息之類跟買賣股票無關的現金增減），公式：
//   (D 的 cash − 前一天的 cash) − (D 的 realizedPL − 前一天的 realizedPL) + (D 的 invested − 前一天的 invested)
// 這樣算出來，如果現金變化單純是買賣股票造成的（已經算在上面 positions 的貢獻裡了），這個數字會剛好是 0，
// 不會被重複計算；只有存提款/利息這種跟交易無關的現金增減才會顯示出來。
//
// 2026-08-24 這筆是啟用這個功能當天的起點快照（從當時的 holdings.js 直接取值），
// 所以還沒有前一天可以比較，日曆點 8/24 不會有拆解可看，8/25 起才開始看得到「當天 vs 前一天」的組成。
window.POSITIONS_HISTORY = {
  "2026-08-24": {
    positions: [
      { symbol: "ASTS", name: "AST Spacemobile", pl: -19419.95, realized: null },
      { symbol: "MP", name: "MP Materials", pl: 4493.25, realized: -8137.50 },
      { symbol: "SMR", name: "NuScale Power", pl: -55292.31, realized: -106338.51 },
      { symbol: "UGL", name: "2x Long Gold", pl: -11128.48, realized: -31372.00 },
      { symbol: "RKLB", name: "Rocket Lab Corporation", pl: -13423.00, realized: 28585.10 },
      { symbol: "VPG", name: "Vishay Precision Group", pl: -17260.80, realized: null },
      { symbol: "VOYG", name: "Voyager Technologies", pl: 8990.00, realized: null },
      { symbol: "VRT", name: "Vertiv Holding", pl: 830.49, realized: 75717.50 },
      { symbol: "FVRR", name: "Fiverr International", pl: -1432.20, realized: null },
      { symbol: "PLTR", name: "Palantir", pl: 13330.31, realized: 5541.56 },
      { symbol: "UUUU", name: "Energy Fuels", pl: -9275.20, realized: -12827.80 },
      { symbol: "VIAV", name: "Viavi Solutions", pl: -3913.75, realized: null },
      { symbol: "MU", name: "Micron", pl: -606.67, realized: null },
      { symbol: "ALGM", name: "Allegro MicroSystems", pl: -5933.40, realized: null },
      { symbol: "CAG", name: "ConAgra Brands", pl: 1813.50, realized: null },
      { symbol: "AESI", name: "Atlas Energy Solutions", pl: 77.50, realized: null },
      { symbol: "MBOT", name: "Microbot Medical", pl: -124.00, realized: null },
      { symbol: "PRZO", name: "ParaZero Technologies", pl: -124.00, realized: null },
      { symbol: "MRCY", name: "Mercury Systems", pl: -1389.42, realized: null },
      { symbol: "HOOD", name: "HOOD 09/18/26 75 Call", pl: 37045.00, realized: -41850.00 },
      { symbol: "XOM", name: "XOM 09/18/26 145 Call", pl: 20460.00, realized: null },
      { symbol: "HAL", name: "HAL 10/16/26 32 Call", pl: -713.00, realized: null },
      { symbol: "GSK", name: "GSK 11/20/26 45 Call", pl: -589.00, realized: null },
      { symbol: "ONDS", name: "ONDS 09/18/26 13 Call", pl: -18135.00, realized: null },
      { symbol: "SLV", name: "SLV 09/18/26 58 Call", pl: 15748.00, realized: null },
      { symbol: "PBR", name: "PBR 09/18/26 19 Call", pl: 4960.00, realized: null },
      { symbol: "CLF", name: "CLF 11/20/26 10 Call", pl: 1612.00, realized: null },
      { symbol: "HIVE", name: "HIVE 09/18/26 4 Call", pl: -3720.00, realized: null }
    ],
    totals: { cash: 93078, invested: 1092203, realizedPL: 372674 }
  },
  "2026-08-25": {
    positions: [
      { symbol: "ASTS", name: "AST Spacemobile", pl: -19978.57, realized: null },
      { symbol: "MP", name: "MP Materials", pl: 8755.75, realized: -8137.50 },
      { symbol: "SMR", name: "NuScale Power", pl: -53054.11, realized: -106338.51 },
      { symbol: "UGL", name: "2x Long Gold", pl: -10705.33, realized: -31372.00 },
      { symbol: "RKLB", name: "Rocket Lab Corporation", pl: -14484.75, realized: 28585.10 },
      { symbol: "VPG", name: "Vishay Precision Group", pl: -18321.00, realized: null },
      { symbol: "VOYG", name: "Voyager Technologies", pl: 7148.60, realized: null },
      { symbol: "VRT", name: "Vertiv Holding", pl: 999.75, realized: 75717.50 },
      { symbol: "FVRR", name: "Fiverr International", pl: -520.80, realized: null },
      { symbol: "PLTR", name: "Palantir", pl: 12448.67, realized: 5541.56 },
      { symbol: "UUUU", name: "Energy Fuels", pl: -7416.75, realized: -12827.80 },
      { symbol: "VIAV", name: "Viavi Solutions", pl: -3324.75, realized: null },
      { symbol: "MU", name: "Micron", pl: 92.07, realized: null },
      { symbol: "ALGM", name: "Allegro MicroSystems", pl: -4811.20, realized: null },
      { symbol: "CAG", name: "ConAgra Brands", pl: 1193.50, realized: null },
      { symbol: "AESI", name: "Atlas Energy Solutions", pl: 263.50, realized: null },
      { symbol: "MBOT", name: "Microbot Medical", pl: 0.00, realized: null },
      { symbol: "PRZO", name: "ParaZero Technologies", pl: 2232.00, realized: null },
      { symbol: "MRCY", name: "Mercury Systems", pl: -1451.42, realized: null },
      { symbol: "HOOD", name: "HOOD 09/18/26 75 Call", pl: 56420.00, realized: -41850.00 },
      { symbol: "XOM", name: "XOM 09/18/26 145 Call", pl: 12307.00, realized: null },
      { symbol: "HAL", name: "HAL 10/16/26 32 Call", pl: -4247.00, realized: null },
      { symbol: "GSK", name: "GSK 11/20/26 45 Call", pl: -589.00, realized: null },
      { symbol: "ONDS", name: "ONDS 09/18/26 13 Call", pl: -18600.00, realized: null },
      { symbol: "SLV", name: "SLV 09/18/26 58 Call", pl: 17546.00, realized: null },
      { symbol: "PBR", name: "PBR 09/18/26 19 Call", pl: -620.00, realized: null },
      { symbol: "CLF", name: "CLF 11/20/26 10 Call", pl: 1302.00, realized: null },
      { symbol: "HIVE", name: "HIVE 09/18/26 4 Call", pl: 0.00, realized: null },
      { symbol: "SOUN", name: "SOUN 10/16/26 9 Call", pl: 310.00, realized: null }
    ],
    totals: { cash: 72085, invested: 1112260, realizedPL: 372674 }
  },
  "2026-08-26": {
    positions: [
      { symbol: "ASTS", name: "AST Spacemobile", pl: -23478.16, realized: null },
      { symbol: "MP", name: "MP Materials", pl: 7422.75, realized: -8137.50 },
      { symbol: "SMR", name: "NuScale Power", pl: -54644.41, realized: -106338.51 },
      { symbol: "UGL", name: "2x Long Gold", pl: -12690.88, realized: -31372.00 },
      { symbol: "RKLB", name: "Rocket Lab Corporation", pl: -15050.50, realized: 28585.10 },
      { symbol: "VPG", name: "Vishay Precision Group", pl: -18562.80, realized: null },
      { symbol: "VOYG", name: "Voyager Technologies", pl: 7371.80, realized: null },
      { symbol: "VRT", name: "Vertiv Holding", pl: 0, realized: 77922.22 },
      { symbol: "FVRR", name: "Fiverr International", pl: -998.20, realized: null },
      { symbol: "PLTR", name: "Palantir", pl: 13779.50, realized: 5541.56 },
      { symbol: "UUUU", name: "Energy Fuels", pl: -7877.10, realized: -12827.80 },
      { symbol: "VIAV", name: "Viavi Solutions", pl: -2495.50, realized: null },
      { symbol: "MU", name: "Micron", pl: 260.40, realized: null },
      { symbol: "ALGM", name: "Allegro MicroSystems", pl: -5152.20, realized: null },
      { symbol: "CAG", name: "ConAgra Brands", pl: 1069.50, realized: null },
      { symbol: "MRCY", name: "Mercury Systems", pl: -1013.08, realized: null },
      { symbol: "AESI", name: "Atlas Energy Solutions", pl: 341.00, realized: null },
      { symbol: "MBOT", name: "Microbot Medical", pl: 124.00, realized: null },
      { symbol: "PRZO", name: "ParaZero Technologies", pl: 1984.00, realized: null },
      { symbol: "HOOD", name: "HOOD 09/18/26 75 Call", pl: 0, realized: 49910.00 },
      { symbol: "HOOD", name: "HOOD 10/16/26 79 Call", pl: -2635.00, realized: null },
      { symbol: "XOM", name: "XOM 09/18/26 145 Call", pl: 4960.00, realized: null },
      { symbol: "HAL", name: "HAL 10/16/26 32 Call", pl: -2666.00, realized: null },
      { symbol: "GSK", name: "GSK 11/20/26 45 Call", pl: -310.00, realized: null },
      { symbol: "ONDS", name: "ONDS 09/18/26 13 Call", pl: -19065.00, realized: null },
      { symbol: "SLV", name: "SLV 09/18/26 58 Call", pl: 13268.00, realized: null },
      { symbol: "PBR", name: "PBR 09/18/26 19 Call", pl: -2480.00, realized: null },
      { symbol: "CLF", name: "CLF 11/20/26 10 Call", pl: 2604.00, realized: null },
      { symbol: "HIVE", name: "HIVE 09/18/26 4 Call", pl: -3720.00, realized: null },
      { symbol: "SOUN", name: "SOUN 10/16/26 9 Call", pl: -310.00, realized: null }
    ],
    totals: { cash: 177762, invested: 1058692, realizedPL: 466638.72 }
  }
};
