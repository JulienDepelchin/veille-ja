"""
main.py — Pipeline de production.

Récupère les décisions publiées sur une fenêtre glissante, ignore celles déjà
analysées (data/dossiers_vus.txt), analyse les nouvelles via Claude, fusionne
avec data/resultats.json existant et sauvegarde. Pensé pour tourner une fois
par jour (GitHub Actions déclenché par le Worker Cloudflare lab-crons — voir
Dashboard_data), mais idempotent et rejouable sans risque de double-facturation :
un dossier déjà dans dossiers_vus.txt n'est jamais renvoyé à Claude.

Usage :
  python main.py       → fenêtre de 10 jours (marge large entre deux runs)
  python main.py 5     → fenêtre de 5 jours
"""

import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

from config import JURIDICTIONS, MIN_SCORE_AFFICHE, OUTPUT_FILE, ANTHROPIC_API_KEY
from api_ja import lister_decisions, recuperer_texte
from analyzer import analyser_decisions

# cp1252 (console Windows) ne couvre pas tous les caractères des résumés
# générés par Claude — voir le même correctif dans raa-veille/main.py.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

_BASE = Path(__file__).resolve().parent
VUS_TXT = _BASE / "data" / "dossiers_vus.txt"
FENETRE_AFFICHAGE_JOURS = 30  # aligné sur raa-veille (filtre 30 jours glissants)
PAUSE_ENTRE_TEXTES = 1.0


def _cle(d: dict) -> str:
    """Identifiant stable d'une décision : Identification + Code_Juridiction
    (reconstruit le même format que le champ _id renvoyé par l'API)."""
    return f"{d['Identification']}_{d['Code_Juridiction']}"


def charger_vus() -> set[str]:
    if not VUS_TXT.exists():
        return set()
    return {l.strip() for l in VUS_TXT.read_text(encoding="utf-8").splitlines() if l.strip()}


def enregistrer_vus(cles: list[str]) -> None:
    VUS_TXT.parent.mkdir(parents=True, exist_ok=True)
    with VUS_TXT.open("a", encoding="utf-8") as f:
        for c in cles:
            f.write(c + "\n")


def charger_resultats_existants() -> list[dict]:
    if not Path(OUTPUT_FILE).exists():
        return []
    with open(OUTPUT_FILE, encoding="utf-8") as f:
        return json.load(f)


def filtrer_fenetre(decisions: list[dict], jours: int) -> list[dict]:
    limite = (date.today() - timedelta(days=jours)).isoformat()
    return [d for d in decisions if not d.get("Date_Lecture") or d["Date_Lecture"] >= limite]


def main():
    n_jours = int(sys.argv[1]) if len(sys.argv) > 1 else 10

    if not ANTHROPIC_API_KEY:
        print("[ERREUR] ANTHROPIC_API_KEY absent. Créez un .env avec ANTHROPIC_API_KEY=...")
        sys.exit(1)

    date_fin = date.today()
    date_debut = date_fin - timedelta(days=n_jours - 1)
    dd, df = date_debut.isoformat(), date_fin.isoformat()

    deja_vus = charger_vus()
    bruts = []

    for code, nom in JURIDICTIONS.items():
        print(f"\n{'=' * 65}\n{nom} ({code}) — {dd} -> {df}\n{'=' * 65}")
        try:
            decisions = lister_decisions(code, dd, df, taille=300)
        except Exception as e:
            print(f"  [ERREUR] récupération de la liste : {e}")
            continue

        a_traiter = [d for d in decisions if _cle(d) not in deja_vus]
        print(f"  {len(decisions)} décision(s) sur la période, {len(a_traiter)} nouvelle(s)")

        for i, d in enumerate(a_traiter, 1):
            identification = d["Identification"].removesuffix(".xml")
            print(f"  [{i}/{len(a_traiter)}] {d.get('Numero_Dossier')} ({d.get('Type_Decision')}, {d.get('Date_Lecture')})")
            try:
                texte = recuperer_texte(identification, d["Code_Juridiction"], d["Numero_Dossier"])
            except Exception as e:
                print(f"    [ERREUR] récupération texte : {e}")
                texte = ""
            bruts.append({**d, "texte": texte})
            time.sleep(PAUSE_ENTRE_TEXTES)

    if not bruts:
        print("\nAucune nouvelle décision à analyser.")
        return

    print(f"\n{'=' * 65}\nANALYSE CLAUDE — {len(bruts)} décision(s)\n{'=' * 65}\n")
    nouveaux_resultats = analyser_decisions(bruts, api_key=ANTHROPIC_API_KEY)

    enregistrer_vus([_cle(d) for d in bruts])

    tous = charger_resultats_existants() + nouveaux_resultats
    tous.sort(key=lambda x: x.get("score", 0), reverse=True)
    tous = filtrer_fenetre(tous, FENETRE_AFFICHAGE_JOURS)

    Path("data").mkdir(exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(tous, f, ensure_ascii=False, indent=2)
    print(f"\nRésultats sauvegardés : {OUTPUT_FILE} ({len(tous)} décisions au total)")

    notables = sorted(
        [r for r in nouveaux_resultats if r.get("score", 0) >= MIN_SCORE_AFFICHE],
        key=lambda x: x.get("score", 0), reverse=True,
    )
    print(f"\n{'=' * 65}\nBILAN — {len(notables)}/{len(nouveaux_resultats)} nouvelles décisions retenues (score >= {MIN_SCORE_AFFICHE})\n{'=' * 65}")
    for r in notables:
        print(f"\nScore {r.get('score')}/5 | {r.get('Nom_Juridiction')}")
        print(f"  {r.get('titre_court')}")
        print(f"  {r.get('resume')}")
        if r.get("communes"):
            print(f"  Communes : {', '.join(r['communes'])}")


if __name__ == "__main__":
    main()
