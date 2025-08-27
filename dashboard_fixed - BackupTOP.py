from bs4 import BeautifulSoup
# streamlit run dashboard_fixed.py
# -*- coding: utf-8 -*-

import os
import re
import ast
import base64
import time
import datetime
from pathlib import Path
from collections import Counter, defaultdict
from urllib.parse import quote_plus, unquote_plus

import streamlit as st
import matplotlib.pyplot as plt
from matplotlib import patches
import matplotlib.image as mpimg
import pandas as pd
import requests

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
BASE_DIR = Path(r"C:\Users\demmelb-ma\OneDrive - COC AG\JWR\Analysen\2526")
LOGO_PATH = Path(r"C:\Temp\SV_Ried.png")   # Fallback-Logo
PREFERRED_TEAM = "JWR"

MATCHPLAN_BASE = Path(r"C:\Users\demmelb-ma\OneDrive\JWR\Matchplan")      # LineUp-PPTX
RL_VIDEOS_BASE = Path(r"C:\Users\demmelb-ma\OneDrive\JWR\RL-AlleTore")    # optional: Team-Videos
IND_ANALYSEN_BASE = Path(r"C:\Users\demmelb-ma\OneDrive\JWR\Individuelle Analysen")
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}
DOC_EXTS = {".pptx", ".pdf", ".xlsx"}
# --- Netz-Settings
HTTP_HEADERS = {"Cache-Control": "no-cache", "User-Agent": "Mozilla/5.0"}
HTTP_TIMEOUT = (3.0, 4.0)  # (connect, read) kurz halten


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
st.set_page_config(page_title="Dashboard", layout="wide", initial_sidebar_state="expanded")
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
    # Standard: Originalname + „kurzer“ Name ohne Präfix
    return list({team, _strip_tokens(_normalize_name(team))})

def _parse_date_safe(date_str: str) -> datetime.date | None:
    date_str = date_str.strip()
    fmts = ["%d.%m.%Y", "%d.%m.%y", "%d.%m."]
    today = datetime.date.today()
    for fmt in fmts:
        try:
            dt = datetime.datetime.strptime(date_str, fmt)
            if fmt == "%d.%m.":
                dt = dt.replace(year=today.year)
            # 2-stelliges Jahr → 2000er
            if dt.year < 100:
                dt = dt.replace(year=2000 + dt.year)
            return dt.date()
        except Exception:
            continue
    return None

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
def list_video_team_dirs(base: Path):
    mapping = {}
    if base.exists():
        for p in sorted(base.iterdir()):
            if p.is_dir():
                mapping[_normalize_name(p.name)] = p
    return mapping
def resolve_video_dir_for_team(team: str):
    mapping = list_video_team_dirs(RL_VIDEOS_BASE)
    norm_team = _normalize_name(team)
    if norm_team in mapping:
        return mapping[norm_team]
    tokens_to_strip = ("sv","fc","sc","ask","usk","sk","dsc","atsv")
    stripped = norm_team
    for t in tokens_to_strip:
        if stripped.startswith(t):
            stripped = stripped[len(t):]
    for key, path in mapping.items():
        ks = key
        for t in tokens_to_strip:
            if ks.startswith(t):
                ks = ks[len(t):]
        if ks == stripped or key.startswith(stripped) or stripped.startswith(key) or ks.startswith(stripped) or stripped.startswith(ks):
            return path
    return None

@st.cache_data(show_spinner=False)
def list_teams_and_files(base_dir: Path, preferred: str = "JWR"):
    teams = []
    file_index = {}
    for p in sorted(base_dir.iterdir() if base_dir.exists() else []):
        if p.is_dir():
            teams.append(p.name)
            files = sorted(list(p.glob("*.py")))
            files = [f for f in files if re.search(r"(eigene|gegen).*tore", f.name, re.IGNORECASE)]
            file_index[p.name] = files
    if preferred in teams:
        teams.remove(preferred)
        teams.insert(0, preferred)
    return teams, file_index

def pick_file(files, kind: str):
    if not files:
        return None
    if kind == 'own':
        wanted_terms = ['eigene', 'tore']
    else:
        wanted_terms = ['gegen', 'tore']
    for f in files:
        name = f.name.lower()
        if all(term in name for term in wanted_terms):
            return f
    primary = wanted_terms[0]
    for f in files:
        if primary in f.name.lower():
            return f
    return files[0]

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

def parse_goals_assists(file_path: Path):
    if not file_path:
        return [], [], None
    try:
        src = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        src = file_path.read_text(encoding="cp1252", errors="ignore")
    goals = parse_vector_list(src, "goals") or []
    assists = parse_vector_list(src, "assists") or []
    title = parse_title(src)
    return goals, assists, title

def find_team_logo(team: str):
    team_dir = BASE_DIR / team
    exts = ("*.png", "*.jpg", "*.jpeg", "*.bmp")
    imgs = []
    for ext in exts:
        imgs.extend(sorted(team_dir.glob(ext)))
    if imgs:
        return imgs[0]
    if LOGO_PATH and LOGO_PATH.exists():
        return LOGO_PATH
    return None

def encode_image_base64(path: Path):
    mime = "image/png"
    name = path.name.lower()
    if name.endswith(".jpg") or name.endswith(".jpeg"):
        mime = "image/jpeg"
    elif name.endswith(".bmp"):
        mime = "image/bmp"
    elif name.endswith(".png"):
        mime = "image/png"
    try:
        data = path.read_bytes()
        b64 = base64.b64encode(data).decode()
        return f"data:{mime};base64,{b64}"
    except Exception:
        return None

def int_to_roman(n: int) -> str:
    vals = [(1000,'M'),(900,'CM'),(500,'D'),(400,'CD'),(100,'C'),(90,'XC'),(50,'L'),(40,'XL'),(10,'X'),(9,'IX'),(5,'V'),(4,'IV'),(1,'I')]
    res = []
    for v, sym in vals:
        while n >= v:
            res.append(sym); n -= v
    return ''.join(res) if res else 'I'

def parse_filename_parts(file: Path):
    stem = file.stem
    parts = stem.split("_")
    team = parts[1] if len(parts) >= 2 else stem
    opponent = parts[2] if len(parts) >= 3 else ""
    low = stem.lower()
    if "elfmeter" in low:
        cat = "Elfmeter"
    elif "1touch" in low:
        cat = "1Touch"
    elif "2touch" in low:
        cat = "2Touch"
    else:
        cat = "Sonstiges Tor"
    scorer = parts[4] if len(parts) >= 5 else None
    return team, opponent, cat, scorer

def extract_scorer_table(files):
    counter = Counter()
    file_map = defaultdict(list)
    rows = []
    for f in files:
        team, opponent, cat, scorer = parse_filename_parts(f)
        if scorer:
            key = (scorer, cat, team, opponent)
            counter[key] += 1
            file_map[key].append(f)
    for key, count in counter.items():
        scorer, cat, team, opponent = key
        rows.append({"Spieler": scorer, "Tore": count, "Kategorie": cat, "Team": team, "Gegner": opponent, "Videos": file_map[key]})
    return rows

