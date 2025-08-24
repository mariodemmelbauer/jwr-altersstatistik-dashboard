# -*- coding: utf-8 -*-
# streamlit run dashboard_fixed.py
"""
Dashboard (robust, ohne Kopf-Logos) – zentrierte, größere Spielfelder
- Keine Logos mehr oben.
- Unter den sortierten Torschützen je Team ein Button „LineUp <TEAM> öffnen“ (lokal via os.startfile).
- Modi: Dashboard / Individuelle Analysen.
- Kartenwarnung (Gelb / Gelb‑Rot / Rot).
- Spielfeld inkl. roter Zone oben (zwischen 5m und 16m), gestrichelte Hilfslinien.
- NEU: Spielfelder größer (figsize 3.5×6.0), Zeilen/Legenden einheitlich, zentral angeordnet.
- NEU: Individuelle Analysen zeigen kleine Video‑Previews, Name + Dateiname darüber.
"""
from __future__ import annotations

from onedrive_manifest_adapter import (
    use_manifest, load_manifest, team_videos, players, player_files,
    team_plot_files, fetch_text, is_url_ref, display_video
)
import os
import re
import ast
import time
from pathlib import Path
from collections import defaultdict, Counter

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import streamlit as st
import pandas as pd
import requests

# ========================= CONFIG =========================
BASE_DIR = Path(r"C:\Users\demmelb-ma\OneDrive - COC AG\JWR\Analysen\2526")
PREFERRED_TEAM = "JWR"

MATCHPLAN_BASE = Path(r"C:\Users\demmelb-ma\OneDrive\JWR\Matchplan")      # LineUp-PPTX (lokal)
RL_VIDEOS_BASE = Path(r"C:\Users\demmelb-ma\OneDrive\JWR\RL-AlleTore")    # optionale Team-Videos
IND_ANALYSEN_BASE = Path(r"C:\Users\demmelb-ma\OneDrive\JWR\Individuelle Analysen")

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}
DOC_EXTS = {".pptx", ".pdf", ".xlsx"}

# ========================= PAGE SETUP =========================
st.set_page_config(page_title="Dashboard", layout="wide", initial_sidebar_state="collapsed")
st.markdown(
    """
    <style>
      .block-container{padding-top:1.25rem!important; max-width: 1400px;}
      .small-heading{font-size:0.95rem;font-weight:600;margin:0.25rem 0;}
      .sidebar-caption{margin:0.25rem 0;font-size:0.8rem;opacity:0.75;}
      .card{background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.15);border-radius:12px;padding:1rem;}
      .tight p{margin:0.15rem 0;}
      .filename{font-size:0.9rem;font-weight:700;margin:0.25rem 0 0.35rem 0;}
      h4.page-title { text-align:center; margin: 0.25rem 0 0.75rem 0; }
      .center-wrap { display:flex; justify-content:center; }
    </style>
    """, unsafe_allow_html=True
)

# ========================= ÖFB-Parser =========================
def extrahiere_kaderdaten(html: str):
    import json as _json, re as _re
    # Strategie 1
    try:
        pattern = r"SG\.container\.appPreloads\[\s*'(\d+)'\s*\]\s*=\s*(\[[\s\S]*?\]);"
        match = _re.search(pattern, html, _re.DOTALL)
        if match:
            data = _json.loads(match.group(2))
            for item in data:
                if isinstance(item, dict) and "kader" in item:
                    return item.get("kader", [])
    except Exception:
        pass
    # Strategie 2
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
        gelb = int(m.group(2) or 0)
        gelbrot = int((m.group(3) or 0))
        rot = int((m.group(4) or 0))
        profil = (m.group(5) or "").strip()
        results.append({"spielerName": name,"kartenGelb": gelb,"kartenGelbRot": gelbrot,"kartenRot": rot,"spielerProfilUrl": profil})
    if results:
        merged = {}
        for r in results:
            n = r["spielerName"]
            if n not in merged:
                merged[n] = r
            else:
                for f in ("kartenGelb","kartenGelbRot","kartenRot"):
                    merged[n][f] = max(int(merged[n].get(f,0)), int(r.get(f,0)))
                if r.get("spielerProfilUrl"):
                    merged[n]["spielerProfilUrl"] = r["spielerProfilUrl"]
        return list(merged.values())
    return []

# ========================= Helper =========================
def _normalize_name(s: str) -> str:
    return "".join(ch for ch in s.lower() if ch.isalnum())

def _strip_tokens(name_norm: str) -> str:
    tokens = ("sv","fc","sc","ask","usk","sk","dsc","atsv","esv","spg","sg","tsv")
    out = name_norm
    for t in tokens:
        if out.startswith(t): out = out[len(t):]
    return out

def _is_video(p: Path) -> bool:
    return p.suffix.lower() in VIDEO_EXTS

