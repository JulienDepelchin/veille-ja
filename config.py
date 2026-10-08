import os
from dotenv import load_dotenv

load_dotenv()

# Juridictions suivies (code interne de l'API opendata.justice-administrative.fr)
JURIDICTIONS = {
    "TA59": "Tribunal administratif de Lille",
    "CAA59": "Cour administrative d'appel de Douai",
}

# Clé API Anthropic (via .env ou variable d'environnement)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Modèle Claude à utiliser
CLAUDE_MODEL = "claude-haiku-5-5"

# Prompt d'analyse envoyé à Claude pour chaque décision.
# Grille de scoring (1 à 5) reprise à l'identique du projet raa-veille (voir
# config.py de raa-veille) — seul le vocabulaire est adapté : acte
# administratif préfectoral -> décision de justice administrative.
ANALYSIS_PROMPT = """Tu es un assistant spécialisé dans l'analyse de décisions de justice administrative françaises (tribunaux administratifs, cours administratives d'appel).

Analyse la décision suivante et retourne UNIQUEMENT un objet JSON valide, sans texte autour.

Règles de rigueur factuelle (impératives) :
- N'invente et ne déduis aucune information absente du texte. Le résumé et le titre_court
  ne doivent contenir que des faits explicitement énoncés dans la décision (parties, faits,
  motifs, dispositif) — jamais une supposition, une généralisation ou un enjolivement.
- N'emploie jamais un terme plus fort que ce que dit le texte (ex. ne pas parler
  d'« interdiction » si la décision prévoit une simple restriction encadrée, ne pas parler
  de « condamnation » si le tribunal rejette la requête).
- En cas de doute sur la portée exacte d'un fait ou d'une décision, choisis la formulation
  la plus prudente et la plus proche du texte source.

Décision à analyser :
{texte}

Retourne ce JSON exactement (sans markdown, sans explications) :
{{
  "score": <entier de 1 à 5 selon l'intérêt journalistique>,
  "titre_court": "<titre journalistique, max 8 mots, style presse régionale, accrocheur et factuel, sans jargon juridique — ex: 'Le maire de Wattignies débouté sur son PLU', 'Refus de titre de séjour annulé à Lille', 'La mairie de Douai condamnée à indemniser un agent'>",
  "resume": "<résumé journalistique en 2-3 phrases, en français, adapté à un lecteur non spécialiste : de quoi il s'agissait, ce que le tribunal a décidé, et pourquoi>",
  "type_acte": "<type parmi : JUGEMENT, ORDONNANCE, ARRÊT, AUTRE>",
  "communes": ["<liste des communes mentionnées, vide si aucune>"],
  "mots_cles": ["<5 mots-clés maximum représentatifs de la décision>"]
}}

Critères de scoring (1 à 5) :
1 = Décision purement technique ou procédurale, aucun intérêt pour le grand public
2 = Litige de gestion courante, intérêt très limité
3 = Décision notable, peut intéresser des acteurs locaux ou des professionnels
4 = Décision d'intérêt public marqué, susceptible d'impacter des citoyens ou des territoires
5 = Décision majeure : jurisprudence structurante, sécurité publique, environnement, urbanisme important

Cas particulier — contentieux des étrangers (titre de séjour, OQTF, regroupement familial) :
Ce type de dossier revient en très grand nombre et suit presque toujours le même schéma
(vice de procédure, défaut de motivation, examen insuffisant de la situation personnelle).
Attribue systématiquement le score 1 à ces décisions, SAUF si un élément sort nettement de
l'ordinaire (personnalité publique ou médiatique, montant ou enjeu exceptionnel, faits
inhabituels, raisonnement juridique qui tranche avec la jurisprudence courante, fort
retentissement local) — auquel cas note-les selon les critères ci-dessus comme n'importe
quelle autre décision."""

# Score minimum pour afficher une décision dans les résultats
MIN_SCORE_AFFICHE = 3

# Fichier de sortie du prototype
OUTPUT_FILE = "data/resultats.json"