def build_labels_with_roman(files):
    counters = defaultdict(int)
    labels = []
    for f in files:
        team, opponent, cat, scorer = parse_filename_parts(f)
        key = (team, cat, opponent)
        counters[key] += 1
        roman = int_to_roman(counters[key])
        base = f"{team} {cat} vs. {opponent} {roman}"
        if scorer:
            base += f" – {scorer}"
        labels.append(base)
    return labels

@st.cache_data(show_spinner=False)
def load_team_videos(team: str):
    resolved_dir = resolve_video_dir_for_team(team)
    vids = {'Elfmeter': [], '1 Touch': [], '2 Touch': [], 'Sonstiges': []}
    if not resolved_dir or not resolved_dir.exists():
        return vids
    files = [f for f in sorted(resolved_dir.iterdir()) if f.is_file() and f.suffix.lower() in VIDEO_EXTS]
    for f in files:
        low = f.name.lower()
        if "elfmeter" in low:
            vids['Elfmeter'].append(f)
        elif "1touch" in low:
            vids['1 Touch'].append(f)
        elif "2touch" in low:
            vids['2 Touch'].append(f)
        else:
            vids['Sonstiges'].append(f)
    return vids

@st.cache_data(show_spinner=False)
def load_opponent_goals_against(opponent: str):
    """Lädt alle Videos, wo der Gegner als TeamB (zweites Team) im Dateinamen vorkommt."""
    vids = {'Elfmeter': [], '1 Touch': [], '2 Touch': [], 'Sonstiges': []}
    
    # Im RL_VIDEOS_BASE Verzeichnis nach Videos suchen
    if RL_VIDEOS_BASE and RL_VIDEOS_BASE.exists():
        for team_dir in RL_VIDEOS_BASE.iterdir():
            if not team_dir.is_dir():
                continue
                
            # Videos im Team-Ordner durchsuchen
            for f in team_dir.iterdir():
                if not f.is_file() or f.suffix.lower() not in VIDEO_EXTS:
                    continue
                    
                # Dateiname parsen: 04_Treibach_StAnna_1Touch_PirkerM.mp4
                parts = f.stem.split('_')
                if len(parts) >= 3:
                    team_a = parts[1] if len(parts) > 1 else ""
                    team_b = parts[2] if len(parts) > 2 else ""
                    
                    # Prüfen ob der Gegner als TeamB (zweites Team) im Dateinamen steht
                    # Normalisiere Namen (entferne Leerzeichen, Punkte, etc.)
                    opponent_norm = opponent.lower().replace(" ", "").replace(".", "")
                    team_b_norm = team_b.lower().replace(" ", "").replace(".", "")
                    
                    if team_b_norm == opponent_norm:
                        low = f.name.lower()
                        if "elfmeter" in low:
                            vids['Elfmeter'].append(f)
                        elif "1touch" in low:
                            vids['1 Touch'].append(f)
                        elif "2touch" in low:
                            vids['2 Touch'].append(f)
                        else:
                            vids['Sonstiges'].append(f)
    
    return vids

# ========================= Matchplan-Auflösung (robust) =========================
@st.cache_data(show_spinner=False)
def list_matchplan_team_dirs(base: Path):
    mapping = {}
    if base.exists():
        for p in sorted(base.iterdir()):
            if p.is_dir():
                mapping[_normalize_name(p.name)] = p
    return mapping

def resolve_matchplan_ppt(team: str):
    if not MATCHPLAN_BASE.exists():
        return None
    norm_team = _normalize_name(team)
    stripped = _strip_tokens(norm_team)
    dir_map = list_matchplan_team_dirs(MATCHPLAN_BASE)
    candidate_dir = None
    if norm_team in dir_map:
        candidate_dir = dir_map[norm_team]
    else:
        for key, path in dir_map.items():
            ks = _strip_tokens(key)
            if ks == stripped or key.startswith(stripped) or stripped.startswith(key) or ks.startswith(stripped) or stripped.startswith(ks):
                candidate_dir = path
                break
    if candidate_dir:
        exact = candidate_dir / f"LineUp_{team}.pptx"
        if exact.exists():
            return exact
        hits = sorted(candidate_dir.glob("LineUp_*.pptx"))
        if hits:
            return hits[0]
    for p in sorted(MATCHPLAN_BASE.rglob("LineUp_*.pptx")):
        name_norm = _normalize_name(p.stem.replace("LineUp_", ""))
        if stripped in _strip_tokens(name_norm):
            return p
    return None

# ========================= Zeichnen / Plot =========================
def draw_pitch(ax, team: str):
    ax.set_facecolor('green')
    ax.set_xlim(0, 68)
    ax.set_ylim(0, 100)

    # Hintergrundlogo
    logo_path = find_team_logo(team)
    if logo_path:
        try:
            logo = mpimg.imread(str(logo_path))
            ax.imshow(logo, extent=[0, 68, 0, 100], alpha=0.05, zorder=1)
        except Exception:
            pass

    # Mittellinie & Mittelkreis
    ax.plot([0, 68], [50, 50], 'white', linestyle="-", linewidth=0.7)
    ax.add_patch(patches.Circle((34, 50), 9.15, edgecolor='white', facecolor='none', linewidth=0.7))

    # Beide Spielfeldseiten
    for side in ['bottom', 'top']:
        if side == 'bottom':
            y_base = 0; direction = 1
        else:
            y_base = 100; direction = -1

        # Strafraum
        ax.add_patch(patches.Rectangle((13.84, y_base if side == 'bottom' else y_base - 16.5),
                                       40.32, 16.5, edgecolor='white', facecolor='none', linewidth=0.7))

        # 5m-Raum (ohne Füllung)
        ax.add_patch(patches.Rectangle((24.84, y_base if side == 'bottom' else y_base - 5.5),
                                       18.32, 5.5, edgecolor='white', facecolor='none', linewidth=0.7))

        # Torfläche (symbolisch)
        ax.add_patch(patches.Rectangle((30.34, y_base if side == 'bottom' else y_base - 2.44),
                                       7.32, 2.44, edgecolor='white', facecolor='none', linewidth=0.7))

        # Elfmeterpunkt
        penalty_y = y_base + (11 * direction)
        ax.plot(34, penalty_y, marker='o', color='white', markersize=2)

        # Rote Zone (nur oben) – Breite wie 5m-Raum, Höhe: Auslinie bis 16er
        if side == 'top':
            ax.add_patch(
                patches.Rectangle(
                    (24.84, y_base - 16.5),
                    18.32,
                    16.5,
                    facecolor='red',
                    alpha=0.2,
                    zorder=0
                )
            )

    # Halbkreise am Strafraumrand (außerhalb)
    arc_radius = 9.15
    arc_diameter = arc_radius * 2
    arc_bottom = patches.Arc((34, 11), arc_diameter, arc_diameter,
                             angle=0, theta1=35, theta2=145,
                             color='white', linewidth=0.7)
    ax.add_patch(arc_bottom)
    arc_top = patches.Arc((34, 89), arc_diameter, arc_diameter,
                          angle=0, theta1=215, theta2=325,
                          color='white', linewidth=0.7)
    ax.add_patch(arc_top)

    # Mittelkreis + Mittelpunkt
    mittelkreis = patches.Circle((34, 50), 9.15, edgecolor='white', facecolor='none', linewidth=0.7)
    ax.add_patch(mittelkreis)
    ax.scatter(34, 50, color='white', marker='o', s=8, zorder=5)

    # Gestrichelte Linien (oben)
    ax.plot([43, 43], [100, 75], 'white', linestyle="--", linewidth=0.75)
    ax.plot([25, 25], [100, 75], 'white', linestyle="--", linewidth=0.75)
    ax.plot([43, 54, 54], [100, 84, 75], 'white', linestyle="--", linewidth=0.75)
    ax.plot([25, 14, 14], [100, 84, 75], 'white', linestyle="--", linewidth=0.75)
    ax.plot([14, 0], [90, 90], 'white', linestyle="--", linewidth=0.75)
    ax.plot([54, 68], [90, 90], 'white', linestyle="--", linewidth=0.75)

    ax.tick_params(labelsize=0)
    ax.set_xlabel("", fontsize=6)
    ax.set_ylabel("", fontsize=6)

