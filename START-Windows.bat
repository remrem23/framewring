@echo off
chcp 65001 >nul
title Framewring - video compressor
cd /d "%~dp0"

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY ( where python >nul 2>nul && set "PY=python" )

if not defined PY (
  echo.
  echo  [!] Python was not found.
  echo      Trying to install it with winget now. If that fails:
  echo      download it from https://www.python.org/downloads/ and tick
  echo      "Add python.exe to PATH" during installation.
  echo.
  echo  [!] Python не найден.
  echo      Сейчас попробую поставить его через winget. Если не выйдет:
  echo      скачай с https://www.python.org/downloads/ и при установке
  echo      поставь галочку "Add python.exe to PATH".
  echo.
  winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
  echo.
  echo  Done? Close this window and run START-Windows.bat again.
  echo  Готово? Закрой это окно и запусти START-Windows.bat ещё раз.
  pause
  exit /b
)

set "HAVEFF="
where ffmpeg >nul 2>nul && set "HAVEFF=1"
if exist "%~dp0ffmpeg\bin\ffmpeg.exe" set "HAVEFF=1"
if exist "%~dp0ffmpeg.exe" set "HAVEFF=1"

if not defined HAVEFF (
  echo.
  echo  [!] FFmpeg was not found. Installing it with winget - Gyan build with x265, AV1 and VMAF...
  echo  [!] FFmpeg не найден. Ставлю через winget (сборка Gyan, с x265, AV1 и VMAF^)...
  echo.
  winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
  echo.
  echo  Done? Close this window and run START-Windows.bat again
  echo  - Windows picks up FFmpeg only in a new window.
  echo  Готово? Закрой это окно и запусти START-Windows.bat ещё раз
  echo  (Windows подхватит FFmpeg только в новом окне^).
  pause
  exit /b
)

%PY% "%~dp0app.py"
pause
