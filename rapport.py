# Rapport en un clic : HTML téléchargeable, chiffres 100 % calculés.
# Contenu : résumé, nettoyage, 3 graphiques, anomalies, limites, pistes.

import base64
import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from scan import N_MIN, pct


def _binaire(df, cible):
    s = df[cible]
    if set(s.dropna().unique()) <= {0, 1, True, False}:
        return s.astype(int)
    return (s == s.dropna().unique()[-1]).astype(int)


def _fig_png(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def _colonnes_ecart(df, y):
    """Colonnes triées par écart max entre segments (n >= 50)."""
    resultats = []
    for col in df.columns:
        if df[col].nunique() > 12:
            continue
        stats = y.groupby(df[col]).agg(["mean", "count"])
        gros = stats[stats["count"] >= N_MIN]
        if len(gros) >= 2:
            resultats.append((col, float(gros["mean"].max() - gros["mean"].min())))
    resultats.sort(key=lambda t: t[1], reverse=True)
    return [c for c, _ in resultats]


def _graphe_taux_par(df, y, col, titre):
    stats = y.groupby(df[col]).agg(["mean", "count"])
    stats = stats[stats["count"] >= N_MIN].sort_values("mean", ascending=False)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar([str(v) for v in stats.index], (stats["mean"] * 100).round(1))
    ax.axhline(y.mean() * 100, linestyle="--")
    ax.set_title(titre)
    ax.set_ylabel("% de départs")
    for i, (v, r) in enumerate(stats.iterrows()):
        ax.text(i, r["mean"] * 100 + 0.5, f"n={int(r['count'])}",
                ha="center", fontsize=8)
    return _fig_png(fig)


def _graphe_hist(df, titre):
    num = df.select_dtypes(include="number")
    col = num.columns[0] if len(num.columns) else None
    fig, ax = plt.subplots(figsize=(7, 4))
    if col is not None:
        ax.hist(df[col].dropna(), bins=20)
        ax.set_title(f"{titre} : {col}")
        ax.set_xlabel(col)
        ax.set_ylabel("Effectif")
    else:
        ax.text(0.5, 0.5, "Pas de colonne numérique", ha="center")
        ax.set_title(titre)
    return _fig_png(fig)


def _graphe_manquants(df):
    manq = df.isna().sum()
    manq = manq[manq > 0].sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(7, 4))
    if manq.empty:
        ax.text(0.5, 0.5, "Aucune valeur manquante", ha="center", fontsize=12)
        ax.set_title("Valeurs manquantes par colonne")
    else:
        ax.bar([str(c) for c in manq.index], manq.values)
        ax.set_title("Valeurs manquantes par colonne")
        ax.set_ylabel("Nombre")
    return _fig_png(fig)


def graphiques_png(df, cible):
    """2 à 3 graphiques clés en PNG bruts (pour le PDF)."""
    import base64

    morceaux = []
    if cible:
        y = _binaire(df, cible)
        tops = _colonnes_ecart(df.drop(columns=[cible]), y)
        for col in tops[:2]:
            morceaux.append(
                (f"Taux de départs par {col}",
                 _graphe_taux_par(df, y, col, f"Taux de départs par {col}")))
        morceaux.append(("Distribution", _graphe_hist(df, "Distribution")))
    else:
        morceaux.append(("Distribution", _graphe_hist(df, "Distribution")))
        morceaux.append(("Valeurs manquantes", _graphe_manquants(df)))
    return [(t, base64.b64decode(img)) for t, img in morceaux[:3]]


def generer_html(df, cible, scan_res, nettoyage, version_label, hypotheses,
                 resume_exec=None):
    """Construit le rapport HTML complet avec 3 graphiques clés."""
    morceaux = []
    if cible:
        y = _binaire(df, cible)
        tops = _colonnes_ecart(df.drop(columns=[cible]), y)
        if tops:
            morceaux.append(("Taux de départs par segment (écart le plus marqué)",
                             _graphe_taux_par(df, y, tops[0],
                                              f"Taux de départs par {tops[0]}")))
        if len(tops) > 1:
            morceaux.append(("Deuxième découpage le plus marqué",
                             _graphe_taux_par(df, y, tops[1],
                                              f"Taux de départs par {tops[1]}")))
        morceaux.append(("Distribution d'une variable clé", _graphe_hist(df, "Distribution")))
    else:
        morceaux.append(("Distribution d'une variable clé", _graphe_hist(df, "Distribution")))
        morceaux.append(("Qualité des données", _graphe_manquants(df)))
    while len(morceaux) < 3:
        morceaux.append(("Qualité des données", _graphe_manquants(df)))
    morceaux = morceaux[:3]

    if scan_res and scan_res["observations"]:
        obs_html = "".join(f"<li>{o['phrase']}</li>"
                           for o in scan_res["observations"][:8])
        pistes_html = "".join(
            f"<li>Écart constaté : {o['phrase']} → piste à vérifier : comparer ce "
            f"segment aux autres sur des facteurs non mesurés ici "
            f"(ancienneté, équipe, contexte…). Rien ne prouve un lien de cause à effet.</li>"
            for o in scan_res["observations"][:3])
    else:
        obs_html = "<li>Aucune anomalie marquée détectée.</li>"
        pistes_html = "<li>Collecter plus de données avant de conclure.</li>"
    hyp_html = "".join(f"<li>{h}</li>" for h in hypotheses) or "<li>Aucune.</li>"
    if resume_exec:
        bloc_resume = ("<h2>Résumé exécutif</h2><ul>"
                       + "".join(f"<li>{l}</li>" for l in resume_exec)
                       + "</ul>")
    else:
        bloc_resume = ""
    net_html = "".join(f"<li>{l}</li>" for l in nettoyage.get("rapport", []))
    lignes_types = "".join(
        f"<tr><td>{c}</td><td>{df[c].dtype}</td>"
        f"<td>{int(df[c].isna().sum())}</td></tr>" for c in df.columns)

    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<title>Rapport DataAgent — {nettoyage.get('fichier', 'données')}</title>
<style>body{{font-family:Arial,sans-serif;max-width:900px;margin:2em auto;padding:0 1em;color:#222}}
h1{{font-size:1.6em}}h2{{font-size:1.2em;margin-top:2em;border-bottom:1px solid #ccc}}
table{{border-collapse:collapse}}td,th{{border:1px solid #ccc;padding:4px 10px;font-size:.9em}}
img{{max-width:100%}}li{{margin:.4em 0}}</style></head><body>
<h1>Rapport DataAgent</h1>
<p>Fichier : {nettoyage.get('fichier', 'données')} — {len(df)} lignes, {len(df.columns)} colonnes.
Version analysée : {version_label}.</p>
{bloc_resume}<h2>Colonnes</h2>
<table><tr><th>Colonne</th><th>Type</th><th>Manquantes</th></tr>{lignes_types}</table>
<h2>Nettoyage effectué</h2><ul>{net_html}</ul>
<h2>Graphiques clés</h2>
{''.join(f'<h3>{t}</h3><img src="data:image/png;base64,{img}">' for t, img in morceaux)}
<h2>Anomalies détectées</h2><ul>{obs_html}</ul>
<h2>Hypothèses et limites</h2><ul>{hyp_html}</ul>
<h2>Pistes de recommandation (à vérifier, jamais des certitudes)</h2>
<ul>{pistes_html}</ul>
<p><em>Rapport généré par DataAgent (Meta Global AI Developer Hackathon). Tous les chiffres
viennent de calculs sur le fichier ; les écarts sont des associations, pas des causes.</em></p>
</body></html>"""
