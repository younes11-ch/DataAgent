# Tests du mode démo hors-ligne (sans clé API, sans appel réseau).

import pandas as pd

import data_agent


def test_budget_question_repli_local_rapide(monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "fausse-cle-test")
    df = pd.DataFrame({"montant": [10, 20, 30]})
    profil = data_agent.profile_data(df, "t.csv")
    res = data_agent.analyser_question(
        df, profil, "Quel est le total de montant ?", [], budget_s=0)
    # Pas d'assertion de durée (fragile sur CI chargée) : le contrat,
    # c'est le repli local immédiat avec le bon message.
    assert "trop de temps" in res["reponse"]
    assert "60" in res["reponse"]


def test_pas_de_cle_sans_env(monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    assert data_agent.cle_api_disponible() is False


def test_cle_detectee_via_env(monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "fausse-cle-test")
    assert data_agent.cle_api_disponible() is True


def test_analyser_sans_cle_ne_leve_pas(monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    df = pd.DataFrame({"ville": ["Paris", "Lyon", "Paris"],
                       "ventes": [10, 20, 30]})
    profil = data_agent.profile_data(df, "t.csv")
    res = data_agent.analyser_question(
        df, profil, "Quel est le total des ventes ?", [])
    assert "60" in res["reponse"]
    assert res["tableau"] is not None
    assert res["figures"] == []
    assert "hors-ligne" in res["agents"]["verdict"]
