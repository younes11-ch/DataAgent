# DataAgent : moteur multi-agents qui analyse des fichiers CSV.
# Agent 0 (Nettoyeur) : répare les données sales à l'envoi du fichier.
# Agent 1 (Planificateur) : découpe la question en plan d'analyse.
# Agent 2 (Codeur) : écrit du code Python (pandas) et se corrige en cas d'erreur.
# Agent 3 (Vérificateur) : exécute en sous-processus, contrôle les chiffres (R1/R2).
# Agent 4 (Rédacteur) : transforme les sorties brutes en réponse claire.

import io
import json
import math
import os
import pickle
import re
import subprocess
import sys
import tempfile
import unicodedata
from contextlib import redirect_stdout  # noqa: F401 (gardé pour compatibilité)

from dotenv import load_dotenv

load_dotenv()

from openai import OpenAI

client = OpenAI(
    base_url=os.getenv("META_BASE_URL", "https://api.meta.ai/v1"),
    api_key=os.getenv("MODEL_API_KEY", ""),
    timeout=120.0,
)
CHAT_MODEL = os.getenv("MUSE_CHAT_MODEL", "muse-spark-1.3")


def _lire_cle():
    """Lit la clé API : variable d'environnement, sinon secrets Streamlit."""
    cle = os.getenv("MODEL_API_KEY", "")
    if cle:
        return cle
    try:
        import streamlit as st
        return str(st.secrets.get("MODEL_API_KEY", "") or "")
    except Exception:
        return ""


def cle_api_disponible():
    """Vrai si une clé API est configurée (env ou secrets Streamlit)."""
    return bool(_lire_cle())

# Sécurité : le code généré par l'IA ne doit jamais contenir ces motifs.
BLOQUES = ["import ", "open(", "os.", "sys.", "subprocess", "socket",
           "__", "eval(", "exec(", "compile("]

# Vocabulaire causal interdit (R4) : les données montrent des associations.
MOTS_CAUSALS = ["parce que", "à cause de", "a cause de", "causé par",
                "cause par", "provoqué par", "provoque par"]

TIMEOUT_CALCUL = 30  # secondes max pour le code généré (R7)


def _demander(prompt):
    """Un appel à Muse Spark, réponse brute."""
    global client
    cle = _lire_cle()
    if not cle:
        raise RuntimeError("CLE_API_MANQUANTE")
    if not getattr(client, "api_key", ""):
        client = OpenAI(
            base_url=os.getenv("META_BASE_URL", "https://api.meta.ai/v1"),
            api_key=cle,
            timeout=120.0,
        )
    messages = [{"role": "user", "content": prompt}]
    try:
        rep = client.chat.completions.create(
            model=CHAT_MODEL, messages=messages,
            response_format={"type": "json_object"},
        )
    except Exception:
        rep = client.chat.completions.create(model=CHAT_MODEL, messages=messages)
    return rep.choices[0].message.content.strip()


def _extraire_json(texte):
    """Récupère l'objet JSON même si le modèle ajoute du texte autour."""
    debut = texte.find("{")
    fin = texte.rfind("}")
    if debut != -1 and fin > debut:
        texte = texte[debut:fin + 1]
    return json.loads(texte, strict=False)


def _sans_accents(texte):
    return "".join(c for c in unicodedata.normalize("NFD", texte)
                   if unicodedata.category(c) != "Mn").lower()


def _est_texte(serie):
    """Vrai pour les colonnes texte (object ou str selon la version de pandas)."""
    import pandas as pd
    return (pd.api.types.is_object_dtype(serie.dtype)
            or pd.api.types.is_string_dtype(serie.dtype))


def _colonnes_ambigues(df):
    """Colonnes dont le sens n'est pas évident (codes, tiers, niveaux...) (R3)."""
    motifs = ["tier", "niveau", "level", "code", "type", "categorie",
              "classe", "statut", "status", "grade", "segment", "tranche"]
    amb = []
    for col in df.columns:
        nom = _sans_accents(str(col))
        if any(m in nom for m in motifs):
            amb.append(str(col))
    return amb


def profile_data(df, nom_fichier="donnees.csv"):
    """Décrit le fichier avec pandas (local, gratuit, instantané)."""
    profil = {
        "fichier": nom_fichier,
        "lignes": len(df),
        "colonnes": list(df.columns),
        "ambigues": _colonnes_ambigues(df),
    }
    detail = []
    for col in df.columns:
        s = df[col]
        detail.append({
            "nom": str(col),
            "type": str(s.dtype),
            "manquantes": int(s.isna().sum()),
            "exemples": [str(x) for x in s.dropna().head(3)],
        })
    profil["detail"] = detail
    nombres = df.select_dtypes(include="number")
    if not nombres.empty:
        profil["stats"] = nombres.describe().round(2).to_dict()
    for col in [c for c in df.columns if _est_texte(df[c])][:6]:
        top = df[col].value_counts().head(5)
        profil.setdefault("top_valeurs", {})[str(col)] = {
            str(k): int(v) for k, v in top.items()
        }
    return profil


