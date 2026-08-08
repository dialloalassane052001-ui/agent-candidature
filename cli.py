"""Interface en ligne de commande de l'agent de candidature.

Exemples :
    python cli.py --offre "https://exemple.com/offre" --cv-auto these
    python cli.py --offre offre.txt --cv "..\\Candidatures_2026\\CV_...html"
    python cli.py --offre offre.txt --format pdf
    python cli.py --lot offres.txt --cv-auto entreprise   (plusieurs offres)
    python cli.py            (mode interactif : colle l'offre au clavier)
"""

import argparse
import csv
import re
import sys
from datetime import datetime

# Sous Windows, la console est parfois en cp1252 et plante a l'affichage de
# caracteres speciaux (emojis, symboles). On force l'UTF-8 par securite.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

from agent_candidature import AgentCandidature, config
from agent_candidature import export
from agent_candidature.cv_loader import charger_cv, lister_cv
from agent_candidature.offre import OffreExtraite, extraire_offre


def choisir_cv(cv_arg: str | None, cv_auto: str | None):
    """Determine quel CV utiliser (chemin explicite, mot-cle, ou choix interactif)."""
    cvs = lister_cv(config.DOSSIER_CV)

    if cv_arg:
        return cv_arg

    if cv_auto:
        for chemin in cvs:
            if cv_auto.lower() in chemin.name.lower():
                return chemin
        print(f"Aucun CV ne correspond a '{cv_auto}'.")

    if not cvs:
        sys.exit(
            f"Aucun CV trouve dans {config.DOSSIER_CV}. Precise un chemin avec --cv."
        )

    print("\nCV disponibles :")
    for i, chemin in enumerate(cvs, 1):
        print(f"  {i}. {chemin.name}")
    choix = input("Numero du CV a utiliser : ").strip()
    return cvs[int(choix) - 1]


def lire_offre_interactive() -> str:
    print(
        "\nColle l'offre (ou une URL), puis termine avec une ligne vide "
        "suivie de Ctrl+Z + Entree :\n"
    )
    return sys.stdin.read()


def _nom_fichier(base: str, defaut: str = "lettre") -> str:
    base = (base or "").strip() or defaut
    base = re.sub(r"[^\w\s-]", "", base, flags=re.ASCII).strip()
    base = re.sub(r"\s+", "_", base)
    return base[:60] or defaut


def _ecrire_lettre(chemin_sans_ext, lettre: str, fmt: str):
    """Ecrit la lettre dans le format demande et renvoie le chemin final."""
    if fmt == "docx":
        chemin = f"{chemin_sans_ext}.docx"
        donnees = export.lettre_vers_docx(lettre)
    elif fmt == "pdf":
        chemin = f"{chemin_sans_ext}.pdf"
        donnees = export.lettre_vers_pdf(lettre)
    else:
        chemin = f"{chemin_sans_ext}.txt"
        donnees = export.lettre_vers_txt(lettre)
    with open(chemin, "wb") as f:
        f.write(donnees)
    return chemin


def _emails(analyse, offre: OffreExtraite) -> list[str]:
    emails = [analyse.email_candidature] if analyse.email_candidature else []
    for e in offre.emails:
        if e not in emails:
            emails.append(e)
    return emails


def _decouper_offres(brut: str) -> list[str]:
    brut = (brut or "").strip()
    if not brut:
        return []
    blocs = [b.strip() for b in re.split(r"(?m)^\s*-{3,}\s*$", brut) if b.strip()]
    if len(blocs) > 1:
        return blocs
    lignes = [l.strip() for l in brut.splitlines() if l.strip()]
    if lignes and all(l.startswith(("http://", "https://")) for l in lignes):
        return lignes
    return [brut]


def afficher_analyse(offre: OffreExtraite, analyse) -> None:
    if offre.resume_source():
        print(f"Offre : {offre.resume_source()}")
    print("=" * 60)
    print(f"SCORE DE MATCH : {analyse.score_global}/100")
    print("=" * 60)
    print(f"\nResume de l'offre :\n{analyse.resume_offre}")
    print("\nPoints forts :")
    for p in analyse.points_forts:
        print(f"  + {p}")
    print("\nPoints a renforcer :")
    for p in analyse.points_faibles:
        print(f"  - {p}")
    print("\nA mettre en avant :")
    for c in analyse.competences_a_mettre_en_avant:
        print(f"  * {c}")
    print(f"\nMots-cles offre : {', '.join(analyse.mots_cles_offre)}")

    emails = _emails(analyse, offre)
    if emails or analyse.contact_candidature or analyse.date_limite:
        print("\nComment postuler :")
        if emails:
            print(f"  E-mail : {', '.join(emails)}")
        if analyse.contact_candidature:
            print(f"  Contact : {analyse.contact_candidature}")
        if analyse.date_limite:
            print(f"  Date limite : {analyse.date_limite}")
        if analyse.procedure_candidature:
            print(f"  Procedure : {analyse.procedure_candidature}")

    print(f"\nRecommandation :\n{analyse.recommandation}")


