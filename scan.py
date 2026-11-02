# Scan déterministe des anomalies : uniquement des calculs pandas.
# Aucun chiffre n'est inventé : chaque phrase vient d'un calcul (règle R1).

SEUIL_ECART = 0.15  # 15 points d'écart avec le taux global
N_MIN = 50  # effectif minimum pour un segment fiable (règle R5)


def pct(x):
    """Formate un taux en français : 0.509 -> '50,9 %'."""
    return f"{x * 100:.1f} %".replace(".", ",")


def detecter_cible(df):
    """Trouve une colonne cible binaire (0/1, oui/non...), None sinon."""
    for col in df.columns:
        vals = df[col].dropna().unique()
        if len(vals) == 2 and set(vals) <= {0, 1, True, False}:
            return col
    for col in df.columns:
        if len(df[col].dropna().unique()) == 2:
            return col
    return None


def _serie_binaire(df, cible):
    """Convertit la cible en 0/1 pour calculer des taux."""
    s = df[cible]
    vals = list(s.dropna().unique())
    if set(vals) <= {0, 1, True, False}:
        return s.astype(int), 1
    for v in vals:
        if str(v).strip().lower() in ("1", "oui", "yes", "y", "true", "vrai"):
            return (s == v).astype(int), v
    return (s == vals[-1]).astype(int), vals[-1]


def _est_annee(col, serie):
    """Une colonne d'années : nom évocateur ou entiers 1900-2100."""
    nom = str(col).lower()
    if "year" in nom or "annee" in nom or "année" in nom:
        return True
    if str(serie.dtype).startswith("int"):
        vals = serie.dropna()
        return len(vals) > 0 and vals.min() >= 1900 and vals.max() <= 2100
    return False


def _est_texte(serie):
    """Vrai pour les colonnes texte (object ou str selon la version de pandas)."""
    import pandas as pd
    return (pd.api.types.is_object_dtype(serie.dtype)
            or pd.api.types.is_string_dtype(serie.dtype))


def _colonnes_segments(df, cible):
    """Colonnes utilisables pour découper en segments (hors cible)."""
    cols = []
    for col in df.columns:
        if col == cible:
            continue
        s = df[col]
        n_uniques = s.nunique()
        if _est_texte(s) or n_uniques <= 10:
            cols.append(col)
    return cols


def _phrase_ecart(col, val, taux, n, taux_global, freres=""):
    base = (f"{col} = {val} : {pct(taux)} de départs (n={n}) "
            f"contre {pct(taux_global)} en moyenne")
    return base + (f" ({freres})." if freres else ".")


