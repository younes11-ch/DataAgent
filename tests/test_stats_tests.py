# Tests des tests statistiques automatiques (sans clé API, données simulées).

import numpy as np
import pandas as pd

import stats_tests

rng = np.random.default_rng(7)


def test_ttest_significatif_et_ns():
    df = pd.DataFrame({"x": np.concatenate([rng.normal(0, 1, 100),
                                            rng.normal(1, 1, 100)]),
                       "g": ["a"] * 100 + ["b"] * 100})
    res = stats_tests.lancer(df, "ttest", "x", "g")
    assert res["ok"] and res["p"] < 0.05
    assert res["effet_nom"] == "d de Cohen" and res["effet"] > 0.5
    assert "significatif" in res["explication"]
    calme = pd.DataFrame({"x": np.concatenate([rng.normal(0, 1, 80),
                                               rng.normal(0, 1, 80)]),
                          "g": ["a"] * 80 + ["b"] * 80})
    res2 = stats_tests.lancer(calme, "ttest", "x", "g")
    assert res2["ok"] and res2["p"] > 0.05
    assert "pas d'écart significatif" in res2["explication"]


def test_mannwhitney_ok():
    df = pd.DataFrame({"x": list(range(20)), "g": ["a"] * 10 + ["b"] * 10})
    res = stats_tests.lancer(df, "mannwhitney", "x", "g")
    assert res["ok"] and res["p"] < 0.05


def test_anova_et_kruskal():
    df = pd.DataFrame({"x": np.concatenate([rng.normal(0, 1, 60),
                                            rng.normal(0, 1, 60),
                                            rng.normal(2, 1, 60)]),
                       "g": ["a"] * 60 + ["b"] * 60 + ["c"] * 60})
    ra = stats_tests.lancer(df, "anova", "x", "g")
    assert ra["ok"] and ra["p"] < 0.05 and ra["effet"] > 0
    rk = stats_tests.lancer(df, "kruskal", "x", "g")
    assert rk["ok"] and rk["p"] < 0.05


def test_chi2_associe_et_independant():
    liee = pd.DataFrame({"a": ["x"] * 50 + ["y"] * 50,
                         "b": ["p"] * 40 + ["q"] * 10 + ["p"] * 10 + ["q"] * 40})
    r1 = stats_tests.lancer(liee, "chi2", "a", "b")
    assert r1["ok"] and r1["p"] < 0.05
    assert "pas une cause" in r1["explication"]
    libre = pd.DataFrame({"a": ["x"] * 50 + ["y"] * 50,
                          "b": (["p", "q"] * 25) + (["p", "q"] * 25)})
    r2 = stats_tests.lancer(liee, "chi2", "a", "b")
    assert r2["ok"]
    r3 = stats_tests.lancer(libre, "chi2", "a", "b")
    assert r3["ok"] and r3["p"] > 0.05


def test_correlation_forte():
    x = np.linspace(0, 10, 50)
    df = pd.DataFrame({"x": x, "y": 2 * x + rng.normal(0, 0.1, 50)})
    res = stats_tests.lancer(df, "correlation", "x", "y")
    assert res["ok"] and res["effet"] > 0.99 and res["p"] < 0.05


def test_choix_auto():
    df = pd.DataFrame({"n1": [1.0, 2.0, 3.0], "n2": [2.0, 4.0, 6.0],
                       "c2": ["a", "a", "b"], "c3": ["a", "b", "c"],
                       "c": ["u", "v", "u"]})
    assert stats_tests.choisir(df, "n1", "n2") == "correlation"
    assert stats_tests.choisir(df, "n1", "c2") == "ttest"
    assert stats_tests.choisir(df, "n1", "c3") == "anova"
    assert stats_tests.choisir(df, "c", "c2") == "chi2"
    assert stats_tests.choisir(df, "c2", "n1") == "ttest"
    assert stats_tests.choisir(df, "c", None).startswith("erreur:")
    r = stats_tests.lancer(df, "auto", "n1", "n2")
    assert r["ok"] and r["test"] == "correlation"


def test_garde_fous():
    df = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0], "g": ["a", "a", "b", "b"]})
    assert stats_tests.lancer(df, "ttest", "g", "x")["ok"]  # ordre inversé admis
    gros = pd.DataFrame({"x": [1.0] * 12, "g": [f"v{i}" for i in range(12)]})
    assert not stats_tests.lancer(gros, "anova", "x", "g")["ok"]
    assert not stats_tests.lancer(df, "ttest", "inconnue", "g")["ok"]
    assert not stats_tests.lancer(df, "chi2", "x", "g")["ok"]