def resumer_donnees(profil):
    """Muse Spark résume le fichier, propose des questions, signale les ambiguïtés."""
    prompt = (
        "Tu es un expert data science. Voici le profil d'un fichier CSV :\n"
        + json.dumps(profil, ensure_ascii=False)[:4000]
        + '\nRéponds UNIQUEMENT avec un objet JSON : {"resume": '
          '"2 phrases en français qui présentent ces données SANS citer de chiffre précis '
          '(tu n\'as que des extraits, pas les vrais calculs)", '
          '"points_cles": ["3 observations prudentes en français, sans chiffre inventé"], '
          '"questions": ["4 questions d\'analyse pertinentes en français"], '
          '"colonnes_ambigues": ["noms des colonnes dont le sens (codes, tiers, niveaux) '
          'n\'est pas défini dans le fichier"]}'
    )
    return _extraire_json(_demander(prompt))


def nettoyer_donnees(df, profil, supprimer_doublons=True):
    """Agent 0 : le Nettoyeur répare les données sales (si besoin)."""
    resultat = {"df_clean": df.copy(), "rapport": [], "code": "",
                "nettoye": False,
                "doublons": {"n": int(df.duplicated().sum()),
                             "pct": round(float(df.duplicated().mean() * 100), 1)}}
    try:
        manq = int(df.isna().sum().sum())
        doublons = int(df.duplicated().sum())
        problemes = []
        if manq:
            problemes.append(f"{manq} valeurs manquantes")
        if doublons and supprimer_doublons:
            problemes.append(f"{doublons} lignes en double")
        for col in [c for c in df.columns if _est_texte(df[c])]:
            s = df[col].dropna().astype(str)
            if len(s) and (s != s.str.strip()).any():
                problemes.append("espaces en trop dans les textes")
                break
        if not problemes:
            resultat["rapport"] = ["Données déjà propres : rien à nettoyer."]
            return resultat
        regle_doublons = ("supprimer les doublons avec drop_duplicates"
                          if supprimer_doublons else
                          "CONSERVER les doublons tels quels (choix de l'utilisateur), "
                          "ne jamais appeler drop_duplicates")
        base_prompt = (
            "Tu es le Nettoyeur d'une équipe data science. Ce fichier CSV a des problèmes : "
            + ", ".join(problemes) + ".\nColonnes : "
            + json.dumps(profil["detail"], ensure_ascii=False)[:2000]
            + "\nRègles : utilise le DataFrame `df` déjà chargé. "
              "Objets disponibles : df, pd, plt, np. "
              "INTERDIT : import, open, lecture de fichiers, appels réseau. "
              "Produis `df_clean` (copie nettoyée) et `rapport` "
              "(liste de phrases en français, chacune avec des chiffres : ce qui a été fait). "
              f"Ordre obligatoire : 1) {regle_doublons}, "
              "2) retirer les espaces dans les textes avec str.strip, "
              "3) convertir les colonnes qui ressemblent à des nombres : "
              "enlever espaces et apostrophes puis pd.to_numeric(..., errors='coerce'), "
              "4) remplir les nombres manquants par la médiane et les textes par le mode. "
              "Ne calcule JAMAIS médiane ou moyenne avant l'étape 3. "
              "Ne supprime jamais une colonne sauf si plus de 80 % vide."
            + '\nRéponds UNIQUEMENT avec un objet JSON : {"code": "le code Python concis", '
              '"explication": "1 phrase en français"}'
        )
        erreur = None
        for _ in range(2):
            prompt = base_prompt
            if erreur:
                prompt += f"\nTon code précédent a échoué : {erreur}\nCorrige-le."
            try:
                resultat["code"] = _extraire_json(_demander(prompt)).get("code", "")
            except Exception as e:
                erreur = f"réponse illisible ({type(e).__name__})"
                continue
            run = executer(df, resultat["code"])
            if run["ok"] and run["df_clean"] is not None and len(run["df_clean"]):
                manq_apres = int(run["df_clean"].isna().sum().sum())
                dup_apres = int(run["df_clean"].duplicated().sum())
                progres = (manq_apres < manq
                           or (supprimer_doublons and dup_apres < doublons))
                rien_a_faire = (manq == 0 and (doublons == 0 or not supprimer_doublons))
                if not (progres or rien_a_faire):
                    erreur = (f"nettoyage incomplet (manquantes {manq}->{manq_apres}, "
                              f"doublons {doublons}->{dup_apres})")
                    continue
                resultat["df_clean"] = run["df_clean"]
                brut_rapport = run["rapport"] or []
                if isinstance(brut_rapport, str):
                    brut_rapport = [brut_rapport]
                resultat["rapport"] = [str(x) for x in brut_rapport]
                if not resultat["rapport"]:
                    resultat["rapport"] = ["Nettoyage effectué."]
                resultat["nettoye"] = True
                return resultat
            erreur = run["erreur"] or "df_clean vide ou absent"
        resultat["rapport"] = [f"Nettoyage automatique impossible ({erreur}), "
                               "on garde les données d'origine."]
    except Exception:
        resultat["rapport"] = ["Nettoyage automatique impossible, "
                               "on garde les données d'origine."]
    return resultat