def scan_anomalies(df, cible):
    """Scanne les segments et rend des phrases chiffrées triées par importance."""
    y = _serie_binaire(df, cible)[0]
    taux_global = float(y.mean())
    n_total = len(df)
    observations = []
    petits = []

    def ajouter(phrase, importance, n):
        observations.append({"phrase": phrase, "importance": importance, "n": n})

    seg_cols = _colonnes_segments(df, cible)

    # 1) Taux par segment pour chaque colonne catégorielle / année.
    for col in seg_cols:
        stats = y.groupby(df[col]).agg(["mean", "count"])
        for val, row in stats.iterrows():
            taux, n = float(row["mean"]), int(row["count"])
            if n >= N_MIN and abs(taux - taux_global) >= SEUIL_ECART:
                freres = ", ".join(
                    f"{v} : {pct(r['mean'])}"
                    for v, r in stats.iterrows()
                    if v != val and int(r["count"]) >= N_MIN
                )
                ajouter(_phrase_ecart(col, val, taux, n, taux_global, freres[:200]),
                        abs(taux - taux_global), n)
            elif 10 <= n < N_MIN and (taux > 0.9 or taux < 0.05):
                petits.append(f"{col} = {val} : {pct(taux)} "
                              f"⚠ échantillon peu fiable (n={n})")
        gros = stats[stats["count"] >= N_MIN]
        if len(gros) >= 2:
            ecart = float(gros["mean"].max() - gros["mean"].min())
            if ecart >= SEUIL_ECART:
                classement = ", ".join(
                    f"{v} : {pct(r['mean'])} (n={int(r['count'])})"
                    for v, r in gros.sort_values("mean", ascending=False).iterrows())
                ajouter(f"Écart marqué pour {col} — {classement[:300]}.",
                        ecart / 2, int(gros["count"].sum()))

    # 2) Cohortes d'années avec taux extrême (> 90 % ou < 5 %).
    for col in seg_cols:
        if not _est_annee(col, df[col]):
            continue
        stats = y.groupby(df[col]).agg(["mean", "count"])
        for val, row in stats.iterrows():
            taux, n = float(row["mean"]), int(row["count"])
            if n >= N_MIN and (taux > 0.9 or taux < 0.05):
                ajouter(f"Cohorte {col} = {val} : {pct(taux)} de départs "
                        f"(n={n}) — cohorte extrême.", 1.0 + abs(taux - taux_global), n)

    # 3) Croisements de 2 colonnes (paires raisonnables pour limiter le calcul).
    paires = [(a, b) for i, a in enumerate(seg_cols)
              for b in seg_cols[i + 1:]
              if df[a].nunique() <= 10 and df[b].nunique() <= 10]
    for a, b in paires[:15]:
        stats = y.groupby([df[a], df[b]]).agg(["mean", "count"])
        for (va, vb), row in stats.iterrows():
            taux, n = float(row["mean"]), int(row["count"])
            if n >= N_MIN and abs(taux - taux_global) >= SEUIL_ECART:
                freres = ", ".join(
                    f"{wa}/{wb} : {pct(r['mean'])}"
                    for (wa, wb), r in stats.iterrows()
                    if (wa, wb) != (va, vb) and wa == va
                    and int(r["count"]) >= N_MIN
                )
                ajouter(f"{a} = {va} et {b} = {vb} : {pct(taux)} de départs "
                        f"(n={n}) contre {pct(taux_global)} en moyenne"
                        + (f" ({freres})." if freres else "."),
                        abs(taux - taux_global), n)

    # 4) Colonnes quasi constantes (une valeur à plus de 95 %).
    for col in df.columns:
        if col == cible or df[col].isna().all():
            continue
        top = df[col].value_counts(normalize=True)
        if not top.empty and top.iloc[0] > 0.95:
            ajouter(f"La colonne {col} est quasi constante : « {top.index[0]} » "
                    f"dans {pct(top.iloc[0])} des cas (n={n_total}).", 0.01, n_total)

    # 5) Paradoxe de Simpson : le classement s'inverse dans un sous-groupe.
    candidats_simpson = []
    for a in seg_cols:
        if df[a].nunique() > 8:
            continue
        ordre_global = list(y.groupby(df[a]).mean().sort_values(ascending=False).index)
        if len(ordre_global) < 2:
            continue
        for b in seg_cols:
            if a == b or df[b].nunique() > 8:
                continue
            for vb, sous in df.groupby(df[b]):
                if len(sous) < N_MIN:
                    continue
                stats = y.loc[sous.index].groupby(sous[a]).agg(["mean", "count"])
                stats = stats[stats["count"] >= 30]
                if len(stats) < 2:
                    continue
                ordre_local = list(stats["mean"].sort_values(ascending=False).index)
                if ordre_local[0] != ordre_global[0]:
                    candidats_simpson.append({
                        "phrase": f"Paradoxe de Simpson possible : globalement « {ordre_global[0]} » "
                                  f"({a}) part le plus, mais chez {b} = {vb} c'est "
                                  f"« {ordre_local[0]} » (n={len(sous)}).",
                        "n": len(sous)})
                    break
            else:
                continue
            break

    candidats_simpson.sort(key=lambda o: o["n"], reverse=True)
    for cand in candidats_simpson[:2]:
        ajouter(cand["phrase"], 0.6, cand["n"])

    observations.sort(key=lambda o: o["importance"], reverse=True)
    return {"cible": cible, "taux_global": taux_global, "n": n_total,
            "observations": observations, "petits": petits}
