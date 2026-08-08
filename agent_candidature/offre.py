"""Lecture d'une offre (emploi / these) depuis une URL, un fichier ou du texte.

En plus du texte brut, on tente d'extraire des metadonnees utiles pour postuler :
titre du poste, entreprise, lieu et adresses e-mail de candidature. Beaucoup de
sites d'emploi (Indeed, Welcome to the Jungle, France Travail, LinkedIn...)
integrent une fiche structuree "JobPosting" (schema.org) dans leur page : quand
elle est presente, elle donne un texte bien plus propre que le HTML brut.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import requests
from bs4 import BeautifulSoup

_ENTETES = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Detection d'adresses e-mail dans le texte d'une offre.
_MOTIF_EMAIL = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


@dataclass
class OffreExtraite:
    """Contenu d'une offre + metadonnees reperees automatiquement."""

    texte: str
    titre: str = ""
    entreprise: str = ""
    lieu: str = ""
    emails: list[str] = field(default_factory=list)
    url_source: str = ""

    def resume_source(self) -> str:
        """Petite ligne recapitulative (utile pour l'affichage / le CSV)."""
        morceaux = [m for m in (self.titre, self.entreprise, self.lieu) if m]
        return " — ".join(morceaux)


def _nettoyer(texte: str) -> str:
    lignes = [ligne.strip() for ligne in texte.splitlines() if ligne.strip()]
    return "\n".join(lignes)


def _extraire_emails(texte: str) -> list[str]:
    """Renvoie la liste des e-mails uniques trouves, dans l'ordre d'apparition."""
    vus: list[str] = []
    for email in _MOTIF_EMAIL.findall(texte or ""):
        email = email.rstrip(".")
        # On ignore les faux positifs frequents (images, exemples de domaine).
        if email.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".svg")):
            continue
        if email not in vus:
            vus.append(email)
    return vus


def _texte_depuis_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for balise in soup(["script", "style", "nav", "footer", "header", "aside"]):
        balise.decompose()
    return _nettoyer(soup.get_text(separator="\n"))


def _parcourir_jsonld(donnee) -> dict | None:
    """Cherche recursivement un objet de type JobPosting dans un bloc JSON-LD."""
    if isinstance(donnee, list):
        for element in donnee:
            trouve = _parcourir_jsonld(element)
            if trouve:
                return trouve
    elif isinstance(donnee, dict):
        if "@graph" in donnee:
            trouve = _parcourir_jsonld(donnee["@graph"])
            if trouve:
                return trouve
        types = donnee.get("@type", "")
        types = types if isinstance(types, list) else [types]
        if any("JobPosting" in str(t) for t in types):
            return donnee
    return None


def _offre_depuis_jsonld(soup: BeautifulSoup) -> dict | None:
    """Extrait la fiche JobPosting (schema.org) si la page en contient une."""
    for balise in soup.find_all("script", type="application/ld+json"):
        contenu = balise.string or balise.get_text()
        if not contenu:
            continue
        try:
            donnee = json.loads(contenu)
        except (json.JSONDecodeError, TypeError):
            continue
        fiche = _parcourir_jsonld(donnee)
        if fiche:
            return fiche
    return None


def _lieu_jsonld(fiche: dict) -> str:
    lieu = fiche.get("jobLocation")
    if isinstance(lieu, list) and lieu:
        lieu = lieu[0]
    if isinstance(lieu, dict):
        adresse = lieu.get("address", {})
        if isinstance(adresse, dict):
            morceaux = [
                adresse.get("addressLocality", ""),
                adresse.get("addressRegion", ""),
                adresse.get("addressCountry", ""),
            ]
            return ", ".join(m for m in morceaux if m and isinstance(m, str))
    return ""


def _depuis_url(url: str) -> OffreExtraite:
    """Telecharge une page et en extrait le texte + les metadonnees."""
    try:
        reponse = requests.get(url, headers=_ENTETES, timeout=25)
        reponse.raise_for_status()
    except requests.HTTPError as e:
        code = e.response.status_code if e.response is not None else "?"
        raise ValueError(
            f"Ce site bloque la lecture automatique (erreur {code}). "
            "Certains sites d'emploi (Indeed, LinkedIn, Welcome to the Jungle...) "
            "empechent les robots de lire leurs pages. "
            "Solution : copie-colle le texte de l'offre dans l'onglet "
            "« Coller l'offre »."
        ) from e
    except requests.RequestException as e:
        raise ValueError(
            "Impossible d'acceder a cette URL. Verifie le lien, ou copie-colle "
            "directement le texte de l'offre dans l'onglet « Coller l'offre »."
        ) from e

    # requests devine mal l'encodage de certaines pages FR : on corrige.
    if not reponse.encoding or reponse.encoding.lower() == "iso-8859-1":
        reponse.encoding = reponse.apparent_encoding

    soup = BeautifulSoup(reponse.text, "html.parser")
    fiche = _offre_depuis_jsonld(soup)

    if fiche:
        # Fiche structuree : bien plus propre que le HTML brut.
        titre = str(fiche.get("title", "") or "")
        org = fiche.get("hiringOrganization", {})
        entreprise = str(org.get("name", "")) if isinstance(org, dict) else str(org)
        lieu = _lieu_jsonld(fiche)
        description = _texte_depuis_html(str(fiche.get("description", "")))
        entete = "\n".join(m for m in (titre, entreprise, lieu) if m)
        texte = _nettoyer(f"{entete}\n\n{description}") if description else entete
    else:
        titre = entreprise = lieu = ""
        texte = _texte_depuis_html(reponse.text)

    return OffreExtraite(
        texte=texte,
        titre=titre,
        entreprise=entreprise,
        lieu=lieu,
        emails=_extraire_emails(reponse.text),
        url_source=url,
    )


def extraire_offre(source: str) -> OffreExtraite:
    """Charge une offre et renvoie texte + metadonnees, depuis :

    - une URL (http:// ou https://)
    - un chemin de fichier existant (.txt, .md, .html)
    - sinon : le texte est considere comme deja colle tel quel
    """
    source = source.strip()

    if source.startswith(("http://", "https://")):
        return _depuis_url(source)

    # Un chemin de fichier est forcement court : on evite de tester Path() sur
    # une offre entiere collee (qui pourrait contenir des caracteres invalides).
    if len(source) < 400:
        chemin = Path(source)
        if chemin.exists() and chemin.is_file():
            if chemin.suffix.lower() in {".html", ".htm"}:
                texte = _texte_depuis_html(chemin.read_text(encoding="utf-8"))
            else:
                texte = _nettoyer(chemin.read_text(encoding="utf-8"))
            return OffreExtraite(texte=texte, emails=_extraire_emails(texte))

    # Texte colle directement.
    return OffreExtraite(texte=source, emails=_extraire_emails(source))


def charger_offre(source: str) -> str:
    """Compatibilite : renvoie uniquement le texte de l'offre."""
    return extraire_offre(source).texte