def planifier(question, profil):
    """Agent 1 : le Planificateur découpe la question en plan."""
    prompt = (
        "Tu es le Planificateur d'une équipe data science. Question du client : "
        + question
        + "\nColonnes disponibles : " + ", ".join(profil["colonnes"])
        + '\nRéponds UNIQUEMENT avec un objet JSON : {"plan": '
          '"plan en 1-2 phrases en français : quelles colonnes, quel calcul, quel graphique si utile"}'
    )
    return _extraire_json(_demander(prompt)).get("plan", "")


def coder(question, plan, profil, historique, erreur=None, graphique="auto"):
    """Agent 2 : le Codeur écrit du code pandas (ou se corrige)."""
    morceaux = []
    for h in historique[-3:]:
        m = f"- Q: {h['question']} / R: {h['reponse'][:300]}"
        code_prev = (h.get("agents") or {}).get("code", "")
        if code_prev:
            m += f" / Code précédent: {code_prev[:800]}"
        morceaux.append(m)
    hist = "\n".join(morceaux)
    reprise = ""
    if erreur:
        reprise = (f"\nTon code précédent a échoué avec cette erreur : {erreur}\n"
                   "Corrige-le.")
    amb = profil.get("ambigues", [])
    pref_graph = ""
    if graphique != "auto":
        pref_graph = (f"\nPréférence de l'utilisateur : si un graphique est utile, "
                      f"impose un graphique de type « {graphique} » (un seul). "
                      f"Si aucun graphique n'est utile, n'en fais pas.")
    prompt = (
        "Tu es le Codeur d'une équipe data science. Tu écris du code Python avec pandas.\n"
        f"Question : {question}\nPlan : {plan}\n"
        "Colonnes : " + json.dumps(profil["detail"], ensure_ascii=False)[:2000]
        + (f"\nÉchanges précédents :\n{hist}" if hist else "")
        + reprise + pref_graph
        + "\nRègles strictes : utilise le DataFrame `df` déjà chargé. "
          "Objets disponibles : df, pd, plt, np. "
          "INTERDIT : import, open, lecture de fichiers, appels réseau. "
          "Termine TOUJOURS par `result = ...` (DataFrame, Series, nombre ou texte). "
          "Affiche les chiffres clés avec print(). "
          "Si tu groupes par segments, affiche TOUJOURS l'effectif n de chaque groupe. "
          "Choix du graphique : camembert si parts d'un tout (6 segments max), courbe si évolution dans le temps, barres pour comparer des catégories, heatmap (matshow) si on demande des corrélations. Un seul graphique, titres en français. "
          "Utilise les noms de colonnes EXACTS (respecte la casse). "
          "Ne montre jamais de code d'exemple : uniquement le code final qui tourne."
        + (f"\nColonnes au sens non défini dans le fichier : {amb} — "
           "tu peux les utiliser pour calculer, mais ne jamais interpréter leur signification."
           if amb else "")
        + '\nRéponds UNIQUEMENT avec un objet JSON : {"code": "le code Python complet", '
          '"explication": "1 phrase en français sur ce que fait le code"}'
    )
    return _extraire_json(_demander(prompt))


SCRIPT_ENFANT = r'''
import pickle, io, sys
from contextlib import redirect_stdout
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

entree, sortie = sys.argv[1], sys.argv[2]
charge = pickle.load(open(entree, "rb"))
espace = {"pd": pd, "plt": plt, "np": np, "df": charge["df"]}
buf = io.StringIO()
try:
    with redirect_stdout(buf):
        exec(charge["code"], {"__builtins__": __builtins__}, espace)
    figures = []
    for num in plt.get_fignums():
        b = io.BytesIO()
        plt.figure(num).savefig(b, format="png", bbox_inches="tight")
        figures.append(b.getvalue())
    resultat = {"ok": True, "erreur": "", "log": buf.getvalue(),
                "result": espace.get("result"), "figures": figures,
                "df_clean": espace.get("df_clean"), "rapport": espace.get("rapport")}
except Exception as e:
    resultat = {"ok": False, "erreur": f"{type(e).__name__}: {e}", "log": buf.getvalue()}
pickle.dump(resultat, open(sortie, "wb"))
'''