GOAL_STYLE = dict(color='blue', marker='o', s=12, edgecolors='white', linewidths=0.5)
ASSIST_STYLE = dict(color='yellow', marker='s', s=9, linewidths=0.5)

def plot_events(ax, goals, assists, add_legend=False, label_prefix=""):
    for i, g in enumerate(goals):
        ax.scatter(g[0], g[1], zorder=10,
                   label=(f"{label_prefix} Tor" if add_legend and i == 0 else None),
                   **GOAL_STYLE)
    for i, a in enumerate(assists):
        ax.scatter(a[0], a[1], zorder=10,
                   label=(f"{label_prefix} Assist" if add_legend and i == 0 else None),
                   **ASSIST_STYLE)
    n_pairs = min(len(goals), len(assists))
    for i in range(n_pairs):
        g = goals[i]; a = assists[i]
        ax.plot([a[0], g[0]], [a[1], g[1]], color="white", linestyle="--", linewidth=0.8, alpha=0.5, zorder=5)

# ======= Individuelle Analysen =======
@st.cache_data(show_spinner=False)
def list_individual_players(base: Path):
    players = []
    if base.exists():
        for p in sorted(base.iterdir()):
            if p.is_dir():
                players.append(p.name)
    return players

@st.cache_data(show_spinner=False)
def list_player_files(player_dir: Path):
    files = []
    if player_dir.exists():
        for f in sorted(player_dir.iterdir()):
            if f.is_file() and (f.suffix.lower() in DOC_EXTS or f.suffix.lower() in VIDEO_EXTS):
                files.append(f)
    return files

