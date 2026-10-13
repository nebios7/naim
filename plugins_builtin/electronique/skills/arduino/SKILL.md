---
name: arduino
description: Programmer une carte Arduino ou ESP32 : écrire le croquis, compiler, téléverser en USB, lire le moniteur série.
---

# Arduino (et ESP32 / ESP8266) depuis le Mac

## Principe
Tu fais tout toi-même avec arduino-cli (run_command), tu n'expliques pas à l'utilisateur comment cliquer dans l'IDE.
Si `arduino-cli` manque : dis-lui d'ouvrir Personnaliser › Plugins › électronique › « Installer les outils ».

## 1. La carte branchée
```bash
arduino-cli board list                 # port (/dev/cu.usbmodem…) et modèle (FQBN, ex. arduino:avr:uno)
```
Rien de listé : câble seulement « charge » (sans données), carte non branchée, ou clone CH340 (il faut son pilote).
FQBN courants : `arduino:avr:uno`, `arduino:avr:nano`, `arduino:avr:mega`, `arduino:renesas_uno:unor4wifi`,
`esp32:esp32:esp32`, `esp8266:esp8266:nodemcuv2`.

## 2. Le cœur de la carte (une seule fois)
```bash
arduino-cli core update-index
arduino-cli core install arduino:avr                     # Uno, Nano, Mega
# ESP32 : ajouter son catalogue d'abord
arduino-cli config init 2>/dev/null; arduino-cli config add board_manager.additional_urls https://espressif.github.io/arduino-esp32/package_esp32_index.json
arduino-cli core update-index && arduino-cli core install esp32:esp32
```
Bibliothèques : `arduino-cli lib search dht` puis `arduino-cli lib install "DHT sensor library"`.

## 3. Le croquis
Un croquis = un dossier et un fichier du même nom : `Clignote/Clignote.ino`. Toujours `setup()` et `loop()`,
`Serial.begin(9600)` pour voir ce qui se passe. Commente les branchements en tête du fichier (broche → composant).

## 4. Compiler puis téléverser
```bash
arduino-cli compile --fqbn arduino:avr:uno Clignote
arduino-cli upload -p /dev/cu.usbmodem1101 --fqbn arduino:avr:uno Clignote
```
Lis l'erreur de compilation ligne par ligne et corrige ; ne téléverse jamais un croquis qui ne compile pas.
« Port busy » : le moniteur série est encore ouvert (arrête-le). ESP32 qui refuse : maintenir BOOT pendant l'envoi.

## 5. Le moniteur série (ce que la carte écrit)
Il ne s'arrête pas seul : lance-le avec start_process, lis process_output après quelques secondes, puis stop_process.
```bash
arduino-cli monitor -p /dev/cu.usbmodem1101 -c baudrate=9600
```

## Sécurité du matériel
Rappelle les résistances (LED : 220 Ω), jamais plus de 20 mA par broche sur un Uno, moteurs et servos alimentés à part
(masses reliées), 3,3 V pour un ESP32 (pas 5 V sur ses broches).
