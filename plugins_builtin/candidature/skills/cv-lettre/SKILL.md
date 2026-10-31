---
name: cv-lettre
description: Faire ou enrichir un CV et une lettre de motivation, dans le style demandé (modèle joint, skill de style ou image).
---

# CV et lettre de motivation

## 1. Le contenu
- Il vient de l'utilisateur : texte collé, ou fichier joint (« fichier original : … » : lis-le avec read_file).
  Un CV joint en Word ou en PDF est la SOURCE : on en tire le contenu, puis on fait le CV dans le style demandé
  (pdf-pro si rien n'est dit). On ne refait pas un Word, sauf si l'utilisateur demande un fichier Word : alors fais
  d'abord le CV comme ci-dessous, puis l'outil `convert_document` du .html vers un .docx (même nom, autre extension).
- Ne réécris JAMAIS un fichier joint : tes fichiers ont toujours un autre nom que les siens (CV_<Nom>.html,
  CV_<Nom>.pdf), dans un dossier à toi.
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
- **« Le style de mes PDF », « style pdf-pro », ou rien de donné** (le cas le plus courant) : PAS de textes.json,
  PAS de modèle à remplir. Écris `cv.json` (write_file) avec TOUTES les informations du CV source, puis UNE commande
  fait le CV dans le style pdf-pro ET son PDF, avec autant de postes, diplômes et projets qu'il en faut :
  `python3 ~/.naim/plugins/candidature/skills/cv-lettre/cv_pro.py cv.json "<dossier>/CV_<Nom>.html"`
  Le format de cv.json est en tête du script (lis-le avec read_file si besoin) : nom, titre, contact, profil,
  experiences, formations, sections (Projets, Publications, Certifications…), competences, langues, et « ordre »
  (l'ordre des rubriques du CV source, ex. ["profil", "competences", "experiences", "Projets", "formations"]).
  Une photo demandée : `"photo"` = le chemin de l'image jointe, ou du CV Word joint (sa photo est prise dedans) ;
  ronde, en haut à droite. N'écris jamais une image avec creer_fichier ou write_file (ce sont des fichiers texte).
  Fidèle = chaque poste, chaque diplôme, chaque projet, chaque date du source, avec ses lignes ; rien de retiré,
  rien d'ajouté. Le script donne les nombres (expériences, formations…) : compare-les avec le source. Pour corriger :
  change cv.json et relance la même commande (jamais d'édition du .html à la main).

## 3. La lettre « avec le même style » : avec le script, jamais à la main
1. Termine d'abord le CV (`CV_<Nom>.html`).
2. Écris le texte de la lettre dans `lettre.txt` (write_file), blocs séparés par une ligne vide : lieu et date ;
   destinataire ; « Objet : … » ; « Madame, » ; 3 ou 4 paragraphes (le poste et pourquoi lui ; ce que j'apporte, avec
   des faits du CV ; ce que nous ferons ensemble) ; formule de politesse ; signature. 250 à 380 mots.
3. Lance : `python3 ~/.naim/plugins/candidature/skills/cv-lettre/lettre_depuis_cv.py "CV_<Nom>.html" lettre.txt "Lettre_motivation_<Nom>.html"`
   Le script reprend le style et l'en-tête du CV et ne garde AUCUNE section du CV : la lettre et le CV restent séparés.
4. Pas de .docx ni de .txt à rendre sauf si l'utilisateur le demande : un .docx joint est une SOURCE de contenu.

## 4. Livrer et vérifier
1. Les deux scripts font AUSSI le PDF (style pdf-pro, A4), à côté du .html : leur dernière ligne dit « PDF : <chemin> ».
   Rien à convertir. S'ils disent « PDF non fait », utilise l'outil `convert_document` (un outil, pas une commande du
   Terminal). Si tu modifies un .html après coup, refais son PDF avec la commande que le script a donnée.
2. `look_at` du PDF : le style est-il celui du modèle ? CV en 1-2 pages, lettre en 1 page ? Sinon corrige le .html
   (resserre les marges ou le texte) et reconvertis.
3. Réponds avec les chemins exacts des PDF (le CV, la lettre) et ce qui a été enrichi. Seulement les PDF : les .html,
   .pro.html, textes.json et lettre.txt sont des brouillons, on ne les cite pas. Jamais un fichier vide ou sans nom.
