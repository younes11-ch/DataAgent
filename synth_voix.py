# Voix off anglaise de la demo : synthese en morceaux + assemblage + duree.
# Script standalone (jamais importe par l'app) : tout s'execute dans main().
import argparse
import re
import time
import urllib.parse
import urllib.request

# Duree : somme des trames MPEG (1152 echantillons par trame).
DEBITS = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320]
TAUX = [44100, 48000, 32000]


def main(entree="demo_voix_en.md", sortie="narration_en.mp3"):
    with open(entree, encoding="utf-8") as f:
        texte = f.read()
    texte = re.sub(r"#[^\r\n]*\r?\n", "", texte).strip()
    texte = re.sub(r"\s+", " ", texte)

    # Decoupe en phrases, regroupees par paquets <= 190 caracteres.
    phrases = re.split(r"(?<=[.!?]) +", texte)
    paquets, courant = [], ""
    for ph in phrases:
        if len(courant) + len(ph) + 1 > 190 and courant:
            paquets.append(courant)
            courant = ph
        else:
            courant = (courant + " " + ph).strip()
    if courant:
        paquets.append(courant)
    print("paquets:", len(paquets))

    brut = b""
    for i, paq in enumerate(paquets):
        q = urllib.parse.urlencode(
            {"ie": "UTF-8", "q": paq, "tl": "en", "client": "tw-ob"})
        url = "https://translate.google.com/translate_tts?" + q
        for essai in range(6):
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": "Mozilla/5.0"})
                brut += urllib.request.urlopen(req, timeout=30).read()
                break
            except Exception as e:
                print("paquet", i, "essai", essai, type(e).__name__, flush=True)
                time.sleep(5 * (essai + 1))
        else:
            raise SystemExit(f"paquet {i} impossible")
        time.sleep(20)
        print(f"paquet {i + 1}/{len(paquets)} ok ({len(paq)} car.)")

    with open(sortie, "wb") as f:
        f.write(brut)

    echantillons = 0
    i = 0
    while i + 4 <= len(brut):
        if brut[i] == 0xFF and (brut[i + 1] & 0xE0) == 0xE0:
            v = (brut[i + 1] >> 3) & 0x03
            l = (brut[i + 1] >> 1) & 0x03
            d = (brut[i + 2] >> 4) & 0x0F
            t = (brut[i + 2] >> 2) & 0x03
            if v == 3 and l == 1 and d not in (0, 15) and t != 3:
                debit = DEBITS[d] * 1000
                taux = TAUX[t]
                pad = (brut[i + 2] >> 1) & 0x01
                taille = int(144 * debit / taux) + pad
                echantillons += 1152
                i += taille
                continue
        i += 1
    print("duree estimee s:", round(echantillons / 48000, 1))


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description="Voix off anglaise de la démo.")
    cli.add_argument("entree", nargs="?", default="demo_voix_en.md")
    cli.add_argument("sortie", nargs="?", default="narration_en.mp3")
    args = cli.parse_args()
    main(args.entree, args.sortie)
