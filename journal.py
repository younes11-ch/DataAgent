# Journal de nettoyage structuré + export d'un script reproductible (fonctionnalité 2).
# Chaque transformation = {"colonne", "action", "lignes", "justification"}.
# Le script exporté rejoue à l'identique : code du Nettoyeur (stocké tel quel,
# déjà exécuté en sandbox) + imputation déterministe (valeurs exactes rejouées).

from __future__ import annotations

import json


def entree(colonne: str = "", action: str = "", lignes=None,
           justification: str = "") -> dict:
    """Fabrique une entrée de journal (lignes=None = non compté, voir phrase)."""
    return {"colonne": str(colonne or ""), "action": str(action or ""),
            "lignes": lignes, "justification": str(justification or "")}


def entrees_nettoyage(nettoyage: dict, doublons_supprimes: bool = True) -> list:
    """Structure le résultat de l'agent Nettoyeur (doublons + phrases du rapport)."""
    nettoyage = nettoyage or {}
    entrees = []
    doublons = nettoyage.get("doublons", {}) or {}
    n_doublons = int(doublons.get("n", 0) or 0)
    if n_doublons:
        entrees.append(entree(
            action=("supprimer_doublons" if doublons_supprimes
                    else "conserver_doublons"),
            lignes=0 if doublons_supprimes else n_doublons,
            justification=(f"{n_doublons} lignes en double exact "
                           f"({'supprimées' if doublons_supprimes else 'conservées, choix utilisateur'})")))
    for phrase in (nettoyage.get("rapport") or []):
        entrees.append(entree(action="nettoyage_auto", lignes=None,
                              justification=str(phrase)))
    if not entrees:
        entrees.append(entree(action="aucun_nettoyage", lignes=0,
                              justification="données déjà propres"))
    return entrees


def _code_texte(valeur) -> str:
    """Rend un littéral Python sûr pour une colonne ou une valeur de remplissage."""
    try:
        return json.dumps(valeur, ensure_ascii=False)
    except (TypeError, ValueError):
        pass
    if hasattr(valeur, "item"):  # scalaire numpy -> type Python natif
        try:
            return json.dumps(valeur.item(), ensure_ascii=False)
        except (TypeError, ValueError):
            pass
    return repr(valeur)  # repli : Timestamp pandas, etc. (pd est importé)


def exporter_script(code_nettoyage: str = "", remplissages: dict | None = None,
                    strategie: str = "auto", nom_fichier: str = "donnees.csv") -> str:
    """Génère un script .py autonome qui rejoue le nettoyage à l'identique.

    Usage : python script_nettoyage.py [fichier_entree.csv] -> donnees_nettoyees.csv.
    Le code du Nettoyeur est repris tel quel (il a déjà tourné en sandbox) ;
    l'imputation est régénérée à partir des valeurs exactes utilisées.
    """
    remplissages = remplissages or {}
    code_nettoyage = (code_nettoyage or "").strip()
    lignes = [
        "# Script reproductible généré par DataAgent : rejoue le nettoyage à l'identique.",
        f"# Fichier d'origine : {nom_fichier} — stratégie d'imputation : {strategie}.",
        "# Usage : python script_nettoyage.py [fichier_entree.csv]",
        "# Sortie : donnees_nettoyees.csv",
        "",
        "import sys",
        "",
        "import pandas as pd",
        "",
        f'ENTREE = sys.argv[1] if len(sys.argv) > 1 else {_code_texte(nom_fichier)}',
        'SORTIE = "donnees_nettoyees.csv"',
        "",
        "# Lecture tolérante (même logique que l'app : virgule, point-virgule, encodages).",
        "df = None",
        'for _sep in (",", ";"):',
        "    try:",
        '        _essai = pd.read_csv(ENTREE, sep=_sep, encoding="utf-8")',
        "        if len(_essai.columns) > 1:",
        "            df = _essai",
        "            break",
        "    except Exception:",
        "        continue",
        "if df is None:",
        '    df = pd.read_csv(ENTREE, encoding="latin-1")',
        "",
    ]
    if code_nettoyage:
        lignes += ["# Étape 1 : nettoyage automatique (code exécuté et vérifié dans l'app).",
                   code_nettoyage, ""]
    else:
        lignes += ["# Étape 1 : aucun nettoyage automatique (données gardées telles quelles).",
                   "df_clean = df.copy()",
                   "rapport = ['Nettoyage automatique impossible, données gardées.']",
                   ""]
    lignes.append("# Étape 2 : imputation choisie par l'utilisateur.")
    if strategie == "supprimer":
        lignes.append("df_clean = df_clean.dropna().reset_index(drop=True)")
    for col, valeur in (remplissages or {}).items():
        lignes.append(f"df_clean[{_code_texte(col)}] = "
                      f"df_clean[{_code_texte(col)}].fillna({_code_texte(valeur)})")
    if strategie != "supprimer" and not remplissages:
        lignes.append("# (rien à remplir : aucune valeur manquante restante)")
    lignes += ["",
               'df_clean.to_csv(SORTIE, index=False)',
               'print(f"{len(df_clean)} lignes, {len(df_clean.columns)} colonnes -> {SORTIE}")',
               ""]
    return "\n".join(lignes)
