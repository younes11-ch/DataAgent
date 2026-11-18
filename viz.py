# Visualisations automatiques Plotly (fonctionnalité DS 5).
# Graphe choisi selon les types de colonnes + une phrase d'insight chiffrée.
# 100 % déterministe, sans appel IA. En cas de doute : erreur claire.

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

TYPES = ("histogramme", "barres", "box", "scatter", "line", "heatmap")

LIBELLES = {
    "auto": "Automatique (selon les colonnes)",
    "histogramme": "Histogramme (distribution)",
    "barres": "Barres (catégories)",
    "box": "Boîtes (groupes comparés)",
    "scatter": "Nuage de points (2 nombres)",
    "line": "Ligne (évolution dans le temps)",
    "heatmap": "Chaleur (corrélations)",
}

COULEURS = ["#0f766e", "#14b8a6", "#0d9488", "#115e59", "#5eead4", "#99f6e4"]
TOP_N = 15


def _f(v, decimales=2) -> str:
    """Nombre en français : 1 234,56."""
    if isinstance(v, (int, np.integer)) or float(v).is_integer():
        return f"{int(v):,}".replace(",", " ")
    return f"{float(v):.{decimales}f}".replace(".", ",")


def est_date(serie: pd.Series) -> bool:
    """Vrai si ≥ 80 % d'un échantillon (200 max) se convertit en date."""
    import warnings

    if pd.api.types.is_numeric_dtype(serie.dtype):
        return False
    if pd.api.types.is_datetime64_any_dtype(serie.dtype):
        return bool(not serie.dropna().empty)
    ech = serie.dropna().head(200)
    if ech.empty:
        return False
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            conv = pd.to_datetime(ech, errors="coerce", format="mixed")
    except Exception:
        return False
    return bool((conv.notna().mean()) >= 0.8)


def type_colonne(serie: pd.Series) -> str:
    """'nombre', 'date' ou 'categorie'."""
    if _est_nombre(serie):
        return "nombre"
    if est_date(serie):
        return "date"
    return "categorie"


def _est_nombre(serie: pd.Series) -> bool:
    return bool(pd.api.types.is_numeric_dtype(serie.dtype))


