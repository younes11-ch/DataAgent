# DataAgent : envoie un CSV (même sale), les agents le nettoient et l'analysent.

import hashlib
import io
import json
import math
import os
import re
import time

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


def _charger_secrets():
    """Pousse les secrets Streamlit Cloud vers l'environnement (avant moteur)."""
    for var in ("MODEL_API_KEY", "META_BASE_URL", "MUSE_CHAT_MODEL"):
        try:
            if not os.getenv(var) and st.secrets.get(var):
                os.environ[var] = str(st.secrets[var])
        except Exception:
            return


_charger_secrets()

import anomalies
import comparer
import data_agent
import export_pdf
import imputation
import journal
import points_aberrants
import prediction
import profiler
import rapport
import scan
import series
import stats_tests
import ui_anim
import verif
import viz
import voix
from scan import pct

st.set_page_config(page_title="DataAgent", page_icon="📊", layout="wide")
st.markdown("""
<div class="hero">
  <div class="hero-titre">DataAgent</div>
  <div class="hero-sous">Envoie un fichier CSV, même sale : les agents le nettoient,
  détectent les anomalies, répondent à tes questions avec des chiffres vérifiés
  et construisent ton rapport.</div>
  <div class="badges"><span class="badge">Nettoyage</span>
  <span class="badge">Anomalies</span>
  <span class="badge">Questions vérifiées</span>
  <span class="badge">Rapport</span></div>
</div>
""", unsafe_allow_html=True)

# Design : entrée en fondu, boutons pilule, cartes sobres. Sans animation
# si l'utilisateur préfère les mouvements réduits (accessibilité).
st.markdown("""
<style>
@keyframes entree { from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: none; } }
.block-container { animation: entree .45s ease-out; max-width: 72rem; }
div[data-testid="stDecoration"] { background: #0f766e; }
section[data-testid="stAppViewContainer"] { background: #f6f9f8; }
.block-container h1 { letter-spacing: -0.02em; }
.block-container h2, .block-container h3 { color: #0f172a; letter-spacing: -0.01em;
  font-weight: 700; }
div.stButton > button, div.stDownloadButton > button {
  border-radius: 999px; font-weight: 600;
  transition: background-color .18s ease, color .18s ease, border-color .18s ease; }
div.stButton > button { border: 1.5px solid #0f766e; color: #0f766e; background: #fff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, .08); }
div.stButton > button:hover { background: #0f766e; color: #fff; }
div.stButton > button:active { background: #115e59; border-color: #115e59; color: #fff; }
div.stButton > button[kind="primary"] { background: #0f766e; color: #fff; }
div.stButton > button[kind="primary"]:hover { background: #115e59; }
div.stDownloadButton > button { background: #0f766e; border: 1.5px solid #0f766e; color: #fff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, .08); }
div.stDownloadButton > button:hover { background: #115e59; border-color: #115e59; }
div[data-testid="stChatMessage"] { border-radius: 14px; border: 1px solid #e2e8f0;
  background: #fff; box-shadow: 0 1px 3px rgba(15, 23, 42, .05); }
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
  background: #f0fdf9; }
div[data-testid="stMetric"] { background: #fff; border: 1px solid #e2e8f0;
  border-radius: 14px; padding: 14px 18px;
  box-shadow: 0 1px 4px rgba(15, 23, 42, .06); }
div[data-testid="stMetricValue"] { color: #0f766e; }
div[data-testid="stExpander"] { border-radius: 12px; background: #fff;
  border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(15, 23, 42, .05); }
div[data-testid="stDataFrame"] { border: 1px solid #e2e8f0; border-radius: 12px;
  background: #fff; box-shadow: 0 1px 3px rgba(15, 23, 42, .05); }
section[data-testid="stSidebar"] h2 { font-size: 1.1rem; }
.hero { background: #fff; border: 1px solid #e2e8f0; border-top: 4px solid #0f766e;
  border-radius: 14px; padding: 20px 24px; margin-bottom: 1.2rem;
  box-shadow: 0 1px 4px rgba(15, 23, 42, .06); }
.hero-titre { color: #0f172a; font-size: 1.9rem; font-weight: 700;
  letter-spacing: -0.02em; line-height: 1.1; }
.hero-sous { color: #475569; font-size: 1rem; margin-top: 8px; max-width: 62em; }
.barre-nettoyage { background: #f0fdf9; border: 1px solid #ccfbf1;
  border-radius: 12px; padding: 12px 18px; margin: 0.6rem 0 1rem 0; }
.badges { margin-top: 12px; }
.badge { display: inline-block; background: #f0fdf9; color: #0f766e;
  border: 1px solid #ccfbf1; border-radius: 999px; font-size: .82rem; font-weight: 600;
  padding: 3px 12px; margin: 0 6px 6px 0; }
.etape { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px;
  padding: 12px 14px; text-align: center; color: #0f172a; font-size: .92rem;
  box-shadow: 0 1px 4px rgba(15, 23, 42, .06); }
.etape strong { display: block; color: #0f766e; font-size: .95rem; }
.carte-recherche { background: #f0fdf9; border: 1px solid #ccfbf1;
  border-radius: 12px; padding: 14px 18px; margin-bottom: 1rem; }
@media (prefers-reduced-motion: reduce) {
  * { animation: none !important; transition: none !important; } }
</style>
""", unsafe_allow_html=True)
st.markdown(ui_anim.CSS_UPLOAD, unsafe_allow_html=True)
st.markdown(ui_anim.CSS_PIPELINE, unsafe_allow_html=True)
st.markdown(ui_anim.CSS_TYPING, unsafe_allow_html=True)


if not data_agent.cle_api_disponible():
    st.warning("Mode démo (sans clé API) : nettoyage IA, questions libres et "
               "graphiques IA désactivés — scan, statistiques, valeurs "
               "aberrantes, comparaison et rapports restent disponibles. "
               "Ajoute ta clé Meta dans `.env` (local) ou les secrets "
               "(Streamlit Cloud) pour tout activer.")


@st.cache_data
def lire_csv(contenu: bytes, nom: str):
    """Lit un CSV en détectant séparateur (`,` ou `;`) et encodage (utf-8, latin-1)."""
    for enc in ("utf-8", "latin-1"):
        for sep in (",", ";"):
            try:
                df = pd.read_csv(io.BytesIO(contenu), sep=sep, encoding=enc)
                if len(df.columns) > 1:
                    return df
            except Exception:
                continue
    return pd.read_csv(io.BytesIO(contenu), encoding="latin-1")


def lire_tableau(contenu: bytes, nom: str, format_fichier=""):
    """Lit un CSV ou un Excel (1er onglet) depuis des octets."""
    from recherche import lire_contenu
    return lire_contenu(contenu, nom, format_fichier)


