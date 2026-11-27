# Tests statistiques automatiques (fonctionnalité DS 6).
# Le module choisit le bon test selon les colonnes, vérifie les hypothèses
# (normalité, variances, effectifs) et explique p-value + taille d'effet
# en langage simple. 100 % déterministe (scipy), sans appel IA.

from __future__ import annotations

import numpy as np
import pandas as pd

ALPHA = 0.05
MAX_GROUPES = 10
N_MAX_SHAPIRO = 5000

TESTS = {
    "auto": "Automatique (selon les colonnes)",
    "ttest": "t de Welch (2 groupes, nombres)",
    "mannwhitney": "Mann-Whitney (2 groupes, sans hypothèse de normalité)",
    "anova": "ANOVA (3 groupes et +, nombres)",
    "kruskal": "Kruskal-Wallis (3 groupes et +, sans normalité)",
    "chi2": "Chi² (2 colonnes catégories)",
    "correlation": "Corrélation (2 colonnes nombres)",
}


def _est_numerique(serie: pd.Series) -> bool:
    return bool(pd.api.types.is_numeric_dtype(serie.dtype))


def _fp(p: float) -> str:
    """p-value en français : 'p < 0,001' ou 'p = 0,023'."""
    return "p < 0,001" if p < 0.001 else f"p = {p:.3f}".replace(".", ",")


def _niveau(nom: str, valeur: float) -> str:
    """Petit / moyen / grand selon les repères de Cohen (ordres de grandeur)."""
    seuils = {"d": (0.2, 0.5, 0.8), "r": (0.1, 0.3, 0.5),
              "v": (0.1, 0.3, 0.5), "eta2": (0.01, 0.06, 0.14)}[nom]
    if valeur < seuils[0]:
        return "négligeable"
    if valeur < seuils[1]:
        return "petit"
    if valeur < seuils[2]:
        return "moyen"
    return "grand"


def _note_normalite(vals: np.ndarray, nom: str) -> str | None:
    """Test de Shapiro (échantillonné à 5000 si besoin) ou None si impossible."""
    from scipy import stats

    vals = np.asarray(vals, dtype=float)
    vals = vals[~np.isnan(vals)]
    if len(vals) < 3:
        return None
    ech = (vals if len(vals) <= N_MAX_SHAPIRO
           else np.random.default_rng(42).choice(vals, N_MAX_SHAPIRO,
                                                 replace=False))
    p = float(stats.shapiro(ech).pvalue)
    verdict = ("suit une loi normale" if p >= ALPHA
               else "ne suit pas une loi normale")
    return (f"Normalité de « {nom} » (Shapiro, n={len(ech)}) : {verdict} "
            f"({_fp(p)}).")


def choisir(df: pd.DataFrame, col1: str, col2: str | None = None) -> str:
    """Rend le nom du test adapté, ou 'erreur:<message>' si impossible."""
    if col1 not in df.columns:
        return "erreur:la colonne n'existe pas"
    if col2 is not None and col2 not in df.columns:
        return "erreur:la 2e colonne n'existe pas"
    if col2 is None or col2 == col1:
        return ("erreur:choisis une 2e colonne "
                "(comparer demande deux colonnes)")
    num1, num2 = _est_numerique(df[col1]), _est_numerique(df[col2])
    if num1 and num2:
        return "correlation"
    if num1 and not num2:
        return "ttest" if df[col2].nunique() == 2 else "anova"
    if not num1 and num2:
        return "ttest" if df[col1].nunique() == 2 else "anova"
    return "chi2"


def _groupes_numeriques(df, col_num, col_cat):
    """Groupes de valeurs (triés), avec garde-fous. Lève ValueError claire."""
    cats = sorted(df[col_cat].dropna().unique().tolist())
    if not 2 <= len(cats) <= MAX_GROUPES:
        raise ValueError(f"« {col_cat} » doit avoir entre 2 et {MAX_GROUPES} "
                         f"catégories (vu : {len(cats)})")
    groupes = [pd.to_numeric(df.loc[df[col_cat] == c, col_num],
                             errors="coerce").dropna().to_numpy(dtype=float)
               for c in cats]
    if any(len(g) < 2 for g in groupes):
        raise ValueError("chaque groupe doit avoir au moins 2 valeurs")
    return cats, groupes


