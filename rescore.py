"""
rescore.py — Relance uniquement l'analyse Claude sur des résultats déjà
récupérés (data/resultats.json), sans refaire d'appel à l'API du site.
Sert à valider un ajustement de prompt sans recoût de fetch.
"""

import json
from config import ANTHROPIC_API_KEY
from analyzer import analyser_decisions

with open("data/resultats.json", encoding="utf-8") as f:
    data = json.load(f)

# On repart des données brutes (texte inclus), sans les anciens scores/résumés
bruts = [{k: v for k, v in d.items() if k not in
          ("score", "titre_court", "resume", "type_acte", "communes", "mots_cles")}
         for d in data]

resultats = analyser_decisions(bruts, api_key=ANTHROPIC_API_KEY)
resultats.sort(key=lambda x: x.get("score", 0), reverse=True)

with open("data/resultats.json", "w", encoding="utf-8") as f:
    json.dump(resultats, f, ensure_ascii=False, indent=2)

print(f"\n{len(resultats)} décisions re-analysées.")
