# Détection d'anomalies combinée : IQR + Z-score + IsolationForest (fonctionnalité 3).
# Une valeur est aberrante si au moins 2 méthodes sur 3 la signalent (vote).
# Calculs 100 % déterministes via points_aberrants ; explications en langage simple.
# L'utilisateur tranche ensuite : garder, corriger (médiane) ou supprimer.

from __future__ import annotations

import pandas as pd

import journal
import points_aberrants

METHODE_COMBINEE = "combine"
LIBELLE_COMBINEE = "Consensus des 3 méthodes (vote 2/3)"
SEUIL_VOTES = 2


def detecter_combine(serie: pd.Series) -> dict:
    """Vote des 3 méthodes. Rend {"masque", "detail", "votes"} (NaN jamais signalés)."""
    detail = {m: points_aberrants.detecter(serie, m).fillna(False)
              for m in points_aberrants.METHODES}
    votes = sum(m.astype(int) for m in detail.values())
    masque = votes >= SEUIL_VOTES
    return {"masque": masque.fillna(False), "detail": detail, "votes": votes}


def _fmt(v) -> str:
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)


def resumer(df: pd.DataFrame, colonne: str) -> dict:
    """Analyse combinée d'une colonne : tableau + explication simple + graphique.

    Rend {"tableau", "explication", "n", "figure", "lignes", "comptes", "colonne"}.
    "lignes" = numéros de lignes (base 1) ; "comptes" = anomalies par méthode.
    """
    vide = {"tableau": pd.DataFrame(), "explication": "", "n": 0, "figure": b"",
            "lignes": [], "index": [], "comptes": {}, "colonne": colonne}
    if colonne not in df.columns:
        vide["explication"] = f"La colonne {colonne} n'existe pas."
        return vide
    vals = pd.to_numeric(df[colonne], errors="coerce").dropna()
    if vals.empty:
        vide["explication"] = (f"La colonne {colonne} n'est pas numérique : "
                               "on ne peut y chercher des valeurs aberrantes.")
        return vide
    vote = detecter_combine(df[colonne])
    masque = vote["masque"]
    idx = df.index[masque]
    vide["tableau"] = pd.DataFrame(
        {"ligne": [int(i) + 1 for i in idx],
         colonne: [df.loc[i, colonne] for i in idx]}).reset_index(drop=True)
    vide["n"] = len(idx)
    vide["lignes"] = [int(df.index.get_loc(i)) + 1 for i in idx]
    vide["index"] = list(idx)
    vide["comptes"] = {m: int(vote["detail"][m].sum())
                       for m in points_aberrants.METHODES}
    vide["figure"] = points_aberrants.figure(df[colonne], masque, colonne)
    if not len(idx):
        vide["explication"] = (
            f"Aucune valeur aberrante dans « {colonne} » : les 3 méthodes "
            f"sont d'accord ({vide['comptes']['iqr']} / {vide['comptes']['zscore']} / "
            f"{vide['comptes']['isolation_forest']} signalements isolés, "
            f"pas de consensus sur {len(vals)} valeurs).")
        return vide
    q1, q3 = float(vals.quantile(0.25)), float(vals.quantile(0.75))
    ecart = q3 - q1
    exemples = ", ".join(_fmt(df.loc[i, colonne]) for i in list(idx)[:3])
    vide["explication"] = (
        f"Consensus des 3 méthodes sur « {colonne} » : {len(idx)} valeur(s) "
        f"aberrante(s) sur {len(vals)} "
        f"(IQR : {vide['comptes']['iqr']}, Z-score : {vide['comptes']['zscore']}, "
        f"Isolation Forest : {vide['comptes']['isolation_forest']}). "
        f"Les valeurs habituelles vont de {_fmt(q1 - 1.5 * ecart)} à "
        f"{_fmt(q3 + 1.5 * ecart)} (médiane {_fmt(float(vals.median()))}) ; "
        f"les valeurs repérées (ex : {exemples}) s'en écartent nettement. "
        f"Choisis : garder, corriger (remplacer par la médiane) ou supprimer.")
    return vide


def appliquer_decision(df: pd.DataFrame, colonne: str, decision: str,
                       lignes: list | None = None,
                       index: list | None = None) -> dict:
    """Applique garder / corriger / supprimer. Rend {"df", "entree", "message"}.

    "corriger" remplace par la médiane de la colonne. On passe de préférence
    "index" (labels renvoyés par resumer()) ; sinon "lignes" (numéros base 1,
    valables quand l'index est continu) ; sinon on recalcule le vote.
    Ne modifie jamais l'original.
    """
    if decision not in ("garder", "corriger", "supprimer"):
        decision = "garder"
    res = df.copy()
    idx = []
    if colonne in res.columns:
        if index:
            idx = [i for i in index if i in res.index]
        elif lignes:
            positions = [i - 1 for i in lignes
                         if 1 <= i <= len(res.index)]
            labels = list(res.index)
            idx = [labels[p] for p in positions if p < len(labels)]
        else:
            idx = list(res.index[detecter_combine(res[colonne])["masque"]])
    if decision == "garder" or not idx:
        ent = journal.entree(colonne=str(colonne), action="anomalies_conservees",
                             lignes=0,
                             justification=(f"{len(idx)} valeur(s) aberrante(s) "
                                            "conservées, choix de l'utilisateur"))
        return {"df": res, "entree": ent, "valeur": None,
                "message": ("Aucune anomalie à traiter, tout est conservé."
                            if not idx else
                            f"{len(idx)} valeur(s) conservée(s) (choix enregistré).")}
    if decision == "supprimer":
        res = res.drop(index=idx).reset_index(drop=True)
        ent = journal.entree(colonne=str(colonne), action="supprimer_anomalies",
                             lignes=len(idx),
                             justification=f"{len(idx)} ligne(s) aberrante(s) "
                                           "supprimée(s), choix de l'utilisateur")
        return {"df": res, "entree": ent, "valeur": None,
                "message": f"{len(idx)} ligne(s) aberrante(s) supprimée(s)."}
    mediane = float(pd.to_numeric(res[colonne], errors="coerce").median())
    res.loc[idx, colonne] = mediane
    ent = journal.entree(colonne=str(colonne), action="corriger_anomalies",
                         lignes=len(idx),
                         justification=f"{len(idx)} valeur(s) remplacée(s) par "
                                       f"la médiane ({_fmt(mediane)}), choix de l'utilisateur")
    return {"df": res, "entree": ent, "valeur": mediane,
            "message": (f"{len(idx)} valeur(s) corrigée(s) "
                        f"(médiane {_fmt(mediane)}).")}


def code_rejeu(colonne: str, decision: str, index_labels: list,
               valeur=None) -> str:
    """Snippet à ajouter au script reproductible pour rejouer la décision."""
    if decision == "supprimer":
        return (f"# Décision valeurs aberrantes : {len(index_labels)} ligne(s) "
                f"supprimée(s) sur « {colonne} ».\n"
                f"df_clean = df_clean.drop(index={index_labels!r}, "
                f"errors='ignore').reset_index(drop=True)")
    if decision == "corriger":
        return (f"# Décision valeurs aberrantes sur « {colonne} » : "
                f"remplacement par {valeur!r} (médiane).\n"
                f"df_clean.loc[df_clean.index.isin({index_labels!r}), "
                f"{colonne!r}] = {valeur!r}")
    return (f"# Décision valeurs aberrantes sur « {colonne} » : conservées "
            f"(aucune modification).")
