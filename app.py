"""Interface web (Streamlit) de l'agent de candidature.

Lancement :
    python -m streamlit run app.py
"""

import csv
import io
import re
import zipfile
from datetime import datetime

import streamlit as st

from agent_candidature import AgentCandidature, config
from agent_candidature import export
from agent_candidature.cv_loader import charger_cv, charger_cv_bytes, lister_cv
from agent_candidature.offre import OffreExtraite, extraire_offre

# --------------------------------------------------------------------------- #
# Coordonnees de l'auteur (modifie librement ces valeurs)
# --------------------------------------------------------------------------- #
AUTEUR = {
    "nom": "Moussa Diallo",
    "titre": "Ingenieur Mathematiques Appliquees, Data Science & IA",
    "email": "diallomoussa052001@gmail.com",
    "telephone": "07 49 65 53 27",
    "github": "https://github.com/dialloalassane052001-ui",
}

st.set_page_config(page_title="Agent de candidature", layout="wide")


# --------------------------------------------------------------------------- #
# Utilitaires
# --------------------------------------------------------------------------- #
def _nom_fichier(base: str, defaut: str = "lettre") -> str:
    """Transforme un texte libre en nom de fichier sain (sans accents ni symboles)."""
    base = (base or "").strip() or defaut
    base = re.sub(r"[^\w\s-]", "", base, flags=re.ASCII).strip()
    base = re.sub(r"[\s]+", "_", base)
    return base[:60] or defaut


def _decouper_offres(brut: str) -> list[str]:
    """Decoupe une saisie multiple en une liste de sources d'offres.

    Regles :
    - une ligne de 3 tirets ou plus (---) separe deux offres collees ;
    - sinon, si toutes les lignes non vides sont des URLs, chaque ligne = une offre ;
    - sinon, tout le texte est considere comme une seule offre.
    """
    brut = (brut or "").strip()
    if not brut:
        return []

    blocs = re.split(r"(?m)^\s*-{3,}\s*$", brut)
    blocs = [b.strip() for b in blocs if b.strip()]
    if len(blocs) > 1:
        return blocs

    lignes = [ligne.strip() for ligne in brut.splitlines() if ligne.strip()]
    if lignes and all(ligne.startswith(("http://", "https://")) for ligne in lignes):
        return lignes

    return [brut]


def _cle_serveur() -> str | None:
    """Cle API cote serveur : secrets Streamlit (deploiement) ou .env (local)."""
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return str(st.secrets["GEMINI_API_KEY"])
    except Exception:
        pass
    return config.GEMINI_API_KEY


def _emails_offre(analyse, offre: OffreExtraite) -> list[str]:
    """Reunit les e-mails detectes (analyse LLM + reperage automatique)."""
    emails: list[str] = []
    if analyse.email_candidature:
        emails.append(analyse.email_candidature)
    for email in offre.emails:
        if email not in emails:
            emails.append(email)
    return emails


# --------------------------------------------------------------------------- #
# En-tete
# --------------------------------------------------------------------------- #
st.title("Agent de candidature")
st.caption(
    "Colle une offre (emploi ou these) et importe ton CV : l'agent evalue le "
    "match, identifie tes atouts, repere comment postuler et redige ta lettre."
)

# --------------------------------------------------------------------------- #
# Barre laterale : configuration
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.header("Configuration")

    cle_utilisateur = st.text_input(
        "Cle API Gemini (optionnel)",
        type="password",
        help="Laisse vide pour utiliser la cle par defaut. "
        "Cle gratuite : https://aistudio.google.com/apikey",
    )
    if not cle_utilisateur and not _cle_serveur():
        st.error("Aucune cle API disponible. Renseigne une cle Gemini ci-dessus.")

    st.divider()

    source_cv = st.radio(
        "Ton CV",
        options=["Importer mon CV", "Choisir un CV d'exemple"],
        index=0,
    )

    cv_upload = None
    cv_exemple = None

    if source_cv == "Importer mon CV":
        cv_upload = st.file_uploader(
            "Televerse ton CV",
            type=["pdf", "docx", "html", "htm", "txt", "md"],
            help="Formats acceptes : PDF, Word (.docx), HTML, texte.",
        )
    else:
        cvs = lister_cv(config.DOSSIER_CV)
        if not cvs:
            st.warning(f"Aucun CV d'exemple trouve dans :\n{config.DOSSIER_CV}")
        else:
            cv_exemple = st.selectbox(
                "CV d'exemple", options=cvs, format_func=lambda p: p.name
            )

    st.caption(f"Modele : `{config.MODELE}`")


def _charger_cv_choisi() -> str | None:
    """Charge le CV selectionne dans la barre laterale, ou None si absent."""
    if cv_upload is not None:
        return charger_cv_bytes(cv_upload.name, cv_upload.getvalue())
    if cv_exemple is not None:
        return charger_cv(cv_exemple)
    return None


def _construire_agent() -> AgentCandidature:
    return AgentCandidature(api_key=cle_utilisateur or None)