def traiter_lot(chemin_lot: str, cv: str, agent, fmt: str) -> None:
    """Traite plusieurs offres depuis un fichier et enregistre lettres + recap CSV."""
    from pathlib import Path

    brut = Path(chemin_lot).read_text(encoding="utf-8")
    sources = _decouper_offres(brut)
    if not sources:
        sys.exit("Le fichier de lot est vide.")

    config.DOSSIER_SORTIE.mkdir(exist_ok=True)
    horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
    dossier = config.DOSSIER_SORTIE / f"lot_{horodatage}"
    dossier.mkdir()

    recap = []
    for i, source in enumerate(sources, 1):
        print(f"\n[{i}/{len(sources)}] Traitement...")
        try:
            offre = extraire_offre(source)
            analyse = agent.analyser(offre.texte, cv)
            lettre = agent.generer_lettre(offre.texte, cv, analyse)
        except Exception as exc:
            print(f"  Echec : {exc}")
            continue
        base = _nom_fichier(offre.entreprise or offre.titre or f"offre_{i}")
        chemin = _ecrire_lettre(dossier / f"{i:02d}_{base}", lettre, fmt)
        print(f"  Score {analyse.score_global}/100 -> {chemin}")
        recap.append(
            {
                "numero": i,
                "titre": offre.titre,
                "entreprise": offre.entreprise,
                "lieu": offre.lieu,
                "score": analyse.score_global,
                "email_candidature": ", ".join(_emails(analyse, offre)),
                "date_limite": analyse.date_limite,
                "recommandation": analyse.recommandation,
                "source": offre.url_source or "(texte colle)",
            }
        )

    if not recap:
        sys.exit("Aucune offre n'a pu etre traitee.")

    chemin_csv = dossier / "recapitulatif.csv"
    with open(chemin_csv, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(recap[0].keys()))
        writer.writeheader()
        writer.writerows(recap)
    print(f"\n{len(recap)} lettre(s) et le recap enregistres dans : {dossier}")


def main() -> None:
    parseur = argparse.ArgumentParser(description="Agent IA de candidature")
    parseur.add_argument("--offre", help="URL, chemin de fichier, ou texte de l'offre")
    parseur.add_argument(
        "--lot", help="Fichier contenant plusieurs offres (URLs ou blocs separes par ---)"
    )
    parseur.add_argument("--cv", help="Chemin explicite vers un CV")
    parseur.add_argument(
        "--cv-auto",
        help="Mot-cle pour choisir un CV automatiquement (ex. these, entreprise)",
    )
    parseur.add_argument(
        "--sans-lettre",
        action="store_true",
        help="Faire seulement l'analyse / le score, sans generer de lettre",
    )
    parseur.add_argument(
        "--format",
        choices=["txt", "docx", "pdf"],
        default="txt",
        help="Format d'enregistrement de la lettre (defaut : txt)",
    )
    parseur.add_argument("--sortie", help="Fichier ou enregistrer la lettre (sans ext.)")
    args = parseur.parse_args()

    config.verifier_cle()
    agent = AgentCandidature()

    # 2) CV (commun aux deux modes)
    chemin_cv = choisir_cv(args.cv, args.cv_auto)
    cv = charger_cv(chemin_cv)
    print(f"\nCV utilise : {chemin_cv}")

    # Mode lot
    if args.lot:
        traiter_lot(args.lot, cv, agent, args.format)
        return

    # Mode unique
    source_offre = args.offre or lire_offre_interactive()
    if not source_offre.strip():
        sys.exit("Aucune offre fournie.")
    offre = extraire_offre(source_offre)

    print("\nAnalyse en cours...\n")
    analyse = agent.analyser(offre.texte, cv)
    afficher_analyse(offre, analyse)

    if args.sans_lettre:
        return

    print("\n" + "=" * 60)
    print("Redaction de la lettre...\n")
    lettre = agent.generer_lettre(offre.texte, cv, analyse)
    print("=" * 60)
    print("LETTRE DE MOTIVATION")
    print("=" * 60 + "\n")
    print(lettre)

    # Sauvegarde
    if args.sortie:
        chemin_sans_ext = args.sortie
    else:
        config.DOSSIER_SORTIE.mkdir(exist_ok=True)
        horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = _nom_fichier(offre.entreprise or offre.titre, "lettre")
        chemin_sans_ext = config.DOSSIER_SORTIE / f"lettre_{base}_{horodatage}"
    chemin = _ecrire_lettre(chemin_sans_ext, lettre, args.format)
    print(f"\nLettre enregistree : {chemin}")


if __name__ == "__main__":
    main()