def executer(df, code):
    """Exécute le code de l'IA dans un sous-processus avec timeout (R7)."""
    echec = {"ok": False, "erreur": "", "log": "", "result": None,
             "figures": [], "df_clean": None, "rapport": None}
    for motif in BLOQUES:
        if motif in code:
            echec["erreur"] = f"motif interdit détecté : {motif}"
            return echec
    with tempfile.TemporaryDirectory() as tmp:
        entree = os.path.join(tmp, "in.pkl")
        sortie = os.path.join(tmp, "out.pkl")
        script = os.path.join(tmp, "run.py")
        with open(entree, "wb") as f:
            pickle.dump({"df": df, "code": code}, f)
        with open(script, "w", encoding="utf-8") as f:
            f.write(SCRIPT_ENFANT)
        try:
            proc = subprocess.run(
                [sys.executable, script, entree, sortie],
                capture_output=True, text=True, timeout=TIMEOUT_CALCUL)
        except subprocess.TimeoutExpired:
            echec["erreur"] = "TIMEOUT"
            return echec
        if proc.returncode != 0 or not os.path.exists(sortie):
            detail = (proc.stderr or "").strip().splitlines()
            echec["erreur"] = detail[-1][:300] if detail else "échec du sous-processus"
            return echec
        with open(sortie, "rb") as f:
            run = pickle.load(f)
    for cle in ("log", "result", "figures", "df_clean", "rapport"):
        run.setdefault(cle, None if cle in ("result", "df_clean", "rapport") else ([] if cle == "figures" else ""))
    return run


def traduire_erreur(erreur, profil):
    """Traduit une erreur technique en français clair, sans trace brute (R8)."""
    m = re.search(r"KeyError: '([^']+)'", erreur or "")
    if m:
        return (f"La colonne '{m.group(1)}' n'existe pas. "
                f"Colonnes disponibles : {', '.join(profil['colonnes'])}.")
    if erreur == "TIMEOUT":
        return ("Le calcul a dépassé 30 secondes et a été arrêté. "
                "Essaie une question plus simple.")
    if "motif interdit" in (erreur or ""):
        return "Le code proposé a été bloqué pour sécurité. Reformule ta question."
    return ("L'analyse a échoué. "
            "Essaie de reformuler ta question plus simplement.")


def _formater_resultat(result, lignes=20):
    """Transforme le résultat du code en texte + tableau affichable."""
    import pandas as pd

    if isinstance(result, pd.DataFrame):
        return result.head(lignes).to_string(), result.head(50)
    if isinstance(result, pd.Series):
        return result.head(lignes).to_string(), result.head(50).to_frame()
    if result is None:
        return "", None
    return str(result), None


def extraire_nombres(texte):
    """Extrait les nombres d'un texte (gère '39,4 %', '53 600', '2018')."""
    trouves = []
    for m in re.finditer(r"\d[\d\s\u00a0\u202f\u2009]*[.,]?\d*", texte or ""):
        brut = m.group(0).strip()
        if not brut or not brut[0].isdigit():
            continue
        propre = re.sub(r"[\s\u00a0\u202f\u2009]", "", brut).replace(",", ".")
        try:
            trouves.append((brut, float(propre)))
        except ValueError:
            pass
    return trouves


def _nombres_proches(a, b):
    """Égalité avec tolérance, en gérant la dualité 0,394 / 39,4 %."""
    if math.isclose(a, b, rel_tol=0.02, abs_tol=0.05):
        return True
    if b != 0 and math.isclose(a, b * 100, rel_tol=0.02, abs_tol=0.05):
        return True
    if a != 0 and math.isclose(a * 100, b, rel_tol=0.02, abs_tol=0.05):
        return True
    return False


