# DataAgent

*English summary: upload a CSV, even messy — AI agents clean it, scan it for anomalies, answer questions with verified numbers (recomputed, never invented), and build your report. Built with Meta's Muse Spark via the Meta Model API.*

Envoie un fichier CSV, même sale : des agents IA le nettoient, détectent les
anomalies, répondent à tes questions avec des chiffres vérifiés, et construisent
ton rapport d'analyse.

Projet pour le **Meta Global AI Developer Hackathon** (track Indie, thème
*Build for Your World*). Construit pendant le hackathon, du 29 oct au 4 nov 2026.

## Démo en ligne

▶ **Ouvre l'app : https://dataagent-vj7dl7bda3ttcisrjc86tn.streamlit.app/**

Pas de clé API sous la main ? L'app démarre en **mode démo** : scan,
statistiques, valeurs aberrantes, comparaison et rapports fonctionnent
sans clé (questions libres et graphiques IA désactivés).

[![Déployer sur Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io/deploy)

## Déployer (10 min, gratuit)

Suis [DEPLOIEMENT.md](DEPLOIEMENT.md) : repo GitHub public → Streamlit Cloud
(Python 3.12) → colle ta clé dans les Secrets → c'est en ligne.

## Points forts

- **Zéro chiffre inventé** : chaque nombre cité est recalculé en pandas et vérifié
- **Scan automatique** : taux par segment, croisements, cohortes extrêmes,
  paradoxe de Simpson, le tout avec effectifs
- **Données sales acceptées** : nettoyage automatique avec rapport avant/après
- **Prudence** : colonnes ambiguës signalées, petits échantillons marqués,
  corrélations (jamais de causes)

## Comment ça marche

1. Tu envoies un fichier CSV (séparateur `,` ou `;`, utf-8 ou latin-1)
2. Doublons détectés : tu choisis de les supprimer ou non (interrupteur)
3. Les agents nettoient (rapport avant/après) puis scannent les anomalies
4. Tu poses tes questions : **Planificateur** → **Codeur** → **Exécuteur**
   (sous-processus, 30 s max) → **Vérificateur** → **Rédacteur**
5. Tu reçois texte clair + tableau + graphique, code visible
6. Bonus : rapport HTML en un clic, tests intégrés, modèle de prédiction

Modèles Meta utilisés : **Muse Spark** (agents, via Meta Model API).

## Lancer l'app (Windows)

Double-clic sur `DEMARRER_APP.bat`, ou en terminal :

```powershell
cd C:\Users\qsdfs\Desktop\hackathon\META
.venv\Scripts\python.exe -m streamlit run app.py
```

Puis ouvre dans ton navigateur : **http://localhost:8501**

Pour essayer vite : `Employee.csv` (données RH), `ventes_exemple.csv` (propre)
ou `ventes_sales.csv` (sale) — pensez à redémarrer l'app (`Ctrl + C` + relance)
après chaque modification du code.

## Lancer les tests

```powershell
.venv\Scripts\python.exe test_agent.py
```

## Installation (déjà faite sur ce PC)

```powershell
uv venv --python 3.12
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
# Copier .env.example vers .env et mettre ta clé Meta Model API dedans
```

## Fichiers

- `app.py` — l'application web (Streamlit)
- `data_agent.py` — le moteur multi-agents (fiabilité R1-R9)
- `scan.py` — scan déterministe des anomalies
- `imputation.py` — imputation choisie par l'utilisateur (déterministe)
- `points_aberrants.py` — IQR / Z-score / Isolation Forest + graphique
- `anomalies.py` — vote 2/3 des 3 méthodes + garder/corriger/supprimer
- `verif.py` — revérification indépendante des chiffres (bouton Revérifier)
- `journal.py` — journal structuré + script Python reproductible
- `profiler.py` — score de qualité des données 0-100 (avant/après)
- `stats_tests.py` — t-test, ANOVA, chi², corrélation + explications simples
- `viz.py` — graphiques Plotly auto + phrase d'insight
- `series.py` — tendance, saisonnalité, prévision Holt-Winters
- `ui_anim.py` — animations CSS pures (upload, pipeline, compteurs, jauge)
- `export_pdf.py` — rapport PDF en un clic
- `tests/` — tests pytest des nouveautés (sans clé API)
- `rapport.py` — rapport HTML en un clic
- `prediction.py` — modèle "qui risque de partir ?"
- `tests.json` — questions des tests intégrés (cibles Employee.csv)
- `test_agent.py` — test complet du projet
- `ventes_exemple.csv`, `ventes_sales.csv` — fichiers d'exemple
- `ventes_anomalies.csv` — exemple piégé (anomalies réelles + manquantes)
- `.env` — ta clé API (secret, ne jamais partager ni publier)

## Architecture des agents

Pipeline : **Profiler** (`profile_data`) → **Nettoyeur** (`nettoyer_donnees` +
`imputation`, journal structuré via `journal.py`) → **Détecteur**
(`scan.py` + consensus `anomalies.py`) → **Analyste** (`planifier` → `coder` →
`executer` en sandbox → `vérifier` → `rédiger`, bouton Revérifier via
`verif.py`) → **Rapport** (`rapport.py`, `export_pdf.py`). Règle d'or : le LLM
n'affiche que des chiffres recalculés en pandas dans le sandbox.

## Scénario de démo (2 minutes, jury)

1. **0h00 — Upload** : dépose `ventes_sales.csv` (sale) → carte de succès +
   pipeline qui s'anime (Profiler ✓, Nettoyeur ✓, Détecteur ✓).
2. **0h30 — Qualité** : compteurs animés + jauge avant → après nettoyage.
3. **0h50 — Anomalies** : §3, méthode Consensus → corriger/supprimer →
   journal et chiffres mis à jour.
4. **1h10 — Question vérifiée** : « quel est le total par ville ? » → réponse
   + « Voir le code » (code pandas + résultat brut) → bouton **Revérifier**.
5. **1h40 — Reproductible** : journal détaillé + téléchargement du script
   `.py` qui rejoue tout.
6. **1h55 — Rapport** : résumé exécutif + export HTML/PDF en un clic.
