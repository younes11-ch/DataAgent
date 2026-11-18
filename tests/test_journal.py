# Tests du journal structuré et du script reproductible (sans clé API).

import sys

import pandas as pd

import imputation
import journal


def _sale():
    return pd.DataFrame({"n": [1.0, 2.0, None, 4.0],
                         "t": ["a", "a", None, "b"]})


def test_details_structures_colonne_action_lignes_justification():
    res = imputation.appliquer(_sale(), "moyenne")
    assert res["restantes"] == 0
    assert len(res["details"]) == 2
    for d in res["details"]:
        assert set(d) == {"colonne", "action", "lignes", "justification"}
        assert d["action"] == "remplir_manquants"
        assert d["lignes"] == 1
    assert res["remplissages"]["n"] == (1 + 2 + 4) / 3
    assert res["remplissages"]["t"] == "a"
    # Phrases d'origine inchangées (aucun affichage cassé).
    assert res["journal"][0] == "Colonne n : 1 valeurs remplies par la moyenne."


def test_details_supprimer():
    res = imputation.appliquer(_sale(), "supprimer")
    assert res["details"] == [{"colonne": "", "action": "supprimer_lignes_incompletes",
                               "lignes": 1,
                               "justification": "lignes avec valeurs manquantes, "
                                                "choix explicite de l'utilisateur"}]
    assert res["remplissages"] == {}


def test_entrees_nettoyage_doublons_et_phrases():
    nettoyage = {"rapport": ["2 lignes en double supprimées."],
                 "doublons": {"n": 2, "pct": 10.0}}
    entrees = journal.entrees_nettoyage(nettoyage, doublons_supprimes=True)
    assert entrees[0]["action"] == "supprimer_doublons"
    assert entrees[1] == {"colonne": "", "action": "nettoyage_auto", "lignes": None,
                          "justification": "2 lignes en double supprimées."}


def _rejouer(script, df, tmp_path, nom="entree.csv"):
    """Exécute le script généré sur df (via CSV temporaire) et rend le résultat relu."""
    entree = tmp_path / nom
    df.to_csv(entree, index=False)
    import os
    monkey_argv = ["script_nettoyage.py", str(entree)]
    ancien_argv, ancien_cwd = sys.argv, os.getcwd()
    os.chdir(tmp_path)
    sys.argv = monkey_argv
    try:
        exec(script, {"__name__": "__main__"})
    finally:
        sys.argv = ancien_argv
        os.chdir(ancien_cwd)
    return pd.read_csv(tmp_path / "donnees_nettoyees.csv")


def test_export_rejoue_imputation_moyenne(tmp_path):
    df = _sale()
    imp = imputation.appliquer(df, "moyenne")
    script = journal.exporter_script("", imp["remplissages"], "moyenne", "entree.csv")
    rejoue = _rejouer(script, df, tmp_path)
    pd.testing.assert_frame_equal(rejoue, imp["df"], check_dtype=False)


def test_export_rejoue_nettoyage_et_supprimer(tmp_path):
    df = pd.DataFrame({"n": [1.0, None, 1.0], "t": ["a", "b", "a"]})
    code = ("df_clean = df.drop_duplicates().reset_index(drop=True)\n"
            "rapport = ['doublons supprimés']")
    script = journal.exporter_script(code, {}, "supprimer", "entree.csv")
    rejoue = _rejouer(script, df, tmp_path)
    assert len(rejoue) == 1
    assert int(rejoue.isna().sum().sum()) == 0


def test_export_rejoue_fichier_sale_reel(tmp_path):
    df = pd.read_csv("ventes_sales.csv", encoding="latin-1")
    assert int(df.isna().sum().sum()) > 0  # le fichier est bien sale
    imp = imputation.appliquer(df, "moyenne")
    assert imp["restantes"] == 0
    script = journal.exporter_script("", imp["remplissages"], "moyenne",
                                     "ventes_sales.csv")
    rejoue = _rejouer(script, df, tmp_path)
    pd.testing.assert_frame_equal(rejoue, imp["df"], check_dtype=False)
