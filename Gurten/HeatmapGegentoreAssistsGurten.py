import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.image as mpimg
import seaborn as sns
import numpy as np

# Spielfeld zeichnen mit korrekten Maßen und grünem Hintergrund
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

    # Fünfmeterraum hinzufügen (5m tief, 18m breit)
    fuenfmeter_oben = patches.Rectangle((25, 100), 18, -5, edgecolor='white', facecolor='none', linewidth=2)
    ax.add_patch(fuenfmeter_oben)

    fuenfmeter_unten = patches.Rectangle((25, 0), 18, 5, edgecolor='white', facecolor='none', linewidth=2)
    ax.add_patch(fuenfmeter_unten)
    
    # Sechzehnmeterraum hinzufügen
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

    plt.title("JWR - Gegentore Assists - Heatmap")
    plt.xlabel("Spielfeldbreite (m)")
    plt.ylabel("Spielfeldtiefe (m)")
    return ax

# Heatmap für Torzonen erstellen
def draw_heatmap(ax, goals):
    goal_positions = np.array(goals)

    # Erstelle Heatmap basierend auf Torpositionen
    sns.kdeplot(x=goal_positions[:,0], y=goal_positions[:,1], cmap="Reds", fill=True, alpha=0.7, levels=100, ax=ax, bw_adjust=0.2)

# Beispiel-Assistpositionen
goals = [(44, 93), (26, 92), (0, 100), (36, 70), (17, 98), (33, 94), (10, 82), (49, 87), (13, 86), (36, 84), (29, 90), (33, 91), (33, 68), (12, 90), (47, 90), (68, 100), (36, 66), (26, 56), (68, 100), (68, 100), (57, 42), (4, 72), (58, 93), (34, 89), (43, 88), (16, 55), (6, 98), (50, 76), (31, 83), (52, 94), (54, 23), (51, 88), (52, 78), (40, 92), (39, 77), (54, 86), (16, 89), (54, 99), (0, 100), (34, 95), (18, 92), (44, 89), (25, 94), (34, 84), (35, 78)]

# Spielfeld zeichnen
ax = draw_field()

# Heatmap hinzufügen
draw_heatmap(ax, goals)

# Zeige das Spielfeld mit Heatmap
plt.show()
