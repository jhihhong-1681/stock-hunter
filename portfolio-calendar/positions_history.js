// 每日「持股組成」歷史，用來拆解報酬日曆某一天的漲跌是哪幾檔貢獻的。
// 跟 holdings.js（只留最新一天）不同，這份是逐日累積、不會被覆蓋掉。
//
// 每一天只存「當天還持有的部位」+「當天剛平倉的部位」的 { symbol, name, pl, realized }：
// - pl：那個部位當下的未實現損益（跟 holdings.js positions[] 裡的 pl 同一個數字）
// - realized：那個部位累積至今的已實現損益（跟 holdings.js positions[]/closedPositions[] 的 realized 同一個數字，沒有就 null）
// 早就平倉、之後也沒再變動的部位不會每天重複列出（反正對後面每一天的貢獻都是 0，列了也只是浪費空間）。
//
// 算某一天(D)某個部位的損益貢獻的公式：
//   (D 的 pl − 前一天的 pl，找不到前一天就當 0) + (D 的 realized − 前一天的 realized，找不到前一天就當 0)
// 用 symbol+"|"+name 當作比對兩天是否為同一個部位的 key（期權滾倉換履約價/到期日會變成新的 key，視為新部位，不算連續）。
//
// 2026-08-24 這筆是啟用這個功能當天的起點快照（從當時的 holdings.js 直接取值），
// 所以還沒有前一天可以比較，日曆點 8/24 不會有拆解可看，8/25 起才開始看得到「當天 vs 前一天」的組成。
window.POSITIONS_HISTORY = {
  "2026-08-24": [
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
  ]
};
