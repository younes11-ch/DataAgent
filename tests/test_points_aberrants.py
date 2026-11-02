# Tests de la détection de valeurs aberrantes (sans appel IA).

import pandas as pd

import points_aberrants as pa


def test_iqr_trouve_valeur_extreme():
    masque = pa.detecter(pd.Series([10] * 20 + [500]), "iqr")
    assert bool(masque.iloc[-1]) and int(masque.sum()) == 1


def test_zscore_colonne_constante():
    assert int(pa.detecter(pd.Series([5] * 30), "zscore").sum()) == 0


def test_isolation_forest_trouve_extreme():
    masque = pa.detecter(pd.Series(list(range(50)) + [10000]), "isolation_forest")
    assert bool(masque.iloc[-1])


def test_analyser_colonne_texte():
    res = pa.analyser(pd.DataFrame({"ville": ["a", "b"]}), "ville", "iqr")
    assert res["n"] == 0 and "pas numérique" in res["explication"]


def test_analyser_rend_tableau_et_png():
    res = pa.analyser(pd.DataFrame({"x": [1] * 20 + [999]}), "x", "iqr")
    assert res["n"] == 1
    assert res["figure"][:8] == b"\x89PNG\r\n\x1a\n"
    assert "habituel" in res["explication"]
