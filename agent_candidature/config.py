"""Configuration centrale : cle API, modele, chemins.

Tous les chemins sont calcules de facon relative a ce fichier : le projet
fonctionne donc a l'identique quel que soit le PC (portable, autre machine,
serveur de deploiement), sans aucun chemin absolu code en dur.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Charge les variables definies dans le fichier .env (a la racine du projet).
load_dotenv()

# Racine du projet (le dossier Agent_Candidature), toujours relative a ce fichier.
RACINE = Path(__file__).resolve().parent.parent


def _lire_secret(nom: str, defaut: str | None = None) -> str | None:
    """Lit un secret depuis l'environnement (.env local) ou les secrets Streamlit.

    En local : la valeur vient de .env ou des variables d'environnement.
    En deploiement (Streamlit Community Cloud) : elle vient de st.secrets, sans
    qu'aucune cle ne soit jamais ecrite dans le code ni sur GitHub.
    """
    valeur = os.getenv(nom)
    if valeur:
        return valeur
    try:  # import paresseux : le CLI n'a pas besoin de Streamlit
        import streamlit as st

        if nom in st.secrets:
            return str(st.secrets[nom])
    except Exception:
        pass
    return defaut


# Cle API Google Gemini. Definie dans .env (local) ou dans les secrets (deploiement).
# Cle gratuite a creer sur https://aistudio.google.com/apikey
GEMINI_API_KEY = _lire_secret("GEMINI_API_KEY")

# Modele Gemini utilise. Voir .env.example pour les options.
MODELE = _lire_secret("GEMINI_MODELE", "gemini-2.5-flash")


def _dossier_cv_defaut() -> Path:
    """Determine le dossier de CV, de maniere portable.

    Priorite : variable DOSSIER_CV -> "Candidatures_2026" a cote du projet ->
    dossier local "exemples_cv" livre avec le projet (fallback toujours present).
    """
    force = os.getenv("DOSSIER_CV")
    if force:
        return Path(force)
    externe = RACINE.parent / "Candidatures_2026"
    if externe.exists():
        return externe
    return RACINE / "exemples_cv"


# Dossier contenant les CV d'exemple (l'import de CV fonctionne pour tout le monde).
DOSSIER_CV = _dossier_cv_defaut()

# Dossier ou sont sauvegardees les lettres generees.
DOSSIER_SORTIE = RACINE / "lettres_generees"


def verifier_cle() -> None:
    """Leve une erreur claire si la cle API est absente."""
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "Cle API Google Gemini introuvable.\n"
            "Cree un fichier .env (copie .env.example) et renseigne "
            "GEMINI_API_KEY, ou definis la variable d'environnement.\n"
            "Cle gratuite : https://aistudio.google.com/apikey"
        )
