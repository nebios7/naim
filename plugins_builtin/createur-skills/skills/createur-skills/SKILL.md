---
name: createur-skills
description: Créer un nouveau skill, ou améliorer un skill qui existe, et le TESTER avant de le livrer — ce qu'il doit faire, ses déclencheurs (les mots qui le chargent tout seul), ses instructions, des phrases de test, puis une version corrigée d'après ce qui a raté. À utiliser dès qu'on parle d'écrire, refaire, corriger, tester un skill ou de « transformer ça en skill ».
---

# Créer et améliorer un skill

Un skill est une méthode que tu suivras plus tard, quand tu auras tout oublié de cette conversation. Il doit donc se
suffire à lui-même : quand s'en servir, quoi faire, comment vérifier. Le travail se fait en boucle : comprendre,
écrire, tester, corriger — jusqu'à ce que les tests passent et que l'utilisateur soit content.

Si l'utilisateur veut juste « un skill vite fait » sans tests, fais-le ; sinon suis les étapes.

## 1. Comprendre ce que le skill doit faire
La conversation contient souvent déjà la réponse (« transforme ça en skill ») : les étapes suivies, les outils
utilisés, les corrections que l'utilisateur a faites, le format attendu. Pars de là, puis complète avec au plus trois
questions, seulement si une information manque vraiment :
1. Que doit faire le skill ? Avec quel résultat (un fichier, un bloc dans la conversation, une action sur le Mac) ?
2. Quand doit-il se charger ? Quelles phrases l'utilisateur écrit-il dans ce cas — et quelles phrases proches ne
   doivent PAS le charger ?
3. À quoi reconnaît-on un bon résultat ?

## 2. Écrire le skill
Avec create_skill : `nom` court (minuscules et tirets), `description`, `instructions`.

**La première ligne des instructions : les déclencheurs.** `déclencheurs: <expression régulière>` — les mots qui
chargent le skill tout seul (sans eux, le skill ne sert que si on le nomme). Exemple :
`déclencheurs: \b(recettes?|cuisiner?)\b[^.?!\n]{0,40}\b(rapides?|15 min|vite)\b`
- Les mots que l'utilisateur tape vraiment, avec leurs variantes (`recettes?`, `[ée]`), dans les deux ordres s'il le
  faut.
- Pas trop large : « recette » seul chargerait le skill pour toute question de cuisine. Pour écarter un sens voisin,
  un début `(?s)^(?!.*\b(excel|fichier)\b)` exclut les demandes qui contiennent ces mots.

**La description** dit ce que fait le skill ET quand s'en servir, en une ou deux phrases.

**Les instructions**, ensuite :
- Explique le POURQUOI de chaque règle plutôt que d'empiler des « TOUJOURS » et des « JAMAIS » : une règle comprise
  s'applique aussi aux cas que tu n'avais pas prévus.
- À l'impératif, concret, vérifiable (« le titre en une ligne, puis la liste »), jamais vague (« faire joli »).
- Le format du résultat, et un exemple complet et juste — l'exemple est ce qui guide le plus.
- Les pièges déjà rencontrés et comment les éviter.
- Court : moins de 300 lignes. Le détail rarement utile (une liste longue, un gabarit, un script) va dans un fichier à
  côté que le skill nomme et fait lire au bon moment.
- Rien de surprenant : un skill ne cache jamais une action que l'utilisateur n'attend pas.

## 3. Tester avant de livrer
**Les déclencheurs.** Écris 5 phrases qui doivent charger le skill et 4 phrases proches qui ne doivent pas, puis
vérifie-les pour de vrai avec run_command :
```bash
python3 -c "import re,sys; r=sys.argv[1]; [print('OUI' if re.search(r,p,re.I) else 'non', '|', p) for p in sys.argv[2:]]" '<expression>' 'phrase 1' 'phrase 2'
```
Une phrase mal classée : corrige l'expression et recommence jusqu'à ce que tout soit juste.

**Le résultat.** Prends 2 ou 3 demandes réalistes, comme l'utilisateur les écrirait (avec ses détails, pas des phrases
abstraites). Pour chacune : suis le skill (use_skill) et fais le travail, puis compare au bon résultat de l'étape 1.
Note ce qui a raté et pourquoi.

## 4. Corriger
- Corrige la MÉTHODE, pas l'exemple : si une demande de test a raté, demande-toi quelle règle manquait ou était mal
  expliquée, et écris-la pour tous les cas. Une règle taillée pour une seule phrase de test ne sert qu'une fois.
- Retire ce qui ne sert pas : une instruction que tu n'as pas suivie ou qui t'a fait perdre du temps.
- Si plusieurs tests t'ont fait écrire le même bout de code, mets-le dans un script à côté du skill.
- create_skill avec le même nom remplace la version précédente (l'utilisateur valide). Puis teste à nouveau.

## 5. Améliorer un skill qui existe
- Lis-le d'abord : son chemin est dans la liste des skills (read_file sur son SKILL.md).
- Un skill de l'utilisateur (dans ~/.naim/skills) : propose les changements, puis create_skill avec le même nom, et
  garde ses déclencheurs (première ligne) s'il en avait.
- Un skill fourni avec Naim (dans un plugin) : tu ne le modifies pas. Crée à côté un skill de l'utilisateur, avec ses
  propres déclencheurs, qui ajoute ce qui manque, et dis-le.

## 6. Répondre
Le nom du skill et son chemin, les phrases qui le chargent, ce que les tests ont donné (les déclencheurs et les
2 ou 3 demandes), et ce qu'il reste à améliorer s'il y a quelque chose.

---
Méthode adaptée du skill « skill-creator » (licence Apache 2.0, texte dans LICENSE.txt à côté), réécrite pour Naim :
ses outils, ses déclencheurs, des tests faits par Naim lui-même.
