@echo off
chcp 65001 >nul
powershell -NoProfile -Command "$p = Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*bot.py*' }; if ($p) { $p | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }; exit 0 } else { exit 1 }"
if errorlevel 1 (echo Бот не был запущен) else (echo Бот остановлен)
timeout /t 3 >nul