def lancer(df: pd.DataFrame, test: str, col1: str,
           col2: str | None = None, alpha: float = ALPHA) -> dict:
    """Exécute le test et rend un dict affichable (ok False + erreur sinon)."""
    from scipy import stats

    base = {"ok": False, "test": test, "col1": col1, "col2": col2,
            "alpha": alpha, "erreur": ""}
    try:
        alpha = float(alpha)
        if not 0 < alpha < 1:
            raise ValueError("alpha doit être entre 0 et 1")
        base["alpha"] = alpha
        if test == "auto":
            test = choisir(df, col1, col2)
            if test.startswith("erreur:"):
                base["erreur"] = test.split(":", 1)[1] + "."
                return base
            base["test"] = test
        if test in ("ttest", "mannwhitney", "anova", "kruskal"):
            num, cat = (col1, col2) if _est_numerique(df[col1]) else (col2, col1)
            if not _est_numerique(df[num]):
                raise ValueError("il faut une colonne de nombres et une "
                                 "colonne de catégories")
            cats, groupes = _groupes_numeriques(df, num, cat)
            noms = [str(c) for c in cats]
            notes = [n for g, c in zip(groupes, noms)
                     if (n := _note_normalite(g, c))]
        if test == "ttest":
            if len(groupes) != 2:
                raise ValueError("le t-test compare exactement 2 groupes "
                                 "(ANOVA au-delà)")
            stat, p = stats.ttest_ind(groupes[0], groupes[1], equal_var=False)
            ecart = np.std(np.concatenate(groupes), ddof=1)
            effet = (abs(float(np.mean(groupes[0]) - np.mean(groupes[1])) / ecart)
                     if ecart else 0.0)
            res = {"libelle": f"t de Welch : « {num} » selon « {cat} »",
                   "statistique": float(stat), "p": float(p),
                   "effet": effet, "effet_nom": "d de Cohen",
                   "n": int(sum(len(g) for g in groupes)),
                   "details": [f"{c} : n={len(g)}, "
                               f"moyenne {float(np.mean(g)):.2f}" for c, g in
                               zip(noms, groupes)]}
        elif test == "mannwhitney":
            if len(groupes) != 2:
                raise ValueError("Mann-Whitney compare exactement 2 groupes")
            u, p = stats.mannwhitneyu(groupes[0], groupes[1],
                                      alternative="two-sided")
            n1, n2 = len(groupes[0]), len(groupes[1])
            effet = abs(1 - 2 * float(u) / (n1 * n2))
            res = {"libelle": f"Mann-Whitney : « {num} » selon « {cat} »",
                   "statistique": float(u), "p": float(p),
                   "effet": effet, "effet_nom": "r rang-bisériale",
                   "n": n1 + n2,
                   "details": [f"{c} : n={len(g)}, "
                               f"médiane {float(np.median(g)):.2f}" for c, g in
                               zip(noms, groupes)]}
        elif test == "anova":
            if len(groupes) < 3:
                raise ValueError("l'ANOVA compare 3 groupes et plus "
                                 "(t-test à 2 groupes)")
            stat, p = stats.f_oneway(*groupes)
            tout = np.concatenate(groupes)
            ss_total = float(((tout - tout.mean()) ** 2).sum())
            ss_inter = float(sum(len(g) * (g.mean() - tout.mean()) ** 2
                                 for g in groupes))
            effet = (ss_inter / ss_total) if ss_total else 0.0
            res = {"libelle": f"ANOVA : « {num} » selon « {cat} »",
                   "statistique": float(stat), "p": float(p),
                   "effet": effet, "effet_nom": "êta²",
                   "n": len(tout),
                   "details": [f"{c} : n={len(g)}, "
                               f"moyenne {float(np.mean(g)):.2f}" for c, g in
                               zip(noms, groupes)]}
        elif test == "kruskal":
            if len(groupes) < 3:
                raise ValueError("Kruskal-Wallis compare 3 groupes et plus")
            stat, p = stats.kruskal(*groupes)
            n = sum(len(g) for g in groupes)
            effet = max(0.0, (float(stat) - len(groupes) + 1) / (n - len(groupes)))
            res = {"libelle": f"Kruskal-Wallis : « {num} » selon « {cat} »",
                   "statistique": float(stat), "p": float(p),
                   "effet": effet, "effet_nom": "êta² (rangs)",
                   "n": n,
                   "details": [f"{c} : n={len(g)}, "
                               f"médiane {float(np.median(g)):.2f}" for c, g in
                               zip(noms, groupes)]}
        elif test == "chi2":
            if _est_numerique(df[col1]) or _est_numerique(df[col2]):
                raise ValueError("le chi² compare 2 colonnes de catégories")
            table = pd.crosstab(df[col1], df[col2])
            if table.shape[0] < 2 or table.shape[1] < 2:
                raise ValueError("table trop petite pour un chi²")
            if max(table.shape) > MAX_GROUPES:
                raise ValueError(f"trop de catégories (max {MAX_GROUPES})")
            stat, p, _, attendus = stats.chi2_contingency(table)
            n = int(table.to_numpy().sum())
            effet = float(np.sqrt(stat / (n * (min(table.shape) - 1)))) if n else 0.0
            res = {"libelle": f"Chi² : « {col1} » × « {col2} »",
                   "statistique": float(stat), "p": float(p),
                   "effet": effet, "effet_nom": "V de Cramér",
                   "n": n, "details": [f"table {table.shape[0]}×{table.shape[1]}"]}
            notes = []
            if (attendus < 5).any():
                notes.append("Effectifs attendus < 5 dans certaines cases : "
                             "le chi² est approximatif, interprète avec prudence.")
        elif test == "correlation":
            if not (_est_numerique(df[col1]) and _est_numerique(df[col2])):
                raise ValueError("la corrélation demande 2 colonnes de nombres")
            x = pd.to_numeric(df[col1], errors="coerce")
            y = pd.to_numeric(df[col2], errors="coerce")
            ok = x.notna() & y.notna()
            if int(ok.sum()) < 3:
                raise ValueError("pas assez de paires complètes (min 3)")
            r, p = stats.pearsonr(x[ok], y[ok])
            if np.isnan(r):
                raise ValueError("corrélation incalculable : "
                                 "une colonne est constante")
            rs, _ = stats.spearmanr(x[ok], y[ok])
            res = {"libelle": f"Corrélation : « {col1} » × « {col2} »",
                   "statistique": float(r), "p": float(p),
                   "effet": abs(float(r)), "effet_nom": "r de Pearson",
                   "n": int(ok.sum()),
                   "details": [f"Spearman (rangs) : {float(rs):.2f}"]}
            notes = []
        else:
            raise ValueError(f"test inconnu : {test}")
    except Exception as e:
        base["erreur"] = str(e)
        return base
    res.update({"ok": True, "test": test, "col1": col1, "col2": col2,
                "alpha": alpha,
                "effet_niveau": _niveau({"d de Cohen": "d",
                                         "r rang-bisériale": "r",
                                         "V de Cramér": "v",
                                         "êta²": "eta2",
                                         "êta² (rangs)": "eta2",
                                         "r de Pearson": "r"}[res["effet_nom"]],
                                        res["effet"]),
                "hypotheses": notes})
    res["explication"] = expliquer(res)
    return res


def expliquer(res: dict) -> str:
    """Phrase simple : verdict p-value + taille d'effet + prudence."""
    signif = res["p"] < res["alpha"]
    seuil = f"{res['alpha']:.2f}".replace(".", ",")
    verdict = (f"{_fp(res['p'])} (< {seuil}) : l'écart est statistiquement "
               f"significatif." if signif else
               f"{_fp(res['p'])} (≥ {seuil}) : pas d'écart significatif détecté.")
    effet = (f"Taille d'effet {res['effet_niveau']} "
             f"({res['effet_nom']} = {res['effet']:.2f}) : "
             + ({"négligeable": "l'écart est trop petit pour compter en pratique.",
                 "petit": "l'écart est réel mais modeste en pratique.",
                 "moyen": "l'écart est notable en pratique.",
                 "grand": "l'écart est important en pratique."}[res["effet_niveau"]]))
    prudence = (" Rappel : une association n'est pas une cause."
                if res["test"] in ("chi2", "correlation") else "")
    return (f"{res['libelle']} (n={res['n']}). {verdict} {effet}{prudence}")
