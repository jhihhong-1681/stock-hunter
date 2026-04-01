with open("start_website.bat", "wb") as f:
    text = "@echo off\r\ncd /d \"%~dp0\"\r\necho Starting Stock Hunter website...\r\npython -m streamlit run 1_抄底怪物.py\r\npause\r\n"
    f.write(text.encode("utf-8"))
