#!/usr/bin/env python3
"""Security check-up of the user's own Mac and home network, read-only: what is well protected, what to fix, and how
(the exact place in Réglages Système, or the command to type). Nothing is changed, nothing is sent outside.

    python3 bilan.py            the Mac (firewall, FileVault, updates, screen lock, open services…)
    python3 bilan.py --reseau   + the local network: Wi-Fi security, the box, the devices and their risky ports
"""
import ipaddress
import json
import re
import socket
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ok, todo, info = [], [], []


def sh(cmd, timeout=20):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def add(good, what, fix="", level="moyenne"):
    (ok if good else todo).append((what, fix, level))


def mac():
    fw = sh(["/usr/libexec/ApplicationFirewall/socketfilterfw", "--getglobalstate"])
    add("enabled" in fw.lower() or "State = 1" in fw or "State = 2" in fw, "Pare-feu du Mac" + (" activé" if "enabled" in fw.lower() else " désactivé"),
        "Réglages Système › Réseau › Coupe-feu : activer. Il bloque les connexions entrantes non voulues (Wi-Fi public).", "haute")
    stealth = sh(["/usr/libexec/ApplicationFirewall/socketfilterfw", "--getstealthmode"])
    add("on" in stealth.lower() and "off" not in stealth.lower(), "Mode furtif du pare-feu" + (" activé" if "off" not in stealth.lower() else " désactivé"),
        "Réglages Système › Réseau › Coupe-feu › Options : « Activer le mode furtif » (le Mac ne répond plus aux sondes).", "faible")
    fv = sh(["fdesetup", "status"])
    add("On" in fv, "FileVault (chiffrement du disque)" + (" activé" if "On" in fv else " désactivé"),
        "Réglages Système › Confidentialité et sécurité › FileVault : activer. Sans lui, un Mac volé se lit en entier.", "haute")
    sip = sh(["csrutil", "status"])
    add("enabled" in sip, "Protection de l'intégrité du système (SIP)" + (" activée" if "enabled" in sip else " désactivée"),
        "Redémarrer en mode de récupération et taper `csrutil enable` (ne la désactive que pour un vrai besoin).", "haute")
    gk = sh(["spctl", "--status"])
    add("enabled" in gk, "Gatekeeper (applications vérifiées)" + (" actif" if "enabled" in gk else " inactif"),
        "Réglages Système › Confidentialité et sécurité : « App Store et développeurs identifiés ».", "haute")
    prefs = "/Library/Preferences/com.apple.SoftwareUpdate"
    crit = sh(["defaults", "read", prefs, "CriticalUpdateInstall"])
    auto = sh(["defaults", "read", prefs, "AutomaticallyInstallMacOSUpdates"])
    add(crit.strip() != "0", "Mises à jour de sécurité automatiques" + (" désactivées" if crit.strip() == "0" else " actives"),
        "Réglages Système › Général › Mise à jour de logiciels › Mises à jour automatiques : tout cocher.", "haute")
    if auto.strip() != "1":
        info.append("Les mises à jour de macOS ne s'installent pas toutes seules : pense à les faire (Général › Mise à jour de logiciels).")
    lock = sh(["sysadminctl", "-screenLock", "status"])
    m = re.search(r"delay is (\d+) seconds", lock)
    if "immediate" in lock.lower():
        add(True, "Mot de passe demandé dès la sortie de veille")
    elif m:
        d = int(m.group(1))
        add(d <= 300, f"Mot de passe demandé {d // 60} min après la mise en veille" if d < 3600 else f"Mot de passe demandé seulement {d // 3600} h après la mise en veille",
            "Réglages Système › Écran verrouillé : « Exiger le mot de passe » immédiatement (ou 5 minutes au plus).", "moyenne")
    elif "off" in lock.lower():
        add(False, "Aucun mot de passe à la sortie de veille", "Réglages Système › Écran verrouillé : « Exiger le mot de passe » immédiatement.", "haute")
    guest = sh(["defaults", "read", "/Library/Preferences/com.apple.loginwindow", "GuestEnabled"])
    add(guest.strip() != "1", "Compte invité" + (" activé" if guest.strip() == "1" else " désactivé"),
        "Réglages Système › Utilisateurs et groupes › Invité : désactiver.", "faible")
    ssh = sh(["nc", "-z", "-G", "1", "127.0.0.1", "22"])
    if ssh is not None and subprocess.run(["nc", "-z", "-G", "1", "127.0.0.1", "22"], capture_output=True).returncode == 0:
        todo.append(("Session à distance (SSH) ouverte sur ce Mac",
                     "Si tu ne t'en sers pas : Réglages Système › Général › Partage › Session à distance : désactiver.", "moyenne"))
    # services listening to the whole network (not only this Mac)
    seen = {}
    for line in sh(["lsof", "-nP", "-iTCP", "-sTCP:LISTEN"]).split("\n")[1:]:
        parts = line.split()
        if len(parts) < 9:
            continue
        prog, addr = parts[0].replace("\\x20", " "), parts[8]
        if addr.startswith(("127.", "[::1]", "localhost")):
            continue
        port = addr.rsplit(":", 1)[-1]
        seen.setdefault(prog, set()).add(port)
    known = {"rapportd": "service Apple (Continuité, AirDrop)", "ControlCe": "Récepteur AirPlay (Centre de contrôle)",
             "sharingd": "service Apple (partage)", "identityservicesd": "service Apple"}
    for prog, ports in sorted(seen.items()):
        name = known.get(prog)
        if name:
            info.append(f"{prog} écoute sur le réseau (ports {', '.join(sorted(ports))}) : {name}, normal.")
        else:
            todo.append((f"{prog} est joignable par tout le réseau (port {', '.join(sorted(ports))})",
                         f"Si c'est un serveur de développement, lance-le sur 127.0.0.1 (seulement ce Mac) ; sinon arrête-le "
                         f"(`lsof -nP -iTCP:{sorted(ports)[0]} -sTCP:LISTEN` pour le retrouver).", "moyenne"))
    ver = sh(["sw_vers", "-productVersion"])
    info.append(f"macOS {ver}.")


