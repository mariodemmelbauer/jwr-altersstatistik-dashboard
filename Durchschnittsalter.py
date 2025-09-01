import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import datetime, date
import plotly.subplots as make_subplots

# Seite konfigurieren
st.set_page_config(
    page_title="SK Rapid Wien II - Durchschnittsalter Dashboard",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS für besseres Styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1.5rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 12px;
        color: white;
        text-align: center;
        box-shadow: 0 6px 24px rgba(0,0,0,0.1);
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: bold;
        margin-bottom: 0.3rem;
    }
    .metric-label {
        font-size: 0.9rem;
        opacity: 0.9;
    }
    .stPlotlyChart {
        border-radius: 12px;
        box-shadow: 0 3px 12px rgba(0,0,0,0.1);
    }
    .team-info {
        background: linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%);
        padding: 0.8rem;
        border-radius: 8px;
        color: white;
        text-align: center;
        margin-bottom: 0.8rem;
    }
</style>
""", unsafe_allow_html=True)

# Funktion zum Laden der Excel-Daten
@st.cache_data
def load_excel_data():
    try:
        # Excel-Datei laden
        excel_path = "Statistik Altersdurchschnitt.xlsx"
        df = pd.read_excel(excel_path)
        
        # Spaltennamen bereinigen
        df.columns = ['Team', 'Altersdurchschnitt']
        
        # Daten sortieren nach Altersdurchschnitt
        df = df.sort_values('Altersdurchschnitt')
        
        return df
    except Exception as e:
        st.error(f"Fehler beim Laden der Excel-Datei: {e}")
        return None

# Team-Farben definieren
TEAM_COLORS = {
    'Liefering': ['#FF0000', '#FFFFFF'],      # Rot-Weiß
    'Altach': ['#FFD700', '#000000'],         # Gelb-Schwarz
    'Rapid': ['#90EE90', '#FFFFFF'],          # Hellgrün-Weiß
    'JWR': ['#006400', '#000000'],            # Dunkelgrün-Schwarz
    'LASK': ['#000000', '#FFFFFF'],           # Schwarz-Weiß
    'Sturm': ['#000000', '#C0C0C0'],          # Schwarz-Gepunktet (Silber)
    'Young Violetts': ['#800080', '#FFFFFF'], # Violett-Weiß
    'WAC': ['#000000', '#FFFFFF']             # Schwarz-Gestreift (Schwarz-Weiß)
}

# Funktion zum Laden der echten Geburtsdaten aus den Mannschaftsblättern
@st.cache_data
def load_birth_quarter_data():
    """Lädt echte Geburtsdaten aus den Mannschaftsblättern der Excel-Datei"""
    try:
        excel_path = "Statistik Altersdurchschnitt.xlsx"
        
        # Mapping der Blattnamen zu den Team-Namen
        sheet_team_mapping = {
            'Liefering': 'Liefering',
            'Altach Juniors': 'Altach',
            'Rapid': 'Rapid',
            'JWR': 'JWR',
            'LASK': 'LASK',
            'Sturm': 'Sturm',
            'Young Violets': 'Young Violetts',
            'WAC': 'WAC'
        }
        
        birth_quarter_data = []
        
        for sheet_name, team_name in sheet_team_mapping.items():
            try:
                # Lade das Mannschaftsblatt
                df_sheet = pd.read_excel(excel_path, sheet_name=sheet_name)
                
                # Prüfe ob Spalte Q existiert (Geburtsdaten)
                if 'Q' in df_sheet.columns or len(df_sheet.columns) >= 17:  # Spalte Q ist die 17. Spalte
                    # Verwende die 17. Spalte (Index 16) für Geburtsdaten
                    birth_column = df_sheet.iloc[:, 16]  # Spalte Q (0-basiert: 16)
                    
                    # Filtere gültige Geburtsdaten (nicht NaN)
                    valid_birth_dates = birth_column.dropna()
                    
                    if len(valid_birth_dates) > 0:
                        # Konvertiere zu Datetime falls möglich
                        try:
                            birth_dates = pd.to_datetime(valid_birth_dates, errors='coerce')
                            birth_dates = birth_dates.dropna()
                            
                            if len(birth_dates) > 0:
                                # Bestimme Quartale
                                q1_count = len(birth_dates[birth_dates.dt.quarter == 1])  # Jan-März
                                q2_count = len(birth_dates[birth_dates.dt.quarter == 2])  # Apr-Jun
                                q3_count = len(birth_dates[birth_dates.dt.quarter == 3])  # Jul-Sep
                                q4_count = len(birth_dates[birth_dates.dt.quarter == 4])  # Okt-Dez
                                total_count = len(birth_dates)
                                
                                birth_quarter_data.append({
                                    'Team': team_name,
                                    'Q1_Jan_Mar': q1_count,
                                    'Q2_Apr_Jun': q2_count,
                                    'Q3_Jul_Sep': q3_count,
                                    'Q4_Oct_Dec': q4_count,
                                    'Gesamt': total_count
                                })
                            else:
                                # Fallback: Keine gültigen Datumsdaten
                                birth_quarter_data.append({
                                    'Team': team_name,
                                    'Q1_Jan_Mar': 0,
                                    'Q2_Apr_Jun': 0,
                                    'Q3_Jul_Sep': 0,
                                    'Q4_Oct_Dec': 0,
                                    'Gesamt': 0
                                })
                        except:
                            # Fallback: Zähle alle nicht-leeren Einträge
                            total_count = len(valid_birth_dates)
                            # Gleichmäßige Verteilung als Fallback
                            q1_count = total_count // 4
                            q2_count = total_count // 4
                            q3_count = total_count // 4
                            q4_count = total_count - q1_count - q2_count - q3_count
                            
                            birth_quarter_data.append({
                                'Team': team_name,
                                'Q1_Jan_Mar': q1_count,
                                'Q2_Apr_Jun': q2_count,
                                'Q3_Jul_Sep': q3_count,
                                'Q4_Oct_Dec': q4_count,
                                'Gesamt': total_count
                            })
                    else:
                        # Keine Geburtsdaten gefunden
                        birth_quarter_data.append({
                            'Team': team_name,
                            'Q1_Jan_Mar': 0,
                            'Q2_Apr_Jun': 0,
                            'Q3_Jul_Sep': 0,
                            'Q4_Oct_Dec': 0,
                            'Gesamt': 0
                        })
                else:
                    # Spalte Q nicht gefunden
                    birth_quarter_data.append({
                        'Team': team_name,
                        'Q1_Jan_Mar': 0,
                        'Q2_Apr_Jun': 0,
                        'Q3_Jul_Sep': 0,
                        'Q4_Oct_Dec': 0,
                        'Gesamt': 0
                    })
                    
            except Exception as e:
                st.warning(f"Fehler beim Laden von {sheet_name}: {e}")
                # Fallback-Daten für dieses Team
                birth_quarter_data.append({
                    'Team': team_name,
                    'Q1_Jan_Mar': 0,
                    'Q2_Apr_Jun': 0,
                    'Q3_Jul_Sep': 0,
                    'Q4_Oct_Dec': 0,
                    'Gesamt': 0
                })
        
        if not birth_quarter_data:
            st.error("❌ Konnte keine Geburtsdaten aus den Mannschaftsblättern laden.")
            return None
            
        return pd.DataFrame(birth_quarter_data)
        
    except Exception as e:
        st.error(f"Fehler beim Laden der Geburtsdaten: {e}")
        return None

# Geburtsquartal-Daten laden
df_birth_quarters = load_birth_quarter_data()

if df_birth_quarters is None:
    st.error("❌ Konnte Geburtsdaten nicht laden. Verwende Beispieldaten.")
    # Fallback zu Beispieldaten
    df_birth_quarters = pd.DataFrame({
        'Team': ['Liefering', 'Altach', 'Rapid', 'JWR', 'LASK', 'Sturm', 'Young Violetts', 'WAC'],
        'Q1_Jan_Mar': [5, 4, 6, 3, 5, 4, 3, 4],
        'Q2_Apr_Jun': [3, 4, 2, 4, 3, 3, 4, 3],
        'Q3_Jul_Sep': [2, 3, 3, 3, 2, 2, 3, 2],
        'Q4_Oct_Dec': [3, 2, 2, 3, 3, 4, 3, 4],
        'Gesamt': [13, 13, 13, 13, 13, 13, 13, 13]
    })

# Standardfarbe für unbekannte Teams
DEFAULT_COLOR = '#1f77b4'

def get_team_color(team_name):
    """Gibt die Farbe für ein Team zurück"""
    for team_key, colors in TEAM_COLORS.items():
        if team_key.lower() in team_name.lower():
            return colors[0]  # Hauptfarbe verwenden
    return DEFAULT_COLOR

def get_team_colors_list(teams):
    """Gibt eine Liste von Farben für alle Teams zurück"""
    return [get_team_color(team) for team in teams]

# Excel-Daten laden
df_teams = load_excel_data()

if df_teams is None:
    st.error("❌ Konnte Excel-Datei nicht laden. Bitte überprüfen Sie den Dateipfad.")
    st.stop()

# Haupttitel
st.markdown('<h1 class="main-header">⚽ Durchschnittsalter Dashboard Amateur-Teams</h1>', unsafe_allow_html=True)
st.markdown('<p style="text-align: center; font-size: 1.2rem; color: #666;">Saison 2025/26 - Alle Teams</p>', unsafe_allow_html=True)

# Team-Auswahl (ohne Sidebar-Header)
# Index für JWR finden (falls vorhanden) und in int konvertieren
jwr_index = 0
if 'JWR' in df_teams['Team'].values:
    jwr_index = int(df_teams[df_teams['Team'] == 'JWR'].index[0])

selected_team = st.sidebar.selectbox(
    "Wählen Sie ein Team aus:",
    options=df_teams['Team'].tolist(),
    index=jwr_index
)

# Gefilterte Daten für das ausgewählte Team
team_data = df_teams[df_teams['Team'] == selected_team].iloc[0]
team_age = team_data['Altersdurchschnitt']

# Hauptmetriken in einer Zeile (alle gleiche Höhe, farblich nach Teams)
col1, col2, col3, col4, col5 = st.columns([1.5, 1, 1, 1, 1])

# Team-Farben für verschiedene Metriken
selected_team_color = get_team_color(selected_team)
youngest_team = df_teams.iloc[0]['Team']  # Jüngstes Team
youngest_team_color = get_team_color(youngest_team)

with col1:
    # Team-Info als metric-card für gleiche Höhe
    st.markdown(f"""
    <div class="metric-card" style="background: linear-gradient(135deg, {selected_team_color} 0%, {selected_team_color}dd 100%);">
        <div class="metric-value">🏆 {selected_team}</div>
        <div class="metric-label">Startelf: {team_age:.2f} Jahre</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    # Team Durchschnittsalter
    st.markdown(f"""
    <div class="metric-card" style="background: linear-gradient(135deg, {selected_team_color} 0%, {selected_team_color}dd 100%);">
        <div class="metric-value">{team_age:.2f}</div>
        <div class="metric-label">Team Ø</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    # Position in der Liga
    team_position = df_teams[df_teams['Altersdurchschnitt'] <= team_age].shape[0]
    st.markdown(f"""
    <div class="metric-card" style="background: linear-gradient(135deg, {selected_team_color} 0%, {selected_team_color}dd 100%);">
        <div class="metric-value">{team_position}</div>
        <div class="metric-label">Position</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    # Differenz zum jüngsten Team
    youngest_age = df_teams['Altersdurchschnitt'].min()
    age_diff = team_age - youngest_age
    st.markdown(f"""
    <div class="metric-card" style="background: linear-gradient(135deg, {youngest_team_color} 0%, {youngest_team_color}dd 100%);">
        <div class="metric-value">{age_diff:.2f}</div>
        <div class="metric-label">Differenz zu {youngest_team}</div>
    </div>
    """, unsafe_allow_html=True)

with col5:
    # Durchschnittsalter aller Teams
    overall_avg = df_teams['Altersdurchschnitt'].mean()
    st.markdown(f"""
    <div class="metric-card" style="background: linear-gradient(135deg, #1f77b4 0%, #1f77b4dd 100%);">
        <div class="metric-value">{overall_avg:.2f}</div>
        <div class="metric-label">Ø Teams</div>
    </div>
    """, unsafe_allow_html=True)



st.markdown("---")

# Hauptvisualisierungen
col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("## 📊 Altersdurchschnitt aller Teams")
    
    # Balkendiagramm aller Teams mit Team-Farben
    fig = go.Figure()
    
    # Jedes Team mit seiner spezifischen Farbe hinzufügen
    for i, team in enumerate(df_teams['Team']):
        team_age_val = df_teams.iloc[i]['Altersdurchschnitt']
        team_color = get_team_color(team)
        
        fig.add_trace(go.Bar(
            x=[team],
            y=[team_age_val],
            name=team,
            marker_color=team_color,
            showlegend=False
        ))
    
    # Ausgewähltes Team hervorheben
    fig.add_hline(
        y=team_age,
        line_dash="dash",
        line_color="red",
        line_width=3,
        annotation_text=f"{selected_team}: {team_age:.2f} Jahre"
    )
    
    fig.update_layout(
        title="Vergleich der Altersdurchschnitte aller Teams",
        xaxis_title="Team",
        yaxis_title="Altersdurchschnitt (Jahre)",
        template='plotly_white',
        height=400,
        showlegend=False
    )
    
    # Y-Achse auf Bereich 18-22 Jahre skalieren
    fig.update_yaxes(range=[18, 22])
    
    st.plotly_chart(fig, use_container_width=True)

# Team-Details in der linken Spalte unter dem Diagramm
with col1:
    st.markdown("## 📋 Team-Details")
    
    # Tabelle mit allen Teams, Q1+Q2 und Q3+Q4 Spielern
    if df_birth_quarters is not None:
        # Erstelle erweiterte Tabelle mit Q1+Q2 und Q3+Q4 Daten
        team_details_df = df_teams.copy()
        
        # Füge Q1+Q2 und Q3+Q4 Spalten hinzu
        for i, team in enumerate(team_details_df['Team']):
            if team in df_birth_quarters['Team'].values:
                team_q1 = df_birth_quarters[df_birth_quarters['Team'] == team]['Q1_Jan_Mar'].iloc[0]
                team_q2 = df_birth_quarters[df_birth_quarters['Team'] == team]['Q2_Apr_Jun'].iloc[0]
                team_q3 = df_birth_quarters[df_birth_quarters['Team'] == team]['Q3_Jul_Sep'].iloc[0]
                team_q4 = df_birth_quarters[df_birth_quarters['Team'] == team]['Q4_Oct_Dec'].iloc[0]
                team_q1_q2 = team_q1 + team_q2
                team_q3_q4 = team_q3 + team_q4
                team_details_df.loc[i, 'Q1_Q2_Spieler'] = team_q1_q2
                team_details_df.loc[i, 'Q3_Q4_Spieler'] = team_q3_q4
            else:
                team_details_df.loc[i, 'Q1_Q2_Spieler'] = 0
                team_details_df.loc[i, 'Q3_Q4_Spieler'] = 0
        
        # Formatiere die Tabelle mit visuell zentrierten Zahlen
        # Erstelle eine Kopie für die Formatierung
        display_df = team_details_df.copy()
        
        # Formatiere Zahlen mit Leerzeichen für visuelle Zentrierung
        display_df['Altersdurchschnitt'] = display_df['Altersdurchschnitt'].apply(lambda x: f"{x:.2f}")
        display_df['Q1_Q2_Spieler'] = display_df['Q1_Q2_Spieler'].apply(lambda x: f"{x:>3}")
        display_df['Q3_Q4_Spieler'] = display_df['Q3_Q4_Spieler'].apply(lambda x: f"{x:>3}")
        
        st.dataframe(
            display_df,
            use_container_width=False,
            width=800,
            height=None
        )
    else:
        # Fallback: Normale Tabelle ohne Q1+Q2 und Q3+Q4
        st.dataframe(
            df_teams.style.format({'Altersdurchschnitt': '{:.2f}'}),
            use_container_width=False,
            width=800,
            height=None
        )

with col2:
    st.markdown("## 📈 Statistiken")
    
    # Zusammenfassungsstatistiken - kompakter
    st.markdown("### Liga-Übersicht")
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(f"**Jüngstes:** {df_teams.iloc[0]['Team']} ({df_teams.iloc[0]['Altersdurchschnitt']:.1f})")
        st.markdown(f"**Ältestes:** {df_teams.iloc[-1]['Team']} ({df_teams.iloc[-1]['Altersdurchschnitt']:.1f})")
    with col_b:
        st.markdown(f"**Ø Teams:** {overall_avg:.1f}")
        team_rank = df_teams[df_teams['Team'] == selected_team].index[0] + 1
        st.markdown(f"**Position:** {team_rank}/{len(df_teams)}")
    


# Team-Details bereits über dem Diagramm angezeigt

st.markdown("---")

# Dritte Zeile - Geburtsquartal-Analyse
st.markdown("## 🎂 Geburtsquartal-Analyse der Spieler")

col1, col2 = st.columns(2)

with col1:
    st.markdown("### 📊 Spieler pro Geburtsquartal")
    
    # Stacked Bar Chart für alle Teams
    fig = go.Figure()
    
    # Q1 (Jan-März) - Wichtigstes Quartal
    fig.add_trace(go.Bar(
        name='Q1 (Jan-März)',
        x=df_birth_quarters['Team'],
        y=df_birth_quarters['Q1_Jan_Mar'],
        marker_color='#FF6B6B',  # Rot für Q1
        text=df_birth_quarters['Q1_Jan_Mar'],
        textposition='auto'
    ))
    
    # Q2 (Apr-Jun)
    fig.add_trace(go.Bar(
        name='Q2 (Apr-Jun)',
        x=df_birth_quarters['Team'],
        y=df_birth_quarters['Q2_Apr_Jun'],
        marker_color='#4ECDC4',  # Türkis für Q2
        text=df_birth_quarters['Q2_Apr_Jun'],
        textposition='auto'
    ))
    
    # Q3 (Jul-Sep)
    fig.add_trace(go.Bar(
        name='Q3 (Jul-Sep)',
        x=df_birth_quarters['Team'],
        y=df_birth_quarters['Q3_Jul_Sep'],
        marker_color='#45B7D1',  # Blau für Q3
        text=df_birth_quarters['Q3_Jul_Sep'],
        textposition='auto'
    ))
    
    # Q4 (Okt-Dez)
    fig.add_trace(go.Bar(
        name='Q4 (Okt-Dez)',
        x=df_birth_quarters['Team'],
        y=df_birth_quarters['Q4_Oct_Dec'],
        marker_color='#96CEB4',  # Grün für Q4
        text=df_birth_quarters['Q4_Oct_Dec'],
        textposition='auto'
    ))
    
    fig.update_layout(
        title="Verteilung der Spieler nach Geburtsquartalen pro Team",
        xaxis_title="Team",
        yaxis_title="Anzahl Spieler",
        template='plotly_white',
        height=500,
        barmode='stack'
    )
    
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.markdown("### 🎯 Fokus: Q1 und Q2 (Jan-Jun) Spieler")
    
    # Q1 + Q2 Spieler als separate Metrik
    q1_q2_data = df_birth_quarters[['Team', 'Q1_Jan_Mar', 'Q2_Apr_Jun', 'Gesamt']].copy()
    q1_q2_data['Q1_Q2_Jan_Jun'] = q1_q2_data['Q1_Jan_Mar'] + q1_q2_data['Q2_Apr_Jun']
    q1_q2_data['Q1_Q2_Prozent'] = (q1_q2_data['Q1_Q2_Jan_Jun'] / q1_q2_data['Gesamt'] * 100).round(1)
    
    # Q1+Q2 Balkendiagramm mit Team-Farben
    fig = go.Figure()
    
    for i, team in enumerate(q1_q2_data['Team']):
        q1_q2_count = q1_q2_data.iloc[i]['Q1_Q2_Jan_Jun']
        team_color = get_team_color(team)
        
        fig.add_trace(go.Bar(
            x=[team],
            y=[q1_q2_count],
            name=team,
            marker_color=team_color,
            text=f"{q1_q2_count} ({q1_q2_data.iloc[i]['Q1_Q2_Prozent']}%)",
            textposition='auto',
            showlegend=False
        ))
    
    fig.update_layout(
        title="Spieler im Q1 und Q2 (Jan-Jun) pro Team",
        xaxis_title="Team",
        yaxis_title="Anzahl Q1+Q2-Spieler",
        template='plotly_white',
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)

# Fünfte Zeile - Detaillierte Q1+Q2-Analyse
st.markdown("---")
st.markdown("## 📈 Detaillierte Q1+Q2 (Jan-Jun) Analyse")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### 🏆 Q1+Q2-Ranking")
    
    # Q1+Q2-Ranking nach Anzahl Spieler
    q1_q2_ranking = q1_q2_data.sort_values('Q1_Q2_Jan_Jun', ascending=False)
    
    for i, (_, row) in enumerate(q1_q2_ranking.iterrows()):
        team_name = row['Team']
        q1_q2_count = row['Q1_Q2_Jan_Jun']
        percentage = row['Q1_Q2_Prozent']
        
        # Emoji für Top 3
        if i == 0:
            medal = "🥇"
        elif i == 1:
            medal = "🥈"
        elif i == 2:
            medal = "🥉"
        else:
            medal = f"{i+1}."
        
        st.metric(f"{medal} {team_name}", f"{q1_q2_count} Spieler", f"{percentage}%")

with col2:
    st.markdown("### 📊 Q1+Q2-Statistiken")
    
    total_q1_q2 = q1_q2_data['Q1_Q2_Jan_Jun'].sum()
    total_players = q1_q2_data['Gesamt'].sum()
    overall_q1_q2_percentage = (total_q1_q2 / total_players * 100).round(1)
    
    st.metric("Gesamt Q1+Q2-Spieler", f"{total_q1_q2}")
    st.metric("Gesamt Spieler", f"{total_players}")
    st.metric("Liga Q1+Q2-Anteil", f"{overall_q1_q2_percentage}%")
    
    # Durchschnitt Q1+Q2 pro Team
    avg_q1_q2 = q1_q2_data['Q1_Q2_Jan_Jun'].mean()
    st.metric("Ø Q1+Q2 pro Team", f"{avg_q1_q2:.1f}")

with col3:
    st.markdown("### 📋 Q1+Q2-Details")
    
    # Tabelle mit Q1+Q2-Daten
    display_df = q1_q2_data[['Team', 'Q1_Jan_Mar', 'Q2_Apr_Jun', 'Q1_Q2_Jan_Jun', 'Gesamt', 'Q1_Q2_Prozent']].copy()
    display_df.columns = ['Team', 'Q1 (Jan-März)', 'Q2 (Apr-Jun)', 'Q1+Q2 (Jan-Jun)', 'Gesamt', 'Q1+Q2 %']
    
    st.dataframe(
        display_df.style.format({'Q1 (Jan-März)': '{:.0f}', 'Q2 (Apr-Jun)': '{:.0f}', 'Q1+Q2 (Jan-Jun)': '{:.0f}', 'Gesamt': '{:.0f}', 'Q1+Q2 %': '{:.1f}%'}),
        use_container_width=True,
        height=300
    )

st.markdown("---")

# Sechste Zeile - Detaillierte Q3+Q4-Analyse
st.markdown("## 📈 Detaillierte Q3+Q4 (Jul-Dez) Analyse")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### 🏆 Q3+Q4-Ranking")
    
    # Q3+Q4-Ranking nach Anzahl Spieler
    q3_q4_data = df_birth_quarters[['Team', 'Q3_Jul_Sep', 'Q4_Oct_Dec', 'Gesamt']].copy()
    q3_q4_data['Q3_Q4_Jul_Dec'] = q3_q4_data['Q3_Jul_Sep'] + q3_q4_data['Q4_Oct_Dec']
    q3_q4_data['Q3_Q4_Prozent'] = (q3_q4_data['Q3_Q4_Jul_Dec'] / q3_q4_data['Gesamt'] * 100).round(1)
    
    q3_q4_ranking = q3_q4_data.sort_values('Q3_Q4_Jul_Dec', ascending=False)
    
    for i, (_, row) in enumerate(q3_q4_ranking.iterrows()):
        team_name = row['Team']
        q3_q4_count = row['Q3_Q4_Jul_Dec']
        percentage = row['Q3_Q4_Prozent']
        
        # Emoji für Top 3
        if i == 0:
            medal = "🥇"
        elif i == 1:
            medal = "🥈"
        elif i == 2:
            medal = "🥉"
        else:
            medal = f"{i+1}."
        
        st.metric(f"{medal} {team_name}", f"{q3_q4_count} Spieler", f"{percentage}%")

with col2:
    st.markdown("### 📊 Q3+Q4-Statistiken")
    
    total_q3_q4 = q3_q4_data['Q3_Q4_Jul_Dec'].sum()
    total_players = q3_q4_data['Gesamt'].sum()
    overall_q3_q4_percentage = (total_q3_q4 / total_players * 100).round(1)
    
    st.metric("Gesamt Q3+Q4-Spieler", f"{total_q3_q4}")
    st.metric("Gesamt Spieler", f"{total_players}")
    st.metric("Liga Q3+Q4-Anteil", f"{overall_q3_q4_percentage}%")
    
    # Durchschnitt Q3+Q4 pro Team
    avg_q3_q4 = q3_q4_data['Q3_Q4_Jul_Dec'].mean()
    st.metric("Ø Q3+Q4 pro Team", f"{avg_q3_q4:.1f}")

with col3:
    st.markdown("### 📋 Q3+Q4-Details")
    
    # Tabelle mit Q3+Q4-Daten
    display_df = q3_q4_data[['Team', 'Q3_Jul_Sep', 'Q4_Oct_Dec', 'Q3_Q4_Jul_Dec', 'Gesamt', 'Q3_Q4_Prozent']].copy()
    display_df.columns = ['Team', 'Q3 (Jul-Sep)', 'Q4 (Okt-Dez)', 'Q3+Q4 (Jul-Dez)', 'Gesamt', 'Q3+Q4 %']
    
    st.dataframe(
        display_df.style.format({'Q3 (Jul-Sep)': '{:.0f}', 'Q4 (Okt-Dez)': '{:.0f}', 'Q3+Q4 (Jul-Dez)': '{:.0f}', 'Gesamt': '{:.0f}', 'Q3+Q4 %': '{:.1f}%'}),
        use_container_width=True,
        height=300
    )

st.markdown("---")

# Vierte Zeile - Erweiterte Analysen
st.markdown("## 🔍 Erweiterte Analysen")

col1, col2 = st.columns(2)

with col1:
    st.markdown("### 📊 Boxplot der Liga")
    
    fig = go.Figure()
    fig.add_trace(go.Box(
        y=df_teams['Altersdurchschnitt'],
        name='Alle Teams',
        boxpoints='outliers',
        marker_color='#1f77b4',
        line_color='#1f77b4'
    ))
    
    # Ausgewähltes Team markieren
    fig.add_hline(
        y=team_age,
        line_dash="dash",
        line_color="red",
        line_width=3,
        annotation_text=f"{selected_team}"
    )
    
    fig.update_layout(
        title="Boxplot der Altersdurchschnitte aller Teams",
        yaxis_title="Alter (Jahre)",
        template='plotly_white',
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.markdown("### 📈 Team-Vergleich")
    
    # Vergleich mit anderen Teams
    comparison_data = df_teams.copy()
    comparison_data['Differenz'] = comparison_data['Altersdurchschnitt'] - team_age
    comparison_data = comparison_data.sort_values('Differenz')
    
    # Balkendiagramm mit Team-Farben
    fig = go.Figure()
    
    for i, team in enumerate(comparison_data['Team']):
        diff_val = comparison_data.iloc[i]['Differenz']
        team_color = get_team_color(team)
        
        fig.add_trace(go.Bar(
            x=[team],
            y=[diff_val],
            name=team,
            marker_color=team_color,
            showlegend=False
        ))
    
    fig.update_layout(
        title=f"Altersdifferenz zu {selected_team}",
        xaxis_title="Team",
        yaxis_title="Altersdifferenz (Jahre)",
        template='plotly_white',
        height=400,
        showlegend=False
    )
    
    st.plotly_chart(fig, use_container_width=True)





# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; padding: 2rem;">
    <p>📊 Dashboard erstellt für die Saison 2025/26</p>
    <p>⚽ Daten aus: Statistik Altersdurchschnitt.xlsx | Wird regelmäßig aktualisiert</p>
    <p>🎂 Geburtsquartal-Analyse: Q1 = Jan-März, Q2 = Apr-Jun, Q3 = Jul-Sep, Q4 = Okt-Dez</p>
</div>
""", unsafe_allow_html=True)

# Sidebar Footer ausgeblendet

# Export-Funktionalität
st.sidebar.markdown("### 💾 Export")
if st.sidebar.button("📥 Alle Daten exportieren (CSV)"):
    csv = df_teams.to_csv(index=False)
    st.sidebar.download_button(
        label="Download CSV",
        data=csv,
        file_name="alle_teams_altersdurchschnitt.csv",
        mime="text/csv"
    )

if st.sidebar.button("📥 Team-Daten exportieren (CSV)"):
    team_csv = df_teams[df_teams['Team'] == selected_team].to_csv(index=False)
    st.sidebar.download_button(
        label=f"Download {selected_team}",
        data=team_csv,
        file_name=f"{selected_team}_altersdurchschnitt.csv",
        mime="text/csv"
    )
