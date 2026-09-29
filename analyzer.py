"""
analyzer.py — Scoring et résumé des décisions via Claude.
Repris du pattern de raa-veille/analyzer.py, simplifié : pas de mode image ici,
le texte intégral est toujours disponible via l'API (voir api_ja.py).
"""

import json
import re
import time
import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, ANALYSIS_PROMPT

PAUSE_ENTRE_APPELS = 3
PAUSE_RATE_LIMIT = 15
MAX_RETRIES = 1


def _parse_json_response(contenu: str) -> dict:
    contenu = contenu.strip()
    contenu = re.sub(r"^```(?:json)?\s*", "", contenu)
    contenu = re.sub(r"\s*```$", "", contenu)
    try:
        return json.loads(contenu)
    except json.JSONDecodeError:
        return {
            "score": 0,
            "titre_court": "",
            "resume": "Erreur de parsing de la réponse Claude.",
            "type_acte": "INCONNU",
            "communes": [],
            "mots_cles": [],
            "raw_response": contenu,
        }


def _appel_api_avec_retry(client: anthropic.Anthropic, **kwargs) -> anthropic.types.Message:
    for tentative in range(MAX_RETRIES + 1):
        try:
            return client.messages.create(**kwargs)
        except anthropic.RateLimitError:
            if tentative < MAX_RETRIES:
                print(f"    [429] Rate limit — attente {PAUSE_RATE_LIMIT}s puis retry...")
                time.sleep(PAUSE_RATE_LIMIT)
            else:
                raise


def analyser_decision_texte(texte: str, client: anthropic.Anthropic) -> dict:
    prompt = ANALYSIS_PROMPT.format(texte=texte[:6000])
    message = _appel_api_avec_retry(
        client,
        model=CLAUDE_MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_json_response(message.content[0].text)


def analyser_decisions(decisions: list[dict], api_key: str = None) -> list[dict]:
    """
    Analyse une liste de décisions (dicts avec au moins une clé "texte") et
    retourne les résultats enrichis.
    """
    cle = api_key or ANTHROPIC_API_KEY
    client = anthropic.Anthropic(api_key=cle)

    resultats = []
    total = len(decisions)

    for i, d in enumerate(decisions, 1):
        print(f"  Analyse {i}/{total} : {d.get('Numero_Dossier')} ({d.get('Nom_Juridiction')})...")
        texte = d.get("texte", "")
        if not texte:
            analyse = {
                "score": 0,
                "titre_court": "",
                "resume": "Texte intégral indisponible.",
                "type_acte": "INCONNU",
                "communes": [],
                "mots_cles": [],
            }
        else:
            try:
                analyse = analyser_decision_texte(texte, client)
            except Exception as e:
                analyse = {
                    "score": 0,
                    "resume": f"Erreur lors de l'analyse : {e}",
                    "type_acte": "ERREUR",
                    "communes": [],
                    "mots_cles": [],
                }

        resultats.append({**d, **analyse})

        if i < total:
            time.sleep(PAUSE_ENTRE_APPELS)

    return resultats
