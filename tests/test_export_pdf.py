# Tests du rapport PDF (sans appel IA).

import pandas as pd

import export_pdf
import points_aberrants as pa


def test_pdf_genere_avec_accents():
    pdf = export_pdf.generer_pdf(
        "Rapport DataAgent", "Fichier : données — test.",
        ["Première ligne du résumé.", "Deuxième ligne."],
        [("Nettoyage", ["café → crème", "✓ vérifié"]), ("Limites", ["aucune"])],
        [])
    assert pdf[:5] == b"%PDF-"
    assert len(pdf) > 500


def test_pdf_avec_image():
    serie = pd.Series([1] * 20 + [999])
    png = pa.figure(serie, pa.detecter(serie, "iqr"), "x")
    pdf = export_pdf.generer_pdf("T", "S", ["r"], [], [("Graphique", png)])
    assert pdf[:5] == b"%PDF-"
    assert len(pdf) > 2000


def test_latin_convertit_symboles():
    assert export_pdf._latin("café → ✓ …") == "café -> OK  ..."
