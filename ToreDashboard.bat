@echo off
REM Starte Streamlit-Dashboard für Tore-Analysen
set PYTHON="C:\Users\demmelb-ma\AppData\Local\Programs\Python\Python314\python.exe"
set SCRIPT="C:\Users\demmelb-ma\OneDrive - COC AG\JWR\Analysen\2526\dashboard_fixed.py"

%PYTHON% -m streamlit run %SCRIPT%
pause