# ========================= Render-Block (Vergleich) =========================
def render_compare(goals_a, assists_a, label_a,
                   goals_b, assists_b, label_b,
                   team_a, team_b):
    # ============== OBERER TEIL: Felder + rechte Stat-Spalte ==============
    colA_field, colB_field, col_stats_top = st.columns([2, 2, 2], gap="small")

    # --- Spielfeld Team A
    with colA_field:
        fig1, ax1 = plt.subplots(figsize=(2.0, 4.0))
        draw_pitch(ax1, team_a)
        plot_events(ax1, goals_a, assists_a, add_legend=True, label_prefix=label_a or team_a)
        ax1.legend(loc="lower left", fontsize=4)
        plt.title(label_a or team_a, fontsize=6)
        st.pyplot(fig1, use_container_width=False)

    # --- Spielfeld Team B
    with colB_field:
        fig2, ax2 = plt.subplots(figsize=(2.0, 4.0))
        draw_pitch(ax2, team_b)
        plot_events(ax2, goals_b, assists_b, add_legend=True, label_prefix=label_b or team_b)
        ax2.legend(loc="lower left", fontsize=4)
        plt.title(label_b or team_b, fontsize=6)
        st.pyplot(fig2, use_container_width=False)

    # --- Statboxen (ALLE TEAMS) direkt rechts neben dem rechten Spielfeld
    with col_stats_top:
        teams_for_stats = globals().get("teams", [team_a, team_b])

        # 1) Torstatistik gesamt (Videos)
        totals = count_all_goals(teams_for_stats)
        st.markdown(
            "<div style='font-size:0.9rem; font-weight:600; "
            "padding:6px 10px; border:1px solid rgba(0,0,0,0.1); "
            "border-radius:6px; background:rgba(0,0,0,0.03); margin-bottom:6px;'>"
            f"Torstatistik: {totals['1 Touch']} 1Touch, "
            f"{totals['2 Touch']} 2Touch, "
            f"{totals['Elfmeter']} Elfmeter, "
            f"{totals['Sonstiges']} Sonstiges"
            "</div>",
            unsafe_allow_html=True
        )

        # 2) Eigene Zonentore (x 24–42, y 84–100): innen / außerhalb
        innen_total, ausser_total, zone_per_team = count_zone_split_all_teams(
            BASE_DIR, teams_for_stats, x_min=24, x_max=42, y_min=84, y_max=100
        )
        gesamt = innen_total + ausser_total
        share_in = f"{(innen_total/gesamt*100):.0f}%" if gesamt else "–"
        share_out = f"{(ausser_total/gesamt*100):.0f}%" if gesamt else "–"

        st.markdown(
            "<div style='font-size:0.9rem; font-weight:600; "
            "padding:6px 10px; border:1px solid rgba(0,0,0,0.1); "
            "border-radius:6px; background:rgba(0,0,0,0.03); margin-bottom:6px;'>"
            f"Eigene Zonentore (x 24–42, y 84–100): "
            f"{innen_total} innen ({share_in}), "
            f"{ausser_total} außerhalb ({share_out})"
            "</div>",
            unsafe_allow_html=True
        )

        with st.expander("Details pro Team – Eigene Zonentore"):
            if zone_per_team:
                df_zone = pd.DataFrame([{"Team": k, **v} for k, v in zone_per_team.items()])
                if not df_zone.empty:
                    df_zone["Anteil innen %"] = df_zone.apply(
                        lambda r: (r["innen"]/r["gesamt"]*100) if r["gesamt"] else 0,
                        axis=1
                    )
                    df_zone = df_zone.sort_values(["Anteil innen %", "Team"], ascending=[False, True])
                    df_zone["Anteil innen %"] = df_zone["Anteil innen %"].apply(lambda v: f"{v:.0f}%" if v else "–")
                st.dataframe(df_zone, use_container_width=True, hide_index=True)
            else:
                st.caption("Keine Zonentore-Daten gefunden.")

        # 3) Gegentore – Zonenstatistik (x 24–42, y 84–100)
        g_in, g_out, g_per_team = count_zone_split_all_teams_against(
            BASE_DIR, teams_for_stats, x_min=24, x_max=42, y_min=84, y_max=100
        )
        g_total = g_in + g_out
        g_share_in = f"{(g_in/g_total*100):.0f}%" if g_total else "–"
        g_share_out = f"{(g_out/g_total*100):.0f}%" if g_total else "–"

        st.markdown(
            "<div style='font-size:0.9rem; font-weight:600; "
            "padding:6px 10px; border:1px solid rgba(0,0,0,0.1); "
            "border-radius:6px; background:rgba(0,0,0,0.03);'>"
            f"Gegentore (x 24–42, y 84–100): "
            f"{g_in} innen ({g_share_in}), "
            f"{g_out} außerhalb ({g_share_out})"
            "</div>",
            unsafe_allow_html=True
        )

        with st.expander("Details pro Team – Gegentore"):
            if g_per_team:
                df_g = pd.DataFrame([{"Team": k, **v} for k, v in g_per_team.items()])
                if not df_g.empty:
                    df_g["Anteil innen %"] = df_g.apply(
                        lambda r: (r["innen"]/r["gesamt"]*100) if r["gesamt"] else 0,
                        axis=1
                    )
                    df_g = df_g.sort_values(["gesamt", "Team"], ascending=[False, True])  # nach Gesamt absteigend
                    df_g["Anteil innen %"] = df_g["Anteil innen %"].apply(lambda v: f"{v:.0f}%" if v else "–")
                st.dataframe(df_g, use_container_width=True, hide_index=True)
            else:
                st.caption("Keine Gegentore-Daten gefunden.")

        # Zusatz: Infoboxen der aktuell ausgewählten Teams (rechts, unterhalb)
        selected_teams = list(dict.fromkeys([team_a, team_b]))
        st.markdown("<div class='small-heading' style='margin-top:8px;'>Ausgewählte Teams – Statistiken</div>", unsafe_allow_html=True)
        for tname in selected_teams:
            vids = load_team_videos(tname)
            ts = {
                "1Touch": len(vids.get("1 Touch", [])),
                "2Touch": len(vids.get("2 Touch", [])),
                "Elfmeter": len(vids.get("Elfmeter", [])),
                "Sonstiges": len(vids.get("Sonstiges", [])),
            }
            zi_in, zi_out, zi_tot = count_zone_split_for_team(BASE_DIR / tname, x_min=24, x_max=42, y_min=84, y_max=100)
            zg_in, zg_out, zg_tot = count_zone_split_for_team_against(BASE_DIR / tname, x_min=24, x_max=42, y_min=84, y_max=100)
            st.markdown(
                f"<div style='border:1px solid rgba(0,0,0,0.1); border-radius:8px; padding:8px; background:rgba(0,0,0,0.02); margin-top:6px;'>"
                f"<div class='small-heading'>{tname}</div>"
                f"<div style='font-size:0.85rem; margin-top:4px;'><b>Torstatistik:</b> {ts['1Touch']} 1Touch, {ts['2Touch']} 2Touch, {ts['Elfmeter']} Elfmeter, {ts['Sonstiges']} Sonstiges</div>"
                f"<div style='font-size:0.85rem; margin-top:2px;'><b>Eigene Zonentore:</b> {zi_in} innen, {zi_out} außerhalb (gesamt {zi_tot})</div>"
                f"<div style='font-size:0.85rem; margin-top:2px;'><b>Gegentore in Zone:</b> {zg_in} innen, {zg_out} außerhalb (gesamt {zg_tot})</div>"
                f"</div>",
                unsafe_allow_html=True
            )

    # ============== UNTERER TEIL: Videos + Scorer ==============
    # --- Team A (links): Videos | Torschützen
    colA_vids, colA_scorers = st.columns([2, 1], gap="small")
    with colA_vids:
        vidsA = load_team_videos(team_a)
        cntE, cnt1, cnt2, cntS = (
            len(vidsA.get('Elfmeter', [])),
            len(vidsA.get('1 Touch', [])),
            len(vidsA.get('2 Touch', [])),
            len(vidsA.get('Sonstiges', []))
        )
        radio_labels_A = [
            f"Elfmeter ({cntE})",
            f"1 Touch ({cnt1})",
            f"2 Touch ({cnt2})",
            f"Sonstiges ({cntS})"
        ]
        radio_map_A = {radio_labels_A[i]: cat for i, cat in enumerate(['Elfmeter', '1 Touch', '2 Touch', 'Sonstiges'])}
        st.markdown("<div class='small-heading'>🎬 Tore " + team_a + "</div>", unsafe_allow_html=True)
        catA_label = st.radio("Kategorie", radio_labels_A, key="vid_cat_A", horizontal=True)
        catA = radio_map_A[catA_label]
        filesA = vidsA.get(catA, [])
        if filesA:
            labelsA = build_labels_with_roman(filesA)
            selA = st.selectbox("Tor auswählen", range(len(filesA)), key="vid_sel_A", format_func=lambda i: labelsA[i])
            st.video(str(filesA[selA]))
        else:
            st.caption("Keine Videos in dieser Kategorie.")
    with colA_scorers:
        st.markdown("<div class='small-heading'>🏆 Torschützen " + team_a + "</div>", unsafe_allow_html=True)
        scorer_data_a = extract_scorer_table(
            vidsA.get("Elfmeter", []) + vidsA.get("1 Touch", []) +
            vidsA.get("2 Touch", []) + vidsA.get("Sonstiges", [])
        )
        if scorer_data_a:
            counts = defaultdict(int)
            for row in scorer_data_a:
                counts[row["Spieler"]] += row["Tore"]
            for name, cnt in sorted(counts.items(), key=lambda x: x[1], reverse=True):
                st.markdown(f"- {name} ({cnt} {'Tor' if cnt==1 else 'Tore'})")
        else:
            st.caption("Keine Torschützen-Daten verfügbar.")

    # --- Team B (rechts unten): Videos | Torschützen
    colB_vids, colB_scorers = st.columns([2, 1], gap="small")
    with colB_vids:
        # Für Team B (Gegner) die Gegentore laden (alle Videos wo er als TeamB im Dateinamen steht)
        if team_b == team_a:  # Wenn es der gleiche Gegner ist
            vidsB = load_opponent_goals_against(team_b)
            title_suffix = " (Gegentore)"
        else:
            vidsB = load_team_videos(team_b)
            title_suffix = ""
            
        cntE, cnt1, cnt2, cntS = (
            len(vidsB.get('Elfmeter', [])),
            len(vidsB.get('1 Touch', [])),
            len(vidsB.get('2 Touch', [])),
            len(vidsB.get('Sonstiges', []))
        )
        radio_labels_B = [
            f"Elfmeter ({cntE})",
            f"1 Touch ({cnt1})",
            f"2 Touch ({cnt2})",
            f"Sonstiges ({cntS})"
        ]
        radio_map_B = {radio_labels_B[i]: cat for i, cat in enumerate(['Elfmeter', '1 Touch', '2 Touch', 'Sonstiges'])}
        st.markdown(f"<div class='small-heading'>🎬 Tore {team_b}{title_suffix}</div>", unsafe_allow_html=True)
        catB_label = st.radio("Kategorie", radio_labels_B, key="vid_cat_B", horizontal=True)
        catB = radio_map_B[catB_label]
        filesB = vidsB.get(catB, [])
        if filesB:
            labelsB = build_labels_with_roman(filesB)
            selB = st.selectbox("Tor auswählen", range(len(filesB)), key="vid_sel_B", format_func=lambda i: labelsB[i])
            st.video(str(filesB[selB]))
        else:
            st.caption("Keine Videos in dieser Kategorie.")
    with colB_scorers:
        st.markdown(f"<div class='small-heading'>🏆 Torschützen {team_b}{title_suffix}</div>", unsafe_allow_html=True)
        scorer_data_b = extract_scorer_table(
            vidsB.get("Elfmeter", []) + vidsB.get("1 Touch", []) +
            vidsB.get("2 Touch", []) + vidsB.get("Sonstiges", [])
        )
        if scorer_data_b:
            counts = defaultdict(int)
            for row in scorer_data_b:
                counts[row["Spieler"]] += row["Tore"]
            for name, cnt in sorted(counts.items(), key=lambda x: x[1], reverse=True):
                st.markdown(f"- {name} ({cnt} {'Tor' if cnt==1 else 'Tore'})")
        else:
            st.caption("Keine Torschützen-Daten verfügbar.")