for cle, defaut in [("identifiant", None), ("nom", ""), ("brut", None),
                    ("df", None), ("profil", None), ("resume", None),
                    ("ambigues", []), ("nettoyage", None), ("version", ""),
                    ("cible", None), ("scan_res", None), ("hypotheses", []),
                    ("historique", []), ("a_poser", None), ("pred", None),
                    ("tests_res", None), ("stat_res", None),
                    ("serie_res", None),
                    ("dedup_applique", None),
                    ("base_nettoyee", None), ("journal", []), ("journal_details", []),
                    ("script_nettoyage", None), ("annule", False),
                    ("strategie_appliquee", None), ("det_aberrantes", None),
                    ("resume_exec", None), ("rapport_cache", None),
                    ("csv_cache", None)]:
    # NOTE : ne jamais pré-remplir ici une clé aussi passée en `value=`
    # à un widget (autoriser_recherche, lecture_vocale) : Streamlit
    # l'interdit (erreur vue dans les logs Cloud) ; le `value=` du
    # widget sert déjà de défaut, et le reste du code lit via .get().
    if cle not in st.session_state:
        st.session_state[cle] = defaut

# Traduction des choix de la barre latérale vers le moteur.
DETAIL_CHOIX = {"Concise": "concise", "Normale": "normale", "Détaillée": "detaillee"}
GRAPH_CHOIX = {"Auto": "auto", "Barres": "barres", "Ligne": "ligne", "Camembert": "camembert"}

with st.sidebar:
    st.header("Réglages")
    st.selectbox("Détail des réponses", list(DETAIL_CHOIX), key="detail_rep")
    st.selectbox("Graphiques préférés", list(GRAPH_CHOIX), key="graph_pref")
    st.slider("Questions suggérées", 2, 6, 4, key="nb_sug")
    st.toggle("Afficher les graphiques", value=True, key="voir_graph")
    st.toggle("Montrer le code par défaut", value=False, key="voir_code")
    st.header("Recherche")
    st.toggle("Autoriser la recherche", value=True,
              key="autoriser_recherche",
              help="L'agent peut chercher des données sur le web sans fichier.")
    st.header("Voix")
    st.toggle("Lecture vocale", value=False, key="lecture_vocale",
              help="Lit les réponses à voix haute (français).")
    if st.session_state.df is not None:
        st.header("Données")
        st.slider("Lignes de l'aperçu", 5, 20, 5, key="lignes_apercu")
        cle_csv = (st.session_state.identifiant,
                   st.session_state.get("strategie_appliquee"),
                   st.session_state.get("annule"))
        if st.session_state.get("csv_cache") is None \
                or st.session_state.csv_cache.get("cle") != cle_csv:
            st.session_state.csv_cache = {
                "cle": cle_csv,
                "octets": _neutraliser_formules(
                    st.session_state.df).to_csv(
                        index=False).encode("utf-8")}
        st.download_button("Télécharger les données nettoyées (CSV)",
                           st.session_state.csv_cache["octets"],
                           "donnees_nettoyees.csv", "text/csv")
    if st.session_state.historique:
        if st.button("Effacer la discussion"):
            st.session_state.historique = []
            st.rerun()


def reconstruire():
    """Pipeline complet : nettoyage IA (1 fois) puis finition déterministe."""
    brut = st.session_state.brut
    nom = st.session_state.nom
    dedup = st.session_state.get("dedup", True)
    lignes_avant = len(brut)
    manq_avant = int(brut.isna().sum().sum())
    with st.spinner("Les agents nettoient les données…"):
        nettoyage = data_agent.nettoyer_donnees(
            brut, data_agent.profile_data(brut, nom),
            supprimer_doublons=dedup)
    base = nettoyage["df_clean"]
    st.session_state.base_nettoyee = base
    st.session_state.nettoyage = {
        "rapport": nettoyage["rapport"], "fichier": nom,
        "avant": {"lignes": lignes_avant, "manquantes": manq_avant},
        "doublons": nettoyage["doublons"], "nettoye": nettoyage["nettoye"],
        "code": nettoyage.get("code", "")}
    doublons_n = nettoyage["doublons"]["n"]
    if nettoyage["nettoye"]:
        suffixe = (f" (doublons supprimés)" if dedup and doublons_n else
                   f" (doublons conservés)" if doublons_n else "")
        st.session_state.version = f"nettoyée{suffixe}"
    elif lignes_avant == len(base) and manq_avant == 0 and doublons_n == 0:
        st.session_state.version = "brute (aucun nettoyage nécessaire)"
    else:
        st.session_state.version = "brute (nettoyage impossible)"
    st.session_state.profil = data_agent.profile_data(base, nom)
    try:
        with st.spinner("Les agents explorent ton fichier…"):
            st.session_state.resume = data_agent.resumer_donnees(st.session_state.profil)
    except Exception:
        st.session_state.resume = None
    extra = (st.session_state.resume or {}).get("colonnes_ambigues", [])
    st.session_state.ambigues = sorted(set(st.session_state.profil["ambigues"]) | set(extra))
    st.session_state.profil["ambigues"] = st.session_state.ambigues
    st.session_state.annule = False
    st.session_state.dedup_applique = dedup
    finaliser()


def finaliser():
    """Finition déterministe : imputation choisie + analyse (sans appel IA)."""
    strat = st.session_state.get("strategie", "auto")
    imp = imputation.appliquer(st.session_state.base_nettoyee, strat)
    df = imp["df"]
    st.session_state.df = df
    st.session_state.journal = (
        list((st.session_state.nettoyage or {}).get("rapport", []))
        + imp["journal"])
    st.session_state.journal_details = (
        journal.entrees_nettoyage(st.session_state.nettoyage,
                                  bool(st.session_state.get("dedup", True)))
        + list(imp.get("details", [])))
    st.session_state.script_nettoyage = journal.exporter_script(
        (st.session_state.nettoyage or {}).get("code", ""),
        imp.get("remplissages", {}), strat,
        st.session_state.nom or "donnees.csv")
    _rafraichir_analyse(df)
    st.session_state.strategie_appliquee = strat


def _appliquer_decision_aberrantes():
    """Applique garder / corriger / supprimer sur les anomalies détectées (§3).

    Met à jour données + journal + script reproductible, puis recalcule
    profil/scan/hypothèses (les anciennes réponses du chat sont invalidées).
    """
    det = st.session_state.det_aberrantes or {}
    col = det.get("colonne")
    df = st.session_state.df
    if not col or df is None or col not in df.columns:
        return
    choix = st.session_state.get("ab_decision", "garder")
    idx_labels = list(det.get("index") or [])
    res = anomalies.appliquer_decision(df, col, choix, index=idx_labels)
    st.session_state.journal = (list(st.session_state.journal or [])
                                + [res["entree"]["justification"]])
    st.session_state.journal_details = (
        list(st.session_state.get("journal_details") or []) + [res["entree"]])
    if choix != "garder" and st.session_state.get("script_nettoyage"):
        st.session_state.script_nettoyage += (
            "\n" + anomalies.code_rejeu(col, choix, idx_labels,
                                        valeur=res.get("valeur")) + "\n")
    st.session_state.df = res["df"]
    st.session_state.det_aberrantes = None
    _rafraichir_analyse(res["df"])
    st.rerun()


