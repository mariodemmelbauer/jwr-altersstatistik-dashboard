# Altersstatistik App - JWR Dashboard

Eine standalone Streamlit-App zur Anzeige der Altersstatistiken der Regionalliga Mitte.

## 🚀 Lokale Ausführung

```bash
# 1. Abhängigkeiten installieren
pip install -r requirements_altersstatistik.txt

# 2. App starten
streamlit run altersstatistik_app.py
```

## 📋 Voraussetzungen

Die App benötigt folgende Dateien:

1. **Durchschnittsalter.py** - Das Altersstatistik-Skript
   - Pfad: `C:\Users\demmelb-ma\OneDrive - COC AG\JWR\Matches\2526\Durchschnittsalter.py`

2. **Statistik Altersdurchschnitt.xlsx** - Die Excel-Datei mit den Daten
   - Pfad: `C:\Users\demmelb-ma\OneDrive - COC AG\JWR\Matches\2526\Statistik Altersdurchschnitt.xlsx`

## 🌐 Cloud-Deployment

### Option 1: Streamlit Cloud
1. Repository auf GitHub hochladen
2. Bei [share.streamlit.io](https://share.streamlit.io) anmelden
3. Repository verknüpfen und `altersstatistik_app.py` als Hauptdatei auswählen

### Option 2: Heroku
```bash
# Procfile erstellen
echo "web: streamlit run altersstatistik_app.py --server.port=$PORT --server.address=0.0.0.0" > Procfile

# Deploy zu Heroku
git init
git add .
git commit -m "Initial commit"
heroku create your-app-name
git push heroku main
```

### Option 3: Docker
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements_altersstatistik.txt .
RUN pip install -r requirements_altersstatistik.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "altersstatistik_app.py", "--server.address=0.0.0.0"]
```

## ⚙️ Konfiguration

Pfade können in der Datei `altersstatistik_app.py` angepasst werden:

```python
# CONFIG Sektion (Zeile ~11)
ALTERSSTATISTIK_SCRIPT = Path(r"...")
ALTERSSTATISTIK_EXCEL = Path(r"...")
```

## 🎨 Features

- **Dark Theme** - Modernes dunkles Design
- **Responsive Layout** - Funktioniert auf allen Bildschirmgrößen  
- **Auto-Updates** - Refresh-Button zum Aktualisieren der Daten
- **Error Handling** - Hilfreiche Fehlermeldungen und Auto-Installation fehlender Pakete

## 📦 Abhängigkeiten

- `streamlit` - Web-Framework
- `pandas` - Datenverarbeitung
- `plotly` - Interaktive Diagramme
- `openpyxl` - Excel-Dateien lesen
- `numpy` - Numerische Berechnungen
