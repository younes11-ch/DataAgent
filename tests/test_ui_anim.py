# Tests des animations d'upload (sans navigateur : contenu HTML/CSS).

import ui_anim


def test_carte_succes_echappe_le_nom_de_fichier():
    html = ui_anim.carte_succes('<img src=x onerror=alert(1)>.csv', 10, 3)
    assert "<img" not in html
    assert "&lt;img" in html
    assert "10 lignes, 3 colonnes" in html
    assert "da-dessine" not in html  # le CSS vit dans CSS_UPLOAD, pas la carte


def test_css_upload_cible_le_vrai_selecteur_streamlit():
    css = ui_anim.CSS_UPLOAD
    assert 'stFileUploaderDropzone' in css
    assert 'role="progressbar"' in css or "role='progressbar'" in css
    assert "@keyframes da-dessine" in css
    assert "prefers-reduced-motion" not in css  # règle globale déjà dans app.py


def _session(**kwargs):
    base = {"brut": None, "profil": None, "nettoyage": None, "scan_res": None,
            "cible": "__absente__", "historique": [], "rapport_cache": None,
            "df": None}
    base.update(kwargs)
    return ui_anim.pipeline_fichier(**base)


def test_pipeline_un_seul_actif_qui_pulse():
    html = _session(brut="x", profil={"colonnes": ["a", "b"]},
                    nettoyage={"avant": {"lignes": 10, "manquantes": 4}},
                    scan_res={"observations": [{"phrase": "p"}]})
    assert html.count('da-noeud fait') == 3
    assert html.count('da-noeud actif') == 1  # Analyste pulse
    assert "Pose ta première question" in html
    assert "10 → 0 lignes, 4 manquantes traitées" in html


def test_pipeline_termine_sans_actif():
    html = _session(profil={"colonnes": ["a"]}, nettoyage={"avant": {}},
                    scan_res={"observations": []}, historique=[{"q": 1}],
                    rapport_cache={"cle": 1})
    assert html.count('da-noeud fait') == 5
    assert "da-noeud actif" not in html
    assert "da-lien plein" in html


def test_pipeline_vide_tout_en_attente():
    html = _session()
    assert "da-noeud actif" not in html
    assert html.count("En attente") >= 5
    for nom in ("Profiler", "Nettoyeur", "Détecteur", "Analyste", "Rapport"):
        assert nom in html


def test_bandeau_compteurs_et_jauge():
    html = ui_anim.bandeau_chiffres(1234, 6, 4, 2, 62, 87)
    assert html.count('data-val=') == 5  # 4 compteurs + score anneau
    assert 'data-val="1234"' in html and 'data-val="87"' in html
    assert "Qualité : 62 → 87" in html
    assert "requestAnimationFrame" in html
    assert "prefers-reduced-motion" in html
    assert "@keyframes da-jauge" in html


def test_decouper_stream_recolle_exact():
    texte = "Bonjour  le monde\nNouvelle ligne,  avec   espaces."
    assert "".join(ui_anim.decouper_stream(texte)) == texte
    assert "".join(ui_anim.decouper_stream("")) == ""
    paquets = list(ui_anim.decouper_stream("un deux trois quatre cinq", mots=2))
    assert len(paquets) == 3
    assert "".join(paquets) == "un deux trois quatre cinq"


def test_indicateur_frappe_trois_points():
    assert "@keyframes da-rebond" in ui_anim.CSS_TYPING
    assert ui_anim.INDICATEUR_FRAPPE.count("<span>") == 3