def annuler_nettoyage():
    """Restaure les données d'origine (ni nettoyage IA, ni imputation)."""
    brut = st.session_state.brut
    st.session_state.df = brut.copy()
    st.session_state.version = "d'origine (nettoyage annulé)"
    st.session_state.journal = ["Nettoyage annulé : données d'origine restaurées."]
    st.session_state.journal_details = []
    st.session_state.script_nettoyage = None
    st.session_state.annule = True
    _rafraichir_analyse(brut)


def _rafraichir_analyse(df):
    """Recalcule profil + scan + hypothèses sur le DataFrame donné (sans IA)."""
    st.session_state.profil = data_agent.profile_data(df, st.session_state.nom)
    st.session_state.profil["ambigues"] = st.session_state.ambigues
    cible = scan.detecter_cible(df)
    st.session_state.cible = cible
    st.session_state.scan_res = scan.scan_anomalies(df, cible) if cible else None
    hypos = []
    if st.session_state.ambigues:
        hypos.append("Colonnes au sens non défini dans le fichier : "
                     + ", ".join(st.session_state.ambigues)
                     + " (leur signification n'est jamais interprétée).")
    else:
        hypos.append("Aucune colonne ambiguë détectée.")
    doublons = (st.session_state.nettoyage or {}).get("doublons", {})
    doublons_n, pct_d = doublons.get("n", 0), doublons.get("pct", 0)
    dedup = st.session_state.get("dedup", True)
    if st.session_state.annule:
        hypos.append(f"{doublons_n} doublons exacts détectés : "
                     "conservés (nettoyage annulé).")
    else:
        hypos.append(f"{doublons_n} doublons exacts ({pct_d} %) : "
                     + ("supprimés." if dedup and doublons_n else
                        "conservés (choix utilisateur)." if doublons_n else "aucun."))
    petits = (st.session_state.scan_res or {}).get("petits", [])
    hypos.extend(petits if petits else ["Aucun petit échantillon extrême signalé."])
    st.session_state.hypotheses = hypos
    st.session_state.historique = []
    st.session_state.pred = None
    st.session_state.tests_res = None
    st.session_state.stat_res = None
    st.session_state.serie_res = None
    st.session_state.det_aberrantes = None
    st.session_state.resume_exec = None
    st.session_state.rapport_cache = None
    st.session_state.csv_cache = None


def questions_secours(profil):
    """4 questions à partir des colonnes détectées (si le résumé échoue)."""
    nums = [d["nom"] for d in profil["detail"]
            if "int" in d["type"] or "float" in d["type"]]
    cats = [d["nom"] for d in profil["detail"] if d["nom"] not in nums]
    qs = []
    if nums and cats:
        qs.append(f"Quel est le total de {nums[0]} par {cats[0]} ?")
    if nums:
        qs.append(f"Quelles sont les statistiques de {nums[0]} ?")
    if cats:
        qs.append(f"Combien de lignes par {cats[0]} ?")
    if len(nums) > 1:
        qs.append(f"Fais un graphique de {nums[0]} en fonction de {nums[1]}.")
    elif nums and cats:
        qs.append(f"Fais un graphique de {nums[0]} par {cats[0]}.")
    return qs[:4]


def _lien_sain(url):
    """Lien affichable : http(s) public, sans userinfo ni rupture markdown."""
    import urllib.parse
    propre = (url or "").strip()
    if not propre.startswith(("http://", "https://")):
        return ""
    if any(c in propre for c in " \t\n()\"'\\<>"):
        return ""
    try:
        if "@" in urllib.parse.urlsplit(propre).netloc:
            return ""
    except Exception:
        return ""
    return propre


def _neutraliser_formules(df):
    """Neutralise l'injection de formules CSV à l'export.

    Une cellule commençant par = + - @ (ou tab/CR) s'exécuterait à
    l'ouverture dans Excel : on la préfixe d'une apostrophe, affichée
    comme simple texte.
    """

    def _nettoie(valeur):
        texte = str(valeur)
        if texte[:1] in ("=", "+", "-", "@", "\t", "\r", "|"):
            return "'" + texte
        return valeur

    return df.apply(lambda col: col.map(_nettoie)
                    if col.dtype == object else col)


def afficher_sources(sources):
    """Sources (nom + lien) sous chaque réponse web."""
    if not sources:
        return
    st.caption("Sources :")
    for src in sources:
        nom = (src.get("nom", "Source") or "Source").replace("[", "(").replace("]", ")")
        # Anti-injection markdown : un nom piégé ("...\n![p](https://evil/t)")
        # ne doit ni sauter de ligne ni embarquer d'image tierce.
        nom = re.sub(r"[\r\n]+", " ", nom).strip()
        nom = re.sub(r"^!+\s*(?=\[)", "", nom)
        url = _lien_sain(src.get("url"))
        if url:
            st.markdown(f"- [{nom}]({url})")
        else:
            st.write(f"- {nom}")
        fichier = _lien_sain(src.get("fichier"))
        if fichier:
            fmt = (src.get("format_fichier") or "").strip() or "fichier"
            st.markdown(f"  Télécharger le fichier ({fmt}) : "
                        f"[lien direct]({fichier})")


def boutons_charger(sources, prefixe):
    """Boutons 'charger dans l'app' pour chaque fichier trouvé (sans upload)."""
    for idx, src in enumerate(sources or []):
        fichier = _lien_sain((src or {}).get("fichier"))
        if not fichier:
            continue
        nom = ((src or {}).get("nom", "fichier") or "fichier")[:50]
        fmt = ((src or {}).get("format_fichier") or "").strip().lower()
        if st.button(f"Charger dans l'app : {nom}", key=f"{prefixe}-load-{idx}"):
            charger_url_dans_app(fichier, nom, fmt)


