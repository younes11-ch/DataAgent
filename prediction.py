# Bouton "Qui risque de partir ?" : modèle simple, limites affichées.
# Modèle : régression logistique (variables numériques + encodage des catégories).

LIMITES = (
    "Limites : ce modèle montre des associations, pas des causes. "
    "Un score moyen ne prouve pas qu'on peut prédire un individu. "
    "Les résultats dépendent des données fournies (déséquilibre, cohortes extrêmes)."
)


def entrainer(df, cible):
    """Entraîne une régression logistique, rend score + importances."""
    from sklearn.compose import ColumnTransformer
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import cross_val_score
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    s = df[cible]
    if set(s.dropna().unique()) <= {0, 1, True, False}:
        y = s.astype(int)
    else:
        y = (s == s.dropna().unique()[-1]).astype(int)
    X = df.drop(columns=[cible])
    num = list(X.select_dtypes(include="number").columns)
    cat = [c for c in X.columns if c not in num]
    etapes = []
    if num:
        etapes.append(("num", StandardScaler(), num))
    if cat:
        etapes.append(("cat", OneHotEncoder(handle_unknown="ignore"), cat))
    pre = ColumnTransformer(etapes)
    modele = Pipeline([("pre", pre),
                       ("lr", LogisticRegression(max_iter=1000))])
    scores = cross_val_score(modele, X, y, cv=3)
    modele.fit(X, y)
    noms = list(modele.named_steps["pre"].get_feature_names_out())
    coefs = modele.named_steps["lr"].coef_[0]
    importances = sorted(zip(noms, [float(c) for c in coefs]),
                         key=lambda t: abs(t[1]), reverse=True)
    return {"score": float(scores.mean()),
            "scores": [float(v) for v in scores],
            "importances": importances[:10],
            "n": len(df),
            "taux_positifs": float(y.mean())}
