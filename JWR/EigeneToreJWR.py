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
    goals = [(35,95),(36,90),(25,85),(45,95),(35,91),(34,93),(39,86),(31,92),(26,89),(24,84),(38,94),(35,96),(34,94),(30,88),(30,79),(29,88),(35,91),(22,92),(24,89),(38,96),(33,98)]  # Torpositionen 
    assists = [(68,100),(34,43),(25,41),(52,47),(17,68),(40,84),(26,63),(39,86),(24,67),(15,58),(39,84),(43,95),(52,68),(34,83),(11,86),(34,89),(20,97),(5,58),(6,42),(68,100),(68,100)]  # Assist-Positionen

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

    plt.title("JWR - Tore\n 2 Elfmeter u. 1 dir.FS n.b.")
    plt.xlabel("Spielfeldbreite (m)")
    plt.ylabel("Spielfeldtiefe (m)")
    return ax

# Zeichne das Spielfeld mit den richtigen Halbkreisen und Toren als Ball-Symbol
ax = draw_field()
plt.show()
