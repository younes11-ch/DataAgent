# Pipeline d'audit : sources, logique, sécurité, décideur (sans API).

import audit


DEUX_SOURCES = [
    {"nom": "Insee", "url": "https://www.insee.fr/x"},
    {"nom": "Wiki", "url": "https://fr.wikipedia.org/wiki/Y"},
]
UNE_SOURCE = DEUX_SOURCES[:1]


def test_sources_sans_chiffre_ok():
    rap = audit.auditer_sources("Bonjour, voici une explication.", DEUX_SOURCES)
    assert rap["ok"] and not rap["problemes"]


def test_sources_chiffre_sans_source_refuse():
    rap = audit.auditer_sources("Le taux vaut 39,4 %.", [])
    assert not rap["ok"] and rap["non_recoupes"]


def test_sources_exige_deux_independantes():
    rap = audit.auditer_sources("Le taux vaut 39,4 %.", UNE_SOURCE)
    assert not rap["ok"]
    assert any("seule source" in p for p in rap["problemes"])
    rap2 = audit.auditer_sources("Le taux vaut 39,4 %.", DEUX_SOURCES)
    assert rap2["ok"]


def test_sources_extraits_non_recoupes():
    rap = audit.auditer_sources("Le taux vaut 39,4 %.", DEUX_SOURCES,
                                extraits=["le ciel est bleu"])
    assert not rap["ok"] and rap["non_recoupes"]
    rap2 = audit.auditer_sources("Le taux vaut 39,4 %.", DEUX_SOURCES,
                                 extraits=["taux de 39,4 % mesuré"])
    assert rap2["ok"]


def test_logique_annees_exemptees():
    assert audit.auditer_logique("Données 2024.", [], "")["ok"]
    rap = audit.auditer_sources("Données 2024.", DEUX_SOURCES)
    assert rap["ok"]


def test_logique_chiffre_calcule_ok():
    rap = audit.auditer_logique("Le total vaut 60.", [(None, 60.0)], "total ?")
    assert rap["ok"]
    rap2 = audit.auditer_logique("Le total vaut 99 999.", [(None, 60.0)],
                                 "total ?")
    assert not rap2["ok"]


def test_logique_date_impossible():
    rap = audit.auditer_logique("Réunion le 32 janvier.", [], "")
    assert not rap["ok"]


def test_securite_detecte_sensible():
    assert not audit.auditer_securite("Écris à martin@example.com.")["ok"]
    assert not audit.auditer_securite("clé LLM_FAUSSE_CLE_TEST_1234567890.")["ok"]
    assert not audit.auditer_securite("ouvre C:\\Users\\moi\\data.csv")["ok"]
    assert not audit.auditer_securite("Traceback (most recent call last)")["ok"]
    assert audit.auditer_securite("Le taux vaut 39,4 % (n=239).")["ok"]


def test_securite_contenu_dangereux():
    assert not audit.auditer_securite("import os\nresult = 1")["ok"]
    assert not audit.auditer_securite("lance rm -rf / pour nettoyer")["ok"]


def test_decideur_ok_corriger_refuse():
    ok = audit.decider({"ok": True, "problemes": [], "non_recoupes": []},
                       {"ok": True, "problemes": []},
                       {"ok": True, "problemes": []}, 2)
    assert (ok["verdict"], ok["confiance"]) == ("OK", "élevé")
    corr = audit.decider({"ok": False, "problemes": ["une seule source"],
                          "non_recoupes": []},
                         {"ok": True, "problemes": []},
                         {"ok": True, "problemes": []}, 1)
    assert corr["verdict"] == "À CORRIGER"
    refus = audit.decider({"ok": True, "problemes": [], "non_recoupes": []},
                          {"ok": True, "problemes": []},
                          {"ok": False, "problemes": ["contient e-mail"]}, 2)
    assert refus["verdict"] == "REFUSE" and refus["confiance"] == "faible"


def test_pipeline_corrige_en_boucle():
    appels = []

    def principal(problemes):
        appels.append(problemes)
        if problemes:
            return "Le ciel est bleu."
        return "Le taux vaut 99 999 %."

    res = audit.pipeline_audit("taux ?", principal, DEUX_SOURCES,
                               donnees_calculees=[("60", 60.0)],
                               extraits=["taux de 60 mesuré"])
    assert res["verdict"] == "OK" and res["boucles"] == 2
    assert appels[0] is None and appels[1]


def test_pipeline_plafonne_les_boucles():
    res = audit.pipeline_audit("taux ?", lambda p: "Le taux vaut 99 999 %.",
                               DEUX_SOURCES,
                               donnees_calculees=[("60", 60.0)],
                               extraits=["taux de 60 mesuré"], max_boucles=3)
    assert res["verdict"] == "À CORRIGER" and res["boucles"] == 4
    assert res["points_non_verifies"]


def test_pipeline_refuse_securite():
    res = audit.pipeline_audit("contact ?", lambda p: "Écris à a@b.com.",
                               DEUX_SOURCES)
    assert res["verdict"] == "REFUSE"
