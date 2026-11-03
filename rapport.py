# Rapport en un clic : HTML téléchargeable, chiffres 100 % calculés.
# Contenu : résumé, nettoyage, 3 graphiques, anomalies, limites, pistes.

import base64
import html as _html
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

    esc = _html.escape
    if scan_res and scan_res["observations"]:
        obs_html = "".join(f"<li>{esc(o['phrase'])}</li>"
                           for o in scan_res["observations"][:8])
        pistes_html = "".join(
            f"<li>Écart constaté : {esc(o['phrase'])} → piste à vérifier : comparer ce "
            f"segment aux autres sur des facteurs non mesurés ici "
            f"(ancienneté, équipe, contexte…). Rien ne prouve un lien de cause à effet.</li>"
            for o in scan_res["observations"][:3])
    else:
        obs_html = "<li>Aucune anomalie marquée détectée.</li>"
        pistes_html = "<li>Collecter plus de données avant de conclure.</li>"
    hyp_html = "".join(f"<li>{esc(h)}</li>" for h in hypotheses) or "<li>Aucune.</li>"
    if resume_exec:
        bloc_resume = ("<section><h2>1 · Résumé exécutif</h2><ul class=\"resume\">"
                       + "".join(f"<li>{esc(l)}</li>" for l in resume_exec)
                       + "</ul></section>")
    else:
        bloc_resume = ""
    net_html = "".join(f"<li>{esc(l)}</li>" for l in nettoyage.get("rapport", []))
    lignes_types = "".join(
        f"<tr><td>{esc(str(c))}</td><td>{esc(str(df[c].dtype))}</td>"
        f"<td>{int(df[c].isna().sum())}</td></tr>" for c in df.columns)
    nom_fichier = esc(str(nettoyage.get('fichier', 'données')))
    sommaire = "".join(
        f'<li><a href="#s{i}">{t}</a></li>' for i, t in
        [(1, "Résumé exécutif"), (2, "Données et colonnes"),
         (3, "Nettoyage effectué"), (4, "Graphiques clés"),
         (5, "Anomalies détectées"), (6, "Hypothèses et limites"),
         (7, "Pistes de recommandation")])

    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rapport DataAgent — {nom_fichier}</title>
<style>
:root{{color-scheme:light}}
body{{font-family:"Segoe UI",Arial,sans-serif;max-width:960px;margin:0 auto;
padding:0 1.2em 3em;color:#1f2937;line-height:1.55;background:#fff}}
.bandeau{{background:#0f766e;color:#fff;border-radius:12px;padding:26px 30px;margin:1.5em 0}}
.bandeau h1{{margin:0;font-size:1.8rem;letter-spacing:-.02em}}
.bandeau p{{margin:.5em 0 0;color:#d7efea}}
.sommaire{{background:#f0fdf9;border:1px solid #ccfbf1;border-radius:12px;
padding:14px 22px;margin:0 0 1.5em}}
.sommaire ol{{margin:.4em 0;padding-left:1.4em}}
.sommaire a{{color:#0f766e}}
section{{margin-bottom:2em}}
h2{{font-size:1.25rem;color:#111827;border-bottom:2px solid #0f766e;
padding-bottom:.3em}}
table{{border-collapse:collapse;width:100%;margin-top:.6em}}
th{{background:#0f766e;color:#fff;text-align:left}}
td,th{{border:1px solid #ccfbf1;padding:6px 12px;font-size:.92em}}
tr:nth-child(even) td{{background:#f0fdf9}}
figure{{margin:1em 0;border:1px solid #e5e7eb;border-radius:12px;padding:14px}}
figcaption{{font-weight:600;color:#0f766e;margin-bottom:.5em}}
img{{max-width:100%;height:auto}}
ul.resume li{{margin:.5em 0}}
.pied{{border-top:1px solid #ccfbf1;margin-top:2em;padding-top:1em;
color:#6b7280;font-size:.9em}}
@media print{{.bandeau{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}}}
</style></head><body>
<header class="bandeau"><h1>Rapport DataAgent</h1>
<p>Fichier : {nom_fichier} — {len(df)} lignes, {len(df.columns)} colonnes.<br>
Version analysée : {esc(str(version_label))}.</p></header>
<nav class="sommaire"><strong>Sommaire</strong><ol>{sommaire}</ol></nav>
{bloc_resume}
<section id="s2"><h2>2 · Données et colonnes</h2>
<table><tr><th>Colonne</th><th>Type</th><th>Manquantes</th></tr>{lignes_types}</table></section>
<section id="s3"><h2>3 · Nettoyage effectué</h2><ul>{net_html}</ul></section>
<section id="s4"><h2>4 · Graphiques clés</h2>
{''.join(f'<figure id="g{i}"><figcaption>{esc(t)}</figcaption>'
         f'<img src="data:image/png;base64,{img}" alt="{esc(t)}"></figure>'
         for i, (t, img) in enumerate(morceaux, 1))}</section>
<section id="s5"><h2>5 · Anomalies détectées</h2><ul>{obs_html}</ul></section>
<section id="s6"><h2>6 · Hypothèses et limites</h2><ul>{hyp_html}</ul></section>
<section id="s7"><h2>7 · Pistes de recommandation (à vérifier, jamais des certitudes)</h2>
<ul>{pistes_html}</ul></section>
<footer class="pied"><em>Rapport généré par DataAgent (Meta Global AI Developer Hackathon). Tous les chiffres
viennent de calculs sur le fichier ; les écarts sont des associations, pas des causes.</em></footer>
</body></html>"""
