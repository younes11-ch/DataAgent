# Recherche de données sans upload : l'agent cherche lui-même sur le web.
# Aucune clé requise (Wikipedia + DuckDuckGo, stdlib uniquement).
# Les tests injectent une `fonction_recherche` factice : aucun réseau en CI.

import html
import io
import json
import re
import time
import urllib.parse
import urllib.request

MOTS_VIDES = {
    "le", "la", "les", "de", "des", "du", "un", "une", "et", "ou", "est",
    "sont", "que", "qui", "quoi", "quel", "quelle", "quels", "quelles",
    "combien", "comment", "pourquoi", "donne", "donnez", "donne-moi",
    "cherche", "chercher", "trouve", "trouver", "quel est", "quelle est",
    "stp", "svp", "sont", "dans", "sur", "avec", "sans", "pour", "par",
    "the", "a", "an", "of", "what", "which", "how", "many", "much",
}

UA = {"User-Agent": "DataAgent/1.0 (hackathon; contact: local)"}

# Portails de données jugés importants : leurs résultats passent en premier.
SITES_IMPORTANTS = (
    "kaggle.com",
    "data.gouv.fr",
    "insee.fr",
    "data.europa.eu",
    "ec.europa.eu",
    "data.gov",
    "worldbank.org",
    "banquemondiale.org",
    "oecd.org",
    "imf.org",
)


def est_important(url):
    """Vrai si l'URL vient d'un portail de données important."""
    try:
        hote = urllib.parse.urlparse(url or "").netloc.lower()
        if hote.startswith("www."):
            hote = hote[4:]
        return any(hote == d or hote.endswith("." + d)
                   for d in SITES_IMPORTANTS)
    except Exception:
        return False


def trier_sources(resultats):
    """Classe les portails importants en premier (tri stable)."""
    propres = [r for r in (resultats or []) if isinstance(r, dict)]
    return sorted(propres,
                  key=lambda r: 0 if est_important(r.get("url")) else 1)


def reformuler_requetes(question, max_requetes=3):
    """Découpe la question en requêtes de recherche (déterministe, sans IA).

    L'agent appelle ça de façon autonome avant de chercher : il reformule
    et croise ensuite plusieurs sources.
    """
    brut = (question or "").strip()
    if not brut:
        return []
    # Découpe sur ponctuation / conjonctions pour des requêtes ciblées.
    morceaux = re.split(r"[?!;]+|\bet\b|\bou\b|\bpuis\b|\bensuite\b", brut,
                        flags=re.IGNORECASE)
    requetes = []
    for morceau in morceaux:
        mots = [m for m in re.findall(r"[\w\-']+", morceau)
                if m.lower() not in MOTS_VIDES and len(m) > 1]
        if len(mots) >= 2:
            requetes.append(" ".join(mots))
        elif morceau.strip() and morceau.strip() not in requetes:
            requetes.append(morceau.strip())
    if brut not in requetes:
        requetes.insert(0, brut)
    return requetes[:max_requetes]


def _nettoyer_html(texte):
    """Enlève les balises d'un extrait (snippets Wikipedia)."""
    propre = re.sub(r"<[^>]+>", " ", texte or "")
    return html.unescape(re.sub(r"\s+", " ", propre)).strip()


LIMITE_REPONSE = 2_000_000  # on ne bufferise jamais plus de 2 Mo
LIMITE_FICHIER = 20_000_000  # jeu de données max chargeable (20 Mo)


def lire_contenu(contenu, nom="", format_fichier=""):
    """Lit un CSV ou un Excel (1er onglet) depuis des octets."""
    import pandas as pd

    fmt = ((format_fichier or "").strip().lower()
           or (nom.rsplit(".", 1)[-1].lower() if "." in nom else ""))
    if fmt in ("xls", "xlsx"):
        try:
            return pd.read_excel(io.BytesIO(contenu))
        except ImportError:
            raise ValueError("Lecture Excel indisponible : installe openpyxl "
                             "et xlrd (`uv pip install --python .venv "
                             "openpyxl xlrd`).")
    for enc in ("utf-8", "latin-1"):
        for sep in (",", ";"):
            try:
                df = pd.read_csv(io.BytesIO(contenu), sep=sep, encoding=enc)
                if len(df.columns) > 1:
                    return df
            except Exception:
                continue
    return pd.read_csv(io.BytesIO(contenu), encoding="latin-1")


