"""
Objectif :
    Créer une carte pour les données Crime et Socio-economique (densité, pop) au niveau UPP
"""

import json
import pickle
from pathlib import Path

import folium
import geopandas as gpd
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_UPP_DIR = ROOT_DIR / "data" / "UPP"
DATA_CENSITORIOS_DIR = ROOT_DIR / "data" / "censitorios"
MAP_DIR = ROOT_DIR / "maps"


def f_matching(row, matching):
    return matching[row["nomeabrev"]]


def geojson_allege(gdf, colonnes, geometry_col="geometry", tolerance=0.0001, precision=6):
    """
    Simplifie la géométrie (tolérance en degrés, ~11m) et arrondit les coordonnées
    pour réduire fortement le poids du GeoJSON embarqué dans le HTML Folium.
    Ne garde que les colonnes utiles (clé + valeur affichée) pour éviter d'embarquer
    les dizaines de colonnes brutes du census dans chaque feature.
    """

    def arrondir(coords):
        if isinstance(coords[0], (int, float)):
            return [round(c, precision) for c in coords]
        return [arrondir(c) for c in coords]

    leger = gdf[colonnes + [geometry_col]].rename(columns={geometry_col: "geometry"})
    leger = leger.set_geometry("geometry")
    leger["geometry"] = leger["geometry"].simplify(tolerance, preserve_topology=True)

    geo = json.loads(leger.to_json())
    for feature in geo["features"]:
        feature["geometry"]["coordinates"] = arrondir(feature["geometry"]["coordinates"])

    return leger, geo


