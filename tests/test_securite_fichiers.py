# Securite fichiers (point 4) : rien d'ecrit sur disque par l'app,
# dossier temp du sous-processus toujours nettoye. Sans cle API.
# (L'isolation entre visiteurs vient de st.session_state, cote serveur.)

import os
import tempfile

import pandas as pd

import data_agent
import export_pdf
import rapport


def test_temp_nettoye_apres_executer(monkeypatch):
    cree = []
    vraie = tempfile.TemporaryDirectory

    def espion(*args, **kwargs):
        t = vraie(*args, **kwargs)
        cree.append(t.name)
        return t

    monkeypatch.setattr(tempfile, "TemporaryDirectory", espion)
    df = pd.DataFrame({"a": [1]})
    data_agent.executer(df, "result = 1")
    data_agent.executer(df, "raise ValueError('x')")
    assert cree, "le sous-processus n'a pas utilisé de dossier temp ?"
    assert all(not os.path.exists(d) for d in cree), cree


def test_rapports_n_ecrivent_rien(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    rapport.generer_html(df, None, None, {"fichier": "x.csv", "rapport": []},
                         "t", [])
    rapport.graphiques_png(df, None)
    export_pdf.generer_pdf("t", "s", ["r"], [("S", ["l"])], [])
    assert list(tmp_path.iterdir()) == []