@st.cache_data(show_spinner=False)
def list_video_team_dirs(base: Path):
    mapping = {}
    if base.exists():
        for p in sorted(base.iterdir()):
            if p.is_dir(): mapping[_normalize_name(p.name)] = p
    return mapping

def resolve_video_dir_for_team(team: str):
    mapping = list_video_team_dirs(RL_VIDEOS_BASE)
    norm_team = _normalize_name(team)
    if norm_team in mapping: return mapping[norm_team]
    tokens_to_strip = ("sv","fc","sc","ask","usk","sk","dsc","atsv")
    stripped = norm_team
    for t in tokens_to_strip:
        if stripped.startswith(t): stripped = stripped[len(t):]
    for key, path in mapping.items():
        ks = key
        for t in tokens_to_strip:
            if ks.startswith(t): ks = ks[len(t):]
        if ks == stripped or key.startswith(stripped) or stripped.startswith(key) or ks.startswith(stripped) or stripped.startswith(ks):
            return path
    return None

@st.cache_data(show_spinner=False)
def list_teams_and_files(base_dir: Path, preferred: str = "JWR"):
    if use_manifest():
        man = load_manifest()
        team_keys = set(man.get("plots_base", {}).keys()) | set(man.get("videos", {}).keys())
        teams = sorted(team_keys)
        file_index = {t: team_plot_files(t) for t in teams}
        if preferred in teams:
            teams.remove(preferred); teams.insert(0, preferred)
        return teams, file_index
    teams, file_index = [], {}
    for p in sorted(base_dir.iterdir() if base_dir.exists() else []):
        if p.is_dir():
            teams.append(p.name)
            files = [f for f in sorted(p.glob("*.py")) if re.search(r"(eigene|gegen).*tore", f.name, re.IGNORECASE)]
            file_index[p.name] = files
    if preferred in teams:
        teams.remove(preferred); teams.insert(0, preferred)
    return teams, file_index

def pick_file(files, kind: str):
    if not files: return None
    wanted_terms = (['eigene','tore'] if kind=='own' else ['gegen','tore'])
    def _nm(f):
        if isinstance(f, dict): return (f.get("name") or f.get("label") or "").lower()
        return getattr(f, "name", str(f)).lower()
    for f in files:
        nm = _nm(f)
        if all(t in nm for t in wanted_terms): return f
    for f in files:
        nm = _nm(f)
        if any(t in nm for t in wanted_terms): return f
    return files[0]

def parse_vector_list(src: str, var_name: str):
    m = re.search(rf"{re.escape(var_name)}\s*=\s*(\[[\s\S]*?\])", src, re.IGNORECASE)
    if not m: return None
    try:
        data = ast.literal_eval(m.group(1))
        out = []
        for item in data:
            if isinstance(item,(list,tuple)) and len(item)==2:
                out.append((float(item[0]), float(item[1])))
        return out
    except Exception:
        return None

def parse_title(src: str):
    m = re.search(r'plt\.title\(\s*["\'](.+?)["\']\s*\)', src)
    return (m.group(1).replace("\\n","\n") if m else None)

def parse_goals_assists(file_path):
    if not file_path: return [], [], None
    try:
        if use_manifest() and is_url_ref(file_path):
            src = fetch_text(file_path["url"])
        else:
            try:
                src = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                src = file_path.read_text(encoding="cp1252", errors="ignore")
    except Exception:
        return [], [], None
    goals = parse_vector_list(src,"goals") or []
    assists = parse_vector_list(src,"assists") or []
    title = parse_title(src)
    return goals, assists, title

def int_to_roman(n: int) -> str:
    vals = [(1000,'M'),(900,'CM'),(500,'D'),(400,'CD'),(100,'C'),(90,'XC'),(50,'L'),(40,'XL'),(10,'X'),(9,'IX'),(5,'V'),(4,'IV'),(1,'I')]
    res = []
    for v,sym in vals:
        while n>=v: res.append(sym); n-=v
    return ''.join(res) if res else 'I'

def parse_filename_parts(file: Path):
    stem = file.stem; parts = stem.split("_")
    team = parts[1] if len(parts)>=2 else stem
    opponent = parts[2] if len(parts)>=3 else ""
    low = stem.lower()
    if "elfmeter" in low: cat = "Elfmeter"
    elif "1touch" in low: cat = "1Touch"
    elif "2touch" in low: cat = "2Touch"
    else: cat = "Sonstiges Tor"
    scorer = parts[4] if len(parts)>=5 else None
    return team, opponent, cat, scorer

def extract_scorer_table(files):
    counter = Counter(); file_map = defaultdict(list); rows = []
    for f in files:
        team, opponent, cat, scorer = parse_filename_parts(f)
        if scorer:
            key = (scorer, cat, team, opponent)
            counter[key] += 1; file_map[key].append(f)
    for key, count in counter.items():
        scorer, cat, team, opponent = key
        rows.append({"Spieler": scorer,"Tore": count,"Kategorie": cat,"Team": team,"Gegner": opponent,"Videos": file_map[key]})
    return rows

