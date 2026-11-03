# Option voix du chatbot : dictée (micro) + lecture des réponses.
# Repose sur l'API Web Speech du navigateur (aucune dépendance pip).
# Le français est prioritaire, avec détection automatique quand le
# navigateur l'expose.

LANGUE_DEFAUT = "fr-FR"

ERREURS_MICRO = {
    "not-allowed": "Micro refusé : autorise l'accès au micro dans le "
                   "navigateur (icône cadenas), puis réessaie.",
    "service-not-allowed": "Micro refusé : autorise l'accès au micro dans "
                           "le navigateur, puis réessaie.",
    "not-found": "Aucun micro détecté : branche un micro puis réessaie.",
    "not-supported": "Navigateur non compatible : utilise Chrome ou Edge "
                     "pour la dictée vocale.",
    "no-speech": "Rien entendu : parle plus fort ou rapproche-toi du micro.",
    "aborted": "Écoute interrompue : relance le micro.",
}


def langue_voix(preference="fr-FR"):
    """Langue de reconnaissance/lecture (français par défaut)."""
    return (preference or "").strip() or LANGUE_DEFAUT


def message_erreur_micro(code):
    """Message clair pour un code d'erreur du micro."""
    return ERREURS_MICRO.get(
        (code or "").strip(),
        "Dictée impossible pour le moment : écris ta question au clavier.")


def echapper_js(texte):
    """Échappe un texte pour l'insérer dans une chaîne JS entre backticks."""
    return ((texte or "").replace("\\", "\\\\").replace("`", "\\`")
            .replace("$", "\\$").replace("</", "<\\/"))


def html_micro(langue="fr-FR", cle="voix"):
    """Composant dictée : bouton micro, voyant d'écoute, zone de texte.

    Affiche un message clair si le navigateur est incompatible ou si le
    micro est refusé. La transcription apparaît dans la zone sous le
    bouton : copiez-la dans le chat (les navigateurs ne laissent pas une
    page web remplir le champ Streamlit directement).
    """
    lang = langue_voix(langue)
    return f"""
<div id="micro-{cle}" style="font-family:inherit">
  <button id="btn-{cle}" title="Dicter (français)"
    style="border:1.5px solid #0f766e;color:#0f766e;background:#fff;
    border-radius:999px;font-weight:600;padding:.35rem .9rem;cursor:pointer">
    🎤 Dicter
  </button>
  <span id="voyant-{cle}" style="display:inline-block;width:.7em;height:.7em;
    border-radius:50%;background:#d1d5db;margin-left:.5em;vertical-align:middle"
    title="État du micro"></span>
  <span id="etat-{cle}" style="margin-left:.4em;font-size:.9em;color:#374151">
    Micro prêt.</span>
  <div id="err-{cle}" style="color:#b91c1c;font-size:.9em;margin-top:.3em"></div>
  <textarea id="txt-{cle}" rows="2" placeholder="Ta dictée apparaîtra ici…"
    style="width:100%;margin-top:.4em;border:1px solid #e5e7eb;
    border-radius:10px;padding:.4em .6em"></textarea>
</div>
<script>
(function() {{
  const btn = document.getElementById('btn-{cle}');
  const voyant = document.getElementById('voyant-{cle}');
  const etat = document.getElementById('etat-{cle}');
  const err = document.getElementById('err-{cle}');
  const txt = document.getElementById('txt-{cle}');
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const ERREURS = __ERREURS_JSON__;
  function setEcoute(on) {{
    voyant.style.background = on ? '#dc2626' : '#d1d5db';
    voyant.style.boxShadow = on ? '0 0 0 4px #fecaca' : 'none';
    etat.textContent = on ? 'J’écoute… parle maintenant.' : 'Micro prêt.';
    btn.textContent = on ? '⏹ Arrêter' : '🎤 Dicter';
  }}
  if (!SR) {{
    err.textContent = ERREURS['not-supported'];
    btn.disabled = true;
    return;
  }}
  let rec = null, ecoute = false;
  // Détection automatique : le navigateur choisit la langue parlée quand
  // il l'expose, sinon français prioritaire.
  btn.onclick = () => {{
    err.textContent = '';
    if (ecoute && rec) {{ rec.stop(); return; }}
    rec = new SR();
    rec.lang = '{lang}';
    rec.interimResults = true;
    rec.onstart = () => {{ ecoute = true; setEcoute(true); }};
    rec.onend = () => {{ ecoute = false; setEcoute(false); }};
    rec.onerror = (e) => {{
      ecoute = false; setEcoute(false);
      err.textContent = ERREURS[e.error] || ERREURS['inconnu'];
    }};
    rec.onresult = (e) => {{
      let final = '', provisoire = '';
      for (const r of e.results) {{
        if (r.isFinal) final += r[0].transcript;
        else provisoire += r[0].transcript;
      }}
      txt.value = (final || provisoire).trim();
      if (final) {{ etat.textContent = 'Transcrit : copie le texte dans le chat.'; }}
    }};
    try {{ rec.start(); }} catch (e) {{
      err.textContent = ERREURS['inconnu'];
    }}
  }};
}})();
</script>
""".replace("__ERREURS_JSON__", _erreurs_js())


def _erreurs_js():
    import json
    tout = dict(ERREURS_MICRO)
    tout["inconnu"] = ("Dictée impossible pour le moment : écris ta "
                       "question au clavier.")
    return json.dumps(tout)


def html_lecture(texte, langue="fr-FR", cle="lec"):
    """Bouton haut-parleur qui lit la réponse (cliquable, désactivable)."""
    lang = langue_voix(langue)
    safe = echapper_js(texte)
    return f"""
<div style="margin:.3em 0">
  <button id="parle-{cle}" title="Lire à voix haute"
    style="border:1.5px solid #0f766e;color:#0f766e;background:#fff;
    border-radius:999px;font-weight:600;padding:.25rem .8rem;cursor:pointer">
    🔊 Écouter
  </button>
  <span id="etatlec-{cle}" style="margin-left:.4em;font-size:.9em;color:#374151"></span>
</div>
<script>
(function() {{
  const btn = document.getElementById('parle-{cle}');
  const etat = document.getElementById('etatlec-{cle}');
  if (!('speechSynthesis' in window)) {{
    etat.textContent = 'Lecture non compatible avec ce navigateur.';
    btn.disabled = true;
    return;
  }}
  let parle = false;
  btn.onclick = () => {{
    if (parle) {{ speechSynthesis.cancel(); parle = false;
      btn.textContent = '🔊 Écouter'; etat.textContent = ''; return; }}
    const u = new SpeechSynthesisUtterance(`{safe}`);
    u.lang = '{lang}';
    u.onend = () => {{ parle = false; btn.textContent = '🔊 Écouter';
      etat.textContent = ''; }};
    speechSynthesis.cancel();
    speechSynthesis.speak(u);
    parle = true; btn.textContent = '⏹ Stop'; etat.textContent = 'Lecture…';
  }};
}})();
</script>
"""
