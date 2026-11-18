# Score de qualité des données 0-100 (animation 3, base du futur agent Profiler).
# Formule simple et expliquée : 100 − manquantes (×40) − doublons (×20)
# − 10 par colonne > 80 % vide (plafond 20). 100 % déterministe (pandas).

from __future__ import annotations

import pandas as pd

SEUIL_COLONNE_VIDE = 0.8
POIDS_MANQUANTES = 40
POIDS_DOUBLONS = 20
POIDS_COLONNE_VIDE = 10
PLAFOND_COLONNES_VIDES = 20


def score_qualite(df: pd.DataFrame) -> dict:
    """Rend {"score" (0-100), "manquantes", "doublons", "colonnes_vides"}."""
    vide = {"score": 0, "manquantes": 0, "doublons": 0, "colonnes_vides": []}
    if df is None or len(df) == 0 or len(df.columns) == 0:
        return vide
    manquantes = int(df.isna().sum().sum())
    doublons = int(df.duplicated().sum())
    vides = [str(c) for c in df.columns
             if float(df[c].isna().mean()) > SEUIL_COLONNE_VIDE]
    total = len(df) * len(df.columns)
    penalite = (round(manquantes / total * POIDS_MANQUANTES)
                + round(doublons / len(df) * POIDS_DOUBLONS)
                + min(PLAFOND_COLONNES_VIDES, POIDS_COLONNE_VIDE * len(vides)))
    return {"score": max(0, 100 - penalite), "manquantes": manquantes,
            "doublons": doublons, "colonnes_vides": vides}
