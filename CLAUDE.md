# stock-hunter — 給 Claude 的專案說明

阿紘（jhihhong-1681）的個人股票儀表板 monorepo。**這個 repo 是公開的**：不要把任何帳密、API key、token、付費電子報內容寫進 repo（secrets 放 `.streamlit/secrets.toml`，已 gitignore）。回報一律用繁體中文。阿紘直接 push `main`，沒有 PR 流程。

## 組成

- **Streamlit 儀表板**：`1_抄底怪物.py` + `pages/` + `utils/`，push 到 main 會自動部署到 https://jhihhong-stock-hunter-v2.streamlit.app/ 。
- **報酬日曆網站**：`portfolio-calendar/`（靜態網站，GitHub Pages：https://jhihhong-1681.github.io/stock-hunter/portfolio-calendar/ ，Streamlit 的「報酬日曆」頁用 iframe 嵌入）。跟阿紘提到報酬日曆時，給 **https://jhihhong-stock-hunter-v2.streamlit.app/報酬日曆**，不要給 GitHub Pages 網址。
- 其他自動化（ETF 持股、法人資料、期貨）由 GitHub Actions 各自 commit 到 `data/`。

## 報酬日曆的資料流

- 資料來源：Google Sheet「輸輸贏贏 那也沒辦法」（file id `1eaUErkLJUOH7aaIKhDWM5vQwAbE2Zrl0w9jI3KK-9yU`，第一分頁「美股持有庫存(每日更新)」），阿紘每天手動更新。
- 每日快照：**雲端排程**照 [`portfolio-calendar/SNAPSHOT_TASK.md`](portfolio-calendar/SNAPSHOT_TASK.md) 寫 `data.js`、`indices.js`、`holdings.js`、`positions_history.js`。要改快照規則就改這個檔案。
- Firstrade 未成交訂單：**阿紘桌機的本機排程**照 [`portfolio-calendar/FIRSTRADE_TASK.md`](portfolio-calendar/FIRSTRADE_TASK.md) 寫 `pending_orders.js`（需要本機已登入的 Chrome；絕不代打密碼登入）。
- 資產淨值頁：`networth_data.js` 不是每日排程管的，只在阿紘說「同步資產淨值」時，讀 Sheet 底部月結表手動更新。
- 這個網站一律用「靜態資料檔 + 從 Sheet 同步」的模式。**不要再加 Firestore 之類的線上即時編輯**（試過兩次，都造成資料不同步）。
- `app.js` 的 `THEME_MAP` 是持股「細分產業」分類（例如 太空-發射與太空基建、AI-記憶體、石油-油服、數位銀行…），`THEME_PARENT` 再把細分產業歸到大類（太空國防、AI與半導體、石油與能源…），主題曝險頁會兩層都顯示。新代號要分類時研究公司主業與未來布局後，歸入既有細分產業，真的沒有適合的才新增細分並同步補 `THEME_PARENT`。
- 網站漲跌色用台股慣例：**紅漲綠跌**。

## 處理 Sheet 資料的已知陷阱

- **已平倉區塊會被截斷**：Google Drive `read_file_content` 在 Sheet 變大時會靜默丟掉已平倉區塊尾端的列。closedPositions 變少不代表阿紘刪除，要用上一份 `holdings.js`（或 git history）補回。
- **已實現損益總額**直接照抄 Sheet 的公式格（`=SUM(N…)`），不要自己用加總或現金流恆等式反推去「修正」它。
- **期權列的「現價」欄是標的股價**（不是權利金），阿紘確認正確，直接用、不用上網查證。期權權利金用 `總投入或現值(NT$) ÷ 31 ÷ 股數` 反推（31 是阿紘固定匯率）。
- 滾倉時新開倉那列的已實現損益偶爾會殘留舊數字；換約的期權每一筆平倉都是獨立交易，同代號多筆都要保留。
- positions_history 用 symbol+name 逐日比對，**同一部位的 name 寫法（大小寫、"Call" vs "CALL"）要跟前一天完全一致**。
- `priceUnchangedDays` 警示（期權現值連續沒變）可能是假警報：如果前一份快照是排程漏跑後補跑或被手動修正過，比對基準會被污染，先查 `git log -- portfolio-calendar/holdings.js`。

## 開發環境備註

- 本機（阿紘桌機）Python 是 embeddable 版本；Node 可用。
- 預覽 `portfolio-calendar/` 要用 HTTP server，直接開 `file://` 不會跑 JS。
