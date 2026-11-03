# Rapport HTML : structure en sections + design + échappement (sans API).

import pandas as pd

import rapport


def _html():
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    return rapport.generer_html(
        df, None, None, {"fichier": "t.csv", "rapport": ["Nettoyé <ok>"]},
        "brute", ["Hypothèse <b>"], resume_exec=["Ligne 1", "Ligne 2"])


def test_html_sections_et_sommaire():
    page = _html()
    assert "<nav" in page and "Sommaire" in page
    for ancre in ["s2", "s3", "s4", "s5", "s6", "s7"]:
        assert f'id="{ancre}"' in page
    assert "<figure" in page and "<figcaption>" in page
    assert "viewport" in page


def test_html_echappe_contenu():
    page = _html()
    assert "&lt;ok&gt;" in page and "&lt;b&gt;" in page
    assert "<ok>" not in page.replace("&lt;ok&gt;", "")


def test_html_sans_resume_ni_anomalie():
    df = pd.DataFrame({"a": [1]})
    page = rapport.generer_html(df, None, None,
                                {"fichier": "t.csv", "rapport": []},
                                "brute", [])
    assert "Aucune anomalie marquée" in page
    assert "<table>" in page
