# Tests des séries temporelles (sans clé API, données simulées).

import importlib.util

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest

import series

STATSMODELS = importlib.util.find_spec("statsmodels") is not None


def _rng():
    """Tirage frais par test : l'ordre d'exécution ne change plus les seuils."""
    return np.random.default_rng(11)


def _df_tendance_saison(n=120):
    rng = _rng()
    t = np.arange(n)
    y = 0.5 * t + 10 * np.sin(2 * np.pi * t / 7) + rng.normal(0, 1, n)
    return pd.DataFrame({"date": pd.date_range("2026-01-01", periods=n),
                         "y": y})


@pytest.mark.skipif(not STATSMODELS, reason="statsmodels absent")
def test_tendance_hausse_et_saison_7():
    res = series.analyser(_df_tendance_saison(), "date", "y", horizon=7)
    assert res["ok"]
    assert res["tendance"]["direction"] == "hausse"
    assert res["saison"] and res["saison"]["periode"] == 7
    assert len(res["prevision"]) == 7
    assert "Holt-Winters" in res["methode"]
    assert isinstance(res["figure"], go.Figure)
    assert len(res["figure"].data) >= 2
    assert any("Prévision" in (t.name or "") for t in res["figure"].data)
    assert "hausse" in res["explication"]


def test_serie_stable():
    df = pd.DataFrame({"date": pd.date_range("2026-01-01", periods=30),
                       "y": 5.0 + _rng().normal(0, 0.01, 30)})
    res = series.analyser(df, "date", "y")
    assert res["ok"]
    assert res["tendance"]["direction"] == "stable"
    assert res["saison"] is None


def test_garde_fous():
    court = pd.DataFrame({"date": pd.date_range("2026-01-01", periods=5),
                          "y": range(5)})
    assert series.analyser(court, "date", "y")["ok"] is False
    df = _df_tendance_saison()
    assert series.analyser(df, "y", "date")["ok"] is False  # rôles inversés
    assert series.analyser(df, "inconnue", "y")["ok"] is False
    assert series.analyser(df, "date", "y", horizon=99)["ok"] is False


def test_garde_un_point_et_horizon_invalide():
    memes_dates = pd.DataFrame(
        {"date": ["2026-01-01"] * 8, "y": range(8)})
    res = series.analyser(memes_dates, "date", "y")
    assert res["ok"] is False and "périodes" in res["erreur"]
    df = _df_tendance_saison()
    assert series.analyser(df, "date", "y", horizon=None)["ok"] is False
    assert series.analyser(df, "date", "y", horizon="abc")["ok"] is False


def test_colonnes_dates():
    df = _df_tendance_saison()
    df["ville"] = "Lyon"
    assert series.colonnes_dates(df) == ["date"]
