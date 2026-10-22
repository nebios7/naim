---
name: cv-lettre
description: Faire ou enrichir un CV et une lettre de motivation, dans le style demandé (modèle joint, skill de style ou image).
---

# CV et lettre de motivation

## 1. Le contenu
- Il vient de l'utilisateur : texte collé, ou fichier joint (« fichier original : … » : lis-le avec read_file).
- N'invente aucun diplôme, poste, date, chiffre ni coordonnée. « Enrichir » = reformuler avec des verbes d'action,
  ordonner (le plus utile pour le poste d'abord), ajouter les mots-clés du poste visé et les compétences qui
  découlent de ce qui est écrit. Dis ensuite ce que tu as ajouté.

## 2. Le style (le plus important : c'est ce qui est demandé)
- **Un modèle HTML** (joint, « enregistré ici : … », ou un fichier du dossier) : NE RETAPE JAMAIS son HTML ni son CSS.
  Fais-le avec le script (il copie le modèle et ne change que les textes) :
  1. `textes.json` (write_file) : la liste des remplacements `[["texte tel qu'il est sur le modèle", "nouveau texte"], …]`,
     un par titre, ligne, poste, date… (lis d'abord le modèle avec read_file pour copier ses textes exacts).
  2. `python3 ~/.naim/plugins/candidature/skills/cv-lettre/remplir_modele.py "<modèle>" textes.json "<dossier>/CV_<Nom>.html"`
  3. Le script dit ce qu'il n'a pas trouvé, avec les textes proches : corrige ces lignes de textes.json et relance.
  Une section en plus : copie une section existante du CV produit avec multi_edit, puis change ses textes.
- **Une skill de style nommée** (design-style-gitingest…) : charge-la avec use_skill et suis ses valeurs exactes ;
  si son dossier contient `modele.html`, pars de ce fichier avec `cp`, comme ci-dessus.
- **Une image de référence** : reprends ce que tu vois (couleurs, polices, disposition, cartes, badges).
- **Rien de donné** : sobre, une colonne, A4, une couleur d'accent.

## 3. La lettre « avec le même style » : avec le script, jamais à la main
1. Termine d'abord le CV (`CV_<Nom>.html`).
2. Écris le texte de la lettre dans `lettre.txt` (write_file), blocs séparés par une ligne vide : lieu et date ;
   destinataire ; « Objet : … » ; « Madame, » ; 3 ou 4 paragraphes (le poste et pourquoi lui ; ce que j'apporte, avec
   des faits du CV ; ce que nous ferons ensemble) ; formule de politesse ; signature. 250 à 380 mots.
3. Lance : `python3 ~/.naim/plugins/candidature/skills/cv-lettre/lettre_depuis_cv.py "CV_<Nom>.html" lettre.txt "Lettre_motivation_<Nom>.html"`
   Le script reprend le style et l'en-tête du CV et ne garde AUCUNE section du CV : la lettre et le CV restent séparés.
4. Pas de .docx ni de .txt à rendre sauf si l'utilisateur le demande : un .docx joint est une SOURCE de contenu.

## 4. Livrer et vérifier
1. `convert_document` de chaque .html vers .pdf (A4).
2. `look_at` du PDF : le style est-il celui du modèle ? CV en 1-2 pages, lettre en 1 page ? Sinon corrige le .html
   (resserre les marges ou le texte) et reconvertis.
3. Réponds avec les chemins exacts des fichiers et ce qui a été enrichi. Jamais un fichier vide ou sans nom.
