"""Agent IA de candidature.

Lit une offre (emploi ou these), la compare a ton CV, score le match
et redige une lettre de motivation personnalisee.
"""

from .agent import AgentCandidature
from .models import AnalyseMatch

__all__ = ["AgentCandidature", "AnalyseMatch"]
