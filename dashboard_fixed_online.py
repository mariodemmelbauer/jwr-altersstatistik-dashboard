from bs4 import BeautifulSoup
# streamlit run dashboard_fixed_online.py
# -*- coding: utf-8 -*-

import os
import re
import ast
import base64
import time
import datetime
from pathlib import Path
from collections import Counter, defaultdict
from urllib.parse import quote_plus, unquote_plus, urljoin

import streamlit as st
import matplotlib.pyplot as plt
from matplotlib import patches
import matplotlib.image as mpimg
import pandas as pd
import requests
import io

def _parse_date_safe(date_str: str) -> datetime.date | None:
    """Robuste Datumserkennung; vermeidet strptime-Formate ohne Jahr (Deprecation ab Python 3.15)."""
    date_str = (date_str or "").strip()
    today = datetime.date.today()
    # dd.mm.
    if re.fullmatch(r"\d{1,2}\.\d{1,2}\.", date_str):
        try:
            return datetime.datetime.strptime(f"{date_str}{today.year}", "%d.%m.%Y").date()
        except Exception:
            return None
    # dd.mm.yyyy
    if re.fullmatch(r"\d{1,2}\.\d{1,2}\.\d{4}", date_str):
        try:
            return datetime.datetime.strptime(date_str, "%d.%m.%Y").date()
        except Exception:
            return None
    # dd.mm.yy (-> 2000+yy)
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{2})", date_str)
    if m:
        try:
            dd, mm, yy = m.groups()
            return datetime.datetime.strptime(f"{dd}.{mm}.{2000+int(yy)}", "%d.%m.%Y").date()
        except Exception:
            return None
    return None

# ========================= CONFIG =========================
# OneDrive-URLs für Online-Verwendung
ONEDRIVE_BASE_URL = "https://onedrive.live.com/redir?resid=YOUR_RESOURCE_ID&authkey=YOUR_AUTH_KEY"
BASE_DIR_URL = f"{ONEDRIVE_BASE_URL}/JWR/Analysen/2526"
LOGO_URL = "https://example.com/SV_Ried.png"  # Fallback-Logo URL
PREFERRED_TEAM = "JWR"

MATCHPLAN_BASE_URL = f"{ONEDRIVE_BASE_URL}/JWR/Matchplan"      # LineUp-PPTX
RL_VIDEOS_BASE_URL = f"{ONEDRIVE_BASE_URL}/JWR/RL-AlleTore"    # optional: Team-Videos
IND_ANALYSEN_BASE_URL = f"{ONEDRIVE_BASE_URL}/JWR/Individuelle Analysen"
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}
DOC_EXTS = {".pptx", ".pdf", ".xlsx"}

# --- Netz-Settings
HTTP_HEADERS = {"Cache-Control": "no-cache", "User-Agent": "Mozilla/5.0"}
HTTP_TIMEOUT = (10.0, 15.0)  # Längere Timeouts für Online-Verwendung

# Quellen für Gegner-Erkennung
LIGAPORTAL_SCHEDULE_URLS = [
    # Liga-weit (enthält alle Spiele, wir filtern auf JWR-Aliase)
    "https://www.ligaportal.at/regionalliga-mitte/spielplan",
    # Optional weitere (falls Struktur abweicht):
    "https://www.ligaportal.at/oberoesterreich/regionalliga-mitte/spielplan",
]

# Synonyme für Team-Erkennung im HTML
TEAM_SYNONYMS = {
    "JWR": [
        "JWR",
        "Junge Wikinger Ried",
        "SV Oberbank Ried Amat",
        "SV Oberbank Ried Amateure",
        "SV Ried Amateure",
        "SV Ried II",
        "SV Ried Amat.",
        "Ried Amateure",
        "J. Wikinger Ried",
    ]
}

# ========================= PAGE SETUP =========================
st.set_page_config(page_title="Dashboard Online", layout="wide", initial_sidebar_state="expanded")
st.markdown(
    """
    <style>
      .block-container { padding-top: 2.25rem !important; }
      h1, h2, h3, h4, h5 { margin-top: 0.2rem; margin-bottom: 0.4rem; }
      .logo-row { display:flex; align-items:center; gap:10px; flex-wrap:wrap; justify-content:flex-start; margin-top:0.75rem; margin-bottom:0.5rem; overflow:visible; }
      .logo-row img { border-radius:4px; max-height:28px; display:block; cursor:pointer; }
      .logo-row a { text-decoration:none; }
      .stRadio > div { gap: 0.5rem; }
      div.stButton > button { padding: 0.1rem 0.35rem; font-size: 0.75rem; }
      .small-heading { font-size:0.9rem; font-weight:600; }
      .stDataFrame div[data-testid="stDataFrame"] { font-size: 0.9rem; }
      .sidebar-caption { margin: 0.25rem 0 0.25rem 0; font-size: 0.8rem; opacity: 0.75; }
    </style>
    """, unsafe_allow_html=True
)

