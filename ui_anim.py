# Animations de l'interface (fonctionnalités Anim 1-3).
# Choix technique en une phrase : l'app est Streamlit (Python, sans build React),
# donc pas de Framer Motion ni npm — tout passe en CSS pur + @keyframes.
# Règles : uniquement transform/opacity (60 fps), 150-300 ms en micro,
# 400-800 ms en sections, et le `prefers-reduced-motion` global de app.py
# coupe tout pour les utilisateurs qui le demandent.

from __future__ import annotations

import html

# Animation 1 : zone d'upload (survol + progression + succès).
CSS_UPLOAD = """
<style>
@keyframes da-dessine { to { stroke-dashoffset: 0; } }
@keyframes da-entree { from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: none; } }
div[data-testid="stFileUploaderDropzone"] {
  border: 2px dashed #0f766e; border-radius: 14px;
  transition: transform .2s ease-out, border-color .2s ease-out,
    background-color .2s ease-out; }
div[data-testid="stFileUploaderDropzone"]:hover,
div[data-testid="stFileUploaderDropzone"]:focus-within {
  transform: scale(1.01); border-color: #14b8a6; background: #f0fdf9; }
div[data-testid="stFileUploader"] div[role="progressbar"] > div {
  transition: width .3s ease-out; }
.da-succes { display: flex; align-items: center; gap: 12px;
  background: #f0fdf9; border: 1px solid #99f6e4; border-radius: 12px;
  padding: 10px 16px; margin: .6rem 0; animation: da-entree .4s ease-out; }
.da-succes .da-texte { color: #115e59; font-weight: 600; }
.da-succes .da-detail { color: #0f766e; font-size: .85rem; }
.da-coche circle { stroke-dasharray: 166; stroke-dashoffset: 166;
  animation: da-dessine .5s ease-out forwards; }
.da-coche path { stroke-dasharray: 48; stroke-dashoffset: 48;
  animation: da-dessine .3s ease-out .45s forwards; }
</style>
"""


def carte_succes(nom: str, lignes: int, colonnes: int) -> str:
    """Carte de succès avec coche SVG qui se dessine (nom échappé)."""
    nom_sain = html.escape(str(nom))
    return f"""
<div class="da-succes">
  <svg class="da-coche" width="34" height="34" viewBox="0 0 52 52">
    <circle cx="26" cy="26" r="24" fill="none" stroke="#0f766e" stroke-width="3"/>
    <path fill="none" stroke="#0f766e" stroke-width="4" stroke-linecap="round"
      d="M14 27l8 8 16-16"/>
  </svg>
  <div><div class="da-texte">Fichier chargé : {nom_sain}</div>
  <div class="da-detail">{int(lignes)} lignes, {int(colonnes)} colonnes</div></div>
</div>
"""

# Animation 2 : pipeline d'agents en direct (états issus de la session :
# la première étape non terminée pulse, les connecteurs se remplissent).
CSS_PIPELINE = """
<style>
@keyframes da-pulse { 0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.12); opacity: .75; } }
@keyframes da-flux { from { opacity: .35; } to { opacity: 1; } }
.da-pipe { display: flex; align-items: flex-start; margin: .4rem 0 1rem 0; }
.da-noeud { flex: 0 0 auto; width: 104px; text-align: center; }
.da-pastille { width: 38px; height: 38px; margin: 0 auto; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-weight: 700; background: #e5e7eb; color: #6b7280; }
.da-nom { font-size: .78rem; font-weight: 600; color: #374151; margin-top: 4px; }
.da-msg { font-size: .7rem; color: #6b7280; min-height: 2em; }
.da-noeud.fait .da-pastille { background: #0f766e; color: #fff; }
.da-noeud.fait .da-msg { color: #0f766e; }
.da-noeud.actif .da-pastille { background: #14b8a6; color: #fff;
  animation: da-pulse 1.2s ease-out infinite; }
.da-noeud.actif .da-msg { color: #115e59; font-weight: 600; }
.da-lien { flex: 1 1 auto; height: 3px; margin-top: 18px; border-radius: 2px;
  background: #e5e7eb; }
.da-lien.plein { background: #0f766e; }
.da-lien.cours { background: #14b8a6; animation: da-flux .8s ease-out infinite alternate; }
</style>
"""