def charger_url_dans_app(url, nom, format_fichier=""):
    """Télécharge un fichier trouvé par la recherche et l'analyse (comme un upload)."""
    from recherche import telecharger_fichier
    try:
        with st.spinner("Téléchargement du fichier…"):
            contenu = telecharger_fichier(url)
        try:
            tableau = lire_tableau(contenu, nom, format_fichier)
        except Exception:
            st.error("Impossible de lire ce fichier (CSV ou Excel attendu).")
            return
        if len(tableau) == 0 or len(tableau.columns) == 0:
            st.error("Ce fichier est vide.")
            return
        st.session_state.brut = tableau
        st.session_state.identifiant = (nom, len(contenu))
        st.session_state.nom = nom
        st.session_state.df = None
        st.rerun()
    except Exception as e:
        st.error(f"Téléchargement impossible : {e}. "
                 "Essaie le lien direct ci-dessus.")


def afficher_audit(resultat):
    """Confiance, verdict et points non vérifiés d'une réponse auditée."""
    confiance = resultat.get("confiance")
    verdict = resultat.get("verdict")
    if confiance or verdict:
        boucles = resultat.get("boucles", "?")
        st.info(f"Confiance : {confiance or '?'} · "
                f"Verdict audit : {verdict or '?'} · "
                f"Boucles : {boucles}")
    points = resultat.get("points_non_verifies") or []
    if points:
        st.warning("Points non vérifiés : " + "; ".join(points[:5]))


def bloc_reverification(echange, cle):
    """Bouton « Revérifier » : relance le code pandas en sandbox, compare les chiffres.

    Le résultat est stocké dans echange["reverification"] pour survivre au rerun.
    Sans code (réponse directe) ou sans données : simple message, pas de bouton.
    """
    ag = echange.get("agents") or {}
    code = (ag.get("code") or "").strip()
    if not code:
        st.caption("Pas de code à revérifier ici (réponse directe, sans calcul).")
        return
    if st.session_state.df is None:
        st.caption("Charge un fichier pour revérifier ce calcul.")
        return
    if st.button("Revérifier", key=f"reverif-{cle}",
                 help="Relance le même code pandas dans un calcul indépendant."):
        with st.spinner("Revérification en cours…"):
            second = verif.reverifier(st.session_state.df, code)
        if not second.get("ok"):
            echange["reverification"] = (
                "⚠ Revérification impossible : "
                + (second.get("erreur") or "échec du calcul."))
        else:
            avant = data_agent.extraire_nombres(ag.get("log") or "")
            comp = verif.comparer_nombres(avant, second.get("nombres") or [])
            echange["reverification"] = verif.formater_verdict(comp)
    if echange.get("reverification"):
        st.info(echange["reverification"])


def _sans_images_markdown(texte):
    """Retire les images markdown d'un texte IA avant affichage.

    `![alt](https://...)` déclencherait sinon une requête sortante (IP du
    lecteur) vers un hôte choisi par le modèle : on garde le texte alt.
    """
    return re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", texte or "")


def _diffuser(texte):
    """Affiche la réponse progressivement (3 mots / 25 ms, texte intact)."""
    def _paquets():
        for morceau in ui_anim.decouper_stream(
                _sans_images_markdown(texte)):
            yield morceau
            time.sleep(0.025)
    st.write_stream(_paquets())


def afficher_lecture(reponse, cle):
    """Bouton haut-parleur sous une réponse (si lecture activée)."""
    if st.session_state.get("lecture_vocale"):
        try:
            components.html(voix.html_lecture(reponse or "", cle=cle),
                            height=70)
        except Exception:
            st.caption("Lecture vocale indisponible ici.")


def afficher_echange(echange, idx):
    """Un échange user/assistant rejouable avec ou sans fichier chargé."""
    st.chat_message("user").write(echange["question"])
    with st.chat_message("assistant"):
        st.write(_sans_images_markdown(echange["reponse"])
                 or "Analyse terminée.")
        if echange.get("tableau") is not None:
            st.dataframe(echange["tableau"])
        if st.session_state.get("voir_graph", True):
            for fig in echange.get("figures") or []:
                st.image(fig, width=520)
        afficher_audit(echange)
        afficher_sources(echange.get("sources") or [])
        boutons_charger(echange.get("sources") or [], f"hist-{idx}")
        afficher_lecture(echange.get("reponse"), f"hist-{idx}")
        with st.expander("Voir le code",
                         expanded=st.session_state.get("voir_code", False)):
            ag = echange.get("agents") or {}
            st.write("**Planificateur** : " + ag.get("plan", ""))
            st.write("**Codeur** : " + ag.get("explication", ""))
            st.code(ag.get("code", ""), language="python")
            if ag.get("log"):
                st.write("**Résultat brut (sortie du code exécuté)** :")
                st.text(str(ag.get("log"))[:2000])
            if echange.get("tableau") is not None:
                st.write("**Tableau brut du résultat** :")
                st.dataframe(echange["tableau"])
            st.write("**Vérificateur** : " + ag.get("verdict", ""))
            if ag.get("audit"):
                st.write("**Audit** : " + ag.get("audit", ""))
            bloc_reverification(echange, idx)


def traiter_recherche(question):
    """Recherche sans fichier : agents web + audit, sources affichées."""
    st.chat_message("user").write(question)
    with st.chat_message("assistant"):
        attente = st.empty()
        attente.markdown(ui_anim.INDICATEUR_FRAPPE, unsafe_allow_html=True)
        with st.status("Recherche en cours…", expanded=True) as statut:
            try:
                resultat = data_agent.analyser_sans_upload(
                    question,
                    permettre_recherche=st.session_state.get(
                        "autoriser_recherche", True),
                    etape=statut.write)
                statut.update(label="Recherche terminée !", state="complete")
            except Exception:
                statut.update(label="Erreur pendant la recherche",
                              state="error")
                attente.empty()
                st.error("Oups, une erreur est arrivée. Essaie de reformuler ta question.")
                return
        attente.empty()
        _diffuser(resultat["reponse"] or "Recherche terminée.")
        afficher_audit(resultat)
        afficher_sources(resultat.get("sources") or [])
        boutons_charger(resultat.get("sources") or [],
                        f"rech-{len(st.session_state.historique)}")
        afficher_lecture(resultat["reponse"], f"rech-{len(st.session_state.historique)}")
    st.session_state.historique.append(
        {"question": question, "reponse": resultat["reponse"],
         "tableau": None, "figures": [],
         "agents": resultat.get("agents", {}),
         "sources": resultat.get("sources") or [],
         "confiance": resultat.get("confiance"),
         "points_non_verifies": resultat.get("points_non_verifies") or [],
         "verdict": resultat.get("verdict")})