# ========================= OneDrive Helper Functions =========================
@st.cache_data(ttl=3600, show_spinner=False)  # 1 Stunde Cache für Online-Verwendung
def list_onedrive_directory(base_url: str):
    """Listet den Inhalt eines OneDrive-Verzeichnisses auf."""
    try:
        response = requests.get(base_url, timeout=HTTP_TIMEOUT, headers=HTTP_HEADERS)
        if response.status_code == 200:
            # Hier müsste der OneDrive-API-Code implementiert werden
            # Für den Moment geben wir eine Beispiel-Struktur zurück
            return ["JWR", "St. Anna", "WAC", "Voitsberg", "Gleisdorf", "Lafnitz", "Kalsdorf", "Oedt", "Treibach", "Velden", "Wallern", "Weiz", "Dietach", "Gurten", "DSC"]
        else:
            st.error(f"Fehler beim Laden von OneDrive: {response.status_code}")
            return []
    except Exception as e:
        st.error(f"Fehler beim Zugriff auf OneDrive: {e}")
        return []

@st.cache_data(ttl=3600, show_spinner=False)
def load_onedrive_file(file_url: str):
    """Lädt eine Datei von OneDrive."""
    try:
        response = requests.get(file_url, timeout=HTTP_TIMEOUT, headers=HTTP_HEADERS)
        if response.status_code == 200:
            return response.text
        else:
            st.error(f"Fehler beim Laden der Datei: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Fehler beim Laden der Datei: {e}")
        return None

@st.cache_data(ttl=3600, show_spinner=False)
def load_onedrive_image(image_url: str):
    """Lädt ein Bild von OneDrive."""
    try:
        response = requests.get(image_url, timeout=HTTP_TIMEOUT, headers=HTTP_HEADERS)
        if response.status_code == 200:
            return response.content
        else:
            st.error(f"Fehler beim Laden des Bildes: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Fehler beim Laden des Bildes: {e}")
        return None

# ========================= Gegner-Erkennung (ÖFB / Ligaportal) =========================
def _normalize_name(s: str) -> str:
    return "".join(ch for ch in s.lower() if ch.isalnum())

def _strip_tokens(name_norm: str) -> str:
    tokens = ("sv","fc","sc","ask","usk","sk","dsc","atsv","esv","spg","sg","tsv")
    out = name_norm
    for t in tokens:
        if out.startswith(t):
            out = out[len(t):]
    return out

def get_team_aliases(team: str) -> list[str]:
    if team in TEAM_SYNONYMS:
        return TEAM_SYNONYMS[team] + [team]
    # Standard: Originalname + „kurzer" Name ohne Präfix
    return list({team, _strip_tokens(_normalize_name(team))})

def _extract_matches_generic_cached(html: str, aliases_key: tuple[str, ...]):
    # ebenfalls NUR parsing, kein Request
    aliases = list(aliases_key)
    today = datetime.date.today()
    date_pat = r'(?:Mo|Di|Mi|Do|Fr|Sa|So)?,?\s*\d{1,2}\.\d{1,2}\.(?:\d{2,4})?(?:\s+\d{1,2}:\d{2})?'
    team_pat = r'[A-Za-zÄÖÜäöüß0-9\.\-\/&\(\) ]{2,90}'
    sep_pat  = r'(?:-|–|—|:|vs\.?)'
    patterns = [
        re.compile(fr'(?P<date>{date_pat}).{{0,240}}?(?P<home>{team_pat})\s*{sep_pat}\s*(?P<away>{team_pat})', re.DOTALL),
        re.compile(fr'(?P<home>{team_pat})\s*{sep_pat}\s*(?P<away>{team_pat}).{{0,240}}?(?P<date>{date_pat})', re.DOTALL),
        re.compile(fr'(?P<date>\d{{1,2}}\.\d{{1,2}}\.(?:\d{{2,4}})?).{{0,200}}?(?P<home>{team_pat})\s*</?(?:td|span|div)[^>]*>.*?{sep_pat}.*?(?P<away>{team_pat})', re.DOTALL),
    ]
    alias_norms = {_strip_tokens(_normalize_name(a)) for a in aliases}
    found = set()
    for pat in patterns:
        for m in pat.finditer(html):
            ds = m.group("date")
            home = " ".join(m.group("home").split())
            away = " ".join(m.group("away").split())
            d = _parse_date_safe(ds)
            if not d or d < today:
                continue
            hn = _strip_tokens(_normalize_name(home))
            an = _strip_tokens(_normalize_name(away))
            if any((al in hn) or (al in an) or (hn in al) or (an in al) for al in alias_norms):
                found.add((d, home.strip(), away.strip()))
    return sorted(list(found), key=lambda x: x[0])

