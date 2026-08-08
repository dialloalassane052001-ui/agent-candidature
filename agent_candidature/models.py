"""Structures de donnees (sorties structurees de l'analyse)."""

from pydantic import BaseModel, Field


class AnalyseMatch(BaseModel):
    """Resultat de l'analyse de correspondance offre / profil."""

    score_global: int = Field(
        description="Score de correspondance entre l'offre et le profil, de 0 a 100."
    )
    resume_offre: str = Field(
        description="Resume en 2 ou 3 phrases de ce que recherche l'offre."
    )
    points_forts: list[str] = Field(
        description="Atouts concrets du candidat pour CE poste precis "
        "(experiences, competences, projets pertinents)."
    )
    points_faibles: list[str] = Field(
        description="Ecarts ou competences manquantes vis-a-vis de l'offre, "
        "formules honnetement."
    )
    competences_a_mettre_en_avant: list[str] = Field(
        description="Competences du CV a mettre en avant en priorite dans la candidature."
    )
    mots_cles_offre: list[str] = Field(
        description="Mots-cles, technologies et notions importantes de l'offre "
        "(utiles pour passer les filtres automatiques / ATS)."
    )
    recommandation: str = Field(
        description="Verdict : faut-il postuler ? Conseils d'ajustement du CV "
        "ou angle a privilegier dans la lettre."
    )
    email_candidature: str = Field(
        default="",
        description="Adresse e-mail de candidature mentionnee dans l'offre, "
        "sinon chaine vide.",
    )
    contact_candidature: str = Field(
        default="",
        description="Nom / fonction de la personne a contacter pour postuler, "
        "si l'offre le precise, sinon chaine vide.",
    )
    date_limite: str = Field(
        default="",
        description="Date limite de candidature si elle figure dans l'offre, "
        "sinon chaine vide.",
    )
    procedure_candidature: str = Field(
        default="",
        description="Comment postuler, en une phrase (ex. envoyer CV + lettre par "
        "e-mail, formulaire en ligne, plateforme...), sinon chaine vide.",
    )
