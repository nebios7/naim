#!/usr/bin/env bash
# Install (or update) Naim on this Mac.
#   runtime  ~/Library/Application Support/Naim  (app files + a small Python venv)
#   app      ~/Applications/Naim.app
#   model    ~/.naim/models  (given to Naim installations by Naim's server)
#   commands naim, naimtools  (Homebrew's bin, or ~/.local/bin)
# Re-running it updates Naim; it never touches your conversations, settings, skills or memory.
# NAIM_YES=1 answers « oui » to every question (installation non interactive).
#
# One command (nothing to download first):
#   curl -fsSL https://raw.githubusercontent.com/nebios7/naim/main/install.sh | bash
set -euo pipefail
REPO="nebios7/naim"
script="${BASH_SOURCE[0]:-}"   # empty when the script comes through a pipe (curl … | bash)
here=""
if [ -n "$script" ] && [ -f "$script" ]; then here="$(cd "$(dirname "$script")" && pwd)"; fi
if [ -z "$here" ] || [ ! -f "$here/naim.py" ]; then
  # run through `curl … | bash`: fetch the latest Naim sources, then run this installer from them
  [ "$(uname -s)" = Darwin ] || { echo "Naim fonctionne uniquement sur macOS (Apple Silicon conseillé)."; exit 1; }
  src="$HOME/.naim/source"
  printf "\033[1m%s\033[0m\n" "Naim — téléchargement de la dernière version"
  tmp="$(mktemp -d)"
  curl -fsSL "https://github.com/$REPO/archive/refs/heads/main.tar.gz" | tar -xz -C "$tmp" --strip-components 1
  rm -rf "$src" && mkdir -p "$(dirname "$src")" && mv "$tmp" "$src"
  if { : </dev/tty; } 2>/dev/null; then exec bash "$src/install.sh" "$@" </dev/tty; fi  # keep the questions interactive
  exec bash "$src/install.sh" "$@"
fi
dest="$HOME/Library/Application Support/Naim"
models="$HOME/.naim/models"
NAIM_SERVER="https://naim-feedback.contact-abdessemed.workers.dev"  # gives the model to Naim installations only

say()  { printf "\033[1m%s\033[0m\n" "$*"; }
ok()   { printf "  \033[32m✓\033[0m %s\n" "$*"; }
warn() { printf "  \033[33m⚠\033[0m %s\n" "$*"; }
ask()  { [ "${NAIM_YES:-}" = 1 ] && return 0; [ -t 0 ] || return 1; read -r -p "  $1 [o/N] " a; [[ "$a" =~ ^[oOyY] ]]; }
# a Naim installed with the one-line command updates itself by running the same command again

# ------------------------------------------------------------------ prerequisites
say "Naim — vérification du Mac"
[ "$(uname -s)" = Darwin ] || { echo "Naim fonctionne uniquement sur macOS."; exit 1; }
[ "$(uname -m)" = arm64 ] && ok "Mac Apple Silicon" || warn "Mac Intel : Naim fonctionnera, mais le modèle sera lent."
if ! xcode-select -p >/dev/null 2>&1 || ! command -v swiftc >/dev/null; then
  warn "Les outils de développement d'Apple (Xcode Command Line Tools) sont nécessaires."
  xcode-select --install 2>/dev/null || true
  echo "  Termine leur installation (fenêtre macOS), puis relance la même commande d'installation."; exit 1
fi
ok "Outils Xcode"
brew_bin=""
if command -v brew >/dev/null; then brew_bin="$(brew --prefix)/bin"; ok "Homebrew"; else warn "Homebrew absent (https://brew.sh) : conseillé pour llama.cpp."; fi

if command -v llama-server >/dev/null || [ -x /opt/homebrew/bin/llama-server ] || [ -x /usr/local/bin/llama-server ]; then
  ok "llama.cpp (moteur rapide de Naim)"
elif [ -n "$brew_bin" ] && ask "Installer llama.cpp (moteur de Naim) avec Homebrew ?"; then
  brew install llama.cpp && ok "llama.cpp installé"
else
  warn "llama.cpp absent : Naim utilisera Ollama s'il est installé (brew install llama.cpp pour le moteur rapide)."