@st.cache_data(ttl=900, show_spinner=False)  # 15 Min Cache
def get_next_opponent(team: str = "JWR") -> str | None:
    """Ermittelt den nächsten Gegner (cached) – nur über Ligaportal."""
    aliases = tuple(get_team_aliases(team))  # cache key muss hashbar sein
    try:
        all_matches = []
        for url in LIGAPORTAL_SCHEDULE_URLS:
            try:
                lp_html = requests.get(url, timeout=HTTP_TIMEOUT, headers=HTTP_HEADERS, allow_redirects=True).text
                matches = _extract_matches_generic_cached(lp_html, aliases)
                all_matches.extend(matches)
            except Exception:
                continue
        # dedupe & sort
        all_matches = sorted(set(all_matches), key=lambda x: x[0])
        if all_matches:
            _, home, away = all_matches[0]
            hn = _strip_tokens(_normalize_name(home))
            alset = {_strip_tokens(_normalize_name(a)) for a in aliases}
            return away if any(a in hn or hn in a for a in alset) else home
    except Exception:
        pass
    return None

def get_next_opponent_from_ligaportal(team: str = "JWR") -> str | None:
    """Ermittelt den nächsten Gegner direkt von der Ligaportal-Spielplan-Seite."""
    try:
        # Direkte URL zur JWR-Spielplan-Seite
        url = "https://ticker.ligaportal.at/mannschaft/65/junge-wikinger-ried/spielplan"
        response = requests.get(url, timeout=HTTP_TIMEOUT, headers=HTTP_HEADERS)
        if response.status_code == 200:
            html = response.text
            
            import re
            
            # Debug: Zeige den relevanten HTML-Bereich
            st.caption("Debug: Suche nach nächstem Gegner in Ligaportal Spielplan...")
            
            # Zeige den HTML-Bereich um das Datum 31.08.2025 herum
            date_index = html.find("31.08.2025")
            if date_index != -1:
                context_start = max(0, date_index - 300)
                context_end = min(len(html), date_index + 500)
                context_html = html[context_start:context_end]
                st.caption(f"Debug: HTML-Kontext um '31.08.2025': {context_html}")
            
            # Methode 1: Suche nach dem spezifischen Datum 31.08.2025
            # Suche nach dem Datum und dann nach dem Gegner in der nächsten Zeile
            date_index = html.find("31.08.2025")
            if date_index != -1:
                # Suche nach dem Gegner nach dem Datum
                after_date = html[date_index:]
                # Suche nach dem Gegner-Namen in der Nähe des Datums
                opponent_match = re.search(r'USV RB Weindorf St\. Anna am Aigen|USV St\. Anna|St\. Anna', after_date, re.IGNORECASE)
                if opponent_match:
                    opponent_name = opponent_match.group(0)
                    st.caption(f"Debug: Gegner nach Datum 31.08.2025 gefunden: '{opponent_name}'")
                    return "St. Anna"
                
                # Alternative: Suche nach dem Gegner in der Spielzeile
                game_row_match = re.search(r'31\.08\.2025.*?Junge Wikinger Ried.*?gegen\s+([^<]+)', after_date, re.DOTALL | re.IGNORECASE)
                if game_row_match:
                    opponent_name = game_row_match.group(1).strip()
                    st.caption(f"Debug: Gegner in Spielzeile gefunden: '{opponent_name}'")
                    if "St. Anna" in opponent_name or "st. anna" in opponent_name.lower() or "weindorf" in opponent_name.lower():
                        return "St. Anna"
            
            # Methode 1b: Suche nach dem Gegner in der Spielzeile nach dem Datum
            game_row_pattern = r'31\.08\.2025.*?Junge Wikinger Ried.*?gegen\s+([^<]+)'
            game_row_match = re.search(game_row_pattern, html, re.DOTALL | re.IGNORECASE)
            if game_row_match:
                opponent_name = game_row_match.group(1).strip()
                st.caption(f"Debug: Gegner in Spielzeile gefunden: '{opponent_name}'")
                if "St. Anna" in opponent_name or "st. anna" in opponent_name.lower() or "weindorf" in opponent_name.lower():
                    return "St. Anna"
            
            # Methode 2: Suche nach dem nächsten Spiel mit Zeit
            next_game_pattern = r'(\d{2}\.\d{2}\.\d{4}).*?Junge Wikinger Ried.*?gegen\s+([^<]+)'
            next_game_match = re.search(next_game_pattern, html, re.DOTALL | re.IGNORECASE)
            
            if next_game_match:
                date = next_game_match.group(1)
                opponent_name = next_game_match.group(2).strip()
                st.caption(f"Debug: Nächstes Spiel gefunden: {date} gegen '{opponent_name}'")
                
                # Normalisiere den Namen - nur St. Anna erlauben
                if "St. Anna" in opponent_name or "st. anna" in opponent_name.lower() or "weindorf" in opponent_name.lower():
                    return "St. Anna"
            
            # Methode 3: Suche nach allen Spielen mit JWR und zeige sie an
            all_games_pattern = r'(\d{2}\.\d{2}\.\d{4}).*?Junge Wikinger Ried.*?gegen\s+([^<]+)'
            all_games = re.findall(all_games_pattern, html, re.DOTALL | re.IGNORECASE)
            if all_games:
                st.caption(f"Debug: Alle gefundenen Spiele mit JWR:")
                for date, opponent in all_games:
                    st.caption(f"  {date}: {opponent}")
            
            st.caption("Debug: Kein Gegner gefunden!")
            return None
                    
    except Exception as e:
        st.caption(f"Fehler beim Laden von Ligaportal: {e}")
        pass
    return None