def build_labels_with_roman(files):
    if use_manifest() and files and isinstance(files[0], dict):
        labels = []
        counters = defaultdict(int)
        for f in files:
            label = f.get("label") or f.get("name") or "Clip"
            key = re.sub(r"\s+\bI{1,3}|IV|V|VI{0,3}|IX\b", "", label)
            counters[key] += 1
            roman = int_to_roman(counters[key])
            labels.append(f"{label} {roman}" if roman else label)
        return labels
    counters = defaultdict(int); labels=[]
    for f in files:
        team, opponent, cat, scorer = parse_filename_parts(f)
        key = (team, cat, opponent); counters[key]+=1
        roman = int_to_roman(counters[key])
        base = f"{team} {cat} vs. {opponent} {roman}"
        labels.append(base + (f" – {scorer}" if scorer else ""))
    return labels

@st.cache_data(show_spinner=False)
def load_team_videos(team: str):
    if use_manifest():
        return team_videos(team)
    resolved_dir = resolve_video_dir_for_team(team)
    vids = {'Elfmeter': [], '1 Touch': [], '2 Touch': [], 'Sonstiges': []}
    if not resolved_dir or not resolved_dir.exists(): return vids
    files = [f for f in sorted(resolved_dir.iterdir()) if f.is_file() and f.suffix.lower() in VIDEO_EXTS]
    for f in files:
        low = f.name.lower()
        if "elfmeter" in low: vids['Elfmeter'].append(f)
        elif "1touch" in low: vids['1 Touch'].append(f)
        elif "2touch" in low: vids['2 Touch'].append(f)
        else: vids['Sonstiges'].append(f)
    return vids

# ========================= Matchplan-Auflösung (robust) =========================
@st.cache_data(show_spinner=False)
def list_matchplan_team_dirs(base: Path):
    mapping = {}
    if base.exists():
        for p in sorted(base.iterdir()):
            if p.is_dir(): mapping[_normalize_name(p.name)] = p
    return mapping

def resolve_matchplan_ppt(team: str):
    if not MATCHPLAN_BASE.exists(): return None
    norm_team = _normalize_name(team); stripped = _strip_tokens(norm_team)
    dir_map = list_matchplan_team_dirs(MATCHPLAN_BASE)
    candidate_dir = None
    if norm_team in dir_map:
        candidate_dir = dir_map[norm_team]
    else:
        for key, path in dir_map.items():
            ks = _strip_tokens(key)
            if ks == stripped or key.startswith(stripped) or stripped.startswith(key) or ks.startswith(stripped) or stripped.startswith(ks):
                candidate_dir = path; break
    if candidate_dir:
        exact = candidate_dir / f"LineUp_{team}.pptx"
        if exact.exists(): return exact
        hits = sorted(candidate_dir.glob("LineUp_*.pptx"))
        if hits: return hits[0]
    for p in sorted(MATCHPLAN_BASE.rglob("LineUp_*.pptx")):
        name_norm = p.stem.replace("LineUp_","").lower()
        if stripped in _strip_tokens(''.join(ch for ch in name_norm if ch.isalnum())):
            return p
    return None

# ========================= Zeichnen / Plot =========================
def draw_pitch(ax, team: str):
    ax.set_facecolor('green'); ax.set_xlim(0,68); ax.set_ylim(0,100)
    # Mittellinie & Mittelkreis
    ax.plot([0,68],[50,50],'white',linestyle="-",linewidth=0.7)
    ax.add_patch(patches.Circle((34,50),9.15,edgecolor='white',facecolor='none',linewidth=0.7))

    # Strafräume, 5m, Tor, Elferpunkte (oben+unten)
    for side in ['bottom','top']:
        y_base = 0 if side=='bottom' else 100; direction = 1 if side=='bottom' else -1
        ax.add_patch(patches.Rectangle((13.84, y_base if side=='bottom' else y_base-16.5),
                                       40.32,16.5,edgecolor='white',facecolor='none',linewidth=0.7))
        ax.add_patch(patches.Rectangle((24.84, y_base if side=='bottom' else y_base-5.5),
                                       18.32,5.5,edgecolor='white',facecolor='none',linewidth=0.7))
        ax.add_patch(patches.Rectangle((30.34, y_base if side=='bottom' else y_base-2.44),
                                       7.32,2.44,edgecolor='white',facecolor='none',linewidth=0.7))
        penalty_y = y_base + (11*direction)
        ax.plot(34, penalty_y, marker='o', color='white', markersize=2)

        # Nur oben: rote Zone zwischen 5m und 16m (Breite wie 5m‑Raum)
        if side=='top':
            ax.add_patch(patches.Rectangle((24.84, y_base-16.5),
                                           18.32, 16.5,
                                           facecolor='red', alpha=0.2, zorder=0))

    # Strafraum‑Halbkreise
    arc_r = 9.15; d = arc_r*2
    ax.add_patch(patches.Arc((34,11), d,d, angle=0, theta1=35, theta2=145, color='white', linewidth=0.7))
    ax.add_patch(patches.Arc((34,89), d,d, angle=0, theta1=215, theta2=325, color='white', linewidth=0.7))

    # Mittelpunkt
    ax.add_patch(patches.Circle((34,50),9.15,edgecolor='white',facecolor='none',linewidth=0.7))
    ax.scatter(34,50,color='white',marker='o',s=8,zorder=5)

    # Gestrichelte Hilfslinien oben
    ax.plot([43,43],[100,75],'white',linestyle="--",linewidth=0.75)
    ax.plot([25,25],[100,75],'white',linestyle="--",linewidth=0.75)
    ax.plot([43,54,54],[100,84,75],'white',linestyle="--",linewidth=0.75)
    ax.plot([25,14,14],[100,84,75],'white',linestyle="--",linewidth=0.75)
    ax.plot([14,0],[90,90],'white',linestyle="--",linewidth=0.75)
    ax.plot([54,68],[90,90],'white',linestyle="--",linewidth=0.75)

    ax.tick_params(labelsize=0); ax.set_xlabel(""); ax.set_ylabel("")

