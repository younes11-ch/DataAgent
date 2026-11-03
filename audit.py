# Agents d'audit : aucune réponse web n'est affichée avant cet audit.
# Pipeline : principal → sources → logique → sécurité → décideur.
# Tout est déterministe et sans API par défaut ; le LLM n'est utilisé
# qu'en complément quand une clé est configurée (jamais pour inventer).

import re

VERDICTS = ("OK", "À CORRIGER", "REFUSE")
CONFIANCES = ("faible", "moyen", "élevé")

# Motifs de données sensibles / dangereuses (complète _nettoyer_erreur).
SENSIBLE = [
    (r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "adresse e-mail"),
    (r"(?:\+33|0)\s?[1-9](?:[\s.\-_]?\d{2}){4}", "numéro de téléphone"),
    (r"\b\d{2}[\s.\-_]?\d{2}[\s.\-_]?\d{2}[\s.\-_]?\d{2}[\s.\-_]?\d{2}\b",
     "numéro de téléphone"),
    (r"LLM_[A-Za-z0-9_]+", "clé API"),
    (r"\b[A-Za-z0-9_\-]{24,}\b", "secret possible"),
    (r"[A-Za-z]:\\[^\s'\"`]*", "chemin local"),
    (r"/(?:home|Users|tmp|app|etc|var)[^\s'\"`]*", "chemin local"),
    (r"\.env\b", "fichier de secrets"),
    (r"Traceback \(most recent call last\)", "trace technique"),
    (r"\bFR\d{2}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{3}\b", "IBAN"),
    (r"\b[12]\d{2}\s?\d{2}\s?\d{2}\s?\d{3}\s?\d{3}\s?\d{2}\b",
     "numéro de sécurité sociale"),
]

DANGEREUX = [
    (r"import\s+(os|subprocess|socket|sys)\b", "import système"),
    (r"\bsubprocess\b", "sous-processus"),
    (r"\bos\.(system|popen|environ|listdir|remove)\b", "appel système"),
    (r"\brm\s+-rf\b", "commande destructive"),
    (r"DROP\s+TABLE", "ordre SQL destructif"),
    (r"__import__", "import masqué"),
]


def phrases(texte):
    """Découpe une réponse en affirmations (une par phrase)."""
    morceaux = re.split(r"(?<=[.!?])\s+|\n+", (texte or "").strip())
    return [m.strip() for m in morceaux if len(m.strip()) > 3]


def _nombres(texte):
    """Nombres d'un texte (tolère espaces, %, virgules)."""
    trouves = []
    for m in re.finditer(r"\d[\d\s\u00a0\u202f\u2009]*[.,]?\d*", texte or ""):
        brut = m.group(0).strip()
        if not brut or not brut[0].isdigit():
            continue
        try:
            trouves.append(
                (brut, float(re.sub(r"[\s\u00a0\u202f\u2009]", "", brut)
                             .replace(",", "."))))
        except ValueError:
            pass
    return trouves


def _proches(a, b, rel=0.02, abs_tol=0.05):
    import math
    if math.isclose(a, b, rel_tol=rel, abs_tol=abs_tol):
        return True
    if b and math.isclose(a, b * 100, rel_tol=rel, abs_tol=abs_tol):
        return True
    return bool(a and math.isclose(a * 100, b, rel_tol=rel, abs_tol=abs_tol))


def auditer_sources(brouillon, sources, extraits=None, question=""):
    """Agent sources : chaque chiffre important doit être recoupé.

    - Sans aucun chiffre : OK (rien à recouper).
    - Avec chiffres : exige au moins 1 source, et 2 domaines indépendants
      dès qu'un chiffre important est cité (non présent dans la question,
      > 31 pour éviter les comptes).
    - Si des extraits sont fournis, chaque chiffre important doit apparaître
      dans au moins 1 extrait, sinon il est listé comme non recoupé.
    """
    from recherche import domaine  # import local : pas de cycle

    problemes, non_recoupes = [], []
    chiffres = [(b, v) for b, v in _nombres(brouillon)
                if not (v.is_integer() and abs(v) <= 31)
                and not (v.is_integer() and 1900 <= v <= 2100)]
    autorises = {v for _, v in _nombres(question)}
    importants = [(b, v) for b, v in chiffres
                  if not any(abs(v - a) < 1e-9 for a in autorises)]
    if not importants:
        return {"ok": True, "problemes": [], "non_recoupes": []}
    if not sources:
        return {"ok": False,
                "problemes": ["chiffres cités sans aucune source"],
                "non_recoupes": [b for b, _ in importants]}
    distincts = {domaine(s.get("url")) for s in sources if s.get("url")}
    distincts.discard("")
    if len(distincts) < 2:
        problemes.append("chiffres importants adossés à une seule source "
                         "(2 sources indépendantes exigées)")
    if extraits:
        for brut, valeur in importants:
            if not any(_proches(valeur, v)
                       for ext in extraits for _, v in _nombres(ext)):
                non_recoupes.append(brut)
        if non_recoupes:
            problemes.append("chiffres non retrouvés dans les extraits : "
                             + ", ".join(non_recoupes[:5]))
    return {"ok": not problemes, "problemes": problemes,
            "non_recoupes": non_recoupes}


