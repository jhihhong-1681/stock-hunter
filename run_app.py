import sys
import os
from streamlit.web import cli as stcli

if __name__ == '__main__':
    # 確保切換到正確的目錄
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    # 透過 Python 內部執行 Streamlit 以避開 cmd.exe 對於中文檔名的編碼問題
    sys.argv = ["streamlit", "run", "1_抄底怪物.py"]
    sys.exit(stcli.main())
