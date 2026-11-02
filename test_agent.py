# Test complet de DataAgent : vérifications locales + moteur via l'API Meta.
# Cibles Employee.csv dédoublonné : 2764 lignes, taux 39,4 %, âge 31,0.

import pandas as pd

import comparer
import data_agent
import scan

print("== A. Vérificateur local (sans API) ==")
calc = data_agent.extraire_nombres("total 53600\ntaux 0.394")
assert data_agent.verifier_reponse("Le total est 53 600 DH.", calc, "total ?")[0]
assert data_agent.verifier_reponse("Le taux est 39,4 %.", calc, "taux ?")[0]
assert not data_agent.verifier_reponse("Le total est 99 999 DH.", calc, "total ?")[0]
assert not data_agent.verifier_reponse("Total 53 600 DH parce que ça monte.", calc, "x")[0]
print("   Vérificateur OK (exact, %, invention refusée, causal refusé)")

print("== B. Exécuteur en sous-processus (sans API) ==")
df_mini = pd.DataFrame({"ville": ["a", "b", "a"], "montant": [10, 20, 30]})
run = data_agent.executer(df_mini, "result = df['montant'].sum()\nprint('total:', result)")
assert run["ok"] and run["result"] == 60 and "total: 60" in run["log"], run
bloque = data_agent.executer(df_mini, "import os\nresult = 1")
assert not bloque["ok"] and "interdit" in bloque["erreur"]
print("   Sous-processus OK (calcul + blocage import)")

print("== C. Scan synthétique (sans API) ==")
lignes = []
for i in range(100):
    lignes.append(("Pune", "F", 1 if i < 78 else 0))      # Pune femmes : 78 %
    lignes.append(("Pune", "H", 1 if i < 27 else 0))       # Pune hommes : 27 %
    lignes.append(("Rabat", "F", 1 if i < 30 else 0))      # Rabat : 30 %
    lignes.append(("Rabat", "H", 1 if i < 30 else 0))
syn = pd.DataFrame(lignes, columns=["ville", "sexe", "parti"])
assert scan.detecter_cible(syn) == "parti"
res = scan.scan_anomalies(syn, "parti")
phrases = " | ".join(o["phrase"] for o in res["observations"])
assert scan.pct(res["taux_global"]) in ("41,2 %", "41,3 %")
assert "41,2 %" in phrases or "41,3 %" in phrases, phrases[:300]
assert "78,0 %" in phrases and "27,0 %" in phrases, phrases[:500]
print("   Scan OK (taux global, segment extrême, comparaison)")

print("== D. Scan Employee.csv dédoublonné (sans API) ==")
emp = pd.read_csv("../../Employee.csv").drop_duplicates().reset_index(drop=True)
assert len(emp) == 2764, len(emp)
assert round(emp["Age"].mean(), 1) == 31.0
res_emp = scan.scan_anomalies(emp, "LeaveOrNot")
tout = " | ".join(o["phrase"] for o in res_emp["observations"])
assert scan.pct(res_emp["taux_global"]) == "39,4 %"
for attendu in ["97,9 %", "(n=239)", "77,9 %", "27,2 %", "50,9 %",
                "35,0 %", "34,1 %", "48,5 %", "60,2 %"]:
    assert attendu in tout, f"manquant : {attendu}"
print("   Employee.csv OK (les 6 valeurs attendues retrouvées)")

print("== E. Routeur R3 + erreurs françaises (sans API) ==")
profil = data_agent.profile_data(df_mini, "mini.csv")
profil["ambigues"] = ["PaymentTier"]
rep = data_agent.analyser_question(df_mini, profil, "Que veut dire PaymentTier ?", [])
assert "sens non défini" in rep["reponse"], rep["reponse"][:150]
assert "n'existe pas" in data_agent.traduire_erreur("KeyError: 'salaire'", profil)
print("   Routeur + erreurs OK")

print("== F. Moteur complet via API (CSV sale) ==")
df = pd.read_csv("ventes_sales.csv")
manq_avant = int(df.isna().sum().sum())
net = data_agent.nettoyer_donnees(df, data_agent.profile_data(df, "ventes_sales.csv"))
clean = net["df_clean"]
print(f"   Nettoyage : {len(df)} -> {len(clean)} lignes, "
      f"{manq_avant} -> {int(clean.isna().sum().sum())} manquantes")
profil = data_agent.profile_data(clean, "ventes_sales.csv")
resume = data_agent.resumer_donnees(profil)
print("   Résumé :", resume.get("resume", "")[:100])
r1 = data_agent.analyser_question(
    clean, profil, "Quel est le chiffre d'affaires total par ville ? "
                   "Ajoute une colonne montant = quantite * prix_unitaire.", [])
print("   Réponse :", r1["reponse"][:250].replace("\n", " | "))
print("   Verdict :", r1["agents"]["verdict"])
r2 = data_agent.analyser_question(
    clean, profil, "Fais un graphique en barres du chiffre d'affaires par categorie.",
    [{"question": "total par ville", "reponse": r1["reponse"][:300], "agents": r1["agents"]}])
print("   Figures :", len(r2["figures"]), "| Verdict :", r2["agents"]["verdict"])

assert len(clean) > 0 and net["rapport"]
assert int(clean.isna().sum().sum()) < manq_avant
assert int(clean.duplicated().sum()) == 0
assert r1["reponse"]
for interdit in ["dtype", "Name:"]:
    assert interdit not in r1["reponse"], f"sortie brute ({interdit})"
for causal in ["parce que", "à cause de", "causé par"]:
    assert causal not in r1["reponse"].lower(), f"causal ({causal})"
assert r2["figures"]
ok, _ = data_agent.verifier_reponse(
    r1["reponse"], data_agent.extraire_nombres(r1["reponse"]), r1["reponse"])

print("== G. Comparaison de 2 fichiers (sans API) ==")
a = pd.read_csv("ventes_exemple.csv")
b = a.copy()
b["quantite"] = b["quantite"] * 2
comp = comparer.comparer(a, b, "A", "B")
att_total = f"{float(a['quantite'].sum()):,.0f}".replace(",", " ")
assert any(att_total in ph for ph in comp["phrases"]), comp["phrases"][:4]
assert any("→" in ph and "+" in ph for ph in comp["phrases"])
assert comp["graphique"] and len(comp["graphique"]) > 5000
print("   Comparaison OK (écarts calculés + graphique)")

print("== H. Routeur questions générales (sans API) ==")
profil_mini = data_agent.profile_data(df_mini, "mini.csv")
r = data_agent.analyser_question(df_mini, profil_mini, "comment tu peux m'aider ?", [])
assert "Je suis DataAgent" in r["reponse"] and r["tableau"] is None and not r["figures"]
r = data_agent.analyser_question(df_mini, profil_mini, "comment tu peu me aidier", [])
assert "Je suis DataAgent" in r["reponse"]
r = data_agent.analyser_question(df_mini, profil_mini, "Bonjour !", [])
assert r["reponse"].startswith("Bonjour")
assert data_agent._reponse_meta("Quel est le total de montant par ville ?",
                                profil_mini) is None
assert data_agent._reponse_meta("Fais un graphique des ventes.", profil_mini) is None
print("   Routeur général OK (aide + bonjour directs, vraies questions intactes)")
print("TOUT EST OK")