# ========================= Query-Param Handling (Logo-Klick öffnet PPTX lokal) =========================
def _open_if_requested():
    try:
        params = st.query_params  # type: ignore[attr-defined]
        get_param = lambda k: params.get(k)
        set_params = lambda **kw: params.update(kw)
    except Exception:
        getp = dict(st.query_params)
        get_param = lambda k: getp.get(k, [None])[0]
        def set_params(**kw):
            st.query_params.update(kw)

    target = get_param("open")
    if target:
        team = unquote_plus(target)
        ppt = resolve_matchplan_ppt(team)
        if ppt and ppt.exists() and os.name == "nt":
            try:
                os.startfile(str(ppt))
                st.toast(f"Öffne LineUp {team} …", icon="📂")
            except Exception as e:
                st.warning(f"Konnte LineUp {team} nicht öffnen: {e}")
        else:
            st.info(f"Kein LineUp für „{team}“ gefunden.")
        try:
            set_params(open="")
        except Exception:
            pass

# ========================= Session-State Utils =========================
def ss_default(key, value):
    if key not in st.session_state:
        st.session_state[key] = value

def select_with_state(label, options, key, index=0, format_func=None):
    use_format = callable(format_func)
    if key in st.session_state:
        return st.selectbox(label, options, key=key, **({'format_func': format_func} if use_format else {}))
    else:
        kwargs = {'index': index, 'key': key}
        if use_format:
            kwargs['format_func'] = format_func
        return st.selectbox(label, options, **kwargs)

def select_idx_with_state(label, n_options, key, default_index=0, labels=None):
    options = list(range(n_options))
    use_format = bool(labels)
    if key in st.session_state:
        return st.selectbox(label, options, key=key, **({'format_func': (lambda i: labels[i])} if use_format else {}))
    else:
        kwargs = {'index': default_index, 'key': key}
        if use_format:
            kwargs['format_func'] = (lambda i: labels[i])
        return st.selectbox(label, options, **kwargs)

def set_defaults(teams, file_index):
    """
    Setzt Start-Defaults:
    - Team A = PREFERRED_TEAM (falls vorhanden)
    - Team B = automatisch ermittelter nächster Gegner (gemappt auf vorhandene Ordner),
      sonst Fallback = Team A
    """
    team0 = PREFERRED_TEAM if PREFERRED_TEAM in teams else teams[0]
    files0 = file_index.get(team0, [])
    file_a_def = pick_file(files0, 'own')
    file_b_def = pick_file(files0, 'against')

    # Einmalige Initialisierung beim (ersten) Start
    first_run = '_init_done' not in st.session_state
    if first_run:
        # Team A
        st.session_state['tA'] = team0

        # Gegner ermitteln + mappen
        try:
            raw_opp = get_next_opponent(team0)
        except Exception:
            raw_opp = None
        mapped = map_to_existing_team(raw_opp, teams) if raw_opp else None
        st.session_state['tB'] = mapped or team0

        # Datei-Defaults (auf Basis Team A, wie bisher)
        st.session_state['fA_idx'] = files0.index(file_a_def) if (files0 and file_a_def in files0) else 0
        st.session_state['fB_idx'] = files0.index(file_b_def) if (files0 and file_b_def in files0) else 0

        st.session_state['_init_done'] = True
    else:
        # Nur nachziehen, falls tB noch fehlt (oder identisch zu team0 geblieben ist und wir einen Gegner haben)
        if 'tB' not in st.session_state or not st.session_state.get('tB'):
            try:
                raw_opp = get_next_opponent(team0)
            except Exception:
                raw_opp = None
            mapped = map_to_existing_team(raw_opp, teams) if raw_opp else None
            st.session_state['tB'] = mapped or team0

        ss_default('tA', team0)
        ss_default('fA_idx', files0.index(file_a_def) if (files0 and file_a_def in files0) else 0)
        ss_default('fB_idx', files0.index(file_b_def) if (files0 and file_b_def in files0) else 0)

def count_all_goals(teams):
    """Zählt alle Tore aus den Video-Ordnern über alle Teams nach Kategorien."""
    totals = {"1 Touch": 0, "2 Touch": 0, "Elfmeter": 0, "Sonstiges": 0}
    for t in teams:
        vids = load_team_videos(t)
        for cat in totals:
            totals[cat] += len(vids.get(cat, []))
    return totals
    
# ——— Nur echte EigeneTore-Dateien (kein "Gegen", keine Backups etc.)
def list_eigene_tore_files(team_dir: Path):
    """
    Nimmt nur *.py, deren Name (case-insensitive) mit 'eigenetore' beginnt
    UND NICHT 'gegen' enthält.
    """
    if not team_dir.exists():
        return []
    out = []
    for p in sorted(team_dir.glob("*.py")):
        name = p.name.lower()
        if name.startswith("eigenetore") and "gegen" not in name:
            out.append(p)
    return out

