# Rio UPP — Pacification et criminalité

Analyse de l'impact de la politique de pacification des favelas de Rio de
Janeiro (Unités de Police Pacificatrice, UPP) sur la criminalité, à partir de
données de criminalité par UPP et de données socio-économiques par secteur de
recensement (census).

![visuel-UPP](picture/visuel-UPP.png)

## Cartes en ligne

Les cartes Folium sont consultables directement, sans cloner le dépôt, via
[htmlpreview.github.io](https://htmlpreview.github.io/) :

- [Rio_Robbery_2012.html](https://htmlpreview.github.io/?https://github.com/Marius-cld/Interactive-Map-Rio-UPP/blob/main/map/Rio_Robbery_2012.html) — vols par UPP en 2012, zones pacifiées vs non pacifiées
- [Rio_Income_Inf_Min_Wages.html](https://htmlpreview.github.io/?https://github.com/Marius-cld/Interactive-Map-Rio-UPP/blob/main/map/Rio_Income_Inf_Min_Wages.html) — % de ménages à revenu < 2x le salaire minimum
- [Rio_Income_Sup_Min_Wages.html](https://htmlpreview.github.io/?https://github.com/Marius-cld/Interactive-Map-Rio-UPP/blob/main/map/Rio_Income_Sup_Min_Wages.html) — % de ménages à revenu > 10x le salaire minimum

## Structure

```
src/
  main.py            Pipeline complet : charge les données, les nettoie,
                     génère les cartes Folium dans map/
data/
  UPP/               Données au niveau UPP (crimes, dates de pacification,
                     limites géographiques, matching UPP <-> shapefile)
  censitorios/       Données socio-économiques au niveau des secteurs de
                     recensement (densité, indicateurs de revenu) — à ajouter
                     manuellement, voir Données ci-dessous
map/                  Cartes HTML générées (Folium)
picture/               Visuels utilisés dans ce README (non générés par le script)
docs/                 Énoncé de l'exercice
```

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Données

Les fichiers `data/censitorios/Densidade.json` et `Inegalidade.json` ne sont
**pas** versionnés (169 Mo et 175 Mo, au-delà de la limite de 100 Mo par
fichier de GitHub). Placez-les dans `data/censitorios/` avant d'exécuter le
script si vous voulez régénérer les cartes socio-économiques — en leur
absence, le script génère uniquement la carte de criminalité et l'indique
clairement plutôt que d'échouer.

## Génération des cartes

```bash
python3 src/main.py
```

Génère dans `map/` :

- `Rio_Robbery_2012.html` — vols par UPP en 2012, zones pacifiées vs non pacifiées
- `Rio_Income_Inf_Min_Wages.html` — % de ménages à revenu < 2x le salaire minimum (nécessite les données census ci-dessus)
- `Rio_Income_Sup_Min_Wages.html` — % de ménages à revenu > 10x le salaire minimum (nécessite les données census ci-dessus)

Les couches socio-économiques (secteurs de recensement) sont simplifiées
géométriquement et les coordonnées arrondies avant export afin de garder des
cartes HTML légères (~11 Mo au lieu de plusieurs centaines de Mo pour les
données brutes), sans perte de lisibilité à l'échelle de la carte.
