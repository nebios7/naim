---
name: animations-web
description: Animations et effets modernes pour un site ou une app web — GSAP (animations, ScrollTrigger), Lenis (défilement fluide), React Bits (composants animés prêts à l'emploi).
---

# Animations web : GSAP, Lenis, React Bits

Trois bibliothèques de référence (dépôts GitHub greensock/GSAP, darkroomengineering/lenis, DavidHDev/react-bits).
Ajoute-les au projet, puis utilise-les avec mesure : une animation doit guider le regard, pas décorer.

## Choisir
- **GSAP** : apparitions, textes qui se révèlent, timelines, animations au défilement (ScrollTrigger). Pour tout projet.
- **Lenis** : défilement doux de toute la page (sites vitrines, portfolios, landing pages). Avec GSAP, synchronise-les.
- **React Bits** : composants animés tout faits (textes, fonds, cartes, curseurs) — seulement dans un projet React.

## Installer
- Projet npm (React, Vite, Next…) : `npm install gsap lenis`
- Page HTML simple (sans npm), avant ton script :
  `<script src="https://cdn.jsdelivr.net/npm/gsap@3.15/dist/gsap.min.js"></script>`
  `<script src="https://cdn.jsdelivr.net/npm/gsap@3.15/dist/ScrollTrigger.min.js"></script>`
  `<script src="https://unpkg.com/lenis/dist/lenis.min.js"></script>` puis `<link rel="stylesheet" href="https://unpkg.com/lenis/dist/lenis.css">`
- React Bits (projet React avec shadcn ; sinon d'abord `npx shadcn@latest init`) :
  `npx shadcn@latest add @react-bits/<Composant>-<JS|TS>-<CSS|TW>` — ex. `npx shadcn@latest add @react-bits/BlurText-TS-TW`
  (TS pour TypeScript, TW pour Tailwind ; les dépendances, gsap par exemple, s'installent toutes seules).
  Composants utiles : BlurText, SplitText, ShinyText, CountUp, FadeContent, AnimatedContent, Aurora, Particles, SpotlightCard.

## Recettes (copier puis adapter)
GSAP + ScrollTrigger (module) :
```js
import gsap from "gsap";
import ScrollTrigger from "gsap/ScrollTrigger";
gsap.registerPlugin(ScrollTrigger);

gsap.from(".hero h1", { y: 40, opacity: 0, duration: 0.9, ease: "power3.out" });
gsap.utils.toArray(".reveal").forEach((el) =>
  gsap.from(el, { y: 30, opacity: 0, duration: 0.8, ease: "power2.out",
                  scrollTrigger: { trigger: el, start: "top 85%" } }));
```
Lenis synchronisé avec GSAP :
```js
import Lenis from "lenis";
import "lenis/dist/lenis.css";
const lenis = new Lenis();
lenis.on("scroll", ScrollTrigger.update);
gsap.ticker.add((time) => lenis.raf(time * 1000));
gsap.ticker.lagSmoothing(0);
```
Lenis seul : `new Lenis({ autoRaf: true })`. En React, crée Lenis dans un `useEffect` et appelle `lenis.destroy()` au démontage ;
pour GSAP en React, utilise `useGSAP` (`npm install @gsap/react`) pour que tout se nettoie tout seul.

## Règles
- Respecte « réduire les animations » : `gsap.matchMedia().add("(prefers-reduced-motion: no-preference)", () => { … })`,
  et pas de Lenis si `matchMedia("(prefers-reduced-motion: reduce)").matches`.
- Anime `transform` et `opacity` (fluide), jamais `top`/`left`/`width`. Durées 0,4 à 1 s, une seule animation forte par écran.
- Le contenu doit rester lisible et cliquable sans JavaScript (n'appelle pas `opacity: 0` en CSS, laisse GSAP le faire).
- Vérifie dans le navigateur (capture) que rien ne saute ni ne reste invisible après le défilement.