# ——— Alle goals aus Dateien sammeln (optional dedupe via Rundung)
def collect_unique_goals_from_files(files, round_ndigits=3):
    """
    Sammelt goals-Punkte aus allen Dateien und dedupliziert per gerundetem (x,y).
    Rundung = 3 Nachkommastellen, damit (35,95) & (35.0, 95.0) als gleich gelten.
    """
    seen = set()
    unique = []
    for f in files:
        goals, _, _ = parse_goals_assists(f)
        for (x, y) in goals:
            xx, yy = float(x), float(y)
            key = (round(xx, round_ndigits), round(yy, round_ndigits))
            if key not in seen:
                seen.add(key)
                unique.append((xx, yy))
    return unique

# ——— Zählen: innen vs. außerhalb (inkl. Spielfeld-Grenze)
def count_zone_split_for_team(team_dir: Path, x_min=24, x_max=42, y_min=84, y_max=100):
    """
    Zählt Tore innerhalb [x_min..x_max] und [y_min..y_max] (inklusive),
    verwirft Punkte außerhalb des Spielfelds (x∉[0,68] oder y∉[0,100]).
    Rückgabe: (innen, außerhalb, gesamt)
    """
    files = list_eigene_tore_files(team_dir)
    pts = collect_unique_goals_from_files(files)

    # Nur valide Spielfeldpunkte
    pts = [(x, y) for (x, y) in pts if 0 <= x <= 68 and 0 <= y <= 100]

    inside = sum(1 for (x, y) in pts if (x_min <= x <= x_max and y_min <= y <= y_max))
    outside = len(pts) - inside
    return inside, outside, len(pts)

# ——— Alle Teams zusammen
def count_zone_split_all_teams(base_dir: Path, teams: list[str], x_min=24, x_max=42, y_min=84, y_max=100):
    innen_total = ausser_total = 0
    per_team = {}
    for t in teams:
        team_dir = base_dir / t
        inside, outside, total = count_zone_split_for_team(team_dir, x_min, x_max, y_min, y_max)
        per_team[t] = {"innen": inside, "außerhalb": outside, "gesamt": total}
        innen_total += inside
        ausser_total += outside
    return innen_total, ausser_total, per_team

# --- Gegentore-Dateien finden (nur "GegenTore*.py")
def list_gegentore_files(team_dir: Path):
    """
    Nimmt nur *.py, deren Name (case-insensitive) mit 'gegentore' beginnt.
    """
    if not team_dir.exists():
        return []
    out = []
    for p in sorted(team_dir.glob("*.py")):
        name = p.name.lower()
        if name.startswith("gegentore"):
            out.append(p)
    return out

# (Nur falls noch nicht vorhanden)
def collect_unique_goals_from_files(files, round_ndigits=3):
    """
    Sammelt goals-Punkte aus allen Dateien und dedupliziert per gerundetem (x,y).
    """
    seen = set()
    unique = []
    for f in files:
        goals, _, _ = parse_goals_assists(f)
        for (x, y) in goals:
            xx, yy = float(x), float(y)
            key = (round(xx, round_ndigits), round(yy, round_ndigits))
            if key not in seen:
                seen.add(key)
                unique.append((xx, yy))
    return unique

# Zählen: innen vs. außerhalb für Gegentore
def count_zone_split_for_team_against(team_dir: Path, x_min=24, x_max=42, y_min=84, y_max=100):
    """
    Zählt Gegentore innerhalb [x_min..x_max] ∧ [y_min..y_max] (inkl.),
    verwirft Punkte außerhalb des Spielfelds ([0..68]×[0..100]).
    Rückgabe: (innen, außerhalb, gesamt)
    """
    files = list_gegentore_files(team_dir)
    pts = collect_unique_goals_from_files(files)

    # Nur valide Spielfeldpunkte
    pts = [(x, y) for (x, y) in pts if 0 <= x <= 68 and 0 <= y <= 100]

    inside = sum(1 for (x, y) in pts if (x_min <= x <= x_max and y_min <= y <= y_max))
    outside = len(pts) - inside
    return inside, outside, len(pts)

# Alle Teams zusammenfassen (Gegentore)
def count_zone_split_all_teams_against(base_dir: Path, teams: list[str], x_min=24, x_max=42, y_min=84, y_max=100):
    innen_total = ausser_total = 0
    per_team = {}
    for t in teams:
        team_dir = base_dir / t
        inside, outside, total = count_zone_split_for_team_against(team_dir, x_min, x_max, y_min, y_max)
        per_team[t] = {"innen": inside, "außerhalb": outside, "gesamt": total}
        innen_total += inside
        ausser_total += outside
    return innen_total, ausser_total, per_team

# ========================= QueryParam Utils =========================
def _qp_get_value(val):
    """Hilfsfunktion: nimmt QueryParam-Werte (Liste oder str) und gibt den ersten Wert zurück."""
    if isinstance(val, (list, tuple)):
        return val[0] if val else None
    return val

# ========================= ÖFB-Parser =========================
def extrahiere_kaderdaten(html: str):
    import json as _json
    import re as _re
    try:
        pattern = r"SG\.container\.appPreloads\[\s*'(\d+)'\s*\]\s*=\s*(\[[\s\S]*?\]);"
        match = _re.search(pattern, html, _re.DOTALL)
        if match:
            json_text = match.group(2)
            data = _json.loads(json_text)
            for item in data:
                if isinstance(item, dict) and "kader" in item:
                    return item.get("kader", [])
    except Exception:
        pass
    results = []
    obj_pattern = _re.compile(
        r'\{[^{}]*?"spielerName"\s*:\s*"([^"]+)"[^{}]*?'
        r'"kartenGelb"\s*:\s*(\d+)[^{}]*?'
        r'(?:\"kartenGelbRot\"\s*:\s*(\d+))?[^{}]*?'
        r'(?:\"kartenRot\"\s*:\s*(\d+))?[^{}]*?'
        r'(?:"spielerProfilUrl"\s*:\s*"([^"]*)")?[^{}]*?\}',
        _re.DOTALL
    )
    for m in obj_pattern.finditer(html):
        name = m.group(1)
        gelb = int(m.group(2)) if m.group(2) else 0
        gelbrot = int(m.group(3)) if m.group(3) else 0
        rot = int(m.group(4)) if m.group(4) else 0
        profil = (m.group(5) or "").strip()
        results.append({
            "spielerName": name,
            "kartenGelb": gelb,
            "kartenGelbRot": gelbrot,
            "kartenRot": rot,
            "spielerProfilUrl": profil
        })
    if results:
        merged = {}
        for r in results:
            n = r["spielerName"]
            if n not in merged:
                merged[n] = r
            else:
                for f in ("kartenGelb", "kartenGelbRot", "kartenRot"):
                    merged[n][f] = max(int(merged[n].get(f, 0)), int(r.get(f, 0)))
                if r.get("spielerProfilUrl"):
                    merged[n]["spielerProfilUrl"] = r["spielerProfilUrl"]
        return list(merged.values())
    return []


