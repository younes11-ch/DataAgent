# DataAgent — description complète

## Le projet en une phrase
DataAgent est une application web qui prend un fichier CSV, même sale, et le
transforme en réponses chiffrées vérifiées et en rapport d'analyse, grâce à
des agents d'intelligence artificielle qui ne montrent que des chiffres
recalculés — jamais inventés.

## Contexte
Projet réalisé pour le **Meta Global AI Developer Hackathon** (catégorie
Indie, thème *Build for Your World*), construit avec **Muse Spark**, le modèle
de Meta, via la Meta Model API.

## Le problème
Dans la vraie vie, les fichiers de données sont sales : doublons, valeurs
manquantes, formats incohérents, valeurs aberrantes. Les nettoyer demande des
compétences techniques. Et les assistants IA classiques ont un défaut grave
pour l'analyse : ils **inventent parfois des chiffres**, ce qui détruit la
confiance. DataAgent résout ces deux problèmes à la fois.

## La solution
L'utilisateur dépose son fichier et dialogue en langage naturel. Derrière,
une équipe d'agents IA se répartit le travail : un agent profile les données,
un autre les nettoie (avec rapport avant/après et possibilité d'annuler), un
autre scanne les anomalies, puis pour chaque question, un planificateur
prépare le plan, un codeur écrit du code pandas, un exécuteur le fait tourner
dans un **bac à sable isolé** (sous-processus, 30 secondes max, code dangereux
bloqué), un vérificateur recontrôle chaque chiffre, et un rédacteur écrit la
réponse finale en français clair, avec tableau et graphique.

## Fonctionnalités principales
1. **Import tolérant** : CSV (séparateurs `,` ou `;`, encodages utf-8 ou
   latin-1) et Excel, même sales.
2. **Nettoyage piloté** : suppression des doublons au choix, imputation des
   manquantes (auto, moyenne, médiane, mode), journal détaillé, bouton
   Annuler/Réappliquer, script Python reproductible téléchargeable.
3. **Score de qualité 0-100** avant et après nettoyage, avec compteurs animés
   et jauge.
4. **Scan automatique des anomalies** : taux par segment, croisements,
   cohortes extrêmes, paradoxe de Simpson — toujours avec les effectifs.
5. **Valeurs aberrantes** : IQR, Z-score, Isolation Forest + vote consensus
   2/3, graphique à points rouges, actions garder/corriger/supprimer, export
   PNG.
6. **Questions vérifiées** : réponse + tableau + graphique + code visible +
   bouton **Revérifier** qui relance un calcul indépendant.
7. **Prudence intégrée** : colonnes ambiguës signalées, petits échantillons
   marqués, corrélations jamais présentées comme des causes.
8. **Tests statistiques** : t-test, ANOVA, chi², corrélation, avec
   explications simples et p-values.
9. **Visualisations auto** : graphiques Plotly choisis selon les colonnes,
   chacun avec une phrase d'insight chiffrée.
10. **Séries temporelles** : tendance, saisonnalité, prévision Holt-Winters.
11. **Comparaison de 2 fichiers**, **rapport HTML/PDF en un clic**, **résumé
    exécutif**, **modèle de prédiction**.
12. **Recherche web** : sans fichier, l'agent cherche lui-même des jeux de
    données (Kaggle, data.gouv.fr, Insee…), avec audit des sources.
13. **Voix** : dictée vocale et lecture des réponses.
14. **Mode démo sans clé API** : scan, stats, aberrantes, comparaison et
    rapports marchent sans clé.

## Architecture technique
Pipeline : **Profiler** → **Nettoyeur** (+ imputation, journal structuré) →
**Détecteur** (scan + consensus) → **Analyste** (planifier → coder → exécuter
en sandbox → vérifier → rédiger) → **Rapport**. Règle d'or : le modèle de
langage n'affiche que des chiffres recalculés en pandas dans le sandbox.
Sécurité durcie : exécution confinée, anti-SSRF sur les téléchargements,
anti-injection (markdown, formules CSV, prompts), plafonds de taille.

## Qualité et tests
167 tests automatisés verts, test de bout en bout complet, et un audit
multi-agents (sécurité, robustesse, tests, UI) dont tous les correctifs sont
appliqués et vérifiés par exécution.

## Stack
Python, Streamlit, pandas, Plotly, scikit-learn, scipy, statsmodels, Meta
Model API (Muse Spark).

## Liens
- Démo : https://dataagent-xrcs6vcq4f5y8c5fzcyner.streamlit.app/
- Code : https://github.com/younes11-ch/DataAgent
