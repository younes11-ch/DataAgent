# Rapport PDF via fpdf2 : textes + graphiques PNG déjà générés.
# Police de base (latin-1) : les accents français passent, les symboles
# spéciaux (→, ✓, ⚠) sont convertis. Aucun fichier de police externe.

from __future__ import annotations

import io

from fpdf import FPDF

REMPLACEMENTS = {
    "→": "->", "✓": "OK ", "✔": "OK ", "✅": "OK ", "❌": "KO ",
    "⚠": "!", "…": "...", "\u00a0": " ", "\u202f": " ", "\u2009": " ",
    "«": '"', "»": '"', "’": "'", "–": "-", "—": "-",
}


def _latin(texte: str) -> str:
    """Convertit un texte pour la police de base du PDF (latin-1)."""
    for ancien, nouveau in REMPLACEMENTS.items():
        texte = texte.replace(ancien, nouveau)
    return texte.encode("latin-1", errors="replace").decode("latin-1")


class _Rapport(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")


def generer_pdf(titre: str, sous_titre: str, resume_exec: list[str],
                sections: list[tuple[str, list[str]]],
                images: list[tuple[str, bytes]]) -> bytes:
    """Construit le rapport PDF complet et rend ses octets."""
    pdf = _Rapport()
    pdf.alias_nb_pages("{nb}")
    pdf.set_auto_page_break(True, margin=20)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 12, _latin(titre), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 6, _latin(sous_titre), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Resume executif", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    for ligne in resume_exec:
        pdf.multi_cell(0, 6, "- " + _latin(ligne), new_x="LMARGIN", new_y="NEXT")
    for nom_section, lignes in sections:
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, _latin(nom_section), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        for ligne in lignes[:30]:
            pdf.multi_cell(0, 6, "- " + _latin(str(ligne))[:300],
                           new_x="LMARGIN", new_y="NEXT")
    for legende, png in images:
        if not png:
            continue
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, _latin(legende)[:100], new_x="LMARGIN", new_y="NEXT")
        try:
            pdf.image(io.BytesIO(png), w=170)
        except Exception:
            pdf.set_font("Helvetica", "I", 11)
            pdf.cell(0, 10, "(graphique illisible)")
    out = pdf.output()
    return bytes(out)
