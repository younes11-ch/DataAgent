# Imputation déterministe des valeurs manquantes (sans IA).
# Appliquée APRÈS le Nettoyeur, selon la stratégie choisie par l'utilisateur.

from __future__ import annotations

import pandas as pd

STRATEGIES = ["auto", "supprimer", "moyenne", "mediane", "mode"]

LIBELLES = {
    "auto": "Automatique (ne rien changer)",
    "supprimer": "Supprimer les lignes incomplètes",
    "moyenne": "Remplir par la moyenne (nombres) / le mode (textes)",
    "mediane": "Remplir par la médiane (nombres) / le mode (textes)",
    "mode": "Remplir par la valeur la plus fréquente (mode)",
}


def appliquer(df: pd.DataFrame, strategie: str) -> dict:
    """Applique la stratégie et rend {"df", "journal", "restantes"}.

    Ne modifie jamais le DataFrame d'origine (travaille sur une copie).
    "auto" ne change rien : on garde le résultat du Nettoyeur.
    """
    journal: list[str] = []
    if strategie not in STRATEGIES:
        strategie = "auto"
    manq_avant = int(df.isna().sum().sum())
    if strategie == "auto" or manq_avant == 0:
        if manq_avant == 0:
            journal.append("Aucune valeur manquante : rien à remplir.")
        else:
            journal.append("Imputation automatique conservée "
                           "(médiane/mode déjà appliqués par le nettoyage).")
        return {"df": df.copy(), "journal": journal, "restantes": manq_avant}

    res = df.copy()
    if strategie == "supprimer":
        lignes_avant = len(res)
        res = res.dropna().reset_index(drop=True)
        journal.append(f"{lignes_avant - len(res)} lignes incomplètes supprimées "
                       f"sur {lignes_avant} ({manq_avant} valeurs manquantes).")
    else:
        remplis = 0
        for col in res.columns:
            n_vides = int(res[col].isna().sum())
            if n_vides == 0:
                continue
            if strategie == "moyenne" and pd.api.types.is_numeric_dtype(res[col]):
                valeur = float(res[col].mean())
                methode = "la moyenne"
            elif strategie == "mediane" and pd.api.types.is_numeric_dtype(res[col]):
                valeur = float(res[col].median())
                methode = "la médiane"
            else:
                modes = res[col].mode(dropna=True)
                if modes.empty:
                    journal.append(f"Colonne {col} entièrement vide : "
                                   "impossible à remplir, conservée telle quelle.")
                    continue
                valeur = modes.iloc[0]
                methode = "le mode"
                if strategie == "moyenne":
                    methode = "le mode (colonne texte, pas de moyenne possible)"
            res[col] = res[col].fillna(valeur)
            remplis += n_vides
            journal.append(f"Colonne {col} : {n_vides} valeurs remplies par {methode}.")
        if remplis == 0:
            journal.append("Aucune valeur n'a pu être remplie.")
    restantes = int(res.isna().sum().sum())
    return {"df": res, "journal": journal, "restantes": restantes}
