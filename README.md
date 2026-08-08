# 🎯 Agent IA de candidature

Un agent qui lit une **offre d'emploi ou de thèse**, la compare à ton **CV**,
**score la correspondance** et **rédige une lettre de motivation** personnalisée.

Construit avec Python + l'API Google Gemini (palier gratuit). Deux façons de l'utiliser :
une **application web** (Streamlit) et une **ligne de commande** (CLI), toutes
deux basées sur le même cœur réutilisable.

---

## 1. Installation

Depuis le dossier `Agent_Candidature`, dans ton terminal :

```powershell
# (optionnel) activer ton environnement conda / venv d'abord
pip install -r requirements.txt
```

## 2. Configuration de la clé API

Copie le fichier d'exemple et renseigne ta clé :

```powershell
# PowerShell :
Copy-Item .env.example .env
# ou en cmd :
copy .env.example .env
```

Puis ouvre `.env` (`notepad .env`) et remplace la valeur de `GEMINI_API_KEY` par
ta clé **gratuite**, obtenue sur https://aistudio.google.com/apikey.

> Ta clé reste locale : `.env` est ignoré par git (voir `.gitignore`).

## 3. Utilisation

### Application web (recommandée pour une démo)

```powershell
python -m streamlit run app.py
```

Une page s'ouvre dans le navigateur : choisis ton CV dans la barre latérale,
colle l'offre (ou une URL), clique sur **Analyser et rédiger**.

L'application a deux onglets :

- **Une candidature** : analyse une offre, affiche le score, **comment postuler**
  (e-mail, contact, date limite) et rédige la lettre. Téléchargement en
  **TXT, Word (.docx) ou PDF**.
- **Traitement par lot** : colle plusieurs offres (une URL par ligne, ou des
  offres séparées par une ligne `---`). L'agent traite tout, affiche un tableau
  récapitulatif et fournit un **.zip** (toutes les lettres) + un **.csv** de suivi.

### Ligne de commande

```powershell
# Mode interactif (colle l'offre au clavier)
python cli.py

# Offre depuis une URL, CV choisi automatiquement par mot-clé
python cli.py --offre "https://exemple.com/offre" --cv-auto these

# Offre depuis un fichier, CV explicite, analyse seule (sans lettre)
python cli.py --offre offre.txt --cv "..\Candidatures_2026\CV_...html" --sans-lettre

# Enregistrer la lettre en PDF (ou docx)
python cli.py --offre offre.txt --format pdf

# Traitement par lot : plusieurs offres dans un fichier (URLs ou blocs ---)
python cli.py --lot offres.txt --cv-auto entreprise --format docx
```

Les lettres générées sont enregistrées dans `lettres_generees/` (le mode lot crée
un sous-dossier `lot_...` avec toutes les lettres et un `recapitulatif.csv`).

---

## Structure du projet

```
Agent_Candidature/
├── agent_candidature/        # cœur réutilisable
│   ├── agent.py              # appels Gemini : analyser() + generer_lettre()
│   ├── models.py             # structure de l'analyse (score, atouts, écarts...)
│   ├── prompts.py            # prompts système + utilisateur
│   ├── cv_loader.py          # lecture des CV (HTML / PDF / Word / texte)
│   ├── offre.py              # lecture de l'offre + extraction (titre, e-mail...)
│   ├── export.py             # export de la lettre en TXT / Word / PDF
│   └── config.py             # clé API, modèle, chemins (portables)
├── app.py                    # interface web Streamlit
├── cli.py                    # interface ligne de commande
├── requirements.txt
└── .env.example
```

## Comment ça marche

1. **Lecture** — l'offre et le CV sont convertis en texte brut.
2. **Analyse (sortie structurée)** — Gemini renvoie un objet typé : score /100,
   points forts, points faibles, compétences à valoriser, mots-clés, recommandation.
3. **Rédaction** — Gemini rédige la lettre en s'appuyant sur cette analyse.

> **Pourquoi pas de "RAG" ici ?** Un CV tient entièrement dans le contexte du
> modèle : lui donner le CV complet donne de meilleurs résultats qu'un système
> de recherche (RAG), qui n'a d'intérêt qu'au-delà de dizaines de documents.

## Publier l'application

**Sur le web (recommandé, gratuit) — Streamlit Community Cloud :**

1. Mets le code sur **GitHub** (dépôt public ou privé).
2. Va sur https://share.streamlit.io, connecte ton GitHub, choisis le dépôt et `app.py`.
3. Dans *Settings → Secrets*, ajoute ta clé :
   ```
   GEMINI_API_KEY = "AIza...ta-clé..."
   ```
4. Déploie : tu obtiens une URL publique (ex. `https://moussa-candidature.streamlit.app`)
   que tu peux partager ou mettre sur ton CV / LinkedIn.


