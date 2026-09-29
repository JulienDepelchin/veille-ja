"""
proto.py — Prototype de veille TA Lille / CAA Douai (SANS automatisation).

Récupère les décisions publiées sur une fenêtre de N jours, les analyse via
Claude et écrit le résultat dans data/resultats.json. Pas de suivi des PDFs
déjà vus, pas de commit git, pas de cron : ce script sert uniquement à juger
de la qualité du scoring avant de décider d'un pipeline complet.

Usage :
  python proto.py                        → 3 derniers jours (Lille + Douai)
  python proto.py 7                      → 7 derniers jours
  python proto.py 2026-09-15 2026-09-21  → plage de dates explicite
"""

import json
import sys
from datetime import date, timedelta
from pathlib import Path

from config import JURIDICTIONS, MIN_SCORE_AFFICHE, OUTPUT_FILE, ANTHROPIC_API_KEY
from api_ja import lister_decisions_completes
from analyzer import analyser_decisions


def charger_api_key() -> str:
    if not ANTHROPIC_API_KEY:
        print("[ERREUR] ANTHROPIC_API_KEY absent. Créez un fichier .env avec ANTHROPIC_API_KEY=...")
        sys.exit(1)
    return ANTHROPIC_API_KEY


def main():
    if len(sys.argv) > 2:
        dd, df = sys.argv[1], sys.argv[2]
    else:
        n_jours = int(sys.argv[1]) if len(sys.argv) > 1 else 3
        date_fin = date.today()
        date_debut = date_fin - timedelta(days=n_jours - 1)
        df, dd = date_fin.isoformat(), date_debut.isoformat()

    api_key = charger_api_key()

    tous_resultats = []
    for code, nom in JURIDICTIONS.items():
        print(f"\n{'=' * 65}\n{nom} ({code}) — {dd} -> {df}\n{'=' * 65}")
        decisions = lister_decisions_completes(code, dd, df)
        print(f"\n{len(decisions)} décision(s) récupérée(s), analyse en cours...\n")
        resultats = analyser_decisions(decisions, api_key=api_key)
        tous_resultats.extend(resultats)

    tous_resultats.sort(key=lambda x: x.get("score", 0), reverse=True)

    Path("data").mkdir(exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(tous_resultats, f, ensure_ascii=False, indent=2)
    print(f"\nRésultats sauvegardés : {OUTPUT_FILE} ({len(tous_resultats)} décisions au total)")

    notables = [r for r in tous_resultats if r.get("score", 0) >= MIN_SCORE_AFFICHE]
    print(f"\n{'=' * 65}\nBILAN — {len(notables)}/{len(tous_resultats)} décisions retenues (score >= {MIN_SCORE_AFFICHE})\n{'=' * 65}")
    for r in notables:
        print(f"\nScore {r.get('score')}/5 | {r.get('Nom_Juridiction')} | {r.get('type_acte', '?')}")
        print(f"  {r.get('titre_court')}")
        print(f"  {r.get('resume')}")
        if r.get("communes"):
            print(f"  Communes : {', '.join(r['communes'])}")


if __name__ == "__main__":
    main()