def _en_dates(serie: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(serie.dtype):
        return serie
    return pd.to_datetime(serie, errors="coerce")


def choisir(df: pd.DataFrame, col_x: str | None = None,
            col_y: str | None = None, force: str | None = None) -> dict:
    """Rend {"kind", "col_x", "col_y", "raison"}. Lève ValueError claire sinon."""
    if force not in (None, "auto") and force not in TYPES:
        raise ValueError(f"type de graphique inconnu : {force}")
    if col_x is not None and col_x not in df.columns:
        raise ValueError(f"la colonne {col_x} n'existe pas")
    if col_y is not None and col_y not in df.columns:
        raise ValueError(f"la colonne {col_y} n'existe pas")
    if force == "heatmap":
        nums = list(df.select_dtypes(include="number").columns)
        if len(nums) < 2:
            raise ValueError("la chaleur demande 2 colonnes de nombres")
        return {"kind": "heatmap", "col_x": None, "col_y": None,
                "raison": "matrice des corrélations (nombres)"}
    if col_x is None:
        raise ValueError("choisis au moins une colonne en X")
    if col_y is None or col_y == col_x:
        t = type_colonne(df[col_x])
        if force in (None, "auto"):
            kind = {"nombre": "histogramme", "date": "histogramme",
                    "categorie": "barres"}[t]
            return {"kind": kind, "col_x": col_x, "col_y": None,
                    "raison": f"« {col_x} » seule ({t})"}
        return {"kind": force, "col_x": col_x, "col_y": None,
                "raison": "choix manuel"}
    tx, ty = type_colonne(df[col_x]), type_colonne(df[col_y])
    if force in (None, "auto"):
        if tx == "date" and ty == "nombre":
            kind = "line"
        elif ty == "date" and tx == "nombre":
            col_x, col_y, kind = col_y, col_x, "line"
        elif tx == "nombre" and ty == "nombre":
            kind = "scatter"
        elif tx == "categorie" and ty == "nombre":
            kind = ("box" if df[col_x].nunique() <= 10 else "barres")
        elif tx == "nombre" and ty == "categorie":
            col_x, col_y = col_y, col_x
            kind = ("box" if df[col_x].nunique() <= 10 else "barres")
        elif tx == "categorie" and ty == "categorie":
            kind = "barres"
        else:
            raise ValueError("combinaison date × catégorie non visualisable "
                             "(ajoute une colonne de nombres)")
        return {"kind": kind, "col_x": col_x, "col_y": col_y,
                "raison": f"« {col_x} » ({type_colonne(df[col_x])}) × "
                          f"« {col_y} » ({type_colonne(df[col_y])})"}
    return {"kind": force, "col_x": col_x, "col_y": col_y,
            "raison": "choix manuel"}


def _base(fig, titre: str):
    fig.update_layout(title=titre, height=420,
                      colorway=COULEURS, margin={"t": 50, "b": 40})
    return fig


def construire(df: pd.DataFrame, kind: str, col_x: str | None,
               col_y: str | None = None) -> go.Figure:
    """Construit la figure Plotly. Lève ValueError si vide/inadapté."""
    if kind == "heatmap":
        nums = df.select_dtypes(include="number")
        if len(nums.columns) < 2:
            raise ValueError("la chaleur demande 2 colonnes de nombres")
        corr = nums.corr(numeric_only=True)
        fig = px.imshow(corr, text_auto=".2f", aspect="auto",
                        color_continuous_scale="Teal",
                        title="Corrélations entre colonnes (nombres)")
        return _base(fig, "Corrélations entre colonnes (nombres)")
    if col_x not in df.columns:
        raise ValueError(f"la colonne {col_x} n'existe pas")
    if kind == "histogramme":
        vals = df[col_x].dropna()
        if vals.empty:
            raise ValueError(f"« {col_x} » est vide")
        fig = px.histogram(df, x=col_x, nbins=20,
                           title=f"Distribution de « {col_x} »")
        return _base(fig, f"Distribution de « {col_x} »")
    if kind == "barres":
        if col_y is None or col_y == col_x:
            top = df[col_x].value_counts().head(TOP_N)
            fig = px.bar(x=top.index.astype(str), y=top.values,
                         labels={"x": col_x, "y": "Effectif"},
                         title=f"Top de « {col_x} »")
        else:
            table = pd.crosstab(df[col_x].astype(str), df[col_y].astype(str))
            if len(table) > TOP_N:
                table = table.loc[table.sum(axis=1).nlargest(TOP_N).index]
            fig = px.bar(table, barmode="stack",
                         title=f"« {col_x} » par « {col_y} »")
        return _base(fig, fig.layout.title.text)
    if col_y not in df.columns:
        raise ValueError("ce graphique demande une colonne en Y")
    if kind == "box":
        fig = px.box(df, x=col_x, y=col_y,
                     title=f"« {col_y} » selon « {col_x} »")
        return _base(fig, f"« {col_y} » selon « {col_x} »")
    if kind == "scatter":
        x = pd.to_numeric(df[col_x], errors="coerce")
        y = pd.to_numeric(df[col_y], errors="coerce")
        ok = x.notna() & y.notna()
        if int(ok.sum()) < 3:
            raise ValueError("pas assez de points (min 3)")
        fig = px.scatter(x=x[ok], y=y[ok], labels={"x": col_x, "y": col_y},
                         title=f"« {col_y} » en fonction de « {col_x} »")
        if x[ok].nunique() > 1:
            a, b = np.polyfit(x[ok].to_numpy(dtype=float),
                              y[ok].to_numpy(dtype=float), 1)
            xs = np.linspace(float(x[ok].min()), float(x[ok].max()), 50)
            fig.add_trace(go.Scatter(x=xs, y=a * xs + b, mode="lines",
                                     name="Tendance",
                                     line={"dash": "dash", "color": "#115e59"}))
        return _base(fig, f"« {col_y} » en fonction de « {col_x} »")
    if kind == "line":
        d = _en_dates(df[col_x])
        y = pd.to_numeric(df[col_y], errors="coerce")
        tmp = pd.DataFrame({"d": d, "y": y}).dropna().sort_values("d")
        if tmp.empty:
            raise ValueError("aucune date exploitable")
        if tmp["d"].duplicated().any():
            tmp = tmp.groupby("d", as_index=False)["y"].mean()
        fig = px.line(tmp, x="d", y="y", markers=True,
                      labels={"d": col_x, "y": col_y},
                      title=f"Évolution de « {col_y} » ({col_x})")
        return _base(fig, f"Évolution de « {col_y} » ({col_x})")
    raise ValueError(f"type de graphique inconnu : {kind}")


def insight(df: pd.DataFrame, kind: str, col_x: str | None,
            col_y: str | None = None) -> str:
    """Une phrase chiffrée qui dit quoi retenir du graphique."""
    if kind == "heatmap":
        nums = df.select_dtypes(include="number")
        corr = nums.corr(numeric_only=True)
        mask = np.triu(np.ones(corr.shape, dtype=bool), k=1)
        pile = corr.where(mask).stack()
        if pile.empty:
            return "Aucune corrélation calculable entre ces colonnes."
        a, b = pile.abs().idxmax()
        r = float(corr.loc[a, b])
        sens = ("varient ensemble" if r > 0 else "varient en sens opposé")
        return (f"La plus forte corrélation : « {a} » × « {b} » "
                f"(r = {_f(r)}) : elles {sens} "
                f"(association, pas cause).")
    vals = df[col_x]
    n = int(vals.count())
    if kind == "histogramme":
        if _est_nombre(vals):
            v = pd.to_numeric(vals, errors="coerce").dropna()
            return (f"« {col_x} » (n={_f(n)}) : médiane {_f(float(v.median()))}, "
                    f"la moitié des valeurs entre {_f(float(v.quantile(0.25)))} "
                    f"et {_f(float(v.quantile(0.75)))}.")
        top = vals.value_counts()
        return (f"« {col_x} » (n={_f(n)}) : valeur la plus fréquente "
                f"« {top.index[0]} » ({_f(top.iloc[0])} fois).")
    if kind == "barres":
        if col_y is None or col_y == col_x:
            top = vals.value_counts()
            part = top.iloc[0] / top.sum() * 100
            return (f"« {top.index[0]} » domine « {col_x} » "
                    f"({_f(part, 1)} %, n={_f(int(top.iloc[0]))}).")
        table = pd.crosstab(vals.astype(str), df[col_y].astype(str))
        dom = table.sum(axis=1).idxmax()
        return (f"« {dom} » est la catégorie la plus nombreuse "
                f"(n={_f(int(table.sum(axis=1).max()))}).")
    y = pd.to_numeric(df[col_y], errors="coerce")
    if kind == "box":
        meds = y.groupby(vals.astype(str)).median()
        lo, hi = meds.idxmin(), meds.idxmax()
        return (f"Écart marqué : « {lo} » (médiane {_f(float(meds.min()))}) "
                f"contre « {hi} » (médiane {_f(float(meds.max()))}).")
    if kind == "scatter":
        x = pd.to_numeric(vals, errors="coerce")
        ok = x.notna() & y.notna()
        r = float(x[ok].corr(y[ok])) if int(ok.sum()) >= 3 else float("nan")
        if np.isnan(r):
            return "Pas assez de points pour mesurer un lien."
        sens = ("quand l'un augmente, l'autre augmente" if r > 0
                else "quand l'un augmente, l'autre diminue")
        return (f"Corrélation {('forte' if abs(r) > 0.7 else 'modérée' if abs(r) > 0.3 else 'faible')} "
                f"(r = {_f(r)}) : {sens} (association, pas cause).")
    if kind == "line":
        d = _en_dates(vals)
        tmp = pd.DataFrame({"d": d, "y": y}).dropna().sort_values("d")
        if tmp["d"].nunique() < 2:
            return "Une seule date : pas d'évolution à décrire."
        premier, dernier = float(tmp["y"].iloc[0]), float(tmp["y"].iloc[-1])
        evo = ((dernier - premier) / abs(premier) * 100) if premier else 0.0
        sens = ("hausse" if evo > 0 else "baisse")
        return (f"« {col_y} » : {sens} de {_f(abs(evo), 1)} % entre le début "
                f"({_f(premier)}) et la fin ({_f(dernier)}).")
    return "Graphique affiché."