GOAL_STYLE = dict(color='blue', marker='o', s=12, edgecolors='white', linewidths=0.5)
ASSIST_STYLE = dict(color='yellow', marker='s', s=9, linewidths=0.5)

def plot_events(ax, goals, assists, add_legend=False, label_prefix=""):
    for i,g in enumerate(goals):
        ax.scatter(g[0],g[1], zorder=10, label=(f"{label_prefix} Tor" if add_legend and i==0 else None), **GOAL_STYLE)
    for i,a in enumerate(assists):
        ax.scatter(a[0],a[1], zorder=10, label=(f"{label_prefix} Assist" if add_legend and i==0 else None), **ASSIST_STYLE)
    for i in range(min(len(goals), len(assists))):
        g, a = goals[i], assists[i]
        ax.plot([a[0], g[0]], [a[1], g[1]], color="white", linestyle="--", linewidth=0.8, alpha=0.5, zorder=5)

# ======= Individuelle Analysen =======
@st.cache_data(show_spinner=False)
def list_individual_players(base: Path):
    if use_manifest():
        return players()
    return [p.name for p in sorted(base.iterdir()) if p.is_dir()] if base.exists() else []

@st.cache_data(show_spinner=False)
def list_player_files(player_dir):
    if use_manifest():
        name = getattr(player_dir, "name", None) or str(player_dir)
        return player_files(name)
    files = []
    if isinstance(player_dir, Path) and player_dir.exists():
        for f in sorted(player_dir.iterdir()):
            if f.is_file() and (f.suffix.lower() in DOC_EXTS or f.suffix.lower() in VIDEO_EXTS):
                files.append(f)
    return files

# ======= LineUp Open Helper =======
def render_lineup_open(team: str, key_suffix: str = ""):
    ppt = resolve_matchplan_ppt(team)
    if use_manifest():
        st.caption("LineUp-Öffnen ist online nicht verfügbar.")
        return
    if ppt and ppt.exists() and os.name == "nt":
        if st.button(f"📂 LineUp {team} öffnen", key=f"open_lineup_{key_suffix or team}"):
            try:
                os.startfile(str(ppt))
                st.toast(f"Öffne LineUp {team} …", icon="📂")
            except Exception as e:
                st.warning(f"Konnte LineUp nicht öffnen: {e}")
    else:
        st.caption("Kein LineUp gefunden.")