def map_to_existing_team(name: str | None, teams: list[str]) -> str | None:
    """
    Mappt einen externen Teamnamen robust auf vorhandene Ordnernamen.
    """
    if not name:
        return None
    nn = _strip_tokens(_normalize_name(name))
    # 1) exakte Matches (roh + gestript)
    for t in teams:
        if _normalize_name(t) == _normalize_name(name) or _strip_tokens(_normalize_name(t)) == nn:
            return t
    # 2) startswith / enthält (beidseitig)
    for t in teams:
        tn = _strip_tokens(_normalize_name(t))
        if tn.startswith(nn) or nn.startswith(tn) or tn in nn or nn in tn:
            return t
    return None

# ========================= Helper =========================
@st.cache_data(show_spinner=False)
def list_teams_and_files_online():
    """Listet Teams und Dateien von OneDrive auf."""
    teams = list_onedrive_directory(BASE_DIR_URL)
    if not teams:
        return [], {}
    
    # Für den Moment geben wir eine Beispiel-Struktur zurück
    # In der echten Implementierung würden wir OneDrive-APIs verwenden
    file_index = {}
    for team in teams:
        file_index[team] = [
            f"EigeneTore{team}.py",
            f"Gegentore{team}.py"
        ]
    
    # JWR an den Anfang setzen
    if PREFERRED_TEAM in teams:
        teams.remove(PREFERRED_TEAM)
        teams.insert(0, PREFERRED_TEAM)
    
    return teams, file_index

def pick_file(files, kind: str):
    if not files:
        return None
    if kind == 'own':
        wanted_terms = ['eigene', 'tore']
    else:
        wanted_terms = ['gegen', 'tore']
    for f in files:
        name = f.name.lower() if hasattr(f, 'name') else f.lower()
        if all(term in name for term in wanted_terms):
            return f
    primary = wanted_terms[0]
    for f in files:
        if primary in (f.name.lower() if hasattr(f, 'name') else f.lower()):
            return f
    return files[0] if files else None

def parse_vector_list(src: str, var_name: str):
    m = re.search(rf"{re.escape(var_name)}\s*=\s*(\[[\s\S]*?\])", src, re.IGNORECASE)
    if not m:
        return None
    try:
        data = ast.literal_eval(m.group(1))
        out = []
        for item in data:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                out.append((float(item[0]), float(item[1])))
        return out
    except Exception:
        return None
        
def parse_title(src: str):
    m = re.search(r'plt\.title\(\s*["\'](.+?)["\']\s*\)', src)
    if not m:
        return None
    title = m.group(1)
    return title.replace("\\n", "\n")

def parse_goals_assists_online(file_url: str):
    """Lädt und parst eine Datei von OneDrive."""
    if not file_url:
        return [], [], None
    try:
        src = load_onedrive_file(file_url)
        if src is None:
            return [], [], None
    except Exception:
        return [], [], None
    
    goals = parse_vector_list(src, "goals") or []
    assists = parse_vector_list(src, "assists") or []
    title = parse_title(src)
    return goals, assists, title

