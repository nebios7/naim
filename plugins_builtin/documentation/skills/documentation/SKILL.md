---
name: documentation
description: Vérifier dans la documentation au lieu de deviner — l'aide exacte de ce qui est installé sur le Mac (module Python, commande, module Node), puis la page officielle (docs.python.org, MDN, nodejs.org, ffmpeg.org…).
---

# Consulter la documentation

Avant d'utiliser une fonction, une option ou une syntaxe dont tu n'es pas SÛR (nom, paramètres, valeur renvoyée), et
toujours après une erreur « n'existe pas » (`cannot import name`, `has no attribute`, `unknown option`…) : vérifie,
ne devine pas une autre version.

```bash
D="$HOME/.naim/plugins/documentation/skills/documentation"
python3 "$D/doc.py" python datetime.datetime.strftime   # l'aide du Python installé (version exacte) ; le .venv du projet s'il existe
python3 "$D/doc.py" python sympy                        # un module : la liste de ce qui existe vraiment, puis son aide
python3 "$D/doc.py" cmd ffmpeg                          # une commande : son manuel ou --help
python3 "$D/doc.py" node fs.readFile                    # un module Node : ce qu'il exporte + sa page nodejs.org
python3 "$D/doc.py" web css grid-template-columns       # la page officielle d'un sujet (MDN, docs.python.org, react.dev…)
```

## Dans quel ordre
1. **Ce qui est installé** (python / cmd / node) : c'est la vérité pour CETTE machine et CETTE version.
   « X n'existe pas dans Y. Noms proches : … » te donne le vrai nom.
2. **Le site officiel** (web) : pour un sujet du web (HTML, CSS, JavaScript) ou ce qui n'est pas installé.
3. Rien trouvé : web_search « <bibliothèque> <fonction> documentation », puis web_fetch de la page officielle
   (pas un forum en premier).

## Ensuite
Utilise le nom et les paramètres lus, exactement. Dis en une phrase ce que tu as vérifié si c'était douteux
(« d'après l'aide de Python 3.15, strftime prend le format en premier argument »).
