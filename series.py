# Séries temporelles (fonctionnalité DS 8) : tendance, saisonnalité,
# prévision simple (Holt-Winters via statsmodels, repli naïf sinon).
# 100 % déterministe, sans appel IA. Prophet exclu (trop lourd pour le Cloud).

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

import viz

N_MIN = 8
FORCE_SAISON_MIN = 0.3


def colonnes_dates(df: pd.DataFrame) -> list:
    """Colonnes reconnues comme dates (même détection que les graphiques)."""
    return [c for c in df.columns if viz.est_date(df[c])]


def _frequence(dates: pd.Series) -> tuple:
    """Rend (code resample, période saisonnière ou None) selon le pas médian."""
    deltas = dates.sort_values().diff().dropna()
    jours = float(deltas.median().total_seconds() / 86400) if len(deltas) else 1
    if jours <= 2:
        return "D", 7
    if jours <= 10:
        return "W", 52
    if jours <= 45:
        return "ME", 12
    if jours <= 120:
        return "QE", 4
    return "YE", None


def preparer(df: pd.DataFrame, col_date: str,
             col_valeur: str) -> dict:
    """Construit la série régulière (moyenne par période, trous interpolés)."""
    if col_date not in df.columns or col_valeur not in df.columns:
        raise ValueError("colonne de date ou de valeur inconnue")
    if not viz.est_date(df[col_date]):
        raise ValueError(f"« {col_date} » n'est pas une colonne de dates")
    if not pd.api.types.is_numeric_dtype(df[col_valeur].dtype):
        raise ValueError(f"« {col_valeur} » doit être une colonne de nombres")
    tmp = pd.DataFrame({"d": viz._en_dates(df[col_date]),
                        "y": pd.to_numeric(df[col_valeur], errors="coerce")})
    tmp = tmp.dropna().sort_values("d")
    if len(tmp) < N_MIN:
        raise ValueError(f"pas assez de points (min {N_MIN}, vu {len(tmp)})")
    freq, periode = _frequence(tmp["d"])
    serie = tmp.groupby(pd.Grouper(key="d", freq=freq))["y"].mean()
    trous = int(serie.isna().sum())
    serie = serie.interpolate().bfill().ffill()
    if periode is not None and len(serie) < 2 * periode:
        periode = None  # pas assez d'historique pour tester un cycle
    return {"serie": serie, "freq": freq, "periode": periode,
            "trous_bouches": trous}


def _tendance(serie: pd.Series) -> dict:
    from scipy import stats as sps

    x = np.arange(len(serie), dtype=float)
    pente, _, _, _, _ = sps.linregress(x, serie.to_numpy(dtype=float))
    base = float(serie.iloc[0])
    evo = (pente * (len(serie) - 1) / abs(base) * 100) if base else 0.0
    direction = ("stable" if abs(evo) < 1 else
                 "hausse" if evo > 0 else "baisse")
    return {"direction": direction, "pente": float(pente), "evo_pct": float(evo)}


def _saison(serie: pd.Series, periode: int | None) -> dict | None:
    if periode is None:
        return None
    try:
        from statsmodels.tsa.seasonal import seasonal_decompose

        dec = seasonal_decompose(serie, model="additive", period=periode,
                                 extrapolate_trend=periode)
        residu = dec.resid.dropna()
        force = max(0.0, 1 - float(residu.var())
                    / float((dec.seasonal.loc[residu.index] + residu).var()))
    except Exception:
        return None
    if force < FORCE_SAISON_MIN:
        return None
    return {"periode": periode, "force": round(float(force), 2)}


def _prevoir(serie: pd.Series, periode: int | None,
             horizon: int) -> tuple:
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing

        modele = ExponentialSmoothing(
            serie, trend="add",
            seasonal="add" if periode else None,
            seasonal_periods=periode).fit(optimized=True)
        return (list(map(float, modele.forecast(horizon))),
                "Holt-Winters " + ("avec saisonnalité" if periode
                                   else "tendance seule"))
    except Exception:
        pass
    return ([float(serie.iloc[-1])] * horizon,
            "naïve (dernière valeur répétée)")


def _f(v, decimales=1) -> str:
    return f"{float(v):.{decimales}f}".replace(".", ",")


def analyser(df: pd.DataFrame, col_date: str, col_valeur: str,
             horizon: int = 7) -> dict:
    """Analyse complète : tendance + saisonnalité + prévision + graphique."""
    if not 1 <= int(horizon) <= 30:
        return {"ok": False, "erreur": "horizon entre 1 et 30"}
    try:
        prep = preparer(df, col_date, col_valeur)
    except ValueError as e:
        return {"ok": False, "erreur": str(e)}
    serie, periode = prep["serie"], prep["periode"]
    tend = _tendance(serie)
    sais = _saison(serie, periode)
    prev, methode = _prevoir(serie, periode if sais else None, int(horizon))
    pas = serie.index[1] - serie.index[0] if len(serie) > 1 else pd.Timedelta("1D")
    dates_prev = [serie.index[-1] + (i + 1) * pas for i in range(int(horizon))]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=serie.index, y=serie.values, mode="lines",
                             name="Observé", line={"color": "#0f766e"}))
    fig.add_trace(go.Scatter(x=dates_prev, y=prev, mode="lines+markers",
                             name=f"Prévision ({methode})",
                             line={"dash": "dash", "color": "#115e59"}))
    fig.update_layout(title=f"« {col_valeur} » dans le temps + prévision",
                      height=420, margin={"t": 50, "b": 40})
    res = {"ok": True, "freq": prep["freq"], "n": len(serie),
           "trous_bouches": prep["trous_bouches"], "tendance": tend,
           "saison": sais, "prevision": prev, "methode": methode, "figure": fig}
    res["explication"] = expliquer(res, col_valeur)
    return res


def expliquer(res: dict, col_valeur: str) -> str:
    """Phrases simples : tendance, saisonnalité, prévision, limites."""
    t = res["tendance"]
    sens = {"hausse": "à la hausse", "baisse": "à la baisse",
            "stable": "stable"}[t["direction"]]
    signe = "+" if t["evo_pct"] >= 0 else ""
    phrases = [
        f"« {col_valeur} » est {sens} sur la période "
        f"({signe}{_f(t['evo_pct'])} % de bout en bout, n={res['n']})."]
    if res["saison"]:
        phrases.append(f"Cycle détecté tous les {res['saison']['periode']} points "
                       f"(force {res['saison']['force']}) : le motif se répète.")
    else:
        phrases.append("Pas de saisonnalité marquée détectée.")
    phrases.append(f"Prévision {res['methode']} : "
                   f"{_f(res['prevision'][-1])} à horizon "
                   f"{len(res['prevision'])} points.")
    phrases.append("Limite : une prévision prolonge le passé, elle ne prédit "
                   "ni rupture ni événement inédit.")
    if res["trous_bouches"]:
        phrases.append(f"{res['trous_bouches']} période(s) sans données "
                       "interpolée(s).")
    return " ".join(phrases)