def verifier_reponse(brouillon, nombres_calcules, question):
    """Agent 3 : le Vérificateur contrôle chiffres (R2) et vocabulaire (R4).

    Rend (ok, problemes). Exempte les nombres déjà présents dans la question
    et les petits entiers (comptes, classements).
    """
    problemes = []
    autorises = [v for _, v in extraire_nombres(question)]
    for brut, valeur in extraire_nombres(brouillon):
        if valeur.is_integer() and abs(valeur) <= 31:
            continue
        if any(math.isclose(valeur, a, rel_tol=1e-9) for a in autorises):
            continue
        if not any(_nombres_proches(valeur, c) for _, c in nombres_calcules):
            problemes.append(f"chiffre non vérifié : {brut}")
    texte_plat = _sans_accents(brouillon)
    for mot in MOTS_CAUSALS:
        if _sans_accents(mot) in texte_plat:
            problemes.append(f"vocabulaire causal interdit : « {mot} » "
                             "(corrélation, pas cause)")
            break
    return (len(problemes) == 0, problemes)


def rediger_reponse(question, plan, log, texte_resultat, a_tableau, a_figures,
                    ambigues, correction=None, detail="normale"):
    """Agent 4 : le Rédacteur écrit une réponse claire (jamais de sortie brute)."""
    longueurs = {"concise": "2 à 4 lignes",
                 "normale": "3 à 8 lignes",
                 "detaillee": "8 à 15 lignes avec des petites sections"}
    longueur = longueurs.get(detail, longueurs["normale"])
    brut = (log.strip() + "\n" + texte_resultat.strip()).strip()[:2500]
    prompt = (
        "Tu es le Rédacteur d'une équipe data science. "
        "Question du client : " + question
        + "\nPlan suivi : " + plan
        + "\nSorties du code (calculs pandas EXACTS, seule source de vérité) :\n" + brut
        + ("\nUn tableau détaillé est affiché à part." if a_tableau else "")
        + ("\nUn graphique est affiché à part." if a_figures else "")
        + "\nRÈGLE ABSOLUE : chaque nombre que tu cites DOIT venir des sorties ci-dessus "
          "(un pourcentage peut être déduit : 0,394 → 39,4 %). "
          "N'invente JAMAIS aucun chiffre. Si une info chiffrée manque, "
          "écris « non calculé » plutôt que d'estimer."
        + (f"\nColonnes au sens non défini dans le fichier : {ambigues} — "
           "ne jamais interpréter leur signification, écrire « sens non défini »."
           if ambigues else "")
        + "\nÉcris la réponse finale EN FRANÇAIS : phrases courtes, "
          f"chiffres clés avec unités, puces si utile, {longueur}. "
          "INTERDIT : code, 'dtype', 'Name:', copier des tableaux bruts. "
          "INTERDIT : « parce que », « à cause de », « causé par » — "
          "utilise « est associé à », « coïncide avec » (corrélation, pas cause). "
          "Si les sorties sont vides, dis-le simplement."
        + (f"\nCorrection demandée par le Vérificateur : {correction}" if correction else "")
        + '\nRéponds UNIQUEMENT avec un objet JSON : {"reponse": "le texte final"}'
    )
    try:
        return _extraire_json(_demander(prompt)).get("reponse", "")
    except Exception:
        return ""


def _reponse_sens_colonne(question, ambigues):
    """Routeur (R3) : question sur le sens d'une colonne ambiguë -> réponse directe."""
    qn = _sans_accents(question)
    demande_sens = any(m in qn for m in
                       ["sens", "signifi", "veut dire", "definition", "correspond"])
    if not demande_sens:
        return None
    for col in ambigues:
        if _sans_accents(col) in qn or _sans_accents(col).replace(" ", "") in qn.replace(" ", ""):
            return (f"Le fichier ne définit pas le sens de « {col} » : "
                    f"sens non défini dans le fichier. Les valeurs observées sont "
                    f"présentées dans l'aperçu des données, mais je ne peux pas interpréter "
                    f"ce qu'elles signifient. Si tu connais le sens, dis-le-moi et je "
                    f"l'utiliserai pour la suite.")
    return None


def _exemples_questions(profil):
    """2 exemples de questions construits depuis les colonnes (sans API)."""
    nums = [d["nom"] for d in profil.get("detail", [])
            if "int" in d["type"] or "float" in d["type"]]
    cats = [d["nom"] for d in profil.get("detail", []) if d["nom"] not in nums]
    exemples = []
    if nums and cats:
        exemples.append(f"Quel est le total de {nums[0]} par {cats[0]} ?")
    if cats:
        exemples.append(f"Combien de lignes par {cats[0]} ?")
    if not exemples and nums:
        exemples.append(f"Quelles sont les statistiques de {nums[0]} ?")
    return exemples[:2]