def telecharger_fichier(url, timeout=20, limite=LIMITE_FICHIER):
    """Télécharge un fichier (http/https uniquement, taille plafonnée)."""
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        raise ValueError("URL de fichier invalide")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as rep:
        morceaux, total = [], 0
        while True:
            bloc = rep.read(65536)
            if not bloc:
                break
            total += len(bloc)
            if total > limite:
                raise ValueError("fichier trop volumineux (max 20 Mo)")
            morceaux.append(bloc)
    return b"".join(morceaux)


def _get_json(url, timeout=10):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as rep:
        brut = rep.read(LIMITE_REPONSE + 1)
        if len(brut) > LIMITE_REPONSE:
            raise ValueError("réponse trop volumineuse")
        return json.loads(brut.decode("utf-8", errors="replace"))


def chercher_wikipedia(requete, max_resultats=3, timeout=10):
    """Cherche sur Wikipédia FR (sans clé). Rend [{nom, url, extrait}]."""
    try:
        params = urllib.parse.urlencode({
            "action": "query", "list": "search", "srsearch": requete,
            "format": "json", "srlimit": max_resultats, "srprop": "snippet",
        })
        donnees = _get_json(
            "https://fr.wikipedia.org/w/api.php?" + params, timeout=timeout)
        resultats = []
        for item in donnees.get("query", {}).get("search", [])[:max_resultats]:
            titre = item.get("title", "")
            resultats.append({
                "nom": f"Wikipédia — {titre}",
                "url": ("https://fr.wikipedia.org/wiki/"
                        + urllib.parse.quote(titre.replace(" ", "_"))),
                "extrait": _nettoyer_html(item.get("snippet", "")),
            })
        return resultats
    except Exception:
        return []


def chercher_duckduckgo(requete, max_resultats=3, timeout=10):
    """Réponse instantanée DuckDuckGo (sans clé). Rend [{nom, url, extrait}]."""
    try:
        params = urllib.parse.urlencode(
            {"q": requete, "format": "json", "no_html": 1, "lang": "fr"})
        donnees = _get_json("https://api.duckduckgo.com/?" + params,
                            timeout=timeout)
        resultats = []
        resume = (donnees.get("AbstractText") or "").strip()
        if resume:
            resultats.append({
                "nom": donnees.get("Heading") or "DuckDuckGo",
                "url": donnees.get("AbstractURL") or "https://duckduckgo.com/",
                "extrait": resume[:500],
            })
        for sujet in donnees.get("RelatedTopics", [])[:max_resultats]:
            texte = (sujet.get("Text") or "").strip()
            url = sujet.get("FirstURL") or ""
            if texte and url:
                resultats.append({
                    "nom": texte.split("—")[0].split("-")[0].strip()[:60]
                    or "DuckDuckGo",
                    "url": url,
                    "extrait": texte[:500],
                })
        return resultats[:max_resultats]
    except Exception:
        return []


FORMATS_FICHIERS = ("csv", "xls", "xlsx", "parquet", "zip", "json")


def _choisir_fichier(resources):
    """Rend (url, format) du meilleur fichier téléchargeable, ou ("", "")."""
    candidates = [r for r in (resources or [])
                  if isinstance(r, dict)
                  and isinstance(r.get("url"), str)
                  and r["url"].startswith(("http://", "https://"))]
    for prefere in FORMATS_FICHIERS:
        for res in candidates:
            if (res.get("format") or "").strip().lower() == prefere:
                return res["url"], prefere
    if candidates:
        return candidates[0]["url"], (candidates[0].get("format") or "").strip().lower()
    return "", ""


