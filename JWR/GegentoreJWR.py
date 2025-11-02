import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.image as mpimg

# Spielfeld zeichnen mit korrekten Maßen und figsize (6,10)
def draw_field():
    fig, ax = plt.subplots(figsize=(6, 10))
    ax.set_facecolor('green')  # Spielfeld grün einfärben
    ax.set_xlim(0, 68)  # Spielfeldbreite (m)
    ax.set_ylim(0, 100)  # Spielfeldtiefe (m)
    
    # 📌 SV Ried Logo als Hintergrund einfügen
    logo = mpimg.imread("C:\\Temp\\SV_Ried.png")  # Stelle sicher, dass die Datei existiert
    ax.imshow(logo, extent=[0, 68, 0, 100], alpha=0.05)  # Logo leicht transparent machen

    # Spielfeldlinien hinzufügen
    ax.plot([0, 68], [50, 50], 'white', linestyle="-", zorder=5, linewidth=2)  # Mittellinie
    mittelkreis = patches.Circle((34, 50), 9, edgecolor='white', facecolor='none', linewidth=2)  # Mittelkreis
    ax.add_patch(mittelkreis)

    # Gestrichelte Linien hinzufügen
    ax.plot([43, 43], [100, 75], 'white', linestyle="--", linewidth=2)  # Erste gestrichelte Linie
    ax.plot([25, 25], [100, 75], 'white', linestyle="--", linewidth=2)  # Zweite gestrichelte Linie
    ax.plot([43, 54, 54], [100, 84, 75], 'white', linestyle="--", linewidth=2)  # Dritte gestrichelte Linie
    ax.plot([25, 14, 14], [100, 84, 75], 'white', linestyle="--", linewidth=2)  # Vierte gestrichelte Linie
    ax.plot([14, 0], [90, 90], 'white', linestyle="--", linewidth=2)  # Neue horizontale Linie links
    ax.plot([54, 68], [90, 90], 'white', linestyle="--", linewidth=2)  # Neue horizontale Linie rechts

    # Fünfmeterraum hinzufügen (5m tief, 18m breit)
    fuenfmeter_oben = patches.Rectangle((25, 100), 18, -5, edgecolor='white', facecolor='none', linewidth=2)
    ax.add_patch(fuenfmeter_oben)

    fuenfmeter_unten = patches.Rectangle((25, 0), 18, 5, edgecolor='white', facecolor='none', linewidth=2)
    ax.add_patch(fuenfmeter_unten)

    # Sechzehnmeterraum hinzufügen (16m tief, 40m breit)
    sechzehn_oben = patches.Rectangle((14, 100), 40, -16, edgecolor='white', facecolor='none', linewidth=2)
    ax.add_patch(sechzehn_oben)

    sechzehn_unten = patches.Rectangle((14, 0), 40, 16, edgecolor='white', facecolor='none', linewidth=2)
    ax.add_patch(sechzehn_unten)

    # Elfmeterpunkte hinzufügen
    ax.scatter(34, 89, color='white', marker='o')  # Elfmeterpunkt oben
    ax.scatter(34, 11, color='white', marker='o')  # Elfmeterpunkt unten

    # Halbkreise um die Elfmeterpunkte
    halbkreis_oben = patches.Arc((34, 89), 18, 18, angle=0, theta1=215, theta2=325, edgecolor='white', linewidth=2)  # Oberer Halbkreis
    ax.add_patch(halbkreis_oben)

    halbkreis_unten = patches.Arc((34, 11), 18, 18, angle=0, theta1=35, theta2=145, edgecolor='white', linewidth=2)  # Unterer Halbkreis
    ax.add_patch(halbkreis_unten)

    # Tore (Fußball-Symbol) & Assists
    goals = [(34,96),(36,86),(30,95),(28,92),(34,88),(31,95),(40,93),(29,85),(37,89),(38,95),(18,83),(38,97),(28,98),(33,95),(37,95),(30,92),(40,98),(41,98),(42,86),(38,75),(26,95),(30,90),(37,97),(36,86),(18,81),(23,89),(30,82),(36,98),(32,76),(38,82),(40,98),(37,95),(30,95)] # Torpositionen 
    assists = [(16,88),(23,21),(43,97),(30,70),(51,94),(44,85),(45,84),(58,63),(24,84),(41,99),(23,76),(12,89),(66,88),(68,100),(48,93),(12,80),(68,100),(68,100),(34,84),(38,77),(20,58),(15,80),(0,100),(56,95),(14,75),(16,70),(51,78),(24,92),(34,81),(42,72),(44,80),(66,95),(11,96)]  # Assist-Positionen

    # Tore markieren (kleiner Ball-Symbol)
    for i, goal in enumerate(goals):
        ax.scatter(goal[0], goal[1], color='red', edgecolors='white', marker='o', s=30, label='Tor' if i == 0 else "")

    # Assists markieren (blaue Quadrate)
    for assist in assists:
        ax.scatter(assist[0], assist[1], color='yellow', marker='s', s=20, label='Assist' if assist == assists[0] else "")

    # Verbindungslinien zwischen Assist und Tor (Passwege)
    for i in range(len(goals)):
        ax.plot([assists[i][0], goals[i][0]], [assists[i][1], goals[i][1]], 'black', linestyle="--", alpha=0.2)

    # Legende seitlich links unten platzieren
    ax.legend(loc="lower left", fontsize=10)

    plt.title("JWR 25/26 - Gegentore\n 3 Elfmeter u. 1 dir.FS n.b.")
    plt.xlabel("Spielfeldbreite (m)")
    plt.ylabel("Spielfeldtiefe (m)")
    return ax

# Zeichne das Spielfeld mit den richtigen Halbkreisen und Toren als Ball-Symbol
ax = draw_field()
plt.show()
