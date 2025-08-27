import cv2
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import traceback

# Video-Pfad
video_path = r"C:\\temp\\jwr\\treibach.mp4"

# Video laden und prüfen
cap = cv2.VideoCapture(video_path)
if not cap.isOpened():
    print("Fehler: Video konnte nicht geöffnet werden! Überprüfe den Dateipfad.")
    input("Drücke Enter zum Beenden...")
    exit()

# Video-Format anzeigen
print(f"Video-Format: {cap.get(cv2.CAP_PROP_FOURCC)}")

# Erste Frame überprüfen
ret, frame = cap.read()
if not ret or frame is None:
    print("Fehler: Erste Frame konnte nicht gelesen werden!")
    input("Drücke Enter zum Beenden...")
    exit()

# ROI-Auswahl mit Fehlerabfang
try:
    print("Bitte wähle die ROI im Video-Fenster aus!")
    bbox = cv2.selectROI("Tracking", frame, False)
    print("ROI erfolgreich ausgewählt. Skript läuft weiter...")
    input("Drücke Enter zum Fortfahren...")
except Exception as e:
    print(f"Fehler bei ROI-Auswahl: {e}")
    traceback.print_exc()
    input("Drücke Enter zum Beenden...")
    exit()

cv2.waitKey(1000)
cv2.destroyAllWindows()

# ROI-Werte überprüfen
print(f"ROI Werte nach Auswahl: {bbox}")
cv2.waitKey(3000)

if bbox == (0, 0, 0, 0):
    print("Fehler: Keine gültige ROI ausgewählt!")
    input("Drücke Enter zum Beenden...")
    exit()

# Überprüfung der ROI-Größe
x, y, w, h = bbox
if w < 10 or h < 10:
    print("Fehler: Die ausgewählte ROI ist zu klein!")
    input("Drücke Enter zum Beenden...")
    exit()

# **Test: Ist frame nach ROI noch gültig?**
if frame is None or frame.size == 0:
    print("Fehler: Frame ist nach ROI-Auswahl ungültig!")
    input("Drücke Enter zum Beenden...")
    exit()

# Frame nach ROI-Auswahl neu laden
ret, frame = cap.read()
if not ret or frame is None:
    print("Fehler: Frame konnte nach ROI-Auswahl nicht neu geladen werden!")
    input("Drücke Enter zum Beenden...")
    exit()

# Kopie des Frames für den Tracker erstellen
frame_copy = frame.copy()

# **TEST: Starte MOSSE-Tracker mit einer festen ROI**
test_bbox = (100, 100, 50, 50)  # Feste Test-ROI
tracker = cv2.TrackerMOSSE_create()
success = tracker.init(frame_copy, test_bbox)

if not success:
    print("Fehler: MOSSE-Tracker konnte nicht mit fester ROI gestartet werden! Wechsel zu CSRT...")
    tracker = cv2.TrackerCSRT_create()
    success = tracker.init(frame_copy, test_bbox)

if not success:
    print("Fehler: Auch CSRT-Tracker konnte nicht gestartet werden!")
    input("Drücke Enter zum Beenden...")
    exit()

# **Erstes Tracking-Update testen**
success, bbox = tracker.update(frame_copy)
if not success:
    print("Fehler: Erstes Tracking-Update fehlgeschlagen!")
    input("Drücke Enter zum Beenden...")
    exit()

positions = []

while True:
    ret, frame = cap.read()
    if not ret:
        print("Fehler: Keine Frames mehr vorhanden oder Video konnte nicht gelesen werden!")
        input("Drücke Enter zum Beenden...")
        break
    
    success, bbox = tracker.update(frame)
    
    if not success:
        print("Fehler: Tracking fehlgeschlagen! ROI eventuell nicht sichtbar?")
        input("Drücke Enter zum Beenden...")
        break
    
    x, y, w, h = [int(v) for v in bbox]
    positions.append((x + w // 2, y + h // 2))  # Mittelpunkt speichern

cap.release()

# **Test: Funktioniert Tracker mit statischem Bild?**
try:
    print("Starte Tracker-Test mit statischem Bild...")
    test_frame = cv2.imread("C:/temp/testbild.jpg")  # Beispielbild
    test_bbox = (100, 100, 50, 50)
    tracker = cv2.TrackerMOSSE_create()
    success = tracker.init(test_frame, test_bbox)
    if not success:
        print("Fehler: Tracker konnte mit statischem Bild nicht gestartet werden!")
except Exception as e:
    print(f"Fehler beim Test mit statischem Bild: {e}")
    traceback.print_exc()

# Überprüfung, ob Positionsdaten vorhanden sind
if len(positions) == 0:
    print("Fehler: Keine Positionsdaten für die Heatmap!")
    input("Drücke Enter zum Beenden...")
    exit()

# Heatmap erzeugen
positions_np = np.array(positions)

plt.figure(figsize=(10, 6))
sns.kdeplot(x=positions_np[:,0], y=positions_np[:,1], cmap="Reds", shade=True)
plt.title("Heatmap der Spielerbewegung")
plt.show()