def pipeline_fichier(brut=None, profil=None, nettoyage=None, scan_res=None,
                     cible="__absente__", historique=None,
                     rapport_cache=None, df=None) -> str:
    """Timeline Profiler → Nettoyeur → Détecteur → Analyste → Rapport.

    Chaque étape est faite/active/en attente selon les données de session
    (que des comptages, aucune chaîne utilisateur : pas d'échappement requis).
    La première étape non terminée pulse avec son message du moment.
    """
    df_lignes = len(df) if df is not None else 0
    etapes = []
    if profil:
        etapes.append(("Profiler", "fait",
                       f"{len(profil.get('colonnes', []))} colonnes analysées"))
    elif brut is not None:
        etapes.append(("Profiler", "actif",
                       f"Analyse de {len(brut.columns)} colonnes…"))
    else:
        etapes.append(("Profiler", "attente", "En attente du fichier"))
    if nettoyage:
        avant = (nettoyage.get("avant") or {})
        etapes.append(("Nettoyeur", "fait",
                       f"{int(avant.get('lignes', df_lignes))} → {df_lignes} lignes, "
                       f"{int(avant.get('manquantes', 0) or 0)} manquantes traitées"))
    elif profil:
        etapes.append(("Nettoyeur", "actif", "Nettoyage en cours…"))
    else:
        etapes.append(("Nettoyeur", "attente", "En attente"))
    if scan_res:
        n_obs = len(scan_res.get("observations", []))
        etapes.append(("Détecteur", "fait", f"{n_obs} observation(s)"))
    elif cible is None and profil:
        etapes.append(("Détecteur", "fait", "Pas de cible, rien à scanner"))
    elif nettoyage:
        etapes.append(("Détecteur", "actif", "Détection des anomalies…"))
    else:
        etapes.append(("Détecteur", "attente", "En attente"))
    n_q = len(historique or [])
    if n_q:
        etapes.append(("Analyste", "fait", f"{n_q} question(s) posée(s)"))
    elif scan_res or (cible is None and profil):
        etapes.append(("Analyste", "actif", "Pose ta première question…"))
    else:
        etapes.append(("Analyste", "attente", "En attente"))
    if rapport_cache:
        etapes.append(("Rapport", "fait", "Rapport généré"))
    elif n_q:
        etapes.append(("Rapport", "actif", "Génère ton rapport…"))
    else:
        etapes.append(("Rapport", "attente", "En attente"))
    presente_actif = False
    morceaux = ['<div class="da-pipe">']
    for i, (nom, etat, msg) in enumerate(etapes):
        if etat == "actif" and presente_actif:
            etat = "attente"
            msg = "En attente"
        if etat == "actif":
            presente_actif = True
        pastille = "✓" if etat == "fait" else str(i + 1)
        morceaux.append(
            f'<div class="da-noeud {etat}"><div class="da-pastille">{pastille}</div>'
            f'<div class="da-nom">{nom}</div><div class="da-msg">{msg}</div></div>')
        if i < len(etapes) - 1:
            suivant = etapes[i + 1][1]
            if etat == "fait" and suivant == "fait":
                lien = "plein"
            elif etat == "fait":
                lien = "cours"
            else:
                lien = ""
            morceaux.append(f'<div class="da-lien {lien}"></div>')
    morceaux.append("</div>")
    return "".join(morceaux)


# Animation 3 : compteurs + jauge qualité (rendu via components.html :
# JavaScript maison, 600 ms, fr-FR, stoppé si prefers-reduced-motion).
CIRCONFERENCE_JAUGE = 326.7  # 2 × π × 52