# ========================= RENDER-BLOCK (vergleichende Ansicht) =========================
def render_compare(goals_a, assists_a, label_a, goals_b, assists_b, label_b, team_a, team_b):
    # Zentrierter Wrapper
    left_pad, center, right_pad = st.columns([1, 12, 1], gap="small")
    with center:
        colA_field, colA_info, colB_field, colB_info = st.columns([3, 1, 3, 1], gap="small")

        # Team A Feld
        with colA_field:
            fig1, ax1 = plt.subplots(figsize=(3.5, 6.0))
            draw_pitch(ax1, team_a)
            plot_events(ax1, goals_a, assists_a, add_legend=True, label_prefix=label_a or team_a)
            ax1.legend(loc="lower left", fontsize=7)
            plt.title(label_a or team_a, fontsize=10)
            st.pyplot(fig1, use_container_width=True)

        # Team A Info + Torschützen + LineUp-Link
        with colA_info:
            st.markdown(f"<div class='small-heading'>🏆 Torschützen {team_a}</div>", unsafe_allow_html=True)
            vidsA_tmp = load_team_videos(team_a)
            scorer_data_a = extract_scorer_table(
                vidsA_tmp.get("Elfmeter", []) + vidsA_tmp.get("1 Touch", []) +
                vidsA_tmp.get("2 Touch", []) + vidsA_tmp.get("Sonstiges", [])
            )
            if scorer_data_a:
                counts = defaultdict(int)
                for row in scorer_data_a: counts[row["Spieler"]] += row["Tore"]
                for name, cnt in sorted(counts.items(), key=lambda x: x[1], reverse=True):
                    st.markdown(f"- {name} ({cnt} {'Tor' if cnt==1 else 'Tore'})")
            else:
                st.caption("Keine Torschützen-Daten verfügbar.")
            render_lineup_open(team_a, key_suffix="A")

        # Team B Feld
        with colB_field:
            fig2, ax2 = plt.subplots(figsize=(3.5, 6.0))
            draw_pitch(ax2, team_b)
            plot_events(ax2, goals_b, assists_b, add_legend=True, label_prefix=label_b or team_b)
            ax2.legend(loc="lower left", fontsize=7)
            plt.title(label_b or team_b, fontsize=10)
            st.pyplot(fig2, use_container_width=True)

        # Team B Info + Torschützen + LineUp-Link
        with colB_info:
            st.markdown(f"<div class='small-heading'>🏆 Torschützen {team_b}</div>", unsafe_allow_html=True)
            vidsB_tmp = load_team_videos(team_b)
            scorer_data_b = extract_scorer_table(
                vidsB_tmp.get("Elfmeter", []) + vidsB_tmp.get("1 Touch", []) +
                vidsB_tmp.get("2 Touch", []) + vidsB_tmp.get("Sonstiges", [])
            )
            if scorer_data_b:
                counts = defaultdict(int)
                for row in scorer_data_b: counts[row["Spieler"]] += row["Tore"]
                for name, cnt in sorted(counts.items(), key=lambda x: x[1], reverse=True):
                    st.markdown(f"- {name} ({cnt} {'Tor' if cnt==1 else 'Tore'})")
            else:
                st.caption("Keine Torschützen-Daten verfügbar.")
            render_lineup_open(team_b, key_suffix="B")

        # Videos & Torschützenlisten (Detail)
        colA_vids, colA_scorers = st.columns([3,1], gap="small")
        with colA_vids:
            vidsA = load_team_videos(team_a)
            cntE, cnt1, cnt2, cntS = len(vidsA['Elfmeter']), len(vidsA['1 Touch']), len(vidsA['2 Touch']), len(vidsA['Sonstiges'])
            radio_labels_A = [f"Elfmeter ({cntE})", f"1 Touch ({cnt1})", f"2 Touch ({cnt2})", f"Sonstiges ({cntS})"]
            radio_map_A = {radio_labels_A[i]: cat for i, cat in enumerate(['Elfmeter','1 Touch','2 Touch','Sonstiges'])}
            st.markdown(f"<div class='small-heading'>🎬 Tore {team_a}</div>", unsafe_allow_html=True)
            catA_label = st.radio("Kategorie", radio_labels_A, key="vid_cat_A", horizontal=True)
            filesA = vidsA.get(radio_map_A[catA_label], [])
            if filesA:
                labelsA = build_labels_with_roman(filesA)
                selA = st.selectbox("Tor auswählen", range(len(filesA)), key="vid_sel_A", format_func=lambda i: labelsA[i])
                display_video(filesA[selA])
            else:
                st.caption("Keine Videos in dieser Kategorie.")
        with colA_scorers:
            st.markdown(f"<div class='small-heading'>🏆 Torschützen {team_a}</div>", unsafe_allow_html=True)
            scorer_data_a = extract_scorer_table(
                vidsA.get("Elfmeter", []) + vidsA.get("1 Touch", []) +
                vidsA.get("2 Touch", []) + vidsA.get("Sonstiges", [])
            )
            if scorer_data_a:
                counts = defaultdict(int)
                for row in scorer_data_a: counts[row["Spieler"]] += row["Tore"]
                for name, cnt in sorted(counts.items(), key=lambda x: x[1], reverse=True):
                    st.markdown(f"- {name} ({cnt} {'Tor' if cnt==1 else 'Tore'})")
            else:
                st.caption("Keine Torschützen-Daten verfügbar.")
            render_lineup_open(team_a, key_suffix="A_bottom")

        colB_vids, colB_scorers = st.columns([3,1], gap="small")
        with colB_vids:
            vidsB = load_team_videos(team_b)
            cntE, cnt1, cnt2, cntS = len(vidsB['Elfmeter']), len(vidsB['1 Touch']), len(vidsB['2 Touch']), len(vidsB['Sonstiges'])
            radio_labels_B = [f"Elfmeter ({cntE})", f"1 Touch ({cnt1})", f"2 Touch ({cnt2})", f"Sonstiges ({cntS})"]
            radio_map_B = {radio_labels_B[i]: cat for i, cat in enumerate(['Elfmeter','1 Touch','2 Touch','Sonstiges'])}
            st.markdown(f"<div class='small-heading'>🎬 Tore {team_b}</div>", unsafe_allow_html=True)
            catB_label = st.radio("Kategorie", radio_labels_B, key="vid_cat_B", horizontal=True)
            filesB = vidsB.get(radio_map_B[catB_label], [])
            if filesB:
                labelsB = build_labels_with_roman(filesB)
                selB = st.selectbox("Tor auswählen", range(len(filesB)), key="vid_sel_B", format_func=lambda i: labelsB[i])
                display_video(filesB[selB])
            else:
                st.caption("Keine Videos in dieser Kategorie.")
        with colB_scorers:
            st.markdown(f"<div class='small-heading'>🏆 Torschützen {team_b}</div>", unsafe_allow_html=True)
            scorer_data_b = extract_scorer_table(
                vidsB.get("Elfmeter", []) + vidsB.get("1 Touch", []) +
                vidsB.get("2 Touch", []) + vidsB.get("Sonstiges", [])
            )
            if scorer_data_b:
                counts = defaultdict(int)
                for row in scorer_data_b: counts[row["Spieler"]] += row["Tore"]
                for name, cnt in sorted(counts.items(), key=lambda x: x[1], reverse=True):
                    st.markdown(f"- {name} ({cnt} {'Tor' if cnt==1 else 'Tore'})")
            else:
                st.caption("Keine Torschützen-Daten verfügbar.")
            render_lineup_open(team_b, key_suffix="B_bottom")