def auditer_logique(brouillon, donnees_calculees=None, question=""):
    """Agent logique : calculs, dates, unités, cohérence interne."""
    problemes = []
    autorises_q = {v for _, v in _nombres(question)}
    calc = {v for _, v in (donnees_calculees or [])}
    for brut, valeur in _nombres(brouillon):
        if valeur.is_integer() and abs(valeur) <= 31:
            continue
        if valeur.is_integer() and 1900 <= valeur <= 2100:
            continue  # années (titres, périodes) : pas des affirmations
        if any(abs(valeur - a) < 1e-9 for a in autorises_q):
            continue
        if calc and not any(_proches(valeur, c) for c in calc):
            problemes.append(f"chiffre non vérifié : {brut}")
    # Dates impossibles les plus courantes.
    for m in re.finditer(r"\b(3[2-9]|[4-9]\d)\s+(janvier|février|mars|avril|mai|"
                         r"juin|juillet|août|septembre|octobre|novembre|"
                         r"décembre)\b", brouillon or "", re.IGNORECASE):
        problemes.append(f"date impossible : {m.group(0)}")
    # Contradiction interne : deux pourcentages dont la somme dépasse 100
    # pour des parts d'un même tout annoncé comme exclusives.
    if re.search(r"parts? (exclusives?|d['’]un même tout)", brouillon or "",
                 re.IGNORECASE):
        pcts = [v if v <= 100 else v / 100 for _, v in _nombres(brouillon)
                if 0 < v <= 10000]
        if sum(pcts) > 100.5:
            problemes.append("parts exclusives dont la somme dépasse 100 %")
    return {"ok": not problemes, "problemes": problemes}


def auditer_securite(brouillon):
    """Agent sécurité : données sensibles et contenu dangereux."""
    problemes = []
    for motif, label in SENSIBLE:
        if re.search(motif, brouillon or ""):
            problemes.append(f"contient {label} : à masquer")
    for motif, label in DANGEREUX:
        if re.search(motif, brouillon or "", re.IGNORECASE):
            problemes.append(f"contenu dangereux ({label}) : à retirer")
    return {"ok": not problemes, "problemes": problemes}


def decider(rap_sources, rap_logique, rap_securite, nb_domaines=0):
    """Agent décideur : verdict + confiance + points non vérifiés."""
    points = (list(rap_sources.get("non_recoupes", []))
              + [p for rap in (rap_sources, rap_logique)
                 for p in rap.get("problemes", [])])
    if not rap_securite.get("ok", True):
        return {"verdict": "REFUSE", "confiance": "faible",
                "problemes": (rap_securite.get("problemes", []) + points),
                "points_non_verifies": points}
    problemes = (rap_sources.get("problemes", [])
                 + rap_logique.get("problemes", []))
    if problemes:
        contradictions = [p for p in problemes
                          if "contredis" in p or "non retrouvés" in p
                          or "non vérifié" in p]
        confiance = "faible" if contradictions else "moyen"
        return {"verdict": "À CORRIGER", "confiance": confiance,
                "problemes": problemes, "points_non_verifies": points}
    confiance = "élevé" if nb_domaines >= 2 else "moyen"
    return {"verdict": "OK", "confiance": confiance, "problemes": [],
            "points_non_verifies": points}


def pipeline_audit(question, fn_principal, sources=None,
                   donnees_calculees=None, extraits=None, max_boucles=3):
    """Fait auditer un brouillon, avec jusqu'à `max_boucles` corrections.

    `fn_principal(problemes_ou_None)` rend le brouillon (str). Ne rend
    jamais que le verdict + le meilleur brouillon : l'appelant décide
    d'afficher ou non (REFUSE → ne pas afficher le brouillon).
    """
    from recherche import domaine  # import local : pas de cycle

    sources = sources or []
    nb_domaines = len({domaine(s.get("url")) for s in sources
                       if s.get("url")} - {""})
    brouillon, problemes, boucles = "", None, 0
    rapports = {}
    while True:
        brouillon = fn_principal(problemes) or ""
        boucles += 1
        rap_s = auditer_sources(brouillon, sources, extraits, question)
        rap_l = auditer_logique(brouillon, donnees_calculees, question)
        rap_sec = auditer_securite(brouillon)
        decision = decider(rap_s, rap_l, rap_sec, nb_domaines)
        rapports = {"sources": rap_s, "logique": rap_l,
                    "securite": rap_sec}
        if decision["verdict"] != "À CORRIGER" or boucles > max_boucles:
            return {"brouillon": brouillon, "verdict": decision["verdict"],
                    "confiance": decision["confiance"],
                    "problemes": decision["problemes"],
                    "points_non_verifies": decision["points_non_verifies"],
                    "sources": sources, "rapports": rapports,
                    "boucles": boucles}
        problemes = decision["problemes"]