# --------------------------------------------------------------------------- #
# Onglets principaux : candidature unique / traitement par lot
# --------------------------------------------------------------------------- #
onglet_unique, onglet_lot = st.tabs(
    ["Une candidature", "Traitement par lot (plusieurs offres)"]
)


# ======================= ONGLET : CANDIDATURE UNIQUE ======================= #
with onglet_unique:
    sous_texte, sous_url = st.tabs(["Coller l'offre", "Depuis une URL"])
    with sous_texte:
        offre_texte = st.text_area(
            "Texte de l'offre",
            height=260,
            placeholder="Colle ici le contenu complet de l'offre...",
        )
    with sous_url:
        offre_url = st.text_input("URL de l'offre", placeholder="https://...")
        st.caption(
            "Astuce : l'agent lit automatiquement les fiches structurees de la "
            "plupart des sites (Indeed, Welcome to the Jungle, France Travail...). "
            "Si un site bloque la lecture, copie-colle le texte dans l'autre onglet."
        )

    lancer = st.button(
        "Analyser et rediger", type="primary", use_container_width=True
    )

    if lancer:
        source = (offre_url or "").strip() or (offre_texte or "").strip()
        if not source:
            st.error("Renseigne une offre (texte ou URL).")
            st.stop()

        try:
            with st.spinner("Lecture de l'offre et du CV..."):
                offre = extraire_offre(source)
                cv = _charger_cv_choisi()
                if cv is None:
                    st.error("Importe ton CV (ou choisis un CV d'exemple) a gauche.")
                    st.stop()

            agent = _construire_agent()

            with st.spinner("Analyse de la correspondance..."):
                analyse = agent.analyser(offre.texte, cv)

            if offre.resume_source():
                st.success(f"Offre detectee : {offre.resume_source()}")

            col_score, col_reco = st.columns([1, 2])
            with col_score:
                st.metric("Score de match", f"{analyse.score_global}/100")
                st.progress(min(max(analyse.score_global, 0), 100) / 100)
            with col_reco:
                st.subheader("Recommandation")
                st.write(analyse.recommandation)

            st.subheader("Resume de l'offre")
            st.write(analyse.resume_offre)

            col_forts, col_faibles = st.columns(2)
            with col_forts:
                st.subheader("Points forts")
                for p in analyse.points_forts:
                    st.markdown(f"- {p}")
            with col_faibles:
                st.subheader("Points a renforcer")
                for p in analyse.points_faibles:
                    st.markdown(f"- {p}")

            st.subheader("A mettre en avant")
            for c in analyse.competences_a_mettre_en_avant:
                st.markdown(f"- {c}")

            st.subheader("Mots-cles de l'offre")
            st.write(", ".join(analyse.mots_cles_offre))

            # -- Comment postuler ------------------------------------------- #
            emails = _emails_offre(analyse, offre)
            infos = [
                ("Contact", analyse.contact_candidature),
                ("Date limite", analyse.date_limite),
                ("Procedure", analyse.procedure_candidature),
            ]
            infos = [(lib, val) for lib, val in infos if val]
            if emails or infos:
                st.subheader("Comment postuler")
                if emails:
                    st.write("E-mail(s) : " + ", ".join(emails))
                    sujet = f"Candidature - {offre.titre}" if offre.titre else "Candidature"
                    st.markdown(
                        f"[Preparer l'e-mail](mailto:{emails[0]}?subject={sujet})"
                    )
                for lib, val in infos:
                    st.write(f"{lib} : {val}")

            # -- Lettre ----------------------------------------------------- #
            with st.spinner("Redaction de la lettre de motivation..."):
                lettre = agent.generer_lettre(offre.texte, cv, analyse)

            st.subheader("Lettre de motivation")
            st.text_area("Lettre (modifiable)", value=lettre, height=420)

            base = _nom_fichier(offre.entreprise or offre.titre, "lettre")
            horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
            nom = f"lettre_{base}_{horodatage}"

            col_txt, col_docx, col_pdf = st.columns(3)
            with col_txt:
                st.download_button(
                    "Telecharger .txt",
                    data=export.lettre_vers_txt(lettre),
                    file_name=f"{nom}.txt",
                    mime="text/plain",
                    use_container_width=True,
                )
            with col_docx:
                st.download_button(
                    "Telecharger Word (.docx)",
                    data=export.lettre_vers_docx(lettre),
                    file_name=f"{nom}.docx",
                    mime="application/vnd.openxmlformats-officedocument."
                    "wordprocessingml.document",
                    use_container_width=True,
                )
            with col_pdf:
                st.download_button(
                    "Telecharger .pdf",
                    data=export.lettre_vers_pdf(lettre),
                    file_name=f"{nom}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )

        except Exception as exc:  # affichage lisible des erreurs dans l'UI
            st.error(f"Une erreur est survenue : {exc}")


# ======================== ONGLET : TRAITEMENT PAR LOT ====================== #
with onglet_lot:
    st.write(
        "Traite plusieurs offres d'un coup avec le meme CV. Pour chaque offre, "
        "l'agent calcule le score, repere comment postuler et redige une lettre. "
        "Tu recuperes toutes les lettres et un tableau recapitulatif."
    )
    st.markdown(
        "**Format de saisie** : soit une **URL par ligne**, soit plusieurs offres "
        "collees, separees par une ligne contenant uniquement `---`."
    )

    lot_brut = st.text_area(
        "Offres a traiter",
        height=240,
        placeholder="https://site1.com/offre-a\n"
        "https://site2.com/offre-b\n\n"
        "ou colle plusieurs offres separees par une ligne ---",
    )
    format_lot = st.radio(
        "Format des lettres exportees",
        options=["Word (.docx)", "PDF", "Texte (.txt)"],
        horizontal=True,
    )
    lancer_lot = st.button(
        "Traiter toutes les offres", type="primary", use_container_width=True
    )

    if lancer_lot:
        sources = _decouper_offres(lot_brut)
        if not sources:
            st.error("Colle au moins une offre.")
            st.stop()

        cv = _charger_cv_choisi()
        if cv is None:
            st.error("Importe ton CV (ou choisis un CV d'exemple) a gauche.")
            st.stop()

        agent = _construire_agent()

        lignes_recap: list[dict] = []
        archives: list[tuple[str, bytes]] = []
        barre = st.progress(0.0, text="Traitement en cours...")
        erreurs: list[str] = []

        for i, source in enumerate(sources, 1):
            barre.progress(i / len(sources), text=f"Offre {i}/{len(sources)}...")
            try:
                offre = extraire_offre(source)
                analyse = agent.analyser(offre.texte, cv)
                lettre = agent.generer_lettre(offre.texte, cv, analyse)
            except Exception as exc:
                erreurs.append(f"Offre {i} : {exc}")
                continue

            emails = _emails_offre(analyse, offre)
            base = _nom_fichier(offre.entreprise or offre.titre or f"offre_{i}")
            nom_lettre = f"{i:02d}_{base}"

            if format_lot.startswith("Word"):
                archives.append((f"{nom_lettre}.docx", export.lettre_vers_docx(lettre)))
            elif format_lot.startswith("PDF"):
                archives.append((f"{nom_lettre}.pdf", export.lettre_vers_pdf(lettre)))
            else:
                archives.append((f"{nom_lettre}.txt", export.lettre_vers_txt(lettre)))

            lignes_recap.append(
                {
                    "numero": i,
                    "titre": offre.titre,
                    "entreprise": offre.entreprise,
                    "lieu": offre.lieu,
                    "score": analyse.score_global,
                    "email_candidature": ", ".join(emails),
                    "date_limite": analyse.date_limite,
                    "recommandation": analyse.recommandation,
                    "fichier_lettre": archives[-1][0],
                    "source": offre.url_source or "(texte colle)",
                }
            )

        barre.empty()

        if erreurs:
            st.warning("Certaines offres n'ont pas pu etre traitees :\n\n" +
                       "\n".join(f"- {e}" for e in erreurs))

        if not lignes_recap:
            st.error("Aucune offre n'a pu etre traitee.")
            st.stop()

        st.success(f"{len(lignes_recap)} offre(s) traitee(s).")

        # Tableau recapitulatif (affichage).
        st.subheader("Recapitulatif")
        st.dataframe(
            [
                {
                    "#": r["numero"],
                    "Offre": r["titre"] or r["source"],
                    "Entreprise": r["entreprise"],
                    "Score": r["score"],
                    "E-mail": r["email_candidature"],
                }
                for r in lignes_recap
            ],
            use_container_width=True,
            hide_index=True,
        )

        # Construction du CSV recap.
        tampon_csv = io.StringIO()
        colonnes = list(lignes_recap[0].keys())
        writer = csv.DictWriter(tampon_csv, fieldnames=colonnes)
        writer.writeheader()
        writer.writerows(lignes_recap)
        csv_bytes = tampon_csv.getvalue().encode("utf-8-sig")  # BOM = accents OK Excel

        # Construction du ZIP (lettres + recap.csv).
        tampon_zip = io.BytesIO()
        with zipfile.ZipFile(tampon_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for nom, donnees in archives:
                zf.writestr(nom, donnees)
            zf.writestr("recapitulatif.csv", csv_bytes)

        horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
        col_zip, col_csv = st.columns(2)
        with col_zip:
            st.download_button(
                "Telecharger tout (.zip)",
                data=tampon_zip.getvalue(),
                file_name=f"candidatures_{horodatage}.zip",
                mime="application/zip",
                use_container_width=True,
            )
        with col_csv:
            st.download_button(
                "Telecharger le recap (.csv)",
                data=csv_bytes,
                file_name=f"recapitulatif_{horodatage}.csv",
                mime="text/csv",
                use_container_width=True,
            )


# --------------------------------------------------------------------------- #
# Pied de page
# --------------------------------------------------------------------------- #
st.divider()
st.markdown(
    f"""
<div style="text-align:center; color:gray; font-size:0.9em;">
  Cree par <b>{AUTEUR['nom']}</b>, {AUTEUR['titre']}<br>
  {AUTEUR['email']} &nbsp;·&nbsp; <a href="{AUTEUR['github']}">GitHub</a>
</div>
""",
    unsafe_allow_html=True,
)
