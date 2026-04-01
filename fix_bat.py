with open("start_website.bat", "wb") as f:
    text = "@echo off\r\nchcp 65001\r\ncd /d \"%~dp0\"\r\necho 正在啟動 Stock Hunter 網站...\r\npython -m streamlit run 1_抄底怪物.py\r\npause\r\n"
    f.write(text.encode("utf-8"))