# ========================= Session-State Utils =========================
def ss_default(key, value):
    if key not in st.session_state:
        st.session_state[key] = value

def select_with_state(label, options, key, index=0, format_func=None):
    use_format = callable(format_func)
    if key in st.session_state:
        return st.selectbox(label, options, key=key, **({'format_func': format_func} if use_format else {}))
    kwargs = {'index': index, 'key': key}
    if use_format: kwargs['format_func'] = format_func
    return st.selectbox(label, options, **kwargs)

def select_idx_with_state(label, n_options, key, default_index=0, labels=None):
    options = list(range(n_options)); use_format = bool(labels)
    if key in st.session_state:
        return st.selectbox(label, options, key=key, **({'format_func': (lambda i: labels[i])} if use_format else {}))
    kwargs = {'index': default_index, 'key': key}
    if use_format: kwargs['format_func'] = (lambda i: labels[i])
    return st.selectbox(label, options, **kwargs)

def set_defaults(teams, file_index):
    team0 = PREFERRED_TEAM if PREFERRED_TEAM in teams else teams[0]
    files0 = file_index.get(team0, [])
    file_a_def = pick_file(files0,'own')
    file_b_def = pick_file(files0,'against')
    ss_default('tA', team0); ss_default('tB', team0)
    ss_default('fA_idx', files0.index(file_a_def) if (files0 and file_a_def in files0) else 0)
    ss_default('fB_idx', files0.index(file_b_def) if (files0 and file_b_def in files0) else 0)
    ss_default('modus', 'Dashboard')

