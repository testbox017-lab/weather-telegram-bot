@echo off
rem Скачать свежую копию данных бота с сервера в папку backups (рядом с этим файлом).
cd /d "%~dp0"
if not exist backups mkdir backups
for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set D=%%d
scp root@2.29.199.153:/var/backups/weather-bot/latest.tar.gz backups\weather-bot-%D%.tar.gz && echo Saved backups\weather-bot-%D%.tar.gz
