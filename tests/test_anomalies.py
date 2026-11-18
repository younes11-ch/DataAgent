# Tests de la détection combinée IQR + Z-score + IsolationForest (sans clé API).

import pandas as pd

import anomalies


def _avec_outlier():
    return pd.DataFrame({"prix": [10.0] * 20 + [1000.0]})


def test_consensus_detecte_l_outlier_evident():
    df = _avec_outlier()
    res = anomalies.resumer(df, "prix")
    assert res["n"] >= 1
    assert 1000.0 in list(res["tableau"]["prix"])
    assert res["figure"] != b""
    assert "médiane" in res["explication"]
    # L'outlier est bien dans les lignes signalées.
    assert 21 in res["lignes"]
    assert set(res["comptes"]) == {"iqr", "zscore", "isolation_forest"}


def test_pas_de_faux_positif_sans_consensus():
    df = pd.DataFrame({"x": [float(i) for i in range(1, 21)]})
    res = anomalies.resumer(df, "x")
    assert res["n"] == 0
    assert "Aucune valeur aberrante" in res["explication"]


def test_nan_jamais_signales():
    df = pd.DataFrame({"prix": [10.0] * 20 + [1000.0, None]})
    vote = anomalies.detecter_combine(df["prix"])
    assert not bool(vote["masque"].iloc[-1])
    assert vote["votes"].iloc[-1] == 0


def test_colonne_non_numerique_et_absente():
    df = pd.DataFrame({"ville": ["Lyon", "Paris"]})
    assert anomalies.resumer(df, "ville")["n"] == 0
    assert "pas numérique" in anomalies.resumer(df, "ville")["explication"]
    assert "n'existe pas" in anomalies.resumer(df, "inconnue")["explication"]


def test_decision_supprimer():
    df = _avec_outlier()
    res = anomalies.resumer(df, "prix")
    out = anomalies.appliquer_decision(df, "prix", "supprimer",
                                       index=res["index"])
    assert len(out["df"]) == len(df) - res["n"]
    assert out["df"]["prix"].max() == 10.0
    assert out["entree"]["action"] == "supprimer_anomalies"
    assert out["entree"]["lignes"] == res["n"]
    assert df["prix"].max() == 1000.0  # l'original n'est jamais modifié


def test_decision_corriger_par_mediane():
    df = _avec_outlier()
    res = anomalies.resumer(df, "prix")
    out = anomalies.appliquer_decision(df, "prix", "corriger",
                                       index=res["index"])
    assert out["df"]["prix"].max() == 10.0
    assert "médiane" in out["message"]
    assert out["entree"]["action"] == "corriger_anomalies"


def test_decision_garder_ne_change_rien():
    df = _avec_outlier()
    out = anomalies.appliquer_decision(df, "prix", "garder")
    pd.testing.assert_frame_equal(out["df"], df)
    assert out["entree"]["action"] == "anomalies_conservees"


def test_code_rejeu_rejoue_la_decision():
    df = _avec_outlier()
    res = anomalies.resumer(df, "prix")
    out = anomalies.appliquer_decision(df, "prix", "supprimer",
                                       index=res["index"])
    snippet = anomalies.code_rejeu("prix", "supprimer", list(res["index"]))
    rejou = {"df_clean": df.copy()}
    exec(snippet, {"__builtins__": __builtins__}, rejou)
    pd.testing.assert_frame_equal(rejou["df_clean"].reset_index(drop=True),
                                  out["df"].reset_index(drop=True))
