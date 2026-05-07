import gspread, os, pandas as pd
from google.oauth2.service_account import Credentials

SHEET_ID = '1eaUErkLJUOH7aaIKhDWM5vQwAbE2Zrl0w9jI3KK-9yU'
scopes = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_file('credentials.json', scopes=scopes)
gc = gspread.authorize(creds)
sh = gc.open_by_key(SHEET_ID)

# 1. 同步投資組合
df = pd.read_csv('my_portfolio.csv', dtype=str).fillna('')
ws_port = sh.worksheet('美股持有庫存(每日更新)')
ws_port.clear()
ws_port.update([df.columns.tolist()] + df.values.tolist())
print(f'投資組合已同步：{len(df)} 筆')

# 2. 自選股監控分頁
WL_COLS = ['股票代號','股票名稱','P₀ (第一批進場價)','總資金 (USD)',
           'T1已填','T2已填','T3已填','T4已填','T5已填','備註']
try:
    ws_wl = sh.worksheet('自選股監控')
    print('自選股監控 已存在')
except:
    ws_wl = sh.add_worksheet(title='自選股監控', rows=200, cols=15)
    print('自選股監控 已建立')

if os.path.exists('watchlist_alerts.csv'):
    wl = pd.read_csv('watchlist_alerts.csv', dtype=str).fillna('')
    if not wl.empty:
        ws_wl.clear()
        ws_wl.update([wl.columns.tolist()] + wl.values.tolist())
        print(f'自選股已同步：{len(wl)} 筆')
    else:
        ws_wl.clear()
        ws_wl.update([WL_COLS])
else:
    ws_wl.clear()
    ws_wl.update([WL_COLS])

# 3. 設定分頁
try:
    ws_cfg = sh.worksheet('設定')
    print('設定 已存在')
except:
    ws_cfg = sh.add_worksheet(title='設定', rows=10, cols=5)
    print('設定 已建立')

cash = 0.0
if os.path.exists('cash_balance.txt'):
    try:
        cash = float(open('cash_balance.txt').read().strip())
    except:
        pass

ws_cfg.clear()
ws_cfg.update([['key', 'value'], ['cash_balance', str(cash)]])
print(f'現金餘額已同步：{cash}')
print('全部完成！')
