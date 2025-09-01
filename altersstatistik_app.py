# -*- coding: utf-8 -*-
"""
Standalone Altersstatistik App
Streamlit: streamlit run altersstatistik_app.py
"""

import os
import streamlit as st
from pathlib import Path

# ========================= CONFIG =========================
BASE_DIR = Path(r"C:\Users\demmelb-ma\OneDrive - COC AG\JWR\Analysen\2526")
ALTERSSTATISTIK_SCRIPT = Path(r"C:\Users\demmelb-ma\OneDrive - COC AG\JWR\Matches\2526\Durchschnittsalter.py")
ALTERSSTATISTIK_EXCEL = Path(r"C:\Users\demmelb-ma\OneDrive - COC AG\JWR\Matches\2526\Statistik Altersdurchschnitt.xlsx")

# ========================= PAGE SETUP =========================
st.set_page_config(
    page_title="Altersstatistik - JWR Dashboard", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# Dark Theme CSS
st.markdown(
    """
    <style>
      /* Base dark background and text */
      html, body, .stApp, .block-container { background-color: #0b0f14 !important; color: #e5e7eb !important; }
      .block-container { padding-top: 2.25rem !important; }
      h1, h2, h3, h4, h5 { margin-top: 0.2rem; margin-bottom: 0.4rem; color: #f3f4f6 !important; }
      a { color: #93c5fd !important; }

      /* Controls */
      div.stButton > button { padding: 0.2rem 0.6rem; font-size: 0.8rem; background:#111827; color:#e5e7eb; border:1px solid #374151; }
      div.stButton > button:hover { border-color:#60a5fa; color:#fff; }
      .stSelectbox div[data-baseweb="select"] { background:#111827 !important; color:#e5e7eb !important; }
      .stNumberInput input, .stTextInput input, .stTextArea textarea { background:#111827 !important; color:#e5e7eb !important; border:1px solid #374151 !important; }

      /* Dataframes */
      .stDataFrame [data-testid="stTable"] { background:#0b0f14 !important; color:#e5e7eb !important; }
      .stDataFrame thead tr th { background:#111827 !important; color:#e5e7eb !important; }
      .stDataFrame tbody tr { background:#0b0f14 !important; }
      .stDataFrame tbody tr:hover { background:#111827 !important; }

      /* Plotly charts */
      .js-plotly-plot { background:#0b0f14 !important; }
    </style>
    """, unsafe_allow_html=True
)

def load_and_execute_altersstatistik_script():
    """Lädt und führt das Altersstatistik-Skript aus."""
    if not ALTERSSTATISTIK_SCRIPT.exists():
        st.error(f"Altersstatistik-Skript nicht gefunden: {ALTERSSTATISTIK_SCRIPT}")
        return False
    
    # Prüfe ob Excel-Datei existiert
    if not ALTERSSTATISTIK_EXCEL.exists():
        st.warning(f"""
        ⚠️ **Excel-Datei nicht gefunden!**
        
        Das Altersstatistik-Skript benötigt die Datei: `Statistik Altersdurchschnitt.xlsx`
        
        **Erwarteter Pfad:** `{ALTERSSTATISTIK_EXCEL}`
        
        **Lösung:**
        1. Stellen Sie sicher, dass die Excel-Datei im Verzeichnis `{ALTERSSTATISTIK_EXCEL.parent}` existiert
        2. Oder kopieren Sie die Datei dorthin
        3. Oder aktualisieren Sie den Pfad in der Konfiguration
        """)
        return False
    
    try:
        # Skript-Inhalt laden
        script_content = ALTERSSTATISTIK_SCRIPT.read_text(encoding='utf-8', errors='ignore')
        
        # Modifiziere das Skript, um den absoluten Pfad zur Excel-Datei zu verwenden
        script_content = script_content.replace(
            '"Statistik Altersdurchschnitt.xlsx"',
            f'r"{str(ALTERSSTATISTIK_EXCEL)}"'
        )
        
        # Modifiziere die get_team_color Funktion im Skript, um ungültige Farben zu verhindern
        script_content = script_content.replace(
            'def get_team_color(team_name):',
            '''def get_team_color(team_name):
    """Gibt eine sichere Farbe für ein Team zurück, immer gültige Hex-Farbe"""
    if team_name is None:
        return '#1f77b4'  # Standard-Blau
    
    team_str = str(team_name).strip()
    if not team_str or team_str.lower() in ['nan', 'none', '']:
        return '#1f77b4'  # Standard-Blau
    
    # Suche nach passender Farbe
    for team_key, color in TEAM_COLORS.items():
        if team_key.lower() in team_str.lower():
            return color
    
    # Fallback: Generiere eine Farbe basierend auf dem Team-Namen
    import hashlib
    hash_object = hashlib.md5(team_str.encode())
    hash_hex = hash_object.hexdigest()
    return f'#{hash_hex[:6]}'  # Erste 6 Zeichen als Farbe'''
        )
        
        # Modifiziere das Dropdownmenü, um nan-Werte zu filtern und JWR als Standard zu setzen
        # Ersetze den kompletten st.selectbox Aufruf
        script_content = script_content.replace(
            'st.sidebar.selectbox(\n    "Wählen Sie ein Team aus:",\n    options=df_teams[\'Team\'].tolist(),\n    index=jwr_index\n)',
            'st.sidebar.selectbox(\n    "Wählen Sie ein Team aus:",\n    options=filter_valid_teams(df_teams[\'Team\'].tolist()),\n    index=filter_valid_teams(df_teams[\'Team\'].tolist()).index("JWR") if "JWR" in filter_valid_teams(df_teams[\'Team\'].tolist()) else 0\n)'
        )
        
        # Korrigiere das Team-Mapping für Young Violets
        script_content = script_content.replace(
            "'Young Violets': 'Young Violetts',",
            "'Young Violets': 'Young Violets',"
        )
        
        # TEAM_COLORS definieren
        TEAM_COLORS = {
            'JWR': '#1f77b4',
            'LASK': '#ff7f0e',
            'Sturm': '#2ca02c',
            'Rapid': '#d62728',
            'WAC': '#9467bd',
            'Liefering': '#8c564b',
            'Altach Juniors': '#e377c2',
            'Young Violets': '#7f7f7f',
            'Gleisdorf': '#bcbd22',
            'Gurten': '#17becf',
            'Kalsdorf': '#ff9896',
            'Lafnitz': '#98df8a',
            'Oedt': '#ffbb78',
            'St. Anna': '#f0027f',
            'Treibach': '#386cb0',
            'Velden': '#fdc086',
            'Voitsberg': '#beaed4',
            'Wallern': '#fccde5',
            'Weiz': '#d9d9d9',
            'Dietach': '#fb8072'
        }
        
        # Skript in einem exec() ausführen
        local_namespace = {
            'st': st,
            'pd': None,  # Wird bei Bedarf importiert
            'plt': None,
            'numpy': None,
            'np': None,
            'matplotlib': None,
            'os': os,
            'pathlib': None,
            'Path': Path,
            'TEAM_COLORS': TEAM_COLORS
        }
        
        # TEAM_COLORS auch global verfügbar machen
        globals()['TEAM_COLORS'] = TEAM_COLORS
        
        # Versuche häufig benötigte Module zu importieren
        try:
            import pandas as pd
            local_namespace['pd'] = pd
            # Wichtig: pandas auch als 'pd' verfügbar machen
            local_namespace['pd'] = pd
            globals()['pd'] = pd
        except ImportError:
            st.error("❌ Das 'pandas' Modul ist nicht installiert. Installieren Sie es mit: `pip install pandas`")
            return False
        
        try:
            import numpy as np
            local_namespace['np'] = np
            local_namespace['numpy'] = np
            globals()['np'] = np
        except ImportError:
            pass
        
        try:
            import matplotlib.pyplot as plt
            local_namespace['plt'] = plt
            globals()['plt'] = plt
        except ImportError:
            pass
        
        try:
            import plotly
            import plotly.express as px
            import plotly.graph_objects as go
            import plotly.offline as pyo
            local_namespace['plotly'] = plotly
            local_namespace['px'] = px
            local_namespace['go'] = go
            local_namespace['pyo'] = pyo
        except ImportError:
            st.warning("⚠️ Das 'plotly' Modul ist nicht installiert. Installieren Sie es mit: `pip install plotly`")
            try:
                import subprocess
                import sys
                st.info("🔄 Versuche plotly zu installieren...")
                subprocess.check_call([sys.executable, "-m", "pip", "install", "plotly"])
                st.success("✅ plotly erfolgreich installiert!")
                
                import plotly
                import plotly.express as px
                import plotly.graph_objects as go
                import plotly.offline as pyo
                local_namespace['plotly'] = plotly
                local_namespace['px'] = px
                local_namespace['go'] = go
                local_namespace['pyo'] = pyo
                # Auch global verfügbar machen
                globals()['plotly'] = plotly
                globals()['px'] = px
                globals()['go'] = go
                globals()['pyo'] = pyo
            except Exception as install_error:
                st.error(f"❌ Konnte plotly nicht installieren: {install_error}")
                st.info("Bitte installieren Sie plotly manuell mit: `pip install plotly`")
                return False
        
        try:
            import openpyxl
            local_namespace['openpyxl'] = openpyxl
        except ImportError:
            st.warning("⚠️ Das 'openpyxl' Modul ist nicht installiert. Es wird für Excel-Dateien benötigt.")
            try:
                import subprocess
                import sys
                st.info("🔄 Versuche openpyxl zu installieren...")
                subprocess.check_call([sys.executable, "-m", "pip", "install", "openpyxl"])
                st.success("✅ openpyxl erfolgreich installiert!")
                
                import openpyxl
                local_namespace['openpyxl'] = openpyxl
            except Exception as install_error:
                st.error(f"❌ Konnte openpyxl nicht installieren: {install_error}")
                st.info("Bitte installieren Sie openpyxl manuell mit: `pip install openpyxl`")
                return False
        
        try:
            import seaborn as sns
            local_namespace['sns'] = sns
        except ImportError:
            pass
        
        try:
            import scipy
            local_namespace['scipy'] = scipy
        except ImportError:
            pass
        
        # Hilfsfunktion zum Filtern von ungültigen Team-Namen
        def filter_valid_teams(teams):
            if teams is None:
                return []
            valid_teams = []
            for team in teams:
                if team is not None and str(team).lower() not in ['nan', 'none', ''] and str(team).strip():
                    valid_teams.append(team)
            return valid_teams
        
        local_namespace['filter_valid_teams'] = filter_valid_teams
        
        # Sichere get_team_color Funktion hinzufügen
        def safe_get_team_color(team_name):
            if team_name is None:
                return '#1f77b4'
            
            team_str = str(team_name).strip()
            if not team_str or team_str.lower() in ['nan', 'none', '']:
                return '#1f77b4'
            
            TEAM_COLORS = local_namespace['TEAM_COLORS']
            for team_key, color in TEAM_COLORS.items():
                if team_key.lower() in team_str.lower():
                    return color
            
            import hashlib
            hash_object = hashlib.md5(team_str.encode())
            hash_hex = hash_object.hexdigest()
            return f'#{hash_hex[:6]}'
        
        local_namespace['get_team_color'] = safe_get_team_color
        local_namespace['safe_get_team_color'] = safe_get_team_color
        
        # Skript ausführen
        exec(script_content, globals(), local_namespace)
        return True
        
    except Exception as e:
        st.error(f"Fehler beim Ausführen des Altersstatistik-Skripts: {e}")
        st.exception(e)
        return False

# ========================= MAIN =========================
def main():
    # Header
    st.title("📊 Altersstatistik - JWR Dashboard")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.markdown("**Analyse der Durchschnittsalter in der Regionalliga Mitte**")
    
    with col2:
        if st.button("🔄 Aktualisieren", help="Daten neu laden"):
            st.rerun()
    
    st.divider()
    
    # Altersstatistik-Skript ausführen
    success = load_and_execute_altersstatistik_script()
    
    if not success:
        st.info("""
        **Hinweis:** Falls das Altersstatistik-Skript nicht geladen werden kann, 
        überprüfen Sie bitte:
        
        1. **Skript-Pfad:** `C:\\Users\\demmelb-ma\\OneDrive - COC AG\\JWR\\Matches\\2526\\Durchschnittsalter.py`
        2. **Excel-Datei:** `C:\\Users\\demmelb-ma\\OneDrive - COC AG\\JWR\\Matches\\2526\\Statistik Altersdurchschnitt.xlsx`
        3. **Abhängigkeiten:** `pip install plotly pandas openpyxl`
        """)

if __name__ == "__main__":
    main()