def traiter_question(question):
    """Fait travailler les agents avec suivi en direct, réponse vérifiée."""
    st.chat_message("user").write(question)
    with st.chat_message("assistant"):
        attente = st.empty()
        attente.markdown(ui_anim.INDICATEUR_FRAPPE, unsafe_allow_html=True)
        with st.status("Les agents travaillent…", expanded=True) as statut:
            try:
                resultat = data_agent.analyser_question(
                    st.session_state.df, st.session_state.profil,
                    question, st.session_state.historique,
                    etape=statut.write,
                    detail=DETAIL_CHOIX[st.session_state.get("detail_rep", "Normale")],
                    graphique=GRAPH_CHOIX[st.session_state.get("graph_pref", "Auto")])
                statut.update(label="Analyse terminée !", state="complete")
            except Exception:
                statut.update(label="Erreur pendant l'analyse", state="error")
                attente.empty()
                st.error("Oups, une erreur est arrivée. Essaie de reformuler ta question.")
                return
        attente.empty()
        _diffuser(resultat["reponse"] or "Analyse terminée.")
        if resultat["tableau"] is not None:
            st.dataframe(resultat["tableau"])
        if st.session_state.get("voir_graph", True):
            for i, fig in enumerate(resultat["figures"]):
                st.image(fig, width=520)
                st.download_button(f"Télécharger le graphique {i + 1}", fig,
                                   f"graphique{i + 1}.png", "image/png",
                                   key=f"g{i}-{len(st.session_state.historique)}")
        with st.expander("Voir le code",
                         expanded=st.session_state.get("voir_code", False)):
            ag = resultat["agents"]
            st.write("**Planificateur** : " + ag.get("plan", ""))
            st.write("**Codeur** : " + ag.get("explication", ""))
            st.code(ag.get("code", ""), language="python")
            if ag.get("log"):
                st.write("**Résultat brut (sortie du code exécuté)** :")
                st.text(str(ag.get("log"))[:2000])
            if resultat["tableau"] is not None:
                st.write("**Tableau brut du résultat** :")
                st.dataframe(resultat["tableau"])
            st.write("**Vérificateur** : " + ag.get("verdict", ""))
            if ag.get("audit"):
                st.write("**Audit** : " + ag.get("audit", ""))
        afficher_audit(resultat)
        afficher_sources(resultat.get("sources") or [])
        afficher_lecture(resultat["reponse"],
                         f"csv-{len(st.session_state.historique)}")
    st.session_state.historique.append(
        {"question": question, "reponse": resultat["reponse"],
         "tableau": resultat["tableau"], "figures": resultat["figures"],
         "agents": resultat["agents"],
         "sources": resultat.get("sources") or [],
         "confiance": resultat.get("confiance"),
         "points_non_verifies": resultat.get("points_non_verifies") or [],
         "verdict": resultat.get("verdict")})
    st.rerun()


def verifier_test(test, reponse):
    """Vérifie un test intégré selon son type."""
    t = test["type"]
    if t == "nombre":
        for _, v in data_agent.extraire_nombres(reponse):
            e, tol = test["attendu"], test.get("tolerance", 0)
            if (math.isclose(v, e, abs_tol=tol)
                    or math.isclose(v * 100, e, abs_tol=tol)
                    or math.isclose(v, e / 100, abs_tol=tol / 100 if tol else 1e-9)):
                return True
        return False
    if t in ("refus_colonne", "contient"):
        return test["attendu"].lower() in (reponse or "").lower()
    if t == "sans_causalite":
        plat = (reponse or "").lower()
        return not any(m in plat or m.replace("é", "e") in plat
                       for m in [w.lower() for w in data_agent.MOTS_CAUSALS])
    return False


et1, et2, et3 = st.columns(3)
et1.markdown('<div class="etape"><strong>1 · Chercher</strong>'
             "L'agent interroge plusieurs sources</div>",
             unsafe_allow_html=True)
et2.markdown('<div class="etape"><strong>2 · Vérifier</strong>'
             "Audit sources, logique, sécurité</div>",
             unsafe_allow_html=True)
et3.markdown('<div class="etape"><strong>3 · Citer</strong>'
             "Réponse avec confiance et liens</div>",
             unsafe_allow_html=True)

st.subheader("0 · Recherche sans fichier")
with st.container(border=True):
    st.write("Pas de CSV ? L'agent cherche lui-même sur le web, puis chaque "
             "réponse passe l'audit (sources, logique, sécurité).")
    st.caption("Sources classées en premier : Kaggle, data.gouv.fr, Insee.")
    col_rech, col_btn = st.columns([4, 1])
    with col_rech:
        question_web = st.text_input("Barre de recherche",
                                     placeholder="Ex : taux de chômage France 2024",
                                     key="question_web",
                                     label_visibility="collapsed")
    with col_btn:
        lancer_rech = st.button("Rechercher")
    if lancer_rech and (question_web or "").strip():
        traiter_recherche(question_web.strip())
        st.rerun()

if st.session_state.df is None and st.session_state.historique:
    st.subheader("Réponses de recherche")
    for idx, echange in enumerate(st.session_state.historique):
        afficher_echange(echange, f"web-{idx}")

components.html(voix.html_micro(cle="global"), height=180)
st.caption("Dictée en français : parle, la transcription s'affiche "
           "ci-dessus, copie-la dans la barre de recherche ou dans le chat. "
           "Le voyant rouge indique l'écoute.")

fichier = st.file_uploader("Envoie ton fichier de données (CSV ou Excel, même sale)",
                            type=["csv", "xlsx", "xls"])

TAILLE_MAX_UPLOAD = 50_000_000  # 50 Mo : au-delà, le serveur partagé ramerait

if fichier is not None:
    if fichier.size > TAILLE_MAX_UPLOAD:
        st.error("Fichier trop volumineux (max 50 Mo) : envoie un extrait.")
        st.stop()
    contenu = fichier.getvalue()
    if len(contenu) > TAILLE_MAX_UPLOAD:
        st.error("Fichier trop volumineux (max 50 Mo) : envoie un extrait.")
        st.stop()
    identifiant = (fichier.name, len(contenu),
                    hashlib.sha256(contenu).hexdigest())
    if st.session_state.identifiant != identifiant:
        try:
            brut_lu = lire_tableau(contenu, fichier.name)
        except Exception:
            st.error("Impossible de lire ce fichier. Vérifie que c'est bien un CSV ou un Excel.")
            st.stop()
        if len(brut_lu) == 0 or len(brut_lu.columns) == 0:
            st.error("Ce fichier est vide : envoie un CSV avec au moins une ligne.")
            st.stop()
        st.session_state.brut = brut_lu
        st.session_state.identifiant = identifiant
        st.session_state.nom = fichier.name
        st.session_state.df = None

    brut = st.session_state.brut
    st.markdown(ui_anim.carte_succes(fichier.name, len(brut), len(brut.columns)),
                unsafe_allow_html=True)
    doublons_n = int(brut.duplicated().sum())
    if doublons_n:
        st.warning(f"⚠ {doublons_n} doublons exacts détectés "
                   f"({round(doublons_n / len(brut) * 100, 1)} %). "
                   f"Sans colonne identifiant, ce ne sont pas forcément de vrais doublons.")
    st.toggle("Supprimer les doublons", value=True, key="dedup")
    if "strategie" not in st.session_state:
        st.session_state.strategie = "auto"
    st.selectbox("Valeurs manquantes restantes", list(imputation.LIBELLES),
                 format_func=lambda k: imputation.LIBELLES[k],
                 disabled=st.session_state.annule, key="strategie")
    if st.session_state.df is None \
            or st.session_state.dedup_applique != st.session_state.get("dedup"):
        reconstruire()
        st.rerun()
    if not st.session_state.annule \
            and st.session_state.get("strategie_appliquee") != st.session_state.get("strategie"):
        finaliser()
        st.rerun()
    if not st.session_state.annule:
        if st.button("Annuler le nettoyage"):
            annuler_nettoyage()
            st.rerun()
    elif st.button("Réappliquer le nettoyage"):
        reconstruire()
        st.rerun()

