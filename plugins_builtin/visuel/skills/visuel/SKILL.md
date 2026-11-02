---
name: visuel
description: Afficher un visuel vivant DANS la conversation (horloge qui avance, carte, compteur, jauge, compte à rebours, petit tableau de bord, mini-calculatrice) avec un bloc ```visuel.
---

# Un visuel dans la conversation

Le visuel s'affiche DANS la conversation, à la place du bloc : pas de fichier, pas d'outil, pas d'Aperçu, jamais de
bloc ```html (il resterait du code). Ta réponse : une phrase courte, puis UN bloc ```visuel, puis rien ou une phrase.

## Le bloc
Du HTML (avec son `<style>` et son `<script>`), sans `<html>` ni `<head>` : il est posé dans une page déjà prête, à la
police et aux couleurs de Naim. Fermé par ``` sur sa propre ligne.

- Vivant : ce qui change (l'heure, un compte à rebours) est calculé par le script, jamais écrit en dur.
  `new Date()`, `setInterval(…, 1000)`, `toLocaleTimeString("fr-FR")`, `toLocaleDateString("fr-FR", {weekday: "long", day: "numeric", month: "long", year: "numeric"})`.
- Rien d'extérieur : ni police, ni image, ni bibliothèque, ni fetch (tout est bloqué). Icônes : SVG au trait dessinés
  dans le bloc. Jamais d'emoji.

## Le style (sobre et soigné, comme Naim)
- Couleurs de Naim, qui suivent le mode clair / sombre : `var(--text)`, `var(--muted)`, `var(--panel)` (fond de
  carte), `var(--side)`, `var(--line)` (bordures), `var(--brand)` (UNE touche d'accent, orange). Pas de dégradé
  violet, pas de couleurs criardes, pas de grosse ombre.
- Une carte : `background: var(--panel); border: 1px solid var(--line); border-radius: 16px; padding: 28px;`
  centrée (`margin: 0 auto`), largeur raisonnable (`max-width: 360px`) ; un « carré » : `aspect-ratio: 1`.
- Les chiffres : `font-variant-numeric: tabular-nums` (ils ne sautent pas), gros et fins (`font-size: 56px;
  font-weight: 300; letter-spacing: -1px`) ; le texte secondaire petit, `var(--muted)`, première lettre en majuscule.
- De l'air : peu d'éléments, bien alignés.

## Exemple : l'heure dans un carré
```visuel
<div class="c">
  <div class="t" id="t">--:--</div>
  <div class="s" id="s">--</div>
  <div class="d" id="d"></div>
</div>
<style>
  .c { width: 240px; aspect-ratio: 1; margin: 0 auto; display: flex; flex-direction: column; align-items: center;
       justify-content: center; gap: 6px; background: var(--panel); border: 1px solid var(--line); border-radius: 20px; }
  .t { font-size: 56px; font-weight: 300; letter-spacing: -1px; font-variant-numeric: tabular-nums; color: var(--text); }
  .s { font-size: 15px; color: var(--brand); font-variant-numeric: tabular-nums; }
  .d { font-size: 13px; color: var(--muted); }
  .d::first-letter { text-transform: uppercase; }
</style>
<script>
  const tick = () => {
    const n = new Date();
    t.textContent = n.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
    s.textContent = String(n.getSeconds()).padStart(2, "0") + " s";
    d.textContent = n.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" });
  };
  tick(); setInterval(tick, 1000);
</script>
```

## Pour finir
« Change la couleur », « plus grand », « ajoute les secondes » : redonne le bloc ```visuel entier, modifié. Un fichier
(logo, affiche, PNG, PDF) demandé explicitement : c'est un autre travail, pas ce bloc.