RISKY = {21: ("FTP", "mots de passe en clair"), 23: ("Telnet", "mots de passe en clair, à couper"),
         445: ("partage de fichiers SMB", "à fermer s'il n'est pas utilisé"), 3389: ("bureau à distance Windows", "à ne jamais exposer"),
         5900: ("partage d'écran VNC", "mot de passe souvent faible"), 1883: ("MQTT sans chiffrement", "domotique lisible par le réseau"),
         554: ("flux vidéo RTSP", "vérifier qu'un mot de passe le protège"), 8080: ("page web d'administration", "mot de passe par défaut ?"),
         80: ("page web (http, non chiffrée)", "mot de passe par défaut ?"), 2323: ("Telnet", "souvent laissé par les caméras bon marché"),
         1900: ("UPnP", "ouvre des ports tout seul sur la box"), 37777: ("caméra Dahua", "souvent ouverte sur Internet"),
         34567: ("enregistreur vidéo (DVR)", "failles connues, ne jamais l'exposer")}


def network():
    route = sh(["route", "-n", "get", "default"])
    iface = (re.search(r"interface:\s*(\S+)", route) or [None, "en0"])[1]
    gw = (re.search(r"gateway:\s*(\S+)", route) or [None, ""])[1]
    me = sh(["ipconfig", "getifaddr", iface]).strip()
    if not me:
        info.append("Pas de réseau local (Wi-Fi ou câble débranché) : partie réseau ignorée.")
        return
    wifi = sh(["system_profiler", "SPAirPortDataType", "-json"], timeout=40)
    try:
        cur = json.loads(wifi)["SPAirPortDataType"][0]["spairport_airport_interfaces"][0].get("spairport_current_network_information", {})
        sec = str(cur.get("spairport_security_mode", ""))
        if sec:
            weak = re.search(r"wep|none|open|wpa_personal(?!_mixed)|wpa1", sec, re.I) and "wpa2" not in sec.lower() and "wpa3" not in sec.lower()
            add(not weak, f"Sécurité du Wi-Fi : {sec.replace('spairport_security_mode_', '').replace('_', ' ')}",
                "Dans l'interface de la box : WPA2 ou WPA3 avec un mot de passe long (12 caractères ou plus).", "haute")
    except (ValueError, KeyError, IndexError):
        pass
    net = ipaddress.ip_network(me + "/24", strict=False)
    if not net.is_private:
        info.append("Réseau non privé : partie réseau ignorée.")
        return
    arp = sh(["arp", "-an"])
    hosts = sorted({m for m in re.findall(r"\((\d+\.\d+\.\d+\.\d+)\) at (?!\(incomplete\))", arp) if ipaddress.ip_address(m) in net and m != me},
                   key=lambda a: ipaddress.ip_address(a))

    def ping(a):
        return a if subprocess.run(["ping", "-c", "1", "-t", "1", a], capture_output=True).returncode == 0 else None
    with ThreadPoolExecutor(64) as ex:
        alive = {a for a in ex.map(ping, [str(h) for h in net.hosts()]) if a and a != me}
    hosts = sorted(set(hosts) | alive, key=lambda a: ipaddress.ip_address(a))

    def ports(a):
        found = []
        for p in RISKY:
            s = socket.socket()
            s.settimeout(0.4)
            try:
                if s.connect_ex((a, p)) == 0:
                    found.append(p)
            finally:
                s.close()
        return a, found
    with ThreadPoolExecutor(32) as ex:
        res = dict(ex.map(ports, hosts))
    info.append(f"{len(hosts)} appareils répondent sur le réseau {net} (box comprise). Liste détaillée : skill reseau-local.")
    for a, found in res.items():
        for p in found:
            what, why = RISKY[p]
            if a == gw and p in (80, 8080):
                todo.append((f"La box ({a}) a son interface d'administration en http (non chiffré)",
                             "Change le mot de passe administrateur d'origine de la box ; désactive l'administration à distance "
                             "depuis Internet et l'UPnP si tu ne t'en sers pas.", "moyenne"))
                continue
            lvl = "haute" if p in (21, 23, 2323, 3389, 34567) else "moyenne"
            todo.append((f"{a} : port {p} ouvert — {what}", f"{why[:1].upper() + why[1:]}{'' if why.endswith('?') else '.'} Ouvre la page de l'appareil, change son mot de passe "
                         "par défaut, coupe ce service s'il ne sert pas, mets à jour son logiciel.", lvl))


def report():
    order = {"haute": 0, "moyenne": 1, "faible": 2}
    todo.sort(key=lambda t: order.get(t[2], 1))
    out = ["# Bilan de sécurité", "", f"{len(ok)} points en ordre, {len(todo)} à améliorer.", ""]
    if todo:
        out.append("## À améliorer (du plus important au moins important)")
        for what, fix, lvl in todo:
            out += [f"- [{lvl.upper()}] {what}", f"  Comment : {fix}"]
        out.append("")
    if ok:
        out.append("## En ordre")
        out += [f"- {what}" for what, _, _ in ok]
        out.append("")
    if info:
        out.append("## Bon à savoir")
        out += [f"- {i}" for i in info]
    out += ["", "Rien n'a été modifié. Pour un réglage, l'utilisateur le change lui-même (ou te le demande clairement)."]
    return "\n".join(out)


if __name__ == "__main__":
    if sys.argv[1:2] in (["-h"], ["--help"]):
        sys.exit(__doc__)
    mac()
    if "--reseau" in sys.argv:
        network()
    print(report())