def charger_donnees_crime():
    """Charge et assemble les données de criminalité au niveau UPP, annualisées."""
    gdf_limit = gpd.read_file(DATA_UPP_DIR / "UPPshp" / "lm_upp_edit.shp")

    df_crime = pd.read_csv(DATA_UPP_DIR / "crimeUPP.csv", sep=",")
    df_upp = pd.read_csv(DATA_UPP_DIR / "dataUPP.csv", sep=",")

    with open(DATA_UPP_DIR / "matching.pickle", "rb") as f:
        matching = pickle.load(f)

    gdf_limit["UPP"] = gdf_limit.apply(f_matching, axis=1, matching=matching)

    gdf_limit = pd.merge(gdf_limit, df_upp, left_on="UPP", right_on="UPP", how="left")
    gdf_limit = pd.merge(gdf_limit, df_crime, left_on="UPP", right_on="upp", how="left")

    ### Préparation des données Crime ###
    gdf_limit = gdf_limit.sort_index(axis=1)

    # Enlever les colonnes inutiles
    gdf_limit_clean = gdf_limit.drop(
        columns=["geometry_x", "geometry_y", "geometry_1", "geometry_2", "upp"]
    )

    # Réarranger l'ordre des colonnes
    colonne = [
        "geometry",
        "City",
        "UPP",
        "date",
        "date_Bope",
        "date_upp",
        "Gang",
        "homicideintentional",
        "bodyinjurydeathfollowed",
        "robberydeathfollowed",
        "deathofmilitarypolice",
        "deathofcivilpolice",
        "totalrobbery",
        "totaltheft",
    ]

    gdf_limit_clean = gdf_limit_clean[colonne].copy()

    # Annualiser les données en créant une nouvelle colonne (année de départ 2007)
    gdf_limit_clean["year"] = ((gdf_limit_clean["date"] - 1) // 12) + 2007

    # Colonnes à sommer
    colonnes_somme = [
        "homicideintentional",
        "bodyinjurydeathfollowed",
        "robberydeathfollowed",
        "deathofmilitarypolice",
        "deathofcivilpolice",
        "totalrobbery",
        "totaltheft",
    ]

    # Colonnes à garder l'information de la premiere ligne (même info à chaque ligne)
    colonnes_info = ["geometry", "City", "date_Bope", "date_upp", "Gang"]

    # Créer le geodataframe final annuel en groupant par UPP et année
    dico_agg = {}
    for ele in colonnes_somme:
        dico_agg[ele] = "sum"
    for ele in colonnes_info:
        dico_agg[ele] = "first"

    # agg fonctionne avec un dict reset_index permet d'avoir "UPP", "year" comme colonne et non comme n° de ligne
    gdf_limit_clean_year = (
        gdf_limit_clean.groupby(["UPP", "year"]).agg(dico_agg).reset_index()
    )
    gdf_limit_clean_year["year"] = gdf_limit_clean_year["year"].astype(int)

    gdf_limit_clean_year = gdf_limit_clean_year[
        [
            "geometry",
            "UPP",
            "City",
            "year",
            "date_Bope",
            "date_upp",
            "Gang",
            "homicideintentional",
            "bodyinjurydeathfollowed",
            "robberydeathfollowed",
            "deathofmilitarypolice",
            "deathofcivilpolice",
            "totalrobbery",
            "totaltheft",
        ]
    ]

    # Créer une colonne de l'année d'intervention de la Police et année de Pacification
    # Ne fonctionne pas si des lignes de la colonne contient des Nan
    if sum(gdf_limit_clean_year["date_Bope"].isna()) != 0:
        gdf_limit_clean_year = gdf_limit_clean_year.dropna(subset=["date_Bope"])
    if sum(gdf_limit_clean_year["date_upp"].isna()) != 0:
        gdf_limit_clean_year = gdf_limit_clean_year.dropna(subset=["date_upp"])

    gdf_limit_clean_year["year_chaos"] = (
        "20" + gdf_limit_clean_year["date_Bope"].str[-2:]
    ).astype(int)
    gdf_limit_clean_year["year_peaceful"] = (
        "20" + gdf_limit_clean_year["date_upp"].str[-2:]
    ).astype(int)
    gdf_limit_clean_year["year_chaos"] = gdf_limit_clean_year["year_chaos"] - 1
    gdf_limit_clean_year["year_peaceful"] = gdf_limit_clean_year["year_peaceful"] + 1

    # Définir la géométrie et le CRS
    gdf_limit_clean_year = gdf_limit_clean_year.set_geometry("geometry")
    gdf_limit_clean_year = gdf_limit_clean_year.set_crs("EPSG:4326", allow_override=True)

    return gdf_limit_clean_year


def carte_criminalite(gdf_limit_clean_year, annee_cible=2012):
    """Carte des vols par UPP pour une année donnée, zones pacifiées vs non pacifiées."""
    gdf_limit_clean_cible = gdf_limit_clean_year[
        gdf_limit_clean_year["year"] == annee_cible
    ]

    # Zones pacifiées
    gdf_peaceful = gdf_limit_clean_cible[
        gdf_limit_clean_cible["year_peaceful"] <= annee_cible
    ].copy()
    gdf_peaceful["status"] = "Zone pacifiée"
    gdf_peaceful["UPP"] = gdf_peaceful["UPP"].str.replace("DoUpp", "")

    # Zones non pacifiées
    gdf_chaos = gdf_limit_clean_cible[
        (gdf_limit_clean_cible["year_peaceful"] > annee_cible)
    ].copy()
    gdf_chaos["status"] = "Zone non pacifiée"
    gdf_chaos["UPP"] = gdf_chaos["UPP"].str.replace("DoUpp", "")

    # Créer la carte centrée sur Rio
    m = folium.Map(location=[-22.9068, -43.1729], zoom_start=11)

    # Calque pour les zones pacifiées
    folium.Choropleth(
        geo_data=gdf_peaceful,
        data=gdf_peaceful,
        columns=["UPP", "totalrobbery"],
        key_on="feature.properties.UPP",
        fill_color="YlGn_r",
        fill_opacity=0.5,
        line_opacity=0.6,
        line_weight=1.3,
        line_color="green",
        nan_fill_color="purple",
        nan_fill_opacity=0.5,
        highlight=True,
        legend_name="Vols (zones pacifiées)",
        name="Zones pacifiées",
    ).add_to(m)

    folium.GeoJson(
        gdf_peaceful,
        style_function=lambda _: {"fillOpacity": 0, "color": "transparent", "weight": 0},
        popup=folium.GeoJsonPopup(
            fields=["status", "UPP", "totalrobbery"],
            aliases=["Statut:", "UPP:", "Total vols:"],
        ),
    ).add_to(m)

    # Calque pour les zones non pacifiées
    folium.Choropleth(
        geo_data=gdf_chaos,
        data=gdf_chaos,
        columns=["UPP", "totalrobbery"],
        key_on="feature.properties.UPP",
        fill_color="YlOrBr",
        fill_opacity=0.5,
        line_opacity=0.6,
        line_weight=1.3,
        line_color="red",
        nan_fill_color="purple",
        nan_fill_opacity=0.5,
        highlight=True,
        legend_name="Vols (zones non pacifiées)",
        name="Zones non pacifiées",
    ).add_to(m)

    folium.GeoJson(
        gdf_chaos,
        style_function=lambda _: {"fillOpacity": 0, "color": "transparent", "weight": 0},
        popup=folium.GeoJsonPopup(
            fields=["status", "UPP", "totalrobbery"],
            aliases=["Statut:", "UPP:", "Total vols:"],
        ),
    ).add_to(m)

    folium.LayerControl().add_to(m)
    m.save(MAP_DIR / "Rio_Robbery_2012.html")


def cartes_socio_economiques():
    """Cartes des indicateurs de revenu par secteur de recensement (census)."""
    with open(DATA_CENSITORIOS_DIR / "densidade.json") as f:
        densidade = json.load(f)
    with open(DATA_CENSITORIOS_DIR / "inegalidade.json") as f:
        inegalidade = json.load(f)

    gdf_densidade = gpd.GeoDataFrame.from_features(densidade)
    gdf_inegalidade = gpd.GeoDataFrame.from_features(inegalidade)

    gdf = pd.merge(
        gdf_inegalidade,
        gdf_densidade,
        left_on="CDURP.DBO.IDS_SETOR10.SETOR_2010",
        right_on="CDURP.DBO.Novos_Setores_Recortados_2010_1.ID_",
        how="inner",
    )
    gdf["diff"] = gdf["geometry_x"] != gdf["geometry_y"]

    gdf = gdf.sort_index(axis=1)
    gdf = gdf.drop(
        columns=[
            "CDURP.DBO.Novos_Setores_Recortados_2010_1.Area_y",
            "CDURP.DBO.Novos_Setores_Recortados_2010_1.Cod_Setor__y",
            "CDURP.DBO.Novos_Setores_Recortados_2010_1.Hab_ha_y",
            "CDURP.DBO.Novos_Setores_Recortados_2010_1.ID__y",
            "CDURP.DBO.Novos_Setores_Recortados_2010_1.OBJECTID_1_y",
            "CDURP.DBO.Novos_Setores_Recortados_2010_1.Shape_Leng_y",
            "CDURP.DBO.Novos_Setores_Recortados_2010_1.OBJECTID_y",
            "geometry_y",
            "diff",
        ]
    )

    gdf = gdf.set_geometry("geometry_x")
    gdf = gdf.set_crs("EPSG:4326", allow_override=True)

    # Pourcentage des ménages dont le chef de famille perçoit un revenu inférieur à 2 fois le salaire minimum
    m = folium.Map(location=[-22.9068, -43.1729], zoom_start=11)

    gdf = gdf.rename(
        columns={
            "CDURP.DBO.IDS_SETOR10.SETOR_2010": "IDS_SETOR10",
            "CDURP.DBO.IDS_SETOR10.INDIC_RENDARESP_POS_ATE2SM": "INDIC_RENDARESP_POS_ATE2SM",
        }
    )

    gdf_income_inf, geo_income_inf = geojson_allege(
        gdf, ["IDS_SETOR10", "INDIC_RENDARESP_POS_ATE2SM"], geometry_col="geometry_x"
    )

    folium.Choropleth(
        geo_data=geo_income_inf,
        data=gdf_income_inf,
        columns=["IDS_SETOR10", "INDIC_RENDARESP_POS_ATE2SM"],
        key_on="feature.properties.IDS_SETOR10",
        fill_color="Reds",
        fill_opacity=0.5,
        line_opacity=0.6,
        line_weight=1,
        line_color="darkred",
        nan_fill_color="purple",
        nan_fill_opacity=0.5,
        highlight=True,
        legend_name="Ménages avec revenu < 2x salaire minimum",
        name="Revenu",
    ).add_to(m)

    m.save(MAP_DIR / "Rio_Income_Inf_Min_Wages.html")

    # Pourcentage des ménages dont le chef de famille perçoit un revenu supérieur à 10 fois le salaire minimum
    m = folium.Map(location=[-22.9068, -43.1729], zoom_start=11)

    gdf = gdf.rename(
        columns={
            "CDURP.DBO.IDS_SETOR10.INDIC_RENDARESP_P_MAISDE10SM": "INDIC_RENDARESP_P_MAISDE10SM",
        }
    )

    gdf_income_sup, geo_income_sup = geojson_allege(
        gdf, ["IDS_SETOR10", "INDIC_RENDARESP_P_MAISDE10SM"], geometry_col="geometry_x"
    )

    folium.Choropleth(
        geo_data=geo_income_sup,
        data=gdf_income_sup,
        columns=["IDS_SETOR10", "INDIC_RENDARESP_P_MAISDE10SM"],
        key_on="feature.properties.IDS_SETOR10",
        fill_color="Greens",
        fill_opacity=0.5,
        line_opacity=0.6,
        line_weight=1,
        line_color="darkgreen",
        nan_fill_color="purple",
        nan_fill_opacity=0.5,
        highlight=True,
        legend_name="Ménages avec revenu > 10x salaire minimum",
        name="Revenu",
    ).add_to(m)

    m.save(MAP_DIR / "Rio_Income_Sup_Min_Wages.html")


def main():
    MAP_DIR.mkdir(parents=True, exist_ok=True)

    gdf_limit_clean_year = charger_donnees_crime()
    carte_criminalite(gdf_limit_clean_year, annee_cible=2012)

    if (DATA_CENSITORIOS_DIR / "Densidade.json").exists() and (
        DATA_CENSITORIOS_DIR / "Inegalidade.json"
    ).exists():
        cartes_socio_economiques()
    else:
        print(
            f"Fichiers census absents de {DATA_CENSITORIOS_DIR} "
            "(Densidade.json / Inegalidade.json) — cartes socio-économiques ignorées. "
            "Voir README pour se les procurer."
        )

    print("Fin")


if __name__ == "__main__":
    main()
