# Recherche sans upload : reformulation, croisement, garde-fous (sans réseau).

import data_agent
import recherche


def test_reformuler_garde_question_complete():
    reqs = recherche.reformuler_requetes("Quel est le taux de chômage en France en 2024 ?")
    assert reqs and reqs[0].startswith("Quel est")
    assert len(reqs) <= 3


def test_reformuler_vide():
    assert recherche.reformuler_requetes("") == []
    assert recherche.reformuler_requetes("  ") == []


def test_domaine_et_independance():
    assert recherche.domaine("https://fr.wikipedia.org/wiki/X") == "fr.wikipedia.org"
    assert recherche.domaine("https://www.example.com/a") == "example.com"
    deux = [{"url": "https://fr.wikipedia.org/wiki/A"},
            {"url": "https://www.insee.fr/x"}]
    assert recherche.domaines_independants(deux)
    assert not recherche.domaines_independants(deux[:1])
    assert not recherche.domaines_independants([])


def test_dedupliquer():
    lignes = [{"nom": "A", "url": "https://x.example/a", "extrait": "1"},
              {"nom": "A", "url": "https://x.example/a", "extrait": "1"},
              {"nom": "B", "url": "", "extrait": "2"}]
    assert len(recherche.dedupliquer(lignes)) == 1


def test_rechercher_croise_plusieurs_requetes():
    def fausse(requete):
        return [{"nom": f"Src {requete[:5]}", "url": f"https://{len(requete)}.example/x",
                "extrait": f"extrait {requete}"}]

    res = recherche.rechercher("taux de chômage France 2024",
                               max_requetes=2, fonction_recherche=fausse)
    assert len(res["requetes"]) >= 1
    assert len(res["sources"]) >= 1
    assert set(res["par_requete"]) == set(res["requetes"])


def test_rechercher_erreur_source_isolee():
    def cassee(requete):
        raise RuntimeError("réseau coupé")

    res = recherche.rechercher("question ?", fonction_recherche=cassee)
    assert res["sources"] == []


def test_sans_upload_refuse_si_desactive(monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    res = data_agent.analyser_sans_upload("taux de chômage ?",
                                          permettre_recherche=False)
    assert res["verdict"] == "REFUSE"
    assert res["sources"] == [] and res["confiance"] == "faible"


def test_sans_upload_question_vide(monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    res = data_agent.analyser_sans_upload("   ")
    assert res["verdict"] == "REFUSE"


def test_sans_upload_hors_ligne_avec_sources(monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)

    def fausse(requete):
        return [
            {"nom": "Insee", "url": "https://www.insee.fr/x",
             "extrait": "Le taux de chômage vaut 7,4 % au deuxième trimestre."},
            {"nom": "Wikipédia — Chômage",
             "url": "https://fr.wikipedia.org/wiki/Chômage",
             "extrait": "Le taux de chômage est de 7,4 % selon les données."},
        ]

    res = data_agent.analyser_sans_upload("Quel est le taux de chômage ?",
                                          fonction_recherche=fausse)
    assert res["verdict"] in ("OK", "A CORRIGER")
    assert len(res["sources"]) == 2
    assert res["confiance"] in ("moyen", "élevé")
    assert "7,4" in res["reponse"]


def test_sites_importants_reconnus():
    assert recherche.est_important("https://www.kaggle.com/datasets/x")
    assert recherche.est_important("https://www.data.gouv.fr/fr/datasets/y")
    assert recherche.est_important("https://www.insee.fr/fr/statistiques/z")
    assert not recherche.est_important("https://blog-perso.example/article")
    assert not recherche.est_important("")


def test_trier_sources_importants_d_abord():
    melange = [
        {"nom": "Blog", "url": "https://blog-perso.example/a", "extrait": "x"},
        {"nom": "Kaggle", "url": "https://www.kaggle.com/datasets/b", "extrait": "y"},
        {"nom": "Wiki", "url": "https://fr.wikipedia.org/wiki/C", "extrait": "z"},
    ]
    tries = recherche.trier_sources(melange)
    assert tries[0]["nom"] == "Kaggle"


def test_chercher_datagouv_parse(monkeypatch):
    def faux_json(url, timeout=10):
        return {"data": [
            {"title": "Chômage trimestriel",
             "description": "<p>Taux par trimestre.</p>",
             "page": "https://www.data.gouv.fr/fr/datasets/123/",
             "resources": [{}, {}]},
            {"title": "", "page": "", "resources": []},
        ]}

    monkeypatch.setattr(recherche, "_get_json", faux_json)
    res = recherche.chercher_datagouv("chômage")
    assert len(res) == 1
    assert res[0]["url"].startswith("https://www.data.gouv.fr")
    assert "2 ressources" in res[0]["extrait"]
    assert recherche.est_important(res[0]["url"])


def test_chercher_datagouv_panne_isolee(monkeypatch):
    def casse(url, timeout=10):
        raise RuntimeError("réseau coupé")

    monkeypatch.setattr(recherche, "_get_json", casse)
    assert recherche.chercher_datagouv("chômage") == []


def test_sans_upload_sans_source_ne_confirme_pas(monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    res = data_agent.analyser_sans_upload("question obscure ?",
                                          fonction_recherche=lambda q: [])
    assert "je ne peux pas confirmer" in res["reponse"].lower()
    assert res["points_non_verifies"]