fi
command -v xcodegen >/dev/null || [ -z "$brew_bin" ] || warn "xcodegen absent : utile pour les apps iOS (brew install xcodegen)."

# ------------------------------------------------------------------ model
say "Modèle"
mkdir -p "$models"
for f in naim-Q4_K_M.gguf naim-mmproj-f16.gguf; do
  src="$(cd "$here/.." && pwd)/gguf/$f"   # developer checkout: link the local build (no extra disk space)
  if [ -f "$src" ] && [ ! "$src" -ef "$models/$f" ]; then rm -f "$models/$f"; ln "$src" "$models/$f" 2>/dev/null || cp "$src" "$models/$f"; fi
done
if [ -f "$models/naim-Q4_K_M.gguf" ]; then
  ok "Modèle Naim présent"
elif ask "Télécharger le modèle Naim maintenant (6,5 Go) ?"; then
  # this installation's random identifier (also used, if you allow it, for the voluntary feedback sharing)
  [ -s "$HOME/.naim/install_id" ] || { mkdir -p "$HOME/.naim"; uuidgen | tr -d '-' | tr 'A-Z' 'a-z' > "$HOME/.naim/install_id"; }
  iid="$(tr -d '[:space:]' < "$HOME/.naim/install_id")"
  for f in naim-Q4_K_M.gguf naim-mmproj-f16.gguf; do
    [ -f "$models/$f" ] && continue
    echo "  → $f"
    curl -L --fail --retry 3 -C - --progress-bar -A "Naim/install" "$NAIM_SERVER/api/model/$f?install=$iid" -o "$models/$f.part" \
      && mv "$models/$f.part" "$models/$f" || warn "téléchargement de $f impossible (l'écran de bienvenue de Naim réessaiera)"
  done
  curl -s --fail -A "Naim/install" "$NAIM_SERVER/api/model-version" -o "$models/naim_version.json" 2>/dev/null || rm -f "$models/naim_version.json"
  ok "Modèle téléchargé"
else
  warn "Modèle pas encore téléchargé : l'écran de bienvenue de Naim proposera de le faire."
fi

