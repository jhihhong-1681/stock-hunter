@echo off
cd /d "%~dp0"
echo 正在啟動 ngrok (準備產生對外公開網址)...
echo.
echo ========================================================
echo 請在稍後出現的畫面中尋找「Forwarding」旁邊的網址
echo 例如： https://xxxx-xx-xx....ngrok-free.app 
echo 這就是您可以分享給其他電腦或手機使用的公開網址！
echo ========================================================
echo.
ngrok\ngrok.exe http 8501
pause