# ========================= MAIN =========================
def main():
    base = BASE_DIR
    if not base.exists():
        st.error(f"Basisverzeichnis nicht gefunden: {base}")
        st.stop()

    teams, file_index = list_teams_and_files(base, preferred=PREFERRED_TEAM)
    if not teams:
        st.warning("Keine Mannschaftsordner gefunden."); st.stop()

    set_defaults(teams, file_index)

    # Sidebar
    with st.sidebar:
        modus = st.selectbox("Ansicht wählen", ["Dashboard", "Individuelle Analysen"], key="modus")

        if modus == "Dashboard":
            team_a = select_with_state("Team wählen", teams, key="tA", index=teams.index(st.session_state['tA']))
            files_a = file_index.get(team_a, [])
            file_labels_a = [f.name for f in files_a]
            desired_a = pick_file(files_a, 'own')
            default_idx_a = files_a.index(desired_a) if (files_a and desired_a in files_a) else 0
            idx_a = select_idx_with_state("Datei wählen", len(files_a), key="fA_idx", default_index=default_idx_a, labels=file_labels_a)

            team_b = select_with_state("Team wählen", teams, key="tB", index=teams.index(st.session_state['tB']))
            files_b = file_index.get(team_b, [])
            file_labels_b = [f.name for f in files_b]
            desired_b = pick_file(files_b, 'against')
            default_idx_b = files_b.index(desired_b) if (files_b and desired_b in files_b) else 0
            idx_b = select_idx_with_state("Datei wählen", len(files_b), key="fB_idx", default_index=default_idx_b, labels=file_labels_b)

            # Links ohne Zwischenabstände
            st.markdown("[📑 Zur aktuellen Tabelle](https://www.ligaportal.at/regionalliga-mitte/tabelle)")
            st.markdown("[📅 Spielplan JWR](https://vereine.oefb.at/SVOberbankRied/Mannschaften/Saison-2025-26/KM-Amat-/Spiele)")
            st.markdown("[🚫 Gesperrte Spieler](https://www.ofv.at/ofv/Spielbetrieb/Sperren/Gesperrte-Spieler)")
            st.markdown("### 🟨 Kartenwarnung")
            col_btn1, col_btn2 = st.columns([1,1])
            with col_btn1:
                if st.button("🟨", help="Kartenwarnung anzeigen", key="btn_show_warn"):
                    st.session_state.show_warnsystem = True; st.session_state.warnsystem_start = time.time()
            with col_btn2:
                if st.button("✖️", help="Ausblenden", key="btn_hide_warn"):
                    st.session_state.show_warnsystem = False

        else:
            st.caption("<div class='sidebar-caption'>Modus: Individuelle Analysen</div>", unsafe_allow_html=True)
            st.markdown("[🏠 zurück zum Dashboard](/)")

    modus = st.session_state.get("modus","Dashboard")

    if modus == "Dashboard":
        # Kartenwarnsystem
        if st.session_state.get("show_warnsystem"):
            start = st.session_state.get("warnsystem_start", 0); now = time.time()
            if now - start <= 60:
                st.subheader("🟨 Gelbe Karten Warnsystem")
                url = "https://vereine.oefb.at/SVOberbankRied/Mannschaften/Saison-2025-26/KM-Amat-/Kader"
                cols = st.columns([1,1,1,1,2])
                with cols[0]: art = st.selectbox("Art", ["Gelb","Gelb-Rot","Rot"], help="Welche Karten-Art prüfen?")
                with cols[1]: thresh = st.number_input("Schwellwert", min_value=1, max_value=10, value=3, step=1)
                with cols[2]: show_all = st.checkbox("Alle Spieler anzeigen", value=False)
                with cols[3]: do_refresh = st.button("🔄 Neu laden")
                with cols[4]: st.caption(f"Letzte Prüfung: {time.strftime('%H:%M:%S')}")
                try:
                    headers = {"Cache-Control": "no-cache","User-Agent":"Mozilla/5.0"} if do_refresh else {"User-Agent":"Mozilla/5.0"}
                    html = requests.get(url, timeout=10, headers=headers).text
                    kader = extrahiere_kaderdaten(html)
                except Exception as e:
                    st.error(f"Kaderdaten konnten nicht geladen werden: {e}"); kader = []
                df = pd.DataFrame(kader) if kader else pd.DataFrame(columns=["spielerName","kartenGelb","kartenGelbRot","kartenRot","spielerProfilUrl"])
                if not df.empty:
                    df["kartenGelb"] = pd.to_numeric(df.get("kartenGelb",0), errors="coerce").fillna(0).astype(int)
                    df["kartenGelbRot"] = pd.to_numeric(df.get("kartenGelbRot",0), errors="coerce").fillna(0).astype(int)
                    df["kartenRot"] = pd.to_numeric(df.get("kartenRot",0), errors="coerce").fillna(0).astype(int)
                    df = df.rename(columns={"spielerName":"Spieler","kartenGelb":"Gelb","kartenGelbRot":"Gelb-Rot","kartenRot":"Rot","spielerProfilUrl":"Profil"})
                    sel_col = {"Gelb":"Gelb","Gelb-Rot":"Gelb-Rot","Rot":"Rot"}[art]
                    warn_df = df[df[sel_col] >= int(thresh)].sort_values([sel_col,"Spieler"], ascending=[False,True])
                    if not warn_df.empty:
                        st.warning(f"⚠️ Spieler mit ≥ {int(thresh)} {sel_col}:")
                        st.dataframe(warn_df[["Spieler", sel_col]], use_container_width=True, hide_index=True)
                    else:
                        st.success(f"✅ Kein Spieler mit ≥ {int(thresh)} {sel_col}")
                    if show_all:
                        st.markdown(f"### Übersicht {sel_col} (alle)")
                        st.dataframe(df[["Spieler", sel_col]].sort_values([sel_col,"Spieler"], ascending=[False,True]), use_container_width=True, hide_index=True)
                else:
                    st.info("Keine Kaderdaten gefunden.")
            else:
                st.session_state.show_warnsystem = False

        # Titel (ohne Logos im Kopf)
        st.markdown("<h4 class='page-title'>📊 Dashboard</h4>", unsafe_allow_html=True)

        # Dateien aus Auswahl
        files_a = file_index.get(st.session_state['tA'], [])
        file_a = files_a[st.session_state['fA_idx']] if files_a else None
        files_b = file_index.get(st.session_state['tB'], [])
        file_b = files_b[st.session_state['fB_idx']] if files_b else None

        goals_a, assists_a, title_a = parse_goals_assists(file_a) if file_a else ([],[],None)
        goals_b, assists_b, title_b = parse_goals_assists(file_b) if file_b else ([],[],None)

        render_compare(goals_a, assists_a, title_a or f"{st.session_state['tA']}",
                       goals_b, assists_b, title_b or f"{st.session_state['tB']}",
                       st.session_state['tA'], st.session_state['tB'])

        # Torschützen-Tabs
        vidsA_all = load_team_videos(st.session_state['tA'])
        vidsB_all = load_team_videos(st.session_state['tB'])
        scorer_data_a = extract_scorer_table(vidsA_all.get("Elfmeter", []) + vidsA_all.get("1 Touch", []) + vidsA_all.get("2 Touch", []) + vidsA_all.get("Sonstiges", []))
        scorer_data_b = extract_scorer_table(vidsB_all.get("Elfmeter", []) + vidsB_all.get("1 Touch", []) + vidsB_all.get("2 Touch", []) + vidsB_all.get("Sonstiges", []))

        if scorer_data_a or scorer_data_b:
            tab1, tab2 = st.tabs([f"Torschützen {st.session_state['tA']}", f"Torschützen {st.session_state['tB']}"])
            with tab1:
                if scorer_data_a:
                    grouped = defaultdict(lambda: {"Tore":0,"Details":[]})
                    for row in scorer_data_a:
                        grouped[row["Spieler"]]["Tore"] += row["Tore"]
                        for video in row["Videos"]:
                            grouped[row["Spieler"]]["Details"].append({"Video": video, "Kategorie": row["Kategorie"], "Gegner": row["Gegner"]})
                    for name, data in sorted(grouped.items(), key=lambda x: x[1]["Tore"], reverse=True):
                        st.markdown(f"### {name} ({data['Tore']} {'Tor' if data['Tore']==1 else 'Tore'})")
                        for detail in data["Details"]:
                            with st.expander(f"▶️ {name} – {detail['Kategorie']} vs. {detail['Gegner']}"):
                                display_video(detail["Video"])
                    # LineUp-Link für Team A auch hier am Ende
                    render_lineup_open(st.session_state['tA'], key_suffix="A_tab")
                else:
                    st.caption("Keine Torschützen-Daten für Team A verfügbar.")
            with tab2:
                if scorer_data_b:
                    grouped = defaultdict(lambda: {"Tore":0,"Details":[]})
                    for row in scorer_data_b:
                        grouped[row["Spieler"]]["Tore"] += row["Tore"]
                        for video in row["Videos"]:
                            grouped[row["Spieler"]]["Details"].append({"Video": video, "Kategorie": row["Kategorie"], "Gegner": row["Gegner"]})
                    for name, data in sorted(grouped.items(), key=lambda x: x[1]["Tore"], reverse=True):
                        st.markdown(f"### {name} ({data['Tore']} {'Tor' if data['Tore']==1 else 'Tore'})")
                        for detail in data["Details"]:
                            with st.expander(f"▶️ {name} – {detail['Kategorie']} vs. {detail['Gegner']}"):
                                display_video(detail["Video"])
                    # LineUp-Link für Team B am Ende
                    render_lineup_open(st.session_state['tB'], key_suffix="B_tab")
                else:
                    st.caption("Keine Torschützen-Daten für Team B verfügbar.")

    else:
        st.markdown("<h4 class='page-title'>🧭 Individuelle Analysen</h4>", unsafe_allow_html=True)
        players = list_individual_players(IND_ANALYSEN_BASE)
        if not players:
            st.info(f"Keine Spieler-Ordner gefunden unter: {IND_ANALYSEN_BASE}")
            st.stop()

        # CSS nur für diese Seite: Video-Vorschauen klein halten
        st.markdown(
            """
            <style>
              #ind-previews div[data-testid="stVideo"] video {
                width: 220px !important;
                height: auto !important;
              }
            </style>
            """, unsafe_allow_html=True
        )

        st.markdown("<div class='card' id='ind-previews'>", unsafe_allow_html=True)

        player = st.selectbox("Spieler wählen", players, key="ind_player_center")
        pdir = IND_ANALYSEN_BASE / player
        pfiles = list_player_files(pdir)

        if not pfiles:
            st.caption("Keine Dateien im gewählten Ordner.")
            st.markdown("</div>", unsafe_allow_html=True)
            st.stop()

        videos = [f for f in pfiles if _is_video(f)]
        if not videos:
            st.caption("Keine Videos vorhanden.")
            st.markdown("</div>", unsafe_allow_html=True)
            st.stop()

        # Überschrift mit vollständigem Spielernamen
        st.markdown(f"### {player} – {len(videos)} Video‑Vorschauen")

        # Grid: 4 Spalten, oben jeweils Dateiname fett
        cols = st.columns(4, gap="small")
        for i, vf in enumerate(videos):
            with cols[i % 4]:
                st.markdown(f"<div class='filename'>{player} — {vf.name}</div>", unsafe_allow_html=True)
                display_video(vf)

        st.markdown("</div>", unsafe_allow_html=True)

# Entry point
if __name__ == "__main__":
    main()
