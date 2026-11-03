---
name: email-pro
description: Écrire et envoyer un email bien structuré (objet clair, paragraphes courts, pièces jointes annoncées) avec des pièces jointes PDF soignées.
---

# Email soigné, pièces jointes PDF propres

La signature de Naim (« Naim · Assistant de … ») est ajoutée AUTOMATIQUEMENT sous chaque email envoyé et chaque
brouillon : ne l'écris pas toi-même, et ne signe pas du nom de l'utilisateur.

## 1. Le destinataire
- Adresse donnée par l'utilisateur, ou trouvée avec chercher_contact. Jamais inventée. Plusieurs personnes
  possibles : demande laquelle.
- Ton : vouvoiement pour un professionnel ou un inconnu ; tutoiement seulement si l'utilisateur tutoie cette personne.

## 2. L'email (texte simple, pas de Markdown : pas de **, pas de #)
- Objet : précis, 4 à 9 mots, sans « Re: » inventé. Ex. : « Devis maison T4 — plan et liste des matériaux ».
- Structure :
  1. Salutation : « Bonjour Sara, » (ou « Bonjour Madame Martin, »).
  2. Une phrase de contexte : pourquoi cet email.
  3. Le contenu, en paragraphes de 2 à 3 lignes ; une liste avec « - » si plus de deux éléments.
  4. Les pièces jointes, annoncées une par une :
     « Vous trouverez en pièce jointe :
     - Plan-maison-T4.pdf : le plan à l'échelle et les surfaces ;
     - Materiaux-maison-T4.pdf : la liste des matériaux. »
  5. Ce qui est attendu (une réponse, une date, une validation), en une phrase.
  6. Formule de politesse : « Bien cordialement, » (pro) ou « Bonne journée, » / « À bientôt, » (proche).
- 120 à 200 mots en général. Pas de phrases creuses (« J'espère que vous allez bien » seulement si l'utilisateur
  écrit ainsi), pas d'emoji dans un email professionnel.

## 3. Les pièces jointes
- Toujours en PDF (jamais .md, .html ou .txt envoyés tels quels), sauf si l'utilisateur demande un autre format.
- Partir du modèle `~/.naim/skills/email-pro/modele-document.html` : le copier dans le dossier de travail, remplacer
  TITRE, DATE, NOM DE L'UTILISATEUR et les sections par le vrai contenu (tableaux pour les chiffres, `<img>` pour les
  plans et schémas), puis convert_document en PDF.
- Nom du fichier : clair, sans espaces ni accents, avec le sujet et la date : `Devis-maison-T4-2026-10-08.pdf`.
- Vérifier CHAQUE PDF avec look_at avant l'envoi : accents corrects, rien ne déborde, tableaux lisibles, pas de
  « … » ni de texte du modèle oublié (TITRE, DATE).
- Rapport long ou dossier technique : suivre aussi le skill `rapport`.

## 4. Avant d'envoyer
Relire : orthographe, destinataire, objet, chaque pièce jointe annoncée existe bien et est jointe. Puis send_email.
Répondre à l'utilisateur en une phrase : à qui, l'objet, les pièces jointes.
