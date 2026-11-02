# Détection de valeurs aberrantes : IQR, Z-score, Isolation Forest.
# Calculs 100 % déterministes (pandas + sklearn), sans appel IA.

from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

METHODES = ["iqr", "zscore", "isolation_forest"]

LIBELLES = {
    "iqr": "Écart interquartile (IQR)",
    "zscore": "Z-score (écart à la moyenne)",
    "isolation_forest": "Isolation Forest (IA non supervisée)",
}

SEUIL_Z = 3.0
CONTAMINATION = 0.05
N_MIN_ISOLATION = 10


def detecter(serie: pd.Series, methode: str) -> pd.Series:
    """Rend un masque booléen (True = aberrant), NaN jamais signalés."""
    propre = pd.to_numeric(serie, errors="coerce")
    masque = pd.Series(False, index=serie.index)
    vals = propre.dropna()
    if vals.empty:
        return masque
    if methode == "iqr":
        q1, q3 = float(vals.quantile(0.25)), float(vals.quantile(0.75))
        ecart = q3 - q1
        bas, haut = q1 - 1.5 * ecart, q3 + 1.5 * ecart
        masque = (propre < bas) | (propre > haut)
    elif methode == "zscore":
        ecart_type = float(vals.std())
        if ecart_type == 0:
            return masque
        z = (propre - float(vals.mean())).abs() / ecart_type
        masque = z > SEUIL_Z
    elif methode == "isolation_forest":
        if len(vals) < N_MIN_ISOLATION:
            return masque
        modele = IsolationForest(contamination=CONTAMINATION, random_state=42)
        pred = modele.fit_predict(vals.to_numpy().reshape(-1, 1))
        masque.loc[vals.index] = pred == -1
    return masque.fillna(False)


def _explication(methode: str, n: int, total: int, vals: pd.Series) -> str:
    if n == 0:
        return (f"Aucune valeur aberrante détectée sur {total} valeurs "
                f"({LIBELLES[methode]}).")
    base = f"{n} valeur(s) aberrante(s) sur {total} ({LIBELLES[methode]}) : "
    if methode == "iqr":
        q1, q3 = float(vals.quantile(0.25)), float(vals.quantile(0.75))
        ecart = q3 - q1
        return (base + f"ces valeurs sortent de l'intervalle habituel "
                f"[{q1 - 1.5 * ecart:.2f} ; {q3 + 1.5 * ecart:.2f}].")
    if methode == "zscore":
        return (base + f"ces valeurs s'écartent de plus de {SEUIL_Z} écarts-types "
                f"de la moyenne ({float(vals.mean()):.2f}).")
    return (base + "ces valeurs sont isolées du reste du groupe "
            "(détectées par Isolation Forest).")


def analyser(df: pd.DataFrame, colonne: str, methode: str) -> dict:
    """Analyse une colonne et rend anomalies + explication en français.

    Rend {"tableau" (DataFrame), "explication" (str), "n", "figure" (PNG)}.
    Si la colonne n'est pas numérique, le tableau est vide et l'explication
    le dit simplement.
    """
    vide = {"tableau": pd.DataFrame(), "explication": "", "n": 0, "figure": b""}
    if methode not in METHODES:
        methode = "iqr"
    if colonne not in df.columns:
        vide["explication"] = f"La colonne {colonne} n'existe pas."
        return vide
    vals = pd.to_numeric(df[colonne], errors="coerce").dropna()
    if vals.empty:
        vide["explication"] = (f"La colonne {colonne} n'est pas numérique : "
                               "on ne peut y chercher des valeurs aberrantes.")
        return vide
    masque = detecter(df[colonne], methode)
    idx = df.index[masque.fillna(False)]
    tableau = pd.DataFrame({"ligne": [int(i) + 1 for i in idx],
                            colonne: [df.loc[i, colonne] for i in idx]})
    vide["tableau"] = tableau.reset_index(drop=True)
    vide["n"] = len(tableau)
    vide["explication"] = _explication(methode, len(tableau), len(vals), vals)
    vide["figure"] = figure(df[colonne], masque, colonne)
    return vide


def figure(serie: pd.Series, masque: pd.Series, colonne: str) -> bytes:
    """Nuage de points : valeurs en bleu, aberrantes en rouge (PNG)."""
    vals = pd.to_numeric(serie, errors="coerce")
    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.scatter(vals.index, vals, s=12, label="Valeurs normales")
    anormales = vals[masque.fillna(False)]
    if not anormales.empty:
        ax.scatter(anormales.index, anormales, s=36, color="red",
                   label=f"Valeurs aberrantes ({len(anormales)})")
    ax.set_title(f"Valeurs aberrantes : {colonne}")
    ax.set_xlabel("Ligne")
    ax.set_ylabel(str(colonne))
    ax.legend(fontsize=8)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()
