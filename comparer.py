# Comparaison de 2 fichiers : écarts calculés en pandas, phrases f-string (R1).
# Aucun chiffre inventé : le texte final ne cite que les nombres calculés ici.

import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def _fmt_nombre(x):
    return f"{x:,.0f}".replace(",", " ")


def _fmt_pct(x):
    return f"{x:+.1f} %".replace(".", ",")


def _est_texte(serie):
    """Vrai pour les colonnes texte (object ou str selon la version de pandas)."""
    import pandas as pd
    return (pd.api.types.is_object_dtype(serie.dtype)
            or pd.api.types.is_string_dtype(serie.dtype))


def _choisir_cat(df, communes):
    """Choisit la catégorielle la plus parlante (ni date, ni trop de valeurs)."""
    candidats = []
    for c in communes:
        if not _est_texte(df[c]):
            continue
        n = df[c].nunique()
        if 2 <= n <= 12 and "date" not in str(c).lower():
            candidats.append((n, c))
    if candidats:
        candidats.sort()
        return candidats[-1][1]
    for c in communes:
        if _est_texte(df[c]) and 2 <= df[c].nunique() <= 30:
            return c
    return None


def comparer(df1, df2, nom1="Fichier A", nom2="Fichier B"):
    """Compare 2 DataFrames : effectifs, colonnes, totaux, segments, graphique."""
    lignes = [f"{nom1} : {len(df1)} lignes ; {nom2} : {len(df2)} lignes."]
    col1, col2 = set(df1.columns), set(df2.columns)
    communes = [c for c in df1.columns if c in col2]
    if col1 - col2:
        lignes.append("Colonnes uniquement dans " + nom1 + " : "
                      + ", ".join(sorted(str(c) for c in col1 - col2)) + ".")
    if col2 - col1:
        lignes.append("Colonnes uniquement dans " + nom2 + " : "
                      + ", ".join(sorted(str(c) for c in col2 - col1)) + ".")
    chiffres = {}
    for col in communes:
        if pd.api.types.is_numeric_dtype(df1[col]) and pd.api.types.is_numeric_dtype(df2[col]):
            t1, t2 = float(df1[col].sum()), float(df2[col].sum())
            ecart = t2 - t1
            pct_ecart = (ecart / t1 * 100) if t1 else None
            chiffres[col] = {"total1": t1, "total2": t2,
                             "ecart": ecart, "pct": pct_ecart}
            ph = (f"{col} : total {_fmt_nombre(t1)} → {_fmt_nombre(t2)} "
                  f"(écart {_fmt_nombre(ecart) if ecart < 0 else '+' + _fmt_nombre(ecart)}"
                  f"{', ' + _fmt_pct(pct_ecart) if pct_ecart is not None else ''})")
            lignes.append(ph + ".")
    graphique = None
    titre = ""
    cat = _choisir_cat(df1, communes)
    nums = list(chiffres)
    if cat and nums:
        num = nums[0]
        s1 = df1.groupby(cat)[num].sum().sort_values(ascending=False).head(8)
        s2 = df2.groupby(cat)[num].sum()
        idx = list(s1.index)
        v1 = [float(s1.get(v, 0)) for v in idx]
        v2 = [float(s2.get(v, 0)) for v in idx]
        for v, a, b in zip(idx, v1, v2):
            e = b - a
            lignes.append(f"{cat} = {v} : {num} {_fmt_nombre(a)} → {_fmt_nombre(b)} "
                          f"({_fmt_nombre(e) if e < 0 else '+' + _fmt_nombre(e)}).")
        fig, ax = plt.subplots(figsize=(8, 4))
        x = list(range(len(idx)))
        larg = 0.35
        ax.bar([i - larg / 2 for i in x], v1, larg, label=nom1[:20])
        ax.bar([i + larg / 2 for i in x], v2, larg, label=nom2[:20])
        ax.set_xticks(x)
        ax.set_xticklabels([str(v) for v in idx], rotation=20, ha="right")
        ax.set_title(f"{num} par {cat} : {nom1} vs {nom2}")
        ax.legend()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        graphique = buf.getvalue()
        titre = f"{num} par {cat}"
    elif nums:
        choix = nums[:6]
        v1 = [chiffres[c]["total1"] for c in choix]
        v2 = [chiffres[c]["total2"] for c in choix]
        fig, ax = plt.subplots(figsize=(8, 4))
        x = list(range(len(choix)))
        larg = 0.35
        ax.bar([i - larg / 2 for i in x], v1, larg, label=nom1[:20])
        ax.bar([i + larg / 2 for i in x], v2, larg, label=nom2[:20])
        ax.set_xticks(x)
        ax.set_xticklabels([str(c) for c in choix], rotation=20, ha="right")
        ax.set_title(f"Totaux : {nom1} vs {nom2}")
        ax.legend()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        graphique = buf.getvalue()
        titre = "Totaux comparés"
    return {"phrases": lignes, "chiffres": chiffres, "graphique": graphique,
            "titre": titre, "nom1": nom1, "nom2": nom2}
