# Tests de la revérification indépendante (sans clé API, sandbox local).

import pandas as pd

import verif


def _df():
    return pd.DataFrame({"ville": ["Lyon", "Paris", "Lyon", "Paris"],
                         "montant": [10.0, 20.0, 30.0, 40.0]})


def test_reverification_retrouve_les_memes_chiffres():
    df = _df()
    code = "print(df['montant'].sum())\nresult = df.groupby('ville')['montant'].mean()"
    premier = verif.reverifier(df, code)
    second = verif.reverifier(df, code)
    assert premier["ok"] and second["ok"]
    assert premier["log"].strip() != ""
    comp = verif.comparer_nombres(premier["nombres"], second["nombres"])
    assert comp["identique"]
    assert "Revérifié" in verif.formater_verdict(comp)


def test_comparaison_detecte_un_ecart():
    comp = verif.comparer_nombres([("100", 100.0)], [("200", 200.0)])
    assert not comp["identique"]
    assert "cart" in verif.formater_verdict(comp).lower()


def test_code_en_echec_ne_crashe_pas():
    res = verif.reverifier(_df(), "print(1/0)")
    assert not res["ok"]
    assert res["erreur"] != ""
    assert res["nombres"] == []