chemin_exemple = None
if (fichier is None and st.session_state.df is None
        and st.session_state.brut is None):
    # Le fichier d'essai = Employee.csv embarqué dans le projet (identique
    # en local et sur Streamlit Cloud), sinon celui du Bureau, sinon
    # l'exemple des ventes.
    bureau = os.path.join(os.path.expanduser("~"), "Desktop")
    candidats = ["Employee.csv", os.path.join(bureau, "Employee.csv"),
                 "ventes_exemple.csv"]
    chemin_exemple = next((c for c in candidats if os.path.exists(c)), None)
if (chemin_exemple is not None and fichier is None
        and st.session_state.df is None and st.session_state.brut is None
        and st.button("Essayer avec un fichier d'exemple")):
    nom_exemple = os.path.basename(chemin_exemple)
    try:
        with open(chemin_exemple, "rb") as f:
            contenu_ex = f.read()
        st.session_state.brut = lire_csv(contenu_ex, nom_exemple)
        st.session_state.identifiant = (nom_exemple, len(contenu_ex))
        st.session_state.nom = nom_exemple
        st.session_state.df = None
        st.rerun()
    except Exception:
        st.error("Impossible de charger le fichier d'exemple.")

if st.session_state.brut is not None and st.session_state.df is None:
    reconstruire()
    st.rerun()

if st.session_state.df is None:
    st.info("Envoie un fichier CSV pour commencer : les agents le nettoient, "
            "le scannent, puis répondent à tes questions. Parcours : "
            "1) Aperçu · 2) Anomalies · 3) Valeurs aberrantes · "
            "4) Questions · 5) Rapport.")

