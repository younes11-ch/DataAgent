# Tests de l'imputation déterministe (sans appel IA).

import pandas as pd

import imputation


def _sale():
    return pd.DataFrame({"n": [1.0, 2.0, None, 4.0],
                         "t": ["a", "a", None, "b"]})


def test_moyenne_et_mode_texte():
    res = imputation.appliquer(_sale(), "moyenne")
    assert res["restantes"] == 0
    assert res["df"]["n"].iloc[2] == (1 + 2 + 4) / 3
    assert res["df"]["t"].iloc[2] == "a"
    assert len(res["journal"]) >= 2


def test_mediane():
    res = imputation.appliquer(_sale(), "mediane")
    assert res["df"]["n"].iloc[2] == 2.0
    assert res["restantes"] == 0


def test_supprimer():
    res = imputation.appliquer(_sale(), "supprimer")
    assert len(res["df"]) == 3
    assert res["restantes"] == 0


def test_auto_ne_change_rien_et_original_intact():
    df = _sale()
    res = imputation.appliquer(df, "auto")
    assert res["restantes"] == 2
    assert df.isna().sum().sum() == 2  # l'original n'est jamais modifié