# ========================= MAIN =========================
def main():
    base = BASE_DIR
    if not base.exists():
        st.error(f"Basisverzeichnis nicht gefunden: {base}")
        st.stop()

    global teams  # für Stat-Box rechts
    teams, file_index = list_teams_and_files(base, preferred=PREFERRED_TEAM)
    if not teams:
        st.warning("Keine Mannschaftsordner gefunden.")
        st.stop()

    # Defaults setzen (Team A = JWR, Team B = nächster Gegner)
    set_defaults(teams, file_index)

    _open_if_requested()

    # Sidebar
    with st.sidebar:
        # Ansicht-Umschalter via Query-Parameter (persistiert nach Refresh/Neutab)
        try:
            params = st.query_params  # Streamlit >= 1.32
            get_param = lambda k: params.get(k)
            def set_params_safe(**kw):
                try:
                    params.update(kw)
                except Exception:
                    st.query_params.update(kw)
        except Exception:
            getp = dict(st.query_params)
            get_param = lambda k: getp.get(k, [None])[0]
            def set_params_safe(**kw):
                st.experimental_set_query_params(**kw)

        current_view = _qp_get_value(get_param("view")) or "Dashboard"
        options = ["Dashboard", "Individuelle Analysen"]
        view = st.selectbox(
            "Ansicht",
            options,
            index=options.index(current_view) if current_view in options else 0,
            key="view_mode"
        )
        if view != current_view:
            set_params_safe(view=view)

        if view == "Dashboard":
            # --- Vorbelegen aus Query-Parametern (persistente Defaults) ---
            qp_tA = _qp_get_value(get_param("tA"))
            qp_tB = _qp_get_value(get_param("tB"))
            if "tA" not in st.session_state and qp_tA in (teams if isinstance(teams, list) else []):
                st.session_state["tA"] = qp_tA
            if "tB" not in st.session_state and qp_tB in (teams if isinstance(teams, list) else []):
                st.session_state["tB"] = qp_tB

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



                # Debug-Panel für Gegner-Erkennung
            st.markdown("### ⚽ Team A")
            team_a = select_with_state("Team wählen", teams, key="tA", index=teams.index(st.session_state['tA']))
            files_a = file_index.get(team_a, [])
            file_labels_a = [f.name for f in files_a]
            # Datei A Vorbelegung aus Param
            qp_fA = _qp_get_value(get_param("fA"))
            if "fA_idx" not in st.session_state and qp_fA and qp_fA in file_labels_a:
                default_idx_a = file_labels_a.index(qp_fA)
            else:
                desired_a = pick_file(files_a, 'own')
                default_idx_a = files_a.index(desired_a) if (files_a and desired_a in files_a) else 0
            idx_a = select_idx_with_state("Datei wählen", len(files_a), key="fA_idx", default_index=default_idx_a, labels=file_labels_a)
            file_a = files_a[idx_a] if files_a else None

            st.markdown("### ⚽ Team B")
            team_b = select_with_state("Team wählen", teams, key="tB", index=teams.index(st.session_state['tB']))
            files_b = file_index.get(team_b, [])
            file_labels_b = [f.name for f in files_b]
            # Datei B Vorbelegung aus Param
            qp_fB = _qp_get_value(get_param("fB"))
            if "fB_idx" not in st.session_state and qp_fB and qp_fB in file_labels_b:
                default_idx_b = file_labels_b.index(qp_fB)
            else:
                desired_b = pick_file(files_b, 'against')
                default_idx_b = files_b.index(desired_b) if (files_b and desired_b in files_b) else 0
            idx_b = select_idx_with_state("Datei wählen", len(files_b), key="fB_idx", default_index=default_idx_b, labels=file_labels_b)
            file_b = files_b[idx_b] if files_b else None

            # Nach Auswahl: Query-Parameter aktualisieren (persistiert Team & Datei)
            try:
                fA_name = file_a.name if file_a else ""
                fB_name = file_b.name if file_b else ""
            except Exception:
                fA_name = ""
                fB_name = ""
            set_params_safe(view=view, tA=team_a, fA=fA_name, tB=team_b, fB=fB_name)

            st.markdown("### 🔗 Links")
            st.markdown("[📑 Zur aktuellen Tabelle](https://www.ligaportal.at/regionalliga-mitte/tabelle)")
            st.markdown("[📅 Spielplan JWR (ÖFB)](https://vereine.oefb.at/SVOberbankRied/Mannschaften/Saison-2025-26/KM-Amat-/Spiele)")
            st.markdown("[🚫 Gesperrte Spieler](https://www.ofv.at/ofv/Spielbetrieb/Sperren/Gesperrte-Spieler)")

            st.markdown("### 🟨 Kartenwarnung")
            col_btn1, col_btn2 = st.columns([1, 1])
            with col_btn1:
                if st.button("🟨", help="Kartenwarnung anzeigen", key="btn_show_warn"):
                    st.session_state.show_warnsystem = True
                    st.session_state.warnsystem_start = time.time()
            with col_btn2:
                if st.button("✖️", help="Ausblenden", key="btn_hide_warn"):
                    st.session_state.show_warnsystem = False
        else:
            st.caption("<div class='sidebar-caption'>Modus: Individuelle Analysen</div>", unsafe_allow_html=True)
            file_a = file_b = None
            team_a = teams[0]
            team_b = teams[0]

    # ======= CONTENT RENDERING =======
    if view == "Dashboard":
        # Warnsystem (zeitlich begrenzt sichtbar)
        if st.session_state.get("show_warnsystem"):
            start = st.session_state.get("warnsystem_start", 0)
            now = time.time()
            if now - start <= 60:
                st.subheader("🟨 Gelbe Karten Warnsystem")
                url = "https://vereine.oefb.at/SVOberbankRied/Mannschaften/Saison-2025-26/KM-Amat-/Kader"
                cols = st.columns([1,1,1,1,2])
                with cols[0]:
                    art = st.selectbox("Art", ["Gelb", "Gelb-Rot", "Rot"], help="Welche Karten-Art prüfen?")
                with cols[1]:
                    thresh = st.number_input("Schwellwert", min_value=1, max_value=10, value=3, step=1, help="Ab wie vielen Karten warnen? Gilt für die gewählte Art.")
                with cols[2]:
                    show_all = st.checkbox("Alle Spieler anzeigen", value=False)
                with cols[3]:
                    do_refresh = st.button("🔄 Neu laden")
                ts = time.strftime("%H:%M:%S")
                with cols[4]:
                    st.caption(f"Letzte Prüfung: {ts}")
                try:
                    headers = {"Cache-Control": "no-cache"} if do_refresh else {}
                    resp = requests.get(url, timeout=8, headers=headers)
                    html = resp.text
                    kader = extrahiere_kaderdaten(html)
                except Exception as e:
                    st.error(f"Kaderdaten konnten nicht geladen werden: {e}")
                    kader = []
                df = pd.DataFrame(kader) if kader else pd.DataFrame(columns=["spielerName","kartenGelb","kartenGelbRot","kartenRot","spielerProfilUrl"])
                if not df.empty:
                    df["kartenGelb"] = pd.to_numeric(df.get("kartenGelb", 0), errors="coerce").fillna(0).astype(int)
                    df["kartenGelbRot"] = pd.to_numeric(df.get("kartenGelbRot", 0), errors="coerce").fillna(0).astype(int)
                    df["kartenRot"] = pd.to_numeric(df.get("kartenRot", 0), errors="coerce").fillna(0).astype(int)
                    df = df.rename(columns={"spielerName": "Spieler", "kartenGelb": "Gelb", "kartenGelbRot": "Gelb-Rot", "kartenRot": "Rot", "spielerProfilUrl": "Profil"})
                    col_map = {"Gelb": "Gelb", "Gelb-Rot": "Gelb-Rot", "Rot": "Rot"}
                    sel_col = col_map.get(art, "Gelb")
                    warn_df = df[df[sel_col] >= int(thresh)].sort_values([sel_col, "Spieler"], ascending=[False, True])
                    if not warn_df.empty:
                        st.warning(f"⚠️ Spieler mit ≥ {int(thresh)} {sel_col}:")
                        st.dataframe(warn_df[["Spieler", sel_col]], use_container_width=True, hide_index=True)
                    else:
                        st.success(f"✅ Kein Spieler mit ≥ {int(thresh)} {sel_col}")
                    if show_all:
                        st.markdown(f"### Übersicht {sel_col} (alle)")
                        st.dataframe(df[["Spieler", sel_col]].sort_values([sel_col, "Spieler"], ascending=[False, True]), use_container_width=True, hide_index=True)
                else:
                    st.info("Keine Kaderdaten gefunden.")
            else:
                st.session_state.show_warnsystem = False

        # Header: Titel + Logos
        head_left, head_right = st.columns([2, 10], gap="small")
        with head_left:
            st.markdown("<h4>📊 Dashboard</h4>", unsafe_allow_html=True)

        with head_right:
            col_logos, col_stats = st.columns([8, 4], gap="small")

            # Logos (klickbar → öffnet LineUp lokal)
            with col_logos:
                logos_html = []
                for t in teams:
                    lp = find_team_logo(t) or LOGO_PATH
                    if lp and lp.exists():
                        data_uri = encode_image_base64(lp)
                        if data_uri:
                            href = f"?open={quote_plus(t)}"
                            logos_html.append(
                                f'<a href="{href}" target="_self" title="LineUp {t} öffnen">'
                                f'<img src="{data_uri}" alt="{t}" /></a>'
                            )
                if logos_html:
                    st.markdown(
                        '<div class="logo-row">' + ''.join(logos_html) + '</div>',
                        unsafe_allow_html=True
                    )

        # Daten laden & Rendern
        goals_a, assists_a, title_a = parse_goals_assists(file_a) if file_a else ([], [], None)
        goals_b, assists_b, title_b = parse_goals_assists(file_b) if file_b else ([], [], None)
        
        render_compare(
            goals_a, assists_a, title_a or f"{team_a}",
            goals_b, assists_b, title_b or f"{team_b}",
            team_a, team_b
        )

        # Extra: Torschützen-Tabs
        vidsA_all = load_team_videos(team_a)
        vidsB_all = load_team_videos(team_b)
        scorer_data_a = extract_scorer_table(
            vidsA_all.get("Elfmeter", []) + vidsA_all.get("1 Touch", []) +
            vidsA_all.get("2 Touch", []) + vidsA_all.get("Sonstiges", [])
        )
        scorer_data_b = extract_scorer_table(
            vidsB_all.get("Elfmeter", []) + vidsB_all.get("1 Touch", []) +
            vidsB_all.get("2 Touch", []) + vidsB_all.get("Sonstiges", [])
        )
        if scorer_data_a or scorer_data_b:
            tab1, tab2 = st.tabs([f"Torschützen {team_a}", f"Torschützen {team_b}"])
            with tab1:
                if scorer_data_a:
                    grouped = defaultdict(lambda: {"Tore": 0, "Details": []})
                    for row in scorer_data_a:
                        grouped[row["Spieler"]]["Tore"] += row["Tore"]
                        for video in row["Videos"]:
                            grouped[row["Spieler"]]["Details"].append({"Video": video, "Kategorie": row["Kategorie"], "Gegner": row["Gegner"]})
                    for name, data in sorted(grouped.items(), key=lambda x: x[1]["Tore"], reverse=True):
                        st.markdown(f"### {name} ({data['Tore']} {'Tor' if data['Tore']==1 else 'Tore'})")
                        for detail in data["Details"]:
                            with st.expander(f"▶️ {name} – {detail['Kategorie']} vs. {detail['Gegner']}"):
                                st.video(str(detail["Video"]))
                else:
                    st.caption("Keine Torschützen-Daten für Team A verfügbar.")
            with tab2:
                if scorer_data_b:
                    grouped = defaultdict(lambda: {"Tore": 0, "Details": []})
                    for row in scorer_data_b:
                        grouped[row["Spieler"]]["Tore"] += row["Tore"]
                        for video in row["Videos"]:
                            grouped[row["Spieler"]]["Details"].append({"Video": video, "Kategorie": row["Kategorie"], "Gegner": row["Gegner"]})
                    for name, data in sorted(grouped.items(), key=lambda x: x[1]["Tore"], reverse=True):
                        st.markdown(f"### {name} ({data['Tore']} {'Tor' if data['Tore']==1 else 'Tore'})")
                        for detail in data["Details"]:
                            with st.expander(f"▶️ {name} – {detail['Kategorie']} vs. {detail['Gegner']}"):
                                st.video(str(detail["Video"]))
                else:
                    st.caption("Keine Torschützen-Daten für Team B verfügbar.")

    else:
        # ============== Individuelle Analysen Ansicht ==============
        st.markdown("<h4>🧠 Individuelle Analysen</h4>", unsafe_allow_html=True)

        players = list_individual_players(IND_ANALYSEN_BASE)
        if not players:
            st.info("Keine Spielerordner gefunden unter „Individuelle Analysen“.")
        else:
            player = st.selectbox("Spieler wählen", players, key="ind_player_center")
            pdir = IND_ANALYSEN_BASE / player
            pfiles = list_player_files(pdir)

            if not pfiles:
                st.caption("Keine Dateien im gewählten Ordner.")
            else:
                video_files = [f for f in pfiles if f.suffix.lower() in VIDEO_EXTS]

                if not video_files:
                    st.caption("Keine Videos für diesen Spieler vorhanden.")
                else:
                    st.markdown("##### 🎬 Video-Vorschauen")
                    cols_per_row = 4
                    cols = st.columns(cols_per_row, gap="small")
                    for i, vf in enumerate(video_files):
                        with cols[i % cols_per_row]:
                            st.video(str(vf))
                            st.caption(vf.name)


# Entry point
if __name__ == "__main__":
    main()

