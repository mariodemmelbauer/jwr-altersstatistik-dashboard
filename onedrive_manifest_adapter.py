# onedrive_manifest_adapter.py
# Drop-in Adapter für Streamlit-Apps: Weg A (OneDrive-Manifest)
from __future__ import annotations
import json, requests, streamlit as st
from typing import Dict, List, Any, Union

def use_manifest() -> bool:
    return st.secrets.get("onedrive", {}).get("mode", "local") == "manifest"

@st.cache_data(show_spinner=False, ttl=300)
def load_manifest() -> Dict[str, Any]:
    url = st.secrets["onedrive"]["manifest_url"]
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.json()

def team_videos(team: str) -> Dict[str, List[Dict[str, str]]]:
    man = load_manifest()
    vids = man.get("videos", {}).get(team, {})
    return {
        "Elfmeter": vids.get("Elfmeter", []),
        "1 Touch": vids.get("1 Touch", []),
        "2 Touch": vids.get("2 Touch", []),
        "Sonstiges": vids.get("Sonstiges", []),
    }

def players() -> List[str]:
    man = load_manifest()
    return sorted(man.get("analysen", {}).keys())

def player_files(player: str) -> List[Dict[str, str]]:
    man = load_manifest()
    return man.get("analysen", {}).get(player, [])

def team_plot_files(team: str) -> List[Dict[str, str]]:
    man = load_manifest()
    return man.get("plots_base", {}).get(team, [])

@st.cache_data(show_spinner=False)
def fetch_text(url: str) -> str:
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.text

# Helper, um lokale Pfad-Consumer weiterzuverwenden
def is_url_ref(obj: Any) -> bool:
    return isinstance(obj, dict) and "url" in obj

def display_video(item: Union[Dict[str,str], str]):
    if isinstance(item, dict):
        label = item.get("label") or item.get("name", "Video")
        if label:
            st.caption(label)
        st.video(item["url"])
    else:
        st.video(str(item))
