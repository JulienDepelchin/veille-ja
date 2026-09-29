"""
api_ja.py — Client pour l'API non documentée d'opendata.justice-administrative.fr

Reverse-engineered (voir https://fondamentaux.org/2025/lapi-secrete-du-site-open-data-de-la-juridiction-administrative/),
NON garantie par l'éditeur (les CGU du site indiquent explicitement l'absence
d'API officielle). Les routes peuvent changer sans préavis lors d'un
redéploiement du site — logger toute erreur inattendue plutôt que planter
silencieusement.
"""

import time
import requests

BASE = "https://opendata.justice-administrative.fr/recherche/api"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
    )
}

PAUSE_ENTRE_APPELS = 1.0  # secondes — politesse envers un service non prévu pour ça


def lister_decisions(juridiction: str, date_debut: str, date_fin: str, taille: int = 200) -> list[dict]:
    """
    Liste les décisions d'une juridiction publiées entre date_debut et date_fin
    (format YYYY-MM-DD, inclusif). Route "juridiction + période" (pattern 5).
    Retourne la liste des métadonnées (_source) telles que renvoyées par l'API.
    """
    url = f"{BASE}/model_date_juri/openData/Date_Lecture/{juridiction}/{date_debut}/{date_fin}/{taille}"
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json()
    hits = data["decisions"]["body"]["hits"]["hits"]
    total = data["decisions"]["body"]["hits"]["total"]["value"]
    if total > taille:
        print(f"  [AVERT] {juridiction} {date_debut}->{date_fin} : {total} décisions au total, "
              f"seules les {taille} premières sont récupérées (augmenter `taille` si besoin).")
    return [h["_source"] for h in hits]


def recuperer_texte(identification: str, juridiction: str, numero_dossier: str) -> str:
    """
    Récupère le texte intégral d'une décision via la route "testView".
    `identification` : valeur du champ Identification SANS l'extension .xml
    (ex. "DTA_2402416_20260923").
    Retourne le texte avec un saut de ligne entre paragraphes (le séparateur
    natif de l'API est "$$$").
    """
    url = f"{BASE}/testView/openData/unHighlight/{identification}/{juridiction}/{numero_dossier}"
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json()
    hits = data["decisions"]["body"]["hits"]["hits"]
    if not hits:
        return ""
    paragraphe = hits[0]["_source"].get("paragraph", "")
    return "\n\n".join(p.strip() for p in paragraphe.split("$$$") if p.strip())


def lister_decisions_completes(juridiction: str, date_debut: str, date_fin: str, taille: int = 200) -> list[dict]:
    """
    Liste les décisions d'une juridiction sur une période, texte intégral inclus.
    Un appel `lister_decisions` + un appel `recuperer_texte` par décision.
    """
    decisions = lister_decisions(juridiction, date_debut, date_fin, taille)
    resultats = []
    for i, d in enumerate(decisions, 1):
        identification = d["Identification"].removesuffix(".xml")
        print(f"  [{i}/{len(decisions)}] {juridiction} — {d.get('Numero_Dossier')} ({d.get('Type_Decision')}, {d.get('Date_Lecture')})")
        try:
            texte = recuperer_texte(identification, d["Code_Juridiction"], d["Numero_Dossier"])
        except Exception as e:
            print(f"    [ERREUR] récupération texte : {e}")
            texte = ""
        resultats.append({**d, "texte": texte})
        time.sleep(PAUSE_ENTRE_APPELS)
    return resultats