def _reponse_meta(question, profil):
    """Routeur : salutations et questions générales -> réponse directe, sans calcul.

    Rend la réponse directe, ou None si c'est une vraie question d'analyse
    (nom de colonne ou mot d'analyse détecté : on laisse le pipeline travailler).
    """
    compact = re.sub(r"[^a-z ]", " ", _sans_accents(question or ""))
    compact = re.sub(r"\s+", " ", compact).strip()
    for col in profil.get("colonnes", []):
        nom = re.sub(r"\s+", " ", _sans_accents(str(col))).strip()
        if nom and nom in compact:
            return None
    analyse = ["total", "moyenne", "somme", "graphique", "graphe", "histogramme",
               "camembert", "courbe", "heatmap", "taux", "pourcent", "combien",
               "maximum", "minimum", "evolution", "tendance", "correlation",
               "comparer", "comparaison", "predi", "mediane", "ecart",
               "distribution", "grouper", "trier", "statistique", "anomalie",
               "doublon", "nettoy", "quel est", "quelle est", "quels sont",
               "nombre de", "repartition"]
    if any(m in compact for m in analyse):
        return None
    salutations = {"bonjour", "salut", "hello", "bonsoir", "coucou", "cc", "yo",
                   "merci", "merci beaucoup", "au revoir", "a plus", "bye", "ok",
                   "d accord", "svp", "s il te plait", "s il vous plait"}
    aide = ["comment tu", "tu peu", "tu peux", "tu peut", "que peux", "que sais",
            "aide", "aidier", "help", "tu fais", "tu sers", "qui es", "qui etes",
            "comment ca marche", "comment fonctionne", "c est quoi",
            "par ou commencer", "quoi faire", "tu connais", "tu es capable",
            "tu sais faire"]
    if compact in salutations:
        bonjour = True
    elif any(m in compact for m in aide):
        bonjour = False
    else:
        return None
    ap = ", ".join(str(c) for c in profil.get("colonnes", [])[:6])
    exemples = _exemples_questions(profil)
    intro = "Bonjour ! " if bonjour else ""
    return (f"{intro}Je suis DataAgent : j'analyse ton fichier "
            f"« {profil.get('fichier', 'donnees.csv')} » "
            f"({profil.get('lignes', '?')} lignes, colonnes : {ap}).\n\n"
            "Je peux : calculer des totaux et moyennes, comparer des groupes, "
            "faire des tableaux et des graphiques, et signaler les anomalies. "
            "Chaque chiffre que je cite est recalculé et vérifié.\n\n"
            "Pose-moi une question sur tes données, par exemple :\n" +
            "\n".join(f"- {e}" for e in exemples))


def reponse_hors_ligne(df, profil, question):
    """Réponse locale sans IA (mode démo quand la clé API est absente).

    Calcule un total / une moyenne / une répartition si la question cite
    une colonne, sinon rend des statistiques descriptives. Zéro inventé.
    """
    import pandas as pd  # noqa: F401 (convention du module)

    def _fmt(v):
        if isinstance(v, float) and v.is_integer():
            return str(int(v))
        if isinstance(v, float):
            return f"{v:.2f}"
        return str(v)

    trace = {"tentatives": 0,
             "plan": "Mode démo : calcul local direct, sans IA.",
             "code": "", "log": "",
             "verdict": "OK : réponse locale hors-ligne (aucun appel IA)."}
    note = ("\n\nAstuce : ajoute ta clé API Meta pour poser des questions "
            "libres, obtenir des graphiques et utiliser tous les agents.")
    qn = _sans_accents(question or "")
    cible = None
    for col in profil.get("colonnes", []):
        if _sans_accents(str(col)) and _sans_accents(str(col)) in qn:
            cible = col
            break
    if cible is not None and cible in df.columns:
        serie = df[cible]
        if "moyenne" in qn and pd.api.types.is_numeric_dtype(serie.dtype):
            val = float(serie.mean())
            tableau = pd.DataFrame({"mesure": ["moyenne"],
                                    "colonne": [str(cible)],
                                    "valeur": [round(val, 2)]})
            rep = (f"La moyenne de « {cible} » vaut {_fmt(val)} "
                   f"(calculée sur {int(serie.count())} valeurs).")
            return {"reponse": rep + note, "tableau": tableau,
                    "figures": [], "agents": trace}
        if any(m in qn for m in ["total", "somme"]) \
                and pd.api.types.is_numeric_dtype(serie.dtype):
            val = float(serie.sum())
            tableau = pd.DataFrame({"mesure": ["total"],
                                    "colonne": [str(cible)],
                                    "valeur": [serie.sum()]})
            rep = (f"Le total de « {cible} » vaut {_fmt(val)} "
                   f"(calculé sur {int(serie.count())} valeurs).")
            return {"reponse": rep + note, "tableau": tableau,
                    "figures": [], "agents": trace}
        if any(m in qn for m in ["combien", "nombre", "repartition"]):
            tableau = serie.value_counts().head(10).rename_axis(
                str(cible)).reset_index(name="nombre")
            rep = (f"Voici la répartition de « {cible} » "
                   f"({int(serie.count())} valeurs renseignées).")
            return {"reponse": rep + note, "tableau": tableau,
                    "figures": [], "agents": trace}
    lignes = [f"Fichier « {profil.get('fichier', 'données')} » : "
              f"{len(df)} lignes, {len(df.columns)} colonnes."]
    nums = df.select_dtypes(include="number")
    for col in list(nums.columns)[:3]:
        lignes.append(f"{col} : moyenne {_fmt(float(nums[col].mean()))}, "
                      f"total {_fmt(float(nums[col].sum()))}.")
    for col in [c for c in df.columns if _est_texte(df[c])][:2]:
        top = df[col].value_counts().head(3)
        lignes.append(f"{col} : "
                      + ", ".join(f"{k} ({v})" for k, v in top.items())
                      + ".")
    return {"reponse": "\n".join(lignes) + note, "tableau": None,
            "figures": [], "agents": trace}


