# Contrat tests.json : les cas des tests intégrés (lus par app.py, jamais
# par pytest jusqu'ici) sont vérifiés ici sans clé API, avec réponses
# hors-ligne forcées (déterministes même si une clé est configurée).

import json
from pathlib import Path

import pandas as pd

import data_agent
import scan

RACINE = Path(__file__).resolve().parent.parent
TYPES = {"nombre", "refus_colonne", "sans_causalite", "contient"}


def _cas():
    with open(RACINE / "tests.json", encoding="utf-8") as f:
        cas = json.load(f)
    assert isinstance(cas, list) and cas
    return cas


def _sans_api(monkeypatch):
    monkeypatch.setattr(data_agent, "cle_api_disponible", lambda: False)


def _employee():
    return pd.read_csv(RACINE / "Employee.csv").drop_duplicates().reset_index(drop=True)


def test_schema_cas():
    for cas in _cas():
        assert cas.get("question") and cas.get("type") in TYPES, cas
        if cas["type"] == "nombre":
            assert isinstance(cas["attendu"], (int, float)), cas
            assert isinstance(cas.get("tolerance", 0), (int, float)), cas


def test_nombre_lignes():
    cas = next(c for c in _cas()
               if c["type"] == "nombre" and "lignes" in c["question"].lower())
    assert abs(len(_employee()) - cas["attendu"]) <= cas.get("tolerance", 0)


def test_nombre_taux_departs():
    cas = next(c for c in _cas()
               if c["type"] == "nombre" and "taux" in c["question"].lower())
    emp = _employee()
    taux = float(scan.scan_anomalies(emp, "LeaveOrNot")["taux_global"]) * 100
    assert abs(taux - cas["attendu"]) <= cas.get("tolerance", 0)


def test_nombre_age_moyen():
    cas = next(c for c in _cas()
               if c["type"] == "nombre" and "moyen" in c["question"].lower())
    assert abs(float(_employee()["Age"].mean()) - cas["attendu"]) <= cas.get("tolerance", 0)


def test_refus_colonne(monkeypatch):
    _sans_api(monkeypatch)
    cas = next(c for c in _cas() if c["type"] == "refus_colonne")
    emp = _employee()
    profil = data_agent.profile_data(emp, "Employee.csv")
    reponse = data_agent.traduire_erreur("KeyError: 'salaire'", profil)
    assert cas["attendu"].lower() in reponse.lower()


def test_contient_sens_non_defini(monkeypatch):
    _sans_api(monkeypatch)
    cas = next(c for c in _cas() if c["type"] == "contient")
    mini = pd.DataFrame({"a": [1, 2], "PaymentTier": [1, 2]})
    profil = data_agent.profile_data(mini, "mini.csv")
    profil["ambigues"] = ["PaymentTier"]
    reponse = data_agent.analyser_question(mini, profil, cas["question"], [])
    assert cas["attendu"].lower() in reponse["reponse"].lower()


def test_sans_causalite(monkeypatch):
    _sans_api(monkeypatch)
    cas = next(c for c in _cas() if c["type"] == "sans_causalite")
    emp = _employee()
    profil = data_agent.profile_data(emp, "Employee.csv")
    reponse = data_agent.analyser_question(emp, profil, cas["question"], [])
    plat = (reponse["reponse"] or "").lower()
    assert not any(m in plat or m.replace("é", "e") in plat
                   for m in [w.lower() for w in data_agent.MOTS_CAUSALS])