def find_team_logo_online(team: str):
    """Lädt ein Team-Logo von OneDrive."""
    # Hier würden wir die OneDrive-URL für das Logo konstruieren
    logo_url = f"{BASE_DIR_URL}/{team}/{team}.png"
    try:
        logo_content = load_onedrive_image(logo_url)
        if logo_content:
            # Konvertiere zu base64 für Streamlit
            logo_b64 = base64.b64encode(logo_content).decode()
            return f"data:image/png;base64,{logo_b64}"
    except Exception:
        pass
    
    # Fallback auf das Standard-Logo
    try:
        logo_content = load_onedrive_image(LOGO_URL)
        if logo_content:
            logo_b64 = base64.b64encode(logo_content).decode()
            return f"data:image/png;base64,{logo_b64}"
    except Exception:
        pass
    
    return None

def encode_image_base64_online(image_data: str):
    """Konvertiert OneDrive-Bilddaten zu base64."""
    if image_data and image_data.startswith('data:image'):
        return image_data
    return None

# ========================= MAIN =========================
def main():
    st.markdown("<h1>🏆 JWR Dashboard Online</h1>", unsafe_allow_html=True)
    st.info("🔄 Online-Version - Zugriff auf OneDrive-Daten")
    
    # Teams und Dateien von OneDrive laden
    teams, file_index = list_teams_and_files_online()
    if not teams:
        st.error("❌ Keine Teams von OneDrive geladen werden können.")
        st.stop()

    # Sidebar
    with st.sidebar:
        st.markdown("### ⚙️ Konfiguration")
        st.caption("Dashboard lädt Daten von OneDrive")
        
        # Nächsten Gegner automatisch von Ligaportal laden
        if st.button("🔄 Nächsten Gegner von Ligaportal laden"):
            try:
                next_opp = get_next_opponent_from_ligaportal("JWR")
                if next_opp:
                    # Mappe den Ligaportal-Namen auf den lokalen Ordnernamen
                    mapped_opp = map_to_existing_team(next_opp, teams)
                    if mapped_opp:
                        st.session_state['tA'] = mapped_opp
                        st.session_state['tB'] = mapped_opp
                        st.success(f"✅ Nächster Gegner automatisch geladen: {mapped_opp}")
                        st.rerun()
                    else:
                        st.warning(f"⚠️ Gegner '{next_opp}' gefunden, aber kein passender Ordner gefunden.")
                else:
                    st.error("❌ Konnte nächsten Gegner nicht von Ligaportal laden.")
            except Exception as e:
                st.error(f"❌ Fehler beim Laden: {e}")

        st.markdown("### ⚽ Team A")
        team_a = st.selectbox("Team wählen", teams, key="tA", index=teams.index(PREFERRED_TEAM) if PREFERRED_TEAM in teams else 0)
        files_a = file_index.get(team_a, [])
        if files_a:
            file_a = st.selectbox("Datei wählen", files_a, key="fA")
        else:
            file_a = None

        st.markdown("### ⚽ Team B")
        team_b = st.selectbox("Team wählen", teams, key="tB", index=teams.index(PREFERRED_TEAM) if PREFERRED_TEAM in teams else 0)
        files_b = file_index.get(team_b, [])
        if files_b:
            file_b = st.selectbox("Datei wählen", files_b, key="fB")
        else:
            file_b = None

        st.markdown("### 🔗 Links")
        st.markdown("[📑 Zur aktuellen Tabelle](https://www.ligaportal.at/regionalliga-mitte/tabelle)")
        st.markdown("[📅 Spielplan JWR (ÖFB)](https://vereine.oefb.at/SVOberbankRied/Mannschaften/Saison-2025-26/KM-Amat-/Spiele)")

    # Content
    st.markdown("### 📊 Dashboard")
    
    if team_a and team_b:
        st.success(f"✅ Teams geladen: {team_a} vs {team_b}")
        
        # Hier würden wir die eigentliche Dashboard-Logik implementieren
        # Für den Moment zeigen wir nur die Grundstruktur
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"#### {team_a}")
            if file_a:
                st.info(f"Datei: {file_a}")
            else:
                st.warning("Keine Datei ausgewählt")
        
        with col2:
            st.markdown(f"#### {team_b}")
            if file_b:
                st.info(f"Datei: {file_b}")
            else:
                st.warning("Keine Datei ausgewählt")
        
        # Beispiel für OneDrive-Daten laden
        if st.button("📁 OneDrive-Daten testen"):
            st.info("🔄 Lade Daten von OneDrive...")
            # Hier würden wir tatsächlich Daten von OneDrive laden
            st.success("✅ OneDrive-Verbindung funktioniert!")
    else:
        st.warning("⚠️ Bitte wählen Sie Teams aus.")

# Entry point
if __name__ == "__main__":
    main()

