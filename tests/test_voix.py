# Option voix : helpers testables sans navigateur (français prioritaire).

import voix


def test_langue_francais_par_defaut():
    assert voix.langue_voix() == "fr-FR"
    assert voix.langue_voix("") == "fr-FR"
    assert voix.langue_voix("en-US") == "en-US"


def test_erreurs_micro_claires():
    refuse = voix.message_erreur_micro("not-allowed")
    assert "Micro refusé" in refuse and "navigateur" in refuse
    assert "Chrome ou Edge" in voix.message_erreur_micro("not-supported")
    assert "micro détecté" in voix.message_erreur_micro("not-found")
    inconnu = voix.message_erreur_micro("bizarre")
    assert "clavier" in inconnu


def test_echapper_js():
    assert "`" not in voix.echapper_js("il dit `bonjour`").replace("\\`", "")
    assert "</" not in voix.echapper_js("fin </script>")
    assert voix.echapper_js("100 $") == "100 \\$"


def test_html_micro_francais_et_voyant():
    page = voix.html_micro()
    assert "fr-FR" in page
    assert "SpeechRecognition" in page
    assert "Dicter" in page and "voyant" in page
    assert "J’écoute" in page  # indique visuellement l'écoute
    assert "Navigateur non compatible" in page or "non compatible" in page


def test_html_lecture_haut_parleur():
    page = voix.html_lecture("Le taux vaut 39,4 %.")
    assert "speechSynthesis" in page
    assert "Écouter" in page and "fr-FR" in page
