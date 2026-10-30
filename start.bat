@echo off
REM Double-click to start Aditi. Works from any folder.
cd /d "%~dp0"
uv run server/main.py
pause