def bandeau_chiffres(lignes: int, colonnes: int, manquantes: int,
                     anomalies_n: int, score_avant: int,
                     score_apres: int) -> str:
    """Bandeau animé : 4 compteurs + anneau qualité avant → après.

    Que des entiers (aucune chaîne utilisateur : pas d'échappement requis).
    """
    lignes, colonnes = int(lignes), int(colonnes)
    manquantes, anomalies_n = int(manquantes), int(anomalies_n)
    score_avant, score_apres = int(score_avant), int(score_apres)
    decalage = CIRCONFERENCE_JAUGE * (1 - score_apres / 100)
    stats = "".join(
        f'<div class="da-stat"><div class="da-nombre" data-val="{v}">0</div>'
        f'<div class="da-legende">{nom}</div></div>'
        for nom, v in (("Lignes", lignes), ("Colonnes", colonnes),
                       ("Manquantes", manquantes), ("Anomalies", anomalies_n)))
    return f"""
<style>
@keyframes da-jauge {{ from {{ stroke-dashoffset: {CIRCONFERENCE_JAUGE}; }} }}
.da-stats {{ display: flex; align-items: center; gap: 18px; flex-wrap: wrap;
  font-family: -apple-system, "Segoe UI", Roboto, sans-serif; }}
.da-stat {{ min-width: 86px; }}
.da-nombre {{ font-size: 1.6rem; font-weight: 700; color: #0f766e; }}
.da-legende {{ font-size: .78rem; color: #6b7280; }}
.da-jauge {{ display: flex; align-items: center; gap: 10px; }}
.da-anneau {{ transform: rotate(-90deg); transform-origin: center; }}
.da-anneau .fond {{ fill: none; stroke: #e5e7eb; stroke-width: 11; }}
.da-anneau .val {{ fill: none; stroke: #0f766e; stroke-width: 11;
  stroke-linecap: round; stroke-dasharray: {CIRCONFERENCE_JAUGE};
  animation: da-jauge .8s ease-out; }}
.da-centre {{ font-size: 1.3rem; font-weight: 700; color: #0f766e; }}
.da-centre small {{ font-size: .75rem; color: #6b7280; font-weight: 400; }}
@media (prefers-reduced-motion: reduce) {{
  .da-anneau .val {{ animation: none; }} }}
</style>
<div class="da-stats">{stats}
  <div class="da-jauge">
    <svg class="da-anneau" width="104" height="104" viewBox="0 0 120 120">
      <circle class="fond" cx="60" cy="60" r="52"/>
      <circle class="val" cx="60" cy="60" r="52"
        stroke-dashoffset="{decalage:.1f}"/>
    </svg>
    <div><div class="da-centre"><span data-val="{score_apres}">0</span>
      <small>/ 100</small></div>
      <div class="da-legende">Qualité : {score_avant} → {score_apres}</div></div>
  </div>
</div>
<script>
(function () {{
  var reduit = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  document.querySelectorAll("[data-val]").forEach(function (el) {{
    var cible = parseInt(el.getAttribute("data-val"), 10) || 0;
    if (reduit) {{ el.textContent = cible.toLocaleString("fr-FR"); return; }}
    var debut = null, duree = 600;
    function pas(t) {{
      if (!debut) debut = t;
      var p = Math.min(1, (t - debut) / duree);
      var ease = 1 - Math.pow(1 - p, 3);
      el.textContent = Math.round(cible * ease).toLocaleString("fr-FR");
      if (p < 1) requestAnimationFrame(pas);
    }}
    requestAnimationFrame(pas);
  }});
}})();
</script>
"""

# Animation 6 : indicateur « l'agent réfléchit » + streaming de la réponse.
# Le découpage préserve le texte à l'octet près (séparateurs conservés) ;
# le rythme est imposé côté app (time.sleep), jamais ici.
CSS_TYPING = """
<style>
@keyframes da-rebond { 0%, 60%, 100% { transform: translateY(0); opacity: .5; }
  30% { transform: translateY(-6px); opacity: 1; } }
.da-typing { display: inline-flex; gap: 6px; align-items: center;
  background: #f0fdf9; border: 1px solid #ccfbf1; border-radius: 14px;
  padding: 10px 16px; margin: .3rem 0; }
.da-typing span { width: 8px; height: 8px; border-radius: 50%;
  background: #0f766e; animation: da-rebond 1.1s ease-out infinite; }
.da-typing span:nth-child(2) { animation-delay: .15s; }
.da-typing span:nth-child(3) { animation-delay: .3s; }
</style>
"""

INDICATEUR_FRAPPE = '<div class="da-typing"><span></span><span></span><span></span></div>'

MOTS_PAR_PAQUET = 3


def decouper_stream(texte: str, mots: int = MOTS_PAR_PAQUET):
    """Découpe en paquets de `mots` mots ; recoller redonne le texte exact."""
    import re

    morceaux = re.split(r"(\s+)", texte or "")
    paquet = []
    for morceau in morceaux:
        paquet.append(morceau)
        if len([m for m in paquet if m.strip()]) >= mots:
            yield "".join(paquet)
            paquet = []
    if paquet:
        yield "".join(paquet)
