# Tests du résumé exécutif local (sans appel IA).

import pandas as pd

import data_agent


def test_repli_5_lignes_factuelles():
    df = pd.DataFrame({"a": [1, 2, 3], "b": list("xyz")})
    lignes = data_agent._resume_repli(df, None, {"fichier": "t.csv", "rapport": []})
    assert len(lignes) == 5
    assert "3 lignes" in lignes[0] and "2 colonnes" in lignes[0]
    assert "Données déjà propres." in lignes[1]