def analyser_question(df, profil, question, historique, etape=None,
                      detail="normale", graphique="auto"):
    """Les agents répondent à une question (auto-correction + vérification R2)."""
    def _etape(message):
        if etape:
            etape(message)

    trace = {"tentatives": 0, "plan": "", "code": "", "log": "", "verdict": ""}
    ambigues = profil.get("ambigues", [])

    _etape("Planificateur : je prépare le plan…")
    direct = _reponse_sens_colonne(question, ambigues)
    if direct:
        trace["plan"] = "Question sur le sens d'une colonne ambiguë : réponse directe, sans calcul."
        trace["verdict"] = "OK : réponse directe (R3, aucun chiffre cité)."
        return {"reponse": direct, "tableau": None, "figures": [],
                "agents": trace}
    meta = _reponse_meta(question, profil)
    if meta:
        trace["plan"] = "Question générale (salutation ou aide) : réponse directe, sans calcul."
        trace["verdict"] = "OK : réponse directe (aucun chiffre cité)."
        return {"reponse": meta, "tableau": None, "figures": [],
                "agents": trace}
    if not cle_api_disponible():
        _etape("Mode démo : réponse calculée localement, sans IA…")
        return reponse_hors_ligne(df, profil, question)
    trace["plan"] = planifier(question, profil)
    erreur = None
    for tentative in range(2):
        trace["tentatives"] = tentative + 1
        _etape(f"Codeur : j'écris le code d'analyse (tentative {tentative + 1})…")
        reponse_codeur = coder(question, trace["plan"], profil, historique, erreur,
                                 graphique=graphique)
        trace["code"] = reponse_codeur.get("code", "")
        trace["explication"] = reponse_codeur.get("explication", "")
        _etape("Exécuteur : je lance le calcul en sous-processus…")
        run = executer(df, trace["code"])
        trace["log"] = run["log"]
        if run["erreur"] == "TIMEOUT":
            trace["verdict"] = "Échec : calcul trop long (timeout 30 s)."
            return {"reponse": traduire_erreur("TIMEOUT", profil),
                    "tableau": None, "figures": [], "agents": trace}
        if run["ok"]:
            texte_res, tableau = _formater_resultat(run["result"])
            texte_ref, _ = _formater_resultat(run["result"], lignes=100)
            brut = (run["log"].strip() + "\n" + texte_res).strip()
            if brut or run["figures"]:
                _etape("Rédacteur : je rédige la réponse…")
                nombres_calcules = extraire_nombres(run["log"] + "\n" + texte_ref)
                brouillon = rediger_reponse(
                    question, trace["plan"], run["log"], texte_res,
                    tableau is not None, bool(run["figures"]), ambigues,
                    detail=detail)
                _etape("Vérificateur : je contrôle chaque chiffre…")
                ok, problemes = verifier_reponse(brouillon, nombres_calcules, question)
                for _ in range(2):
                    if ok:
                        break
                    _etape("Vérificateur : correction demandée, je réécris…")
                    autorises = ", ".join(sorted({b for b, _ in nombres_calcules})[:40])
                    brouillon = rediger_reponse(
                        question, trace["plan"], run["log"], texte_res,
                        tableau is not None, bool(run["figures"]), ambigues,
                        correction=("Problèmes : " + "; ".join(problemes)
                                    + f". Nombres calculés autorisés : {autorises}"),
                        detail=detail)
                    ok, problemes = verifier_reponse(brouillon, nombres_calcules, question)
                if not ok:
                    brouillon += ("\n\n⚠ Certains chiffres n'ont pas pu être vérifiés : "
                                  "interprète-les avec prudence.")
                trace["verdict"] = ("OK : code exécuté" + (
                    f" après correction (tentative {tentative + 1})"
                    if tentative > 0 else " du premier coup")
                    + (", réponse vérifiée" if ok else ", réponse partiellement vérifiée"))
                return {"reponse": brouillon or brut, "tableau": tableau,
                        "figures": run["figures"], "agents": trace}
            erreur = "le code a tourné mais n'a rien produit (ni print, ni result, ni graphique)"
        else:
            erreur = run["erreur"]
    trace["verdict"] = "Échec après 2 tentatives."
    return {"reponse": traduire_erreur(erreur or "", profil),
            "tableau": None, "figures": [], "agents": trace}


