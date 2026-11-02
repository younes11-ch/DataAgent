# Déployer DataAgent en ligne (10 minutes, gratuit)

Objectif : une adresse publique `https://dataagent-....streamlit.app` à mettre
dans la soumission du hackathon. Tout est déjà prêt dans le projet
(requirements figés, secrets, mode démo sans clé).

## Étape 1 — Mettre le code sur GitHub (repo public, obligatoire)

1. Installe **Git for Windows** : https://git-scm.com → Download → suivant,
   suivant… (options par défaut), puis **ferme et rouvre le terminal**.
2. Crée le repo vide sur https://github.com → **New repository** →
   nom `dataagent`, **Public**, **sans README**, Create.
3. Dans un terminal :

```powershell
cd C:\Users\qsdfs\Desktop\hackathon\META
git init
git add .
git commit -m "DataAgent : analyse CSV multi-agents (hackathon Meta)"
git remote add origin https://github.com/younes11-ch/dataagent.git
git branch -M main
git push -u origin main
```

4. Vérifie sur GitHub : le fichier `.env` ne doit **jamais** apparaître
   (il est dans `.gitignore`). Si tu le vois : supprime le repo et recommence
   après avoir régénéré ta clé.

## Étape 2 — Déployer sur Streamlit Cloud (gratuit)

1. Va sur https://share.streamlit.io → **Sign in with GitHub** (autorise).
2. **New app** → repo `dataagent`, branche `main`, fichier `app.py`.
3. **Advanced settings** → Python version → **3.12** → Save.
4. Onglet **Secrets** : colle le contenu de `.streamlit/secrets.toml.example`
   en remplaçant `colle-ta-cle-meta-ici` par ta vraie clé (celle de `.env`) :

```toml
MODEL_API_KEY = "ta-vraie-cle"
META_BASE_URL = "https://api.meta.ai/v1"
MUSE_CHAT_MODEL = "muse-spark-1.3"
```

5. **Deploy** → attends 2-5 minutes → tu reçois l'URL publique.

## Étape 3 — Vérifier (2 minutes)

1. Ouvre l'URL → clique **« Essayer avec un fichier d'exemple »**.
2. Vérifie : aperçu, anomalies, valeurs aberrantes, une question, un rapport.
3. Colle l'URL dans `README.md` (section Démo en ligne) et dans ta soumission.

## Dépannage

- **Bandeau « Mode démo (sans clé API) »** : la clé n'est pas lue →
  Streamlit Cloud → ton app → **Settings → Secrets** → colle les 3 lignes →
  **Save** → **Reboot app**.
- **L'app ne démarre pas** : Manage app → **Logs**, lis l'erreur en rouge.
  Cause fréquente : Python ≠ 3.12 (corrige dans Settings → Python version).
- **Mise à jour** : modifie le code en local, puis
  `git add .` + `git commit -m "..."` + `git push` → le site se redéploie seul.