def chercher_datagouv(requete, max_resultats=4, timeout=15):
    """Cherche des jeux de données sur data.gouv.fr (API ouverte, sans clé).

    Rend [{nom, url, extrait, fichier, format_fichier}] : l'URL est la
    fiche du jeu, `fichier` le lien direct du meilleur fichier (CSV
    préféré) pour le télécharger sans passer par le site.
    """
    try:
        params = urllib.parse.urlencode(
            {"q": requete, "page_size": max_resultats})
        donnees = _get_json("https://www.data.gouv.fr/api/1/datasets/?"
                            + params, timeout=timeout)
        resultats = []
        for jeu in donnees.get("data", [])[:max_resultats]:
            if not isinstance(jeu, dict):
                continue
            titre = (jeu.get("title") or "").strip()
            if not titre:
                continue
            extrait = ((jeu.get("description_short")
                        or jeu.get("description") or "").strip())
            if not isinstance(extrait, str):
                extrait = ""
            extrait = _nettoyer_html(extrait)[:400]
            n_res = len(jeu.get("resources") or [])
            if n_res == 1:
                extrait += " (1 ressource téléchargeable)"
            elif n_res:
                extrait += f" ({n_res} ressources téléchargeables)"
            fichier, format_fichier = _choisir_fichier(jeu.get("resources"))
            resultats.append({
                "nom": f"data.gouv.fr — {titre}",
                "url": jeu.get("page") or jeu.get("uri") or "",
                "extrait": extrait,
                "fichier": fichier,
                "format_fichier": format_fichier,
            })
        return [r for r in resultats if r["url"]]
    except Exception:
        return []


def chercher_web(requete, max_resultats=5, timeout=15):
    """Cherche sur plusieurs sources et croise (open data + web).

    Les portails importants (Kaggle, data.gouv.fr, Insee…) passent
    en premier dans les résultats. Budget global `timeout` : on arrête
    d'interroger quand il est épuisé au lieu de tronquer chaque source.
    """
    debut = time.monotonic()
    trouves = []
    for interroger in (chercher_datagouv, chercher_wikipedia,
                       chercher_duckduckgo):
        restant = timeout - (time.monotonic() - debut)
        if restant < 2:
            break
        trouves += interroger(requete, max_resultats, min(timeout, restant))
    return trier_sources(dedupliquer(trouves))[:max_resultats]


def domaine(url):
    """Domaine d'une URL (pour juger de l'indépendance des sources)."""
    try:
        hote = urllib.parse.urlparse(url or "").netloc.lower()
        return hote[4:] if hote.startswith("www.") else hote
    except Exception:
        return ""


def dedupliquer(resultats):
    """Enlève les doublons (même URL ou même domaine + même nom)."""
    vus, uniques = set(), []
    for res in resultats or []:
        if not isinstance(res, dict):
            continue
        cle = ((res.get("url") or "").rstrip("/").lower(), domaine(res.get("url")))
        if cle in vus or not res.get("url"):
            continue
        vus.add(cle)
        uniques.append(res)
    return uniques


def domaines_independants(sources, minimum=2):
    """Vrai si au moins `minimum` domaines distincts parmi les sources."""
    distincts = {domaine(s.get("url")) for s in (sources or [])
                 if isinstance(s, dict) and s.get("url")}
    distincts.discard("")
    return len(distincts) >= minimum


def rechercher(question, max_requetes=3, max_par_requete=4,
               fonction_recherche=None, timeout=30):
    """Pipeline de recherche autonome : reformule, cherche, croise.

    `fonction_recherche(requete)` peut être injectée (tests, sources
    connectées) : elle rend une liste [{nom, url, extrait}].
    """
    requetes = reformuler_requetes(question, max_requetes)
    toutes, par_requete = [], {}
    for requete in requetes:
        try:
            if fonction_recherche is not None:
                trouves = fonction_recherche(requete) or []
            else:
                trouves = chercher_web(requete, max_par_requete, timeout)
            trouves = [t for t in (trouves or [])
                       if isinstance(t, dict) and isinstance(t.get("url"), str)]
        except Exception:
            trouves = []
        par_requete[requete] = trouves
        toutes.extend(trouves)
    sources = trier_sources(dedupliquer(toutes))
    return {"requetes": requetes, "sources": sources,
            "par_requete": par_requete}
