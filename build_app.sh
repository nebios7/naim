#!/usr/bin/env bash
# Build Naim.app: a macOS app that launches the Naim desktop window (naim.py).
# usage: build_app.sh APP_DIR PYTHON OUT_DIR   (APP_DIR/PYTHON are informative: the app finds them itself)
#   APP_DIR  folder containing naim.py / server.py / web/ (must be outside ~/Documents, ~/Desktop, ~/Downloads:
#            macOS blocks Finder-launched apps from reading those folders until the user grants access)
#   PYTHON   interpreter with pywebview installed
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
appdir="$1"
python="$2"
out="$3/Naim.app"

rm -rf "$out"
mkdir -p "$out/Contents/MacOS" "$out/Contents/Resources"

# icon
tmp="$(mktemp -d)"
swift "$here/make_icon.swift" "$tmp/icon.png"
mkdir "$tmp/Naim.iconset"
for s in 16 32 128 256 512; do
  sips -z $s $s "$tmp/icon.png" --out "$tmp/Naim.iconset/icon_${s}x${s}.png" >/dev/null
  sips -z $((s * 2)) $((s * 2)) "$tmp/icon.png" --out "$tmp/Naim.iconset/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$tmp/Naim.iconset" -o "$out/Contents/Resources/Naim.icns"
rm -rf "$tmp"

# native app (window, menus, WKWebView); it starts the Python engine as a child so macOS permissions apply to Naim.app
src="$(mktemp -d)"; cp "$here/NaimApp.swift" "$src/main.swift"   # the file with top-level code must be main.swift
swiftc -O "$src/main.swift" "$here/NaimInput.swift" "$here/NaimDictation.swift" -o "$out/Contents/MacOS/Naim" \
  -framework AppKit -framework WebKit -framework Speech -framework AVFoundation
rm -rf "$src"

cat > "$out/Contents/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Naim</string>
  <key>CFBundleDisplayName</key><string>Naim</string>
  <key>CFBundleIdentifier</key><string>com.redhamohamed.naim</string>
  <key>CFBundleVersion</key><string>3.0</string>
  <key>CFBundleShortVersionString</key><string>3.0</string>
  <key>CFBundleExecutable</key><string>Naim</string>
  <key>CFBundleIconFile</key><string>Naim</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSAppleEventsUsageDescription</key><string>Naim pilote Mail pour envoyer les emails que tu lui demandes.</string>
  <key>NSMicrophoneUsageDescription</key><string>Naim écoute ta voix quand tu cliques sur le micro, pour écrire ton message.</string>
  <key>NSSpeechRecognitionUsageDescription</key><string>Naim transforme ta voix en texte (sur ce Mac quand c'est possible).</string>
  <key>NSHumanReadableCopyright</key><string>© ABDESSEMED Mohamed</string>
</dict>
</plist>
EOF
codesign --force --deep -s - --identifier com.redhamohamed.naim "$out"
echo "built $out"
