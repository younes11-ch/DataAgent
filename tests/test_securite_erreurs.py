# Securite interface (point 3) : jamais de chemins ni de secrets
# dans les erreurs, le journal ou les rapports. Sans cle API.

import pandas as pd

import data_agent
import export_pdf
import rapport

SALES = [
    "KeyError: 'C:\\Users\\moi\\data.csv'",
    "FileNotFoundError: [Errno 2] /home/admin/.env",
    "motif interdit détecté : open(",
    "TIMEOUT",
    "ValueError: clé LLM_FAUSSE_CLE_1234567890 invalide",
    "Traceback (most recent call last):\n  File \"/app/app.py\"",
]

INTERDITS = ["C:\\", "/home/", "/app/", ".env", "LLM_", "Traceback"]


def test_traduire_erreur_toujours_generique():
    profil = {"colonnes": ["a", "b"]}
    for erreur in SALES:
        msg = data_agent.traduire_erreur(erreur, profil)
        assert msg, erreur
        for interdit in INTERDITS:
            assert interdit not in msg, (erreur, msg)


def test_traduire_erreur_garde_colonne_utile():
    msg = data_agent.traduire_erreur("KeyError: 'salaire'",
                                     {"colonnes": ["age", "ville"]})
    assert "n'existe pas" in msg and "salaire" in msg


def test_nettoyer_erreur():
    sale = ("File 'C:\\Temp\\x.csv' key=LLM_FAUSSE_CLE_1234567890123456 "
            "err /tmp/yy tok=ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890")
    propre = data_agent._nettoyer_erreur(sale)
    for interdit in ["C:\\Temp", "LLM_FAUSSE", "/tmp/yy", "ABCDEF1234567890"]:
        assert interdit not in propre, propre
    assert "[chemin]" in propre and "[secret?]" in propre


def test_rapports_sans_fuite_ni_plantage():
    df = pd.DataFrame({"MODEL_API_KEY": ["LLM_FAUSSE_CLE_POISON_1234567890"] * 2,
                       "chemin": ["C:\\secret\\fichier.csv"] * 2,
                       "n": [1, 2]})
    html = rapport.generer_html(df, None, None,
                                {"fichier": "x.csv", "rapport": []},
                                "test", ["hypothèse"])
    assert "Traceback" not in html
    assert "LLM_FAUSSE_CLE_POISON_1234567890" not in html
    pdf = export_pdf.generer_pdf(
        "t", "s C:\\chemin\\x", ["r1"],
        [("S", ["l1", "Traceback (most recent call last)"])], [])
    assert isinstance(pdf, bytes) and len(pdf) > 100
