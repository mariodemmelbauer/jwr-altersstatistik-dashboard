@echo off
REM Starte Streamlit-Dashboard für Alter-Analysen
set PYTHON="C:\Users\demmelb-ma\AppData\Local\Programs\Python\Python313\python.exe"
set SCRIPT="C:\Users\demmelb-ma\OneDrive - COC AG\JWR\Analysen\2526\altersstatistik_app.py"

%PYTHON% -m streamlit run %SCRIPT%
pause
