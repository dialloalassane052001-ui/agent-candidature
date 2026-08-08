"""Chargement du CV depuis differents formats (HTML, PDF, Word, texte).

Deux entrees possibles :
- charger_cv(chemin)       : depuis un fichier sur le disque
- charger_cv_bytes(nom, d) : depuis des donnees en memoire (ex. fichier televerse)
"""

import io
from pathlib import Path

from bs4 import BeautifulSoup

# Formats de CV reconnus.
EXTENSIONS = {".html", ".htm", ".pdf", ".txt", ".md", ".docx"}


def _nettoyer(texte: str) -> str:
    """Supprime les lignes vides et les espaces superflus."""
    lignes = [ligne.strip() for ligne in texte.splitlines() if ligne.strip()]
    return "\n".join(lignes)


def _html_vers_texte(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for balise in soup(["script", "style"]):
        balise.decompose()
    return _nettoyer(soup.get_text(separator="\n"))


def _pdf_vers_texte(data: bytes) -> str:
    from pypdf import PdfReader

    lecteur = PdfReader(io.BytesIO(data))
    return _nettoyer("\n".join(page.extract_text() or "" for page in lecteur.pages))


def _docx_vers_texte(data: bytes) -> str:
    from docx import Document

    document = Document(io.BytesIO(data))
    return _nettoyer("\n".join(p.text for p in document.paragraphs))


def charger_cv_bytes(nom: str, data: bytes) -> str:
    """Extrait le texte d'un CV a partir de ses donnees brutes (bytes)."""
    suffixe = Path(nom).suffix.lower()
    if suffixe in {".html", ".htm"}:
        return _html_vers_texte(data.decode("utf-8", errors="ignore"))
    if suffixe == ".pdf":
        return _pdf_vers_texte(data)
    if suffixe == ".docx":
        return _docx_vers_texte(data)
    if suffixe in {".txt", ".md"}:
        return _nettoyer(data.decode("utf-8", errors="ignore"))
    raise ValueError(
        f"Format de CV non supporte : {suffixe}. "
        "Formats acceptes : PDF, Word (.docx), HTML, texte."
    )


def charger_cv(chemin) -> str:
    """Charge le texte d'un CV depuis un fichier sur le disque."""
    chemin = Path(chemin)
    if not chemin.exists():
        raise FileNotFoundError(f"CV introuvable : {chemin}")
    return charger_cv_bytes(chemin.name, chemin.read_bytes())


def lister_cv(dossier) -> list[Path]:
    """Liste les fichiers CV disponibles dans un dossier."""
    dossier = Path(dossier)
    if not dossier.exists():
        return []
    return sorted(
        p for p in dossier.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONS
    )
