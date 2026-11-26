# Tests des visualisations automatiques (sans clé API, figures non affichées).

import pandas as pd
import plotly.graph_objects as go

import viz

df = pd.DataFrame({
    "ville": ["Lyon", "Paris", "Lyon", "Paris", "Lyon", "Paris"] * 5,
    "montant": [10.0, 20.0, 12.0, 22.0, 11.0, 21.0] * 5,
    "quantite": [1, 2, 3, 4, 5, 6] * 5,
    "date": pd.date_range("2026-01-01", periods=30).astype(str).tolist(),
})


def test_choisir_selon_types_et_inversion():
    assert viz.choisir(df, "montant")["kind"] == "histogramme"
    assert viz.choisir(df, "ville")["kind"] == "barres"
    assert viz.choisir(df, "montant", "quantite")["kind"] == "scatter"
    assert viz.choisir(df, "ville", "montant")["kind"] == "box"
    assert viz.choisir(df, "montant", "ville")["kind"] == "box"
    assert viz.choisir(df, "date", "montant")["kind"] == "line"
    assert viz.choisir(df, "montant", "date")["kind"] == "line"
    assert viz.choisir(df, "ville", "montant", force="scatter")["kind"] == "scatter"
    try:  # combinaison date × catégorie refusée
        viz.choisir(df, "ville", "date")
        refuse = False
    except ValueError:
        refuse = True
    assert refuse
    try:
        viz.choisir(df, "inconnue")
        manque = False
    except ValueError:
        manque = True
    assert manque


def test_construire_chaque_type():
    cas = [("histogramme", "montant", None), ("barres", "ville", None),
           ("box", "ville", "montant"), ("scatter", "montant", "quantite"),
           ("line", "date", "montant"), ("heatmap", None, None)]
    for kind, x, y in cas:
        fig = viz.construire(df, kind, x, y)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) > 0


def test_insight_chiffre_en_francais():
    assert "médiane" in viz.insight(df, "histogramme", "montant")
    barres = viz.insight(df, "barres", "ville")
    assert "domine" in barres and "%" in barres
    scat = viz.insight(df, "scatter", "montant", "quantite")
    assert "r = " in scat and "," in scat  # virgule française
    assert "pas cause" in scat
    chauf = viz.insight(df, "heatmap", None)
    assert "corrélation" in chauf
    ligne = viz.insight(df, "line", "date", "montant")
    assert "hausse" in ligne or "baisse" in ligne


def test_histogramme_date_compte_par_jour():
    # La capture du bug : 2 lignes sur 3 jours donnaient un seul bloc
    # bleu illisible. On exige une barre par jour distinct.
    df_dates = pd.DataFrame({
        "date": ["2026-09-04 18:00", "2026-09-05 09:00",
                 "2026-09-05 18:00", "2026-09-06 12:00"],
    })
    choix = viz.choisir(df_dates, "date")
    fig = viz.construire(df_dates, choix["kind"], choix["col_x"],
                         choix["col_y"])
    assert isinstance(fig, go.Figure)
    assert len(fig.data) > 0
    assert len(fig.data[0].x) == 3  # un point par jour, pas un bloc unique
    assert "par jour" in (fig.layout.title.text or "")
    phrase = viz.insight(df_dates, choix["kind"], choix["col_x"])
    assert "pic le" in phrase and "05/09/2026" in phrase


def test_est_date():
    assert viz.est_date(df["date"])
    assert not viz.est_date(df["ville"])
    assert viz.type_colonne(df["montant"]) == "nombre"
    assert viz.type_colonne(df["ville"]) == "categorie"
    assert viz.type_colonne(df["date"]) == "date"
