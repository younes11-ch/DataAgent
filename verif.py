# Vérification indépendante des chiffres (fonctionnalité 1).
# Règle d'or : le LLM ne calcule jamais, seul le code pandas exécuté fait foi.
# Ce module relance le même code dans le sandbox et compare les nombres.

from __future__ import annotations

import data_agent


def reverifier(df, code: str) -> dict:
    """Relance le code dans un sous-processus isolé, indépendamment du 1er calcul.

    Rend {"ok", "log", "texte", "nombres", "erreur"}.
    "nombres" = liste (brut, valeur) extraite du log + résultat, via extraire_nombres.
    Ne lève jamais : un échec sandbox devient ok=False + message français.
    """
    try:
        run = data_agent.executer(df, code or "")
    except Exception as e:  # garde-fou : la revérification ne doit jamais crasher l'UI
        return {"ok": False, "log": "", "texte": "",
                "nombres": [], "erreur": f"revérification impossible ({type(e).__name__})"}
    if not run.get("ok"):
        return {"ok": False, "log": run.get("log") or "",
                "texte": "", "nombres": [],
                "erreur": run.get("erreur") or "échec du calcul"}
    texte, _tableau = data_agent._formater_resultat(run.get("result"))
    nombres = data_agent.extraire_nombres((run.get("log") or "") + "\n" + (texte or ""))
    return {"ok": True, "log": run.get("log") or "", "texte": texte or "",
            "nombres": nombres, "erreur": ""}


def comparer_nombres(avant: list, apres: list) -> dict:
    """Compare deux listes de nombres (brut, valeur) avec la tolérance du Vérificateur.

    Rend {"identique", "manquants", "details"}.
    "manquants" = valeurs de `avant` introuvables dans `apres` (tolérance _nombres_proches).
    """
    manquants = []
    for brut, val in (avant or []):
        if not any(data_agent._nombres_proches(val, v2) for _, v2 in (apres or [])):
            manquants.append(brut)
    identique = len(manquants) == 0
    details = ("chiffres identiques" if identique
               else f"{len(manquants)} chiffre(s) introuvable(s) au 2e calcul : "
                    + ", ".join(manquants[:5]))
    return {"identique": identique, "manquants": manquants, "details": details}


def formater_verdict(comparaison: dict) -> str:
    """Phrase simple pour l'utilisateur à partir de comparer_nombres()."""
    if comparaison.get("identique"):
        return "✅ Revérifié : le 2e calcul indépendant retrouve les mêmes chiffres."
    return ("⚠ Écart détecté à la revérification : " + comparaison.get("details", "")
            + " — interprète les chiffres avec prudence.")
