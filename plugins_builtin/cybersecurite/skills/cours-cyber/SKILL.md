---
name: cours-cyber
description: Apprendre la cybersécurité — expliquer une notion (chiffrement, hachage, XSS, injection SQL, réseau, authentification, malware, OWASP Top 10), faire un cours ou une fiche en PDF, préparer une certification, et aider sur des exercices d'entraînement et des CTF (web, crypto, forensique, reverse, stéganographie, réseau) sur des plateformes prévues pour ça.
---

# Cours de cybersécurité et CTF

## Expliquer une notion

1. **L'idée en une phrase**, avec une image de la vie courante (« un hachage, c'est une empreinte digitale :
   on reconnaît le doigt, on ne peut pas refaire le doigt »).
2. **Comment ça marche**, étape par étape, avec un schéma (`make_diagram`) quand il y a un échange (TLS, une
   connexion, une attaque XSS : qui envoie quoi à qui).
3. **Un exemple concret** : un petit code vulnérable, puis le même corrigé, à essayer sur sa machine
   (application locale, conteneur, page de test) — jamais sur un vrai site.
4. **Comment s'en protéger** ; **à retenir** en 3 points ; un **exercice** avec son corrigé à la fin.

## Un cours ou une fiche en PDF

Skill **pdf-pro** (couverture, sommaire, chapitres, encadrés « Définition », « Attention », « Exercice »), avec au
moins 3 sources fiables à la fin, par exemple : ANSSI (cyber.gouv.fr), cybermalveillance.gouv.fr, OWASP
(owasp.org), CNIL, MDN Web Docs, la documentation officielle de l'outil. Un plan type pour débuter :

1. Les bases : confidentialité, intégrité, disponibilité ; menaces, vulnérabilités, risques.
2. Les mots de passe et l'authentification (hachage, sel, double authentification, gestionnaire de mots de passe).
3. La cryptographie utile : symétrique / asymétrique, signatures, certificats, TLS.
4. Le réseau : IP, ports, DNS, HTTP/HTTPS, pare-feu, Wi-Fi.
5. Le web : OWASP Top 10 (injection, XSS, contrôle d'accès, configuration…), avec un exemple chacun.
6. Les attaques courantes : hameçonnage, rançongiciel, ingénierie sociale — et les bons réflexes.
7. Se protéger au quotidien : mises à jour, sauvegardes 3-2-1, chiffrement du disque, comptes séparés.
8. Pour aller plus loin : métiers, certifications (CompTIA Security+, CEH, OSCP, ISC2 CC), plateformes.

## CTF et exercices d'entraînement

Plateformes prévues pour s'entraîner : **Root-Me** (français), **TryHackMe**, **Hack The Box**, **PicoCTF**,
**OverTheWire** (Bandit pour débuter), **PortSwigger Web Security Academy** (le web, gratuit), les CTF de
CTFtime.org.

Méthode pour un défi :
1. Lis l'énoncé et la catégorie ; note ce qui est donné (fichier, adresse du défi, indice).
2. **Reconnaissance** : `file`, `strings`, `exiftool`, `xxd | head` sur un fichier ; pour un défi web, regarde le
   code de la page, les cookies, les requêtes (naim_browser).
3. Hypothèses par catégorie :
   - **web** : injection SQL (`' OR 1=1--`), XSS, IDOR (changer un identifiant), cookies modifiables, fichiers cachés (robots.txt, .git) ;
   - **crypto** : encodages (base64, hex, ROT13 — CyberChef), César/Vigenère, XOR, RSA à petits nombres ;
   - **forensique** : `binwalk`, métadonnées, fichiers supprimés, captures réseau (Wireshark / `tshark`) ;
   - **stéganographie** : `zsteg`, `steghide`, les bits de poids faible d'une image ;
   - **reverse** : `strings`, Ghidra, désassembler, chercher la comparaison qui vérifie le mot de passe ;
   - **réseau / système** : `nmap` sur la machine du défi, services, versions, élévation de privilèges (GTFOBins).
4. Avance par petites étapes, en expliquant chacune : le but est d'**apprendre**, donc l'utilisateur doit
   comprendre pourquoi ça marche. Donne d'abord un indice, la solution complète s'il la demande.
5. Le drapeau trouvé (`flag{…}`), résume ce qu'il fallait comprendre et comment on s'en protège dans la vraie vie.

Les outils (nmap, binwalk, steghide…) s'installent avec Homebrew quand l'utilisateur est d'accord. Les attaques
se font sur les machines des plateformes d'entraînement ou sur ses propres machines de test.