# ------------------------------------------------------------------ app files
say "Installation de Naim"
mkdir -p "$dest/app" "$dest/bin"
cp "$here"/*.py "$here"/*.swift "$here/NAIM.default.md" "$dest/app/"
[ -f "$here/naim_prompts.json" ] && cp "$here/naim_prompts.json" "$dest/app/"  # owner's checkout; otherwise fetched from Naim's server
rm -rf "$dest/app/web" && cp -R "$here/web" "$dest/app/web"
mkdir -p "$dest/app/tools/benchmark" && cp "$here/tools/curate_feedback.py" "$dest/app/tools/" && cp "$here/tools/benchmark/bench.py" "$here/tools/benchmark/results.json" "$dest/app/tools/benchmark/"
# native helper for screen reading, clicks and PDF reading (rebuilt only when its source changes)
h="$(shasum "$here/naim_input.swift" | cut -c1-16)"
if [ "$(cat "$dest/bin/.naim-input.hash" 2>/dev/null)" != "$h" ] || [ ! -x "$dest/bin/naim-input" ]; then
  swiftc -O "$here/naim_input.swift" -o "$dest/bin/naim-input" 2>/dev/null && echo "$h" > "$dest/bin/.naim-input.hash" \
    && ok "naim-input compilé" || warn "naim-input non compilé"
fi
# HTML / Word / Markdown -> PDF with the Mac's WebKit (the convert_document tool)
h="$(shasum "$here/naim_pdf.swift" | cut -c1-16)"
if [ "$(cat "$dest/bin/.naim-pdf.hash" 2>/dev/null)" != "$h" ] || [ ! -x "$dest/bin/naim-pdf" ]; then
  swiftc -O "$here/naim_pdf.swift" -o "$dest/bin/naim-pdf" 2>/dev/null && echo "$h" > "$dest/bin/.naim-pdf.hash" \
    && ok "naim-pdf compilé" || warn "naim-pdf non compilé (il le sera au premier PDF)"
fi
# real browser Naim uses to test web apps (the browser tool)
h="$(shasum "$here/naim_browser.swift" | cut -c1-16)"
if [ "$(cat "$dest/bin/.naim-browser.hash" 2>/dev/null)" != "$h" ] || [ ! -x "$dest/bin/naim-browser" ]; then
  swiftc -O "$here/naim_browser.swift" -o "$dest/bin/naim-browser" 2>/dev/null && echo "$h" > "$dest/bin/.naim-browser.hash" \
    && ok "naim-browser compilé" || warn "naim-browser non compilé (il le sera au premier test web)"
fi
# optional private module (absent from the public sources)
if [ -f "$here/naim_train_window.swift" ]; then
  h="$(shasum "$here/naim_train_window.swift" | cut -c1-16)"
  if [ "$(cat "$dest/bin/.naim-train-window.hash" 2>/dev/null)" != "$h" ] || [ ! -x "$dest/bin/naim-train-window" ]; then
    swiftc -O "$here/naim_train_window.swift" -o "$dest/bin/naim-train-window" 2>/dev/null && echo "$h" > "$dest/bin/.naim-train-window.hash"
  fi
fi
# Mermaid (diagrams drawn in the chat and exported by Naim), kept locally so it works offline
if [ ! -s "$dest/vendor/mermaid.min.js" ]; then
  mkdir -p "$dest/vendor"
  curl -fsSL "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js" -o "$dest/vendor/mermaid.min.js" \
    && ok "Mermaid (schémas)" || { rm -f "$dest/vendor/mermaid.min.js"; warn "Mermaid non téléchargé (il le sera au premier schéma)"; }
fi

# Python environment (the engine uses only the standard library; pywebview is for `naim --window`)
if [ ! -x "$dest/venv/bin/python" ]; then
  if command -v uv >/dev/null; then uv venv --python 3.12 -q "$dest/venv"; else python3 -m venv "$dest/venv"; fi
fi
python="$dest/venv/bin/python"
if command -v uv >/dev/null; then uv pip install -q --python "$python" pywebview 2>/dev/null || true
else "$python" -m pip install -q pywebview 2>/dev/null || true; fi
ok "Environnement Python"

# terminal commands
bin="${brew_bin:-$HOME/.local/bin}"
[ -w "$bin" ] || bin="$HOME/.local/bin"
mkdir -p "$bin"
for cmd in naim naimtools; do
  cat > "$bin/$cmd" <<EOF
#!/bin/bash
exec "$python" "$dest/app/$cmd.py" "\$@"
EOF
  chmod +x "$bin/$cmd"
done
case ":$PATH:" in *":$bin:"*) ;; *) warn "Ajoute $bin à ton PATH pour les commandes naim / naimtools." ;; esac

# Rebuild Naim.app only when the native app or its icon change: a new build gets a new signature and macOS would
# forget the permissions (Accessibility, Screen Recording, Automation) the user granted.
apphash="$(cat "$here/NaimApp.swift" "$here/NaimInput.swift" "$here/build_app.sh" "$here/make_icon.swift" | shasum | cut -c1-16)"
if [ "$(cat "$dest/.app-build-hash" 2>/dev/null)" != "$apphash" ] || [ ! -d "$HOME/Applications/Naim.app" ]; then
  "$here/build_app.sh" "$dest/app" "$python" "$dest" >/dev/null 2>&1
  mkdir -p "$HOME/Applications"
  rm -rf "$HOME/Applications/Naim.app"
  cp -R "$dest/Naim.app" "$HOME/Applications/Naim.app"
  rm -rf "$dest/Naim.app"  # one Naim.app only: two identical apps confuse Spotlight and the Dock
  echo "$apphash" > "$dest/.app-build-hash"
  warn "Naim.app (re)construite : si tu avais donné des autorisations macOS à Naim, réactive-le dans Réglages Système."
else
  ok "Naim.app inchangée (autorisations macOS conservées)"
fi

say "Naim installé :"
echo "  • Application : ~/Applications/Naim.app (Launchpad / Spotlight « Naim »)"
echo "  • Terminal    : naim (ouvre l'app), naim --web (navigateur), naimtools (agent en terminal)"
