@echo off
REM Double-clic = lance DataAgent en local (http://localhost:8501).
cd /d "%~dp0"
".venv\Scripts\python.exe" -m streamlit run app.py
pause