def expliquer_comparaison(comp):
    """Explique les écarts entre 2 fichiers depuis les chiffres calculés (R1)."""
    base = "\n".join(comp["phrases"][:30])
    prompt = (
        "Tu es le Rédacteur d'une équipe data science. Voici des écarts calculés "
        "en pandas entre 2 fichiers (seule source de vérité) :\n" + base
        + "\nRÈGLE ABSOLUE : chaque nombre cité DOIT venir des lignes ci-dessus. "
          "N'invente JAMAIS aucun chiffre. "
          "INTERDIT : « parce que », « à cause de », « causé par » — "
          "utilise « est associé à », « coïncide avec ». "
          "Écris 4 à 8 lignes EN FRANÇAIS : les 3 écarts les plus importants, "
          "puis 2 pistes à vérifier (pas des certitudes)."
        + '\nRéponds UNIQUEMENT avec un objet JSON : {"reponse": "le texte final"}'
    )
    try:
        brouillon = _extraire_json(_demander(prompt)).get("reponse", "")
    except Exception:
        return base
    nombres = extraire_nombres(base)
    ok, _ = verifier_reponse(brouillon, nombres, "comparer deux fichiers")
    if not ok:
        brouillon += ("\n\n⚠ Certains chiffres n'ont pas pu être vérifiés : "
                      "interprète-les avec prudence.")
    return brouillon or base


def _resume_repli(df, scan_res, nettoyage):
    """Résumé exécutif local, sans IA : 5 lignes 100 % factuelles."""
    import pandas as pd  # noqa: F401 (convention du module)

    lignes = [
        f"Fichier {nettoyage.get('fichier', 'données')} : "
        f"{len(df)} lignes, {len(df.columns)} colonnes analysées.",
    ]
    rapport = nettoyage.get("rapport", [])
    lignes.append(rapport[0] if rapport else "Données déjà propres.")
    if scan_res:
        from scan import pct
        lignes.append(f"Taux global de {scan_res['cible']} : "
                      f"{pct(scan_res['taux_global'])} (n={scan_res['n']}).")
        obs = scan_res.get("observations", [])
        lignes.append(obs[0]["phrase"] if obs else "Aucun écart marqué détecté.")
    else:
        lignes.append("Pas de cible binaire : analyse descriptive uniquement.")
        lignes.append("Pose une question pour explorer les colonnes.")
    lignes.append("Les écarts sont des associations, jamais des causes.")
    return lignes[:5]


def resumer_executif(df, scan_res, nettoyage):
    """Rédige un résumé exécutif de 5 lignes en français.

    L'IA reformule les faits calculés ; si elle échoue ou cite un chiffre
    non vérifié, on rend le résumé local (toujours factuel).
    """
    base = "\n".join(_resume_repli(df, scan_res, nettoyage))
    prompt = (
        "Tu es le Rédacteur d'une équipe data science. Voici des faits calculés "
        "en pandas (seule source de vérité) :\n" + base
        + "\nRÈGLE ABSOLUE : chaque nombre cité DOIT venir des lignes ci-dessus. "
          "N'invente JAMAIS aucun chiffre. "
          "Écris un résumé exécutif EN FRANÇAIS : exactement 5 lignes courtes, "
          "ton professionnel, dernière ligne = prudence (association, pas cause)."
        + '\nRéponds UNIQUEMENT avec un objet JSON : {"resume": ["ligne1", ..., "ligne5"]}'
    )
    try:
        lignes = _extraire_json(_demander(prompt)).get("resume", [])
        lignes = [str(x) for x in lignes][:5]
    except Exception:
        return _resume_repli(df, scan_res, nettoyage)
    if len(lignes) != 5:
        return _resume_repli(df, scan_res, nettoyage)
    nombres = extraire_nombres(base)
    ok, _ = verifier_reponse("\n".join(lignes), nombres, "résumé exécutif")
    if not ok:
        return _resume_repli(df, scan_res, nettoyage)
    return lignes
