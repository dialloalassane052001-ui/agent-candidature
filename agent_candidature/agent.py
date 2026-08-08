"""Coeur de l'agent : appels a Google Gemini pour analyser puis rediger."""

from google import genai
from google.genai import types

from . import config
from .models import AnalyseMatch
from .prompts import (
    SYSTEME_ANALYSE,
    SYSTEME_LETTRE,
    prompt_analyse,
    prompt_lettre,
)


class AgentCandidature:
    """Agent qui compare une offre a un CV, score le match et redige une lettre."""

    def __init__(self, api_key: str | None = None, modele: str | None = None):
        cle = api_key or config.GEMINI_API_KEY
        if not cle:
            config.verifier_cle()  # leve une erreur explicite
        self.client = genai.Client(api_key=cle)
        self.modele = modele or config.MODELE

    def analyser(self, offre: str, cv: str) -> AnalyseMatch:
        """Analyse la correspondance et renvoie un objet structure."""
        reponse = self.client.models.generate_content(
            model=self.modele,
            contents=prompt_analyse(offre, cv),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEME_ANALYSE,
                response_mime_type="application/json",
                response_schema=AnalyseMatch,
                temperature=0.6,
            ),
        )
        # Gemini renvoie directement une instance AnalyseMatch dans .parsed
        return reponse.parsed

    def generer_lettre(self, offre: str, cv: str, analyse: AnalyseMatch) -> str:
        """Redige une lettre de motivation a partir de l'analyse."""
        reponse = self.client.models.generate_content(
            model=self.modele,
            contents=prompt_lettre(offre, cv, analyse),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEME_LETTRE,
                temperature=0.85,
            ),
        )
        return (reponse.text or "").strip()

    def candidater(self, offre: str, cv: str) -> tuple[AnalyseMatch, str]:
        """Enchaine l'analyse puis la redaction de la lettre."""
        analyse = self.analyser(offre, cv)
        lettre = self.generer_lettre(offre, cv, analyse)
        return analyse, lettre
