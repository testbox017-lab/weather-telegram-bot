@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Какой Python использовать: переменная PYTHON, затем файл python_path.txt (одна строка — путь
rem к python.exe, файл не попадает в git), затем py или python из PATH
set "PY=%PYTHON%"
if not defined PY if exist "python_path.txt" set /p PY=<"python_path.txt"
if not defined PY (
  where py >nul 2>&1 && (set "PY=py") || (set "PY=python")
)
if not exist ".env" (
  echo Нет файла .env со строкой BOT_TOKEN=ваш_токен
  pause
  exit /b 1
)
rem Уже запущен? Ищем процесс python с bot.py в командной строке (надёжнее заголовка окна)
powershell -NoProfile -Command "if (Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*bot.py*' }) { exit 0 } else { exit 1 }"
if not errorlevel 1 (
  echo Бот уже запущен. Чтобы перезапустить, сначала выполните stop_bot.bat
  timeout /t 5 >nul
  exit /b 0
)
echo Проверяю зависимости...
"%PY%" -m pip install -q -r requirements.txt >nul 2>&1
start "WeatherBot" /min cmd /c ""%PY%" bot.py >> bot.out.log 2>> bot.log"
echo Бот запущен в свёрнутом окне WeatherBot. Логи: bot.log. Остановить: stop_bot.bat
timeout /t 5 >nul
