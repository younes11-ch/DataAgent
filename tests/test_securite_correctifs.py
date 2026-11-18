# Correctifs de l'audit : chaque faille prouvée doit rester fermée. Sans clé API.

import pandas as pd

import data_agent
import recherche

DF = pd.DataFrame({"ville": ["Paris", "Lyon"], "montant": [10, 20]})

# Vecteurs prouvés le 18 nov (sondes P2b/P3b/P4b/P5) + famille proche.
VECTEURS_FERMES = [
    "ds = np.lib.npyio.DataSource('.')\nprint(ds.open ('requirements.txt'))",
    "h = pd.io.common.get_handle('requirements.txt', 'r')\nresult = 1",
    "result = pd.HDFStore('x.h5')",
    "print('{0}'.format(df))",
    "print('{0.\\x5f\\x5fclass\\x5f\\x5f}'.format(df))",
    "license()",
]


def test_vecteurs_prouves_refuses():
    for code in VECTEURS_FERMES:
        run = data_agent.executer(DF, code)
        assert run["ok"] is False, code
        assert "interdit" in (run["erreur"] or ""), (code, run["erreur"])


def test_cle_api_masquee_dans_le_log(monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "FAUSSE-CLE-TEST-1234567890")
    run = data_agent.executer(DF, "print('voici FAUSSE-CLE-TEST-1234567890')")
    assert run["ok"] is True
    assert "FAUSSE-CLE-TEST-1234567890" not in run["log"]
    assert "[clé API]" in run["log"]


def test_resultat_volumineux_refuse():
    run = data_agent.executer(DF, "result = 'x' * 9_000_000")
    assert run["ok"] is False
    assert "volumineux" in (run["erreur"] or "")


def test_telecharger_redirection_hors_http_refusee(monkeypatch):
    class FausseRep:
        def geturl(self):
            return "file:///home/appuser/.env"

        def read(self, n=-1):
            return b""

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(recherche.urllib.request, "urlopen",
                        lambda *a, **k: FausseRep())
    try:
        recherche.telecharger_fichier("https://example.com/data.csv")
    except ValueError as e:
        assert "redirection" in str(e)
    else:
        raise AssertionError("redirection file:// acceptée !")


def test_nettoyer_erreur_nouveaux_motifs():
    sale = ("password: s3cr3t! chemin /data/x.csv et "
            "\\\\\\\\SERVEUR\\\\partage\\\\f.csv")
    propre = data_agent._nettoyer_erreur(sale)
    assert "s3cr3t" not in propre
    assert "/data/x.csv" not in propre
    assert "SERVEUR" not in propre