if st.session_state.df is not None:
    df = st.session_state.df
    r = st.session_state.resume or {}
    net = st.session_state.nettoyage or {}
    st.caption(f"Version analysée : {st.session_state.version}.")
    st.markdown(ui_anim.pipeline_fichier(
        st.session_state.brut, st.session_state.profil,
        st.session_state.nettoyage, st.session_state.scan_res,
        st.session_state.cible, st.session_state.historique,
        st.session_state.get("rapport_cache"), df),
        unsafe_allow_html=True)

    brut_q = st.session_state.brut
    score_avant = profiler.score_qualite(brut_q if brut_q is not None else df)["score"]
    n_anomalies = len((st.session_state.scan_res or {}).get("observations", []))
    components.html(ui_anim.bandeau_chiffres(
        len(df), len(df.columns), int(df.isna().sum().sum()), n_anomalies,
        score_avant, profiler.score_qualite(df)["score"]), height=180)

    if net.get("rapport"):
        avant = net.get("avant", {})
        if avant.get("lignes", len(df)) != len(df):
            raison = "doublons exacts supprimés"
        elif avant.get("manquantes", 0) != int(df.isna().sum().sum()):
            raison = "valeurs manquantes réparées"
        else:
            raison = "aucune modification"
        st.success(f"{avant.get('lignes', len(df))} lignes avant, {len(df)} lignes après "
                   f"(raison : {raison}).")

    if st.session_state.journal:
        with st.expander("Journal du nettoyage"):
            for ligne in st.session_state.journal:
                st.write("- " + ligne)
            details = st.session_state.get("journal_details") or []
            if details:
                st.write("**Détail par transformation** :")
                st.dataframe(pd.DataFrame([{
                    "Colonne": d.get("colonne") or "—",
                    "Action": d.get("action"),
                    "Lignes": (d.get("lignes") if d.get("lignes") is not None
                               else "—"),
                    "Justification": d.get("justification")} for d in details]))
    if st.session_state.get("script_nettoyage"):
        st.download_button("Télécharger le script reproductible (.py)",
                           st.session_state.script_nettoyage.encode("utf-8"),
                           "script_nettoyage.py", "text/x-python")

    with st.expander("Hypothèses et limites"):
        for h in st.session_state.hypotheses:
            st.write("- " + h)

    st.subheader("1 · Aperçu des données")
    st.dataframe(df.head(st.session_state.get("lignes_apercu", 5)))
    st.dataframe(pd.DataFrame({
        "Colonne": list(df.columns),
        "Type": [str(t) for t in df.dtypes],
        "Manquantes": [int(df[c].isna().sum()) for c in df.columns]}))

    st.subheader("2 · Ce que les agents ont remarqué")
    scan_res = st.session_state.scan_res
    if scan_res:
        st.info(f"Taux global de {scan_res['cible']} : {pct(scan_res['taux_global'])} "
                f"(n={scan_res['n']}).")
        obs = scan_res["observations"]
        for o in obs[:8]:
            st.write("- " + o["phrase"])
        if len(obs) > 8:
            with st.expander(f"Voir les {len(obs) - 8} autres observations"):
                for o in obs[8:]:
                    st.write("- " + o["phrase"])
    elif r.get("points_cles"):
        for point in r["points_cles"]:
            st.write("- " + point)

    st.subheader("3 · Valeurs aberrantes")
    nums_ab = list(df.select_dtypes(include="number").columns)
    if not nums_ab:
        st.info("Pas de colonne numérique : impossible de chercher des valeurs aberrantes.")
    else:
        libelles_ab = {anomalies.METHODE_COMBINEE: anomalies.LIBELLE_COMBINEE,
                       **points_aberrants.LIBELLES}
        col_ab, met_ab = st.columns(2)
        col_ab.selectbox("Colonne à examiner", nums_ab, key="ab_colonne")
        met_ab.radio("Méthode de détection", list(libelles_ab),
                     format_func=lambda k: libelles_ab[k],
                     key="ab_methode")
        if st.button("Détecter les valeurs aberrantes"):
            with st.spinner("Détection en cours…"):
                col = st.session_state.ab_colonne
                met = st.session_state.ab_methode
                if met == anomalies.METHODE_COMBINEE:
                    det = anomalies.resumer(df, col)
                else:
                    det = points_aberrants.analyser(df, col, met)
                    det["index"] = list(
                        df.index[points_aberrants.detecter(df[col], met)])
                det["colonne"], det["methode"] = col, met
                st.session_state.det_aberrantes = det
        det = st.session_state.det_aberrantes
        if det:
            st.write(det["explication"])
            if len(det["tableau"]):
                st.dataframe(det["tableau"].head(50))
            if det["figure"]:
                st.image(det["figure"], width=640)
                st.download_button("Télécharger le graphique", det["figure"],
                                   "aberrantes.png", "image/png")
            if det.get("n", 0) > 0 and det.get("colonne") in df.columns:
                st.radio("Que faire de ces valeurs ?",
                         ["garder", "corriger", "supprimer"],
                         format_func=lambda k: {
                             "garder": "Garder (les conserver telles quelles)",
                             "corriger": "Corriger (remplacer par la médiane)",
                             "supprimer": "Supprimer (retirer les lignes)"}[k],
                         key="ab_decision")
                if st.button("Appliquer la décision"):
                    _appliquer_decision_aberrantes()

    questions = r.get("questions") or questions_secours(st.session_state.profil)
    if questions:
        st.subheader("4 · Questions suggérées (clique pour lancer)")
        for idx_sug, q in enumerate(questions[:st.session_state.get("nb_sug", 4)]):
            if st.button(q, key=f"sug-{idx_sug}-{q[:20]}"):
                st.session_state.a_poser = q

    st.divider()
    st.subheader("5 · Pose tes questions")
    for idx, echange in enumerate(st.session_state.historique):
        afficher_echange(echange, idx)

    components.html(voix.html_micro(cle="chat"), height=180)
    st.caption("Dictée vocale (français) : dicte, copie la transcription "
               "dans le chat. Le voyant rouge = écoute en cours.")
    question = st.chat_input("Ex : quel est le total par ville ?")
    if question:
        traiter_question(question)
    elif st.session_state.a_poser:
        q = st.session_state.a_poser
        st.session_state.a_poser = None
        traiter_question(q)
        st.rerun()

    st.divider()
    st.subheader("6 · Comparer 2 fichiers")
    st.write("Compare le fichier actuel avec un second fichier (ex : 2025 vs 2026).")
    fichier_b = st.file_uploader("Envoie le second fichier",
                                     type=["csv", "xlsx", "xls"], key="fichier_b")
    if fichier_b is not None and st.button("Lancer la comparaison"):
        try:
            df_b = lire_tableau(fichier_b.getvalue(), fichier_b.name)
        except Exception:
            st.error("Impossible de lire ce second fichier. "
                     "Vérifie que c'est bien un CSV ou un Excel.")
            df_b = None
        if df_b is not None:
            with st.spinner("Comparaison en cours…"):
                comp = comparer.comparer(df, df_b, st.session_state.nom, fichier_b.name)
                try:
                    explication = data_agent.expliquer_comparaison(comp)
                except Exception:
                    explication = "\n".join(comp["phrases"][:10])
            st.write(explication)
            if comp["graphique"]:
                st.image(comp["graphique"], width=640)
                st.download_button("Télécharger le graphique comparatif", comp["graphique"],
                                   "comparaison.png", "image/png")
            with st.expander("Voir le détail chiffré"):
                for ph in comp["phrases"]:
                    st.write("- " + ph)

    st.divider()
    st.subheader("7 · Rapport, tests et prédiction")
    if st.button("Rédiger le résumé exécutif"):
        with st.spinner("Rédaction du résumé…"):
            try:
                st.session_state.resume_exec = data_agent.resumer_executif(
                    df, scan_res, net)
            except Exception:
                st.session_state.resume_exec = data_agent._resume_repli(
                    df, scan_res, net)
    if st.session_state.resume_exec:
        st.write("**Résumé exécutif**")
        for ligne in st.session_state.resume_exec:
            st.write("- " + ligne)
    lignes_resume = (st.session_state.resume_exec
                     or data_agent._resume_repli(df, scan_res, net))
    cle_rapport = (st.session_state.identifiant,
                   st.session_state.get("strategie_appliquee"),
                   st.session_state.get("annule"),
                   tuple(lignes_resume))
    cache = st.session_state.get("rapport_cache")
    if not cache or cache.get("cle") != cle_rapport:
        html = rapport.generer_html(df, st.session_state.cible, scan_res, net,
                                    st.session_state.version,
                                    st.session_state.hypotheses,
                                    resume_exec=lignes_resume)
        obs_pdf = [o["phrase"] for o in (scan_res or {}).get("observations", [])[:8]]
        pdf = export_pdf.generer_pdf(
            "Rapport DataAgent",
            f"Fichier : {net.get('fichier', 'données')} — {len(df)} lignes, "
            f"{len(df.columns)} colonnes. Version analysée : {st.session_state.version}.",
            lignes_resume,
            [("Nettoyage effectué", st.session_state.journal or ["Aucun."]),
             ("Anomalies détectées", obs_pdf or ["Aucune anomalie marquée détectée."]),
             ("Hypothèses et limites", st.session_state.hypotheses or ["Aucune."])],
            rapport.graphiques_png(df, st.session_state.cible))
        st.session_state.rapport_cache = {"cle": cle_rapport, "html": html, "pdf": pdf}
        cache = st.session_state.rapport_cache
    chtml, cpdf = st.columns(2)
    chtml.download_button("Générer le rapport (HTML)", cache["html"].encode("utf-8"),
                          "rapport.html", "text/html")
    cpdf.download_button("Générer le rapport (PDF)", cache["pdf"],
                         "rapport.pdf", "application/pdf")

    if st.session_state.cible and st.button("Qui risque de partir ?"):
        with st.spinner("Entraînement du modèle…"):
            try:
                st.session_state.pred = prediction.entrainer(df, st.session_state.cible)
            except Exception:
                st.error("Le modèle n'a pas pu être entraîné sur ces données.")
                st.session_state.pred = None
    pred = st.session_state.pred
    if pred:
        st.metric("Score moyen (validation croisée)",
                  f"{pred['score'] * 100:.1f} %")
        st.caption(f"Détail des 3 plis : "
                   f"{', '.join(f'{v * 100:.1f} %' for v in pred['scores'])} — "
                   f"n={pred['n']}, {pct(pred['taux_positifs'])} de départs.")
        st.dataframe(pd.DataFrame(pred["importances"],
                                  columns=["Variable", "Coefficient"]).head(10))
        st.warning(prediction.LIMITES)

    if st.button("Lancer les tests"):
        st.caption("Les tests posent des questions à l'agent : cela prend quelques minutes "
                   "et consomme des crédits API. Valeurs attendues : Employee.csv dédoublonné.")
        try:
            with open("tests.json", encoding="utf-8") as f:
                tests = json.load(f)
        except Exception:
            st.error("Fichier tests.json introuvable.")
            tests = []
        resultats = []
        with st.status("Tests en cours…", expanded=True) as statut:
            for i, t in enumerate(tests):
                statut.write(f"Test {i + 1}/{len(tests)} : {t['question'][:60]}…")
                try:
                    rep = data_agent.analyser_question(
                        st.session_state.df, st.session_state.profil,
                        t["question"], [])
                    ok = verifier_test(t, rep["reponse"])
                except Exception:
                    ok = False
                resultats.append({"question": t["question"], "ok": ok})
            statut.update(label="Tests terminés !", state="complete")
        st.session_state.tests_res = resultats
    if st.session_state.tests_res:
        score = sum(1 for t in st.session_state.tests_res if t["ok"])
        st.subheader(f"Score : {score}/{len(st.session_state.tests_res)} correct")
        for t in st.session_state.tests_res:
            st.write(("✅ " if t["ok"] else "❌ ") + t["question"])

    st.divider()
    st.subheader("8 · Tests statistiques")
    st.write("Le module choisit le bon test selon tes colonnes, vérifie "
             "les hypothèses et explique la p-value simplement.")
    cst1, cst2 = st.columns(2)
    cst1.selectbox("Colonne 1", list(df.columns), key="st_col1")
    cst2.selectbox("Colonne 2 (optionnelle)", ["—"] + list(df.columns),
                   key="st_col2")
    st.selectbox("Test", list(stats_tests.TESTS),
                 format_func=lambda k: stats_tests.TESTS[k], key="st_test")
    if st.button("Lancer le test statistique"):
        col2 = (None if st.session_state.st_col2 == "—"
                else st.session_state.st_col2)
        st.session_state.stat_res = stats_tests.lancer(
            df, st.session_state.st_test, st.session_state.st_col1, col2)
    sres = st.session_state.get("stat_res")
    if sres:
        if not sres.get("ok"):
            st.warning(sres.get("erreur") or "Test impossible.")
        else:
            st.write("**" + sres["libelle"] + f"** (n={sres['n']})")
            m1, m2, m3 = st.columns(3)
            m1.metric("Statistique", f"{sres['statistique']:.3f}")
            m2.metric("p-value", "p < 0,001" if sres["p"] < 0.001
                      else f"{sres['p']:.3f}".replace(".", ","))
            m3.metric(sres["effet_nom"], f"{sres['effet']:.2f}")
            st.write(sres["explication"])
            for h in sres.get("hypotheses") or []:
                st.caption("- " + h)
            for d in sres.get("details") or []:
                st.caption("- " + d)

    st.divider()
    st.subheader("9 · Visualisations")
    st.write("Choisis X (et Y en option) : le graphique adapté s'affiche "
             "avec sa phrase d'insight.")
    cvx, cvy = st.columns(2)
    cvx.selectbox("Axe X", list(df.columns), key="viz_x")
    cvy.selectbox("Axe Y (optionnel)", ["—"] + list(df.columns), key="viz_y")
    st.selectbox("Type de graphique", list(viz.LIBELLES),
                 format_func=lambda k: viz.LIBELLES[k], key="viz_kind")
    try:
        vx = st.session_state.get("viz_x")
        vy = st.session_state.get("viz_y")
        force = (None if st.session_state.get("viz_kind", "auto") == "auto"
                 else st.session_state.get("viz_kind"))
        choix_viz = viz.choisir(df, vx, None if vy == "—" else vy, force)
        st.plotly_chart(viz.construire(df, choix_viz["kind"],
                                       choix_viz["col_x"], choix_viz["col_y"]),
                        use_container_width=True)
        st.write(viz.insight(df, choix_viz["kind"],
                             choix_viz["col_x"], choix_viz["col_y"]))
        st.caption("Choix auto : " + choix_viz["raison"] + ".")
    except Exception as e:
        st.warning(f"Graphique impossible : {e}.")

    st.divider()
    st.subheader("10 · Séries temporelles")
    dates_sr = series.colonnes_dates(df)
    nums_sr = list(df.select_dtypes(include="number").columns)
    if not dates_sr:
        st.info("Aucune colonne de dates détectée : impossible d'analyser "
                "une série temporelle.")
    elif not nums_sr:
        st.info("Aucune colonne de nombres à prévoir.")
    else:
        csd, csv_ = st.columns(2)
        csd.selectbox("Colonne de dates", dates_sr, key="sr_date")
        csv_.selectbox("Valeur à prévoir", nums_sr, key="sr_val")
        st.slider("Horizon de prévision", 3, 30, 7, key="sr_horizon")
        if st.button("Analyser la série"):
            st.session_state.serie_res = series.analyser(
                df, st.session_state.sr_date, st.session_state.sr_val,
                st.session_state.sr_horizon)
        sr = st.session_state.get("serie_res")
        if sr:
            if not sr.get("ok"):
                st.warning(sr.get("erreur") or "Analyse impossible.")
            else:
                t1, t2, t3 = st.columns(3)
                t1.metric("Tendance", sr["tendance"]["direction"])
                t2.metric("Saisonnalité",
                          f"cycle {sr['saison']['periode']}"
                          if sr["saison"] else "non détectée")
                t3.metric("Méthode", sr["methode"])
                st.plotly_chart(sr["figure"], use_container_width=True)
                st.write(sr["explication"])

    if st.session_state.historique:
        st.divider()
        discussion = "# Rapport DataAgent\n\n"
        for e in st.session_state.historique:
            discussion += f"## {e['question']}\n\n{e['reponse']}\n\n"
        st.download_button("Télécharger la discussion", discussion.encode("utf-8"),
                           "discussion.md", "text/markdown")
    if st.button("Tout recommencer"):
        for cle in ["identifiant", "nom", "brut", "df", "profil", "resume",
                    "nettoyage", "version", "cible", "scan_res", "a_poser",
                    "pred", "tests_res", "stat_res", "serie_res",
                    "dedup_applique",
                    "base_nettoyee",
                    "strategie_appliquee", "det_aberrantes", "resume_exec",
                    "rapport_cache", "csv_cache"]:
            st.session_state[cle] = None
        st.session_state.identifiant = None
        st.session_state.nom = ""
        st.session_state.ambigues = []
        st.session_state.journal = []
        st.session_state.journal_details = []
        st.session_state.script_nettoyage = None
        st.session_state.annule = False
        st.session_state.hypotheses = []
        st.session_state.historique = []
        st.rerun()
    st.divider()
    st.caption("DataAgent — propulsé par Muse Spark via l'API Meta.")
