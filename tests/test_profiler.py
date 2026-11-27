# Tests du score de qualité (sans clé API, pandas seul).

from pathlib import Path

import pandas as pd

import profiler

RACINE = Path(__file__).resolve().parent.parent


def test_donnees_propres_score_100():
    df = pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": ["x", "y", "z"]})
    res = profiler.score_qualite(df)
    assert res["score"] == 100
    assert res["manquantes"] == 0 and res["doublons"] == 0
    assert res["colonnes_vides"] == []


def test_manquantes_et_doublons_font_baisser():
    df = pd.DataFrame({"a": [1.0, None, 1.0, 2.0], "b": ["x", "y", "x", "z"]})
    res = profiler.score_qualite(df)
    assert res["manquantes"] == 1
    assert res["doublons"] == 1
    assert 0 < res["score"] < 100


def test_colonne_quasi_vide_penalisee_et_score_plafonne():
    df = pd.DataFrame({"a": [None] * 9 + [1.0], "b": range(10)})
    res = profiler.score_qualite(df)
    assert res["colonnes_vides"] == ["a"]
    assert res["score"] < 100 and res["manquantes"] == 9


def test_vide_vaut_zero_sans_crasher():
    assert profiler.score_qualite(pd.DataFrame())["score"] == 0
    assert profiler.score_qualite(None)["score"] == 0


def test_nettoyage_ameliore_le_score():
    sale = pd.read_csv(RACINE / "ventes_sales.csv", encoding="latin-1")
    avant = profiler.score_qualite(sale)["score"]
    propre = sale.dropna().reset_index(drop=True)
    assert profiler.score_qualite(propre)["score"] >= avant
