#!/usr/bin/env python3
"""The devices of the user's OWN local network, read-only: who answers, their name, their open service ports.

    python3 scan.py                 the whole local network (the Mac's own /24), about 15 s
    python3 scan.py 192.168.1.20   one device, its ports in detail
    python3 scan.py --annonces      only what devices announce (their name, model and services), about 8 s

Devices that ignore the ping are found by what they announce on the network (Bonjour / mDNS): every announced kind
of service is asked, each device's name, model and services are shown as it gives them — no guess about makes.

Nothing is changed and nothing is sent but a ping and a connection attempt on a few well-known ports: it only looks.
It never leaves the local network (private addresses only).
"""
import ipaddress
import re
import socket
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

# the ports that say what a device is
PORTS = {22: "SSH", 53: "DNS", 80: "web", 443: "web https", 445: "partage de fichiers", 554: "RTSP (flux vidéo)",
         631: "imprimante", 1883: "MQTT (domotique)", 5000: "web", 8000: "web", 8080: "web", 8443: "web https",
         8554: "RTSP (flux vidéo)", 8899: "ONVIF (caméra)", 9100: "imprimante", 37777: "caméra Dahua", 34567: "caméra (DVR)",
         5555: "ADB (débogage Android)", 8008: "Google Cast", 8009: "Google Cast"}
CAMERA = {554, 8554, 8899, 37777, 34567}


def sh(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def own_network():
    """The Mac's address, its router and its /24 (the interface of the default route)."""
    route = sh(["route", "-n", "get", "default"])
    iface = (re.search(r"interface:\s*(\S+)", route) or [None, "en0"])[1]
    gateway = (re.search(r"gateway:\s*(\S+)", route) or [None, ""])[1]
    me = sh(["ipconfig", "getifaddr", iface]).strip()
    if not me:
        sys.exit("Pas de réseau local trouvé (Wi-Fi ou câble débranché ?).")
    net = ipaddress.ip_network(me + "/24", strict=False)
    if not net.is_private:
        sys.exit(f"{net} n'est pas un réseau local privé : rien n'est scanné.")
    return me, gateway, iface, net


def knock(ip, port, t=0.4):
    s = socket.socket(); s.settimeout(t)
    try:
        return s.connect_ex((ip, port)) == 0
    finally:
        s.close()


def alive(ip):
    """It answers the ping — or, like many cameras that ignore the ping, a web or video port."""
    if sh(["ping", "-c", "1", "-W", "500", "-t", "1", ip]).find(" 0.0% packet loss") >= 0:
        return ip
    return ip if any(knock(ip, p) for p in (554, 80, 8554, 443)) else None


def open_ports(ip, ports=PORTS, wait=0.35):
    def one(p):
        return p if knock(ip, p, wait) else None
    with ThreadPoolExecutor(32) as ex:
        return sorted(p for p in ex.map(one, ports) if p)


def names():
    """IP → (name, MAC) from the ARP table (filled by the pings)."""
    out = {}
    for line in sh(["arp", "-an"]).splitlines():
        m = re.search(r"\(([\d.]+)\) at ([0-9a-f:]+)", line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def host(ip):
    try:
        return socket.gethostbyaddr(ip)[0].replace(".local", "").replace(".home", "")
    except OSError:
        return ""


# what devices announce on the network (Bonjour / mDNS), read with the Mac's own dns-sd: every kind of service the
# network announces is asked first (the standard meta-query), then each one — nothing is listed in advance
def _service_types(seconds=2.5):
    import time
    pr = subprocess.Popen(["dns-sd", "-B", "_services._dns-sd._udp", "local."], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    time.sleep(seconds)
    pr.kill()
    out = pr.communicate()[0]
    types = set()
    for line in out.splitlines():
        m = re.search(r"\sAdd\s+\d+\s+\d+\s+\S+\s+(_\S+?)\.local\.?\s+(_\S+)\s*$", line)
        if m:
            types.add(f"{m.group(2)}.{m.group(1).split('.')[0]}")
    return sorted(types)


def announced(seconds=3.5):
    """[{ip, name, model, services, kind, system}] from Bonjour announcements, read-only."""
    import time
    types = _service_types()
    procs = {t: subprocess.Popen(["dns-sd", "-B", t, "local."], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
             for t in types}
    time.sleep(seconds)
    found = []
    for t, pr in procs.items():
        pr.kill()
        out = pr.communicate()[0]
        for line in out.splitlines():
            m = re.search(r"\sAdd\s+\d+\s+\d+\s+\S+\s+(\S+)\s+(.+?)\s*$", line)
            if m:
                found.append((t, m.group(2)))
    found = list(dict.fromkeys(found))
    # each announced name: its host, port and description (TXT), then its address
    look = {k: subprocess.Popen(["dns-sd", "-L", k[1], k[0], "local."], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
            for k in found}
    time.sleep(2.5)
    devices = {}
    for (t, inst), pr in look.items():
        pr.kill()
        out = pr.communicate()[0]
        m = re.search(r"can be reached at (\S+?)\.?:(\d+)", out)
        if not m:
            continue
        hostname = m.group(1)
        try:
            ip = socket.gethostbyname(hostname)
        except OSError:
            continue
        txt = dict(re.findall(r"(\w+)=((?:\\ |[^ ])+)", out))
        clean = lambda v: re.sub(r"\\(.)", r"\1", v or "").strip('"')
        d = devices.setdefault(ip, {"ip": ip, "name": "", "model": "", "services": [], "kind": "", "system": ""})
        d["services"].append(t.replace("._tcp", "").replace("._udp", " (udp)").lstrip("_"))
        name = clean(txt.get("fn")) or inst.replace("\\032", " ")
        if name and (not d["name"] or len(name) < len(d["name"]) or re.fullmatch(r"[\w-]{24,}|uuid:.*", d["name"])):
            d["name"] = name  # the shortest readable name it gives (not a long identifier)
        d["model"] = d["model"] or clean(txt.get("md") or txt.get("model") or txt.get("ty") or txt.get("product"))
    me = sh(["ipconfig", "getifaddr", "en0"]).strip() or sh(["ipconfig", "getifaddr", "en1"]).strip()
    if "127.0.0.1" in devices:  # this Mac answers its own announcements on the loopback
        d = devices.pop("127.0.0.1")
        d["ip"] = me or d["ip"]
        devices[d["ip"]] = d
    for d in devices.values():  # no guess about brands: what the device itself announces, for Naim to read and reason on
        if d["ip"] == me:
            d["kind"] = "ce Mac"
        d["services"] = sorted(set(d["services"]))
    return sorted(devices.values(), key=lambda d: ipaddress.ip_address(d["ip"]))


def kind(ports, ip, gateway, me=""):
    if ip == me:
        return "ce Mac"
    if ip == gateway:
        return "box / routeur"
    if CAMERA & set(ports):
        return "CAMÉRA probable"
    if 631 in ports or 9100 in ports:
        return "imprimante"
    if 445 in ports:
        return "ordinateur / NAS"
    if 22 in ports:
        return "ordinateur / Raspberry"
    if 5555 in ports:
        return "ADB ouvert (Android)"
    if {80, 443, 8080, 8000} & set(ports):
        return "appareil avec page web"
    return ""


def show_announced(devs):
    if not devs:
        print("Aucun appareil ne s'annonce sur le réseau.")
        return
    print(f"{'Adresse':<16}{'Nom annoncé':<30}{'Modèle annoncé':<22}Services annoncés")
    for d in devs:
        print(f"{d['ip']:<16}{(d['name'] + (' (ce Mac)' if d['kind'] == 'ce Mac' else ''))[:29]:<30}{d['model'][:21]:<22}{', '.join(d['services'])}")
    print("\nLe modèle et les services disent ce qu'est l'appareil : cherche le modèle sur le web si besoin, avant de conclure.")


def main():
    if sys.argv[1:2] == ["--annonces"]:
        own_network()
        show_announced(announced())
        return
    me, gateway, iface, net = own_network()
    if len(sys.argv) > 1:
        ip = sys.argv[1]
        if not ipaddress.ip_address(ip).is_private:
            sys.exit("Seules les adresses du réseau local (privées) sont testées.")
        # one device: more time for each port (a camera answers its RTSP port slowly)
        ports = open_ports(ip, {**PORTS, **{p: "" for p in (21, 23, 81, 88, 3000, 5543, 7070, 8001, 8081, 8088, 10554)}}, wait=1.5)
        print(f"{ip} {host(ip)} — ports ouverts : " + (", ".join(f"{p} {PORTS.get(p, '')}".strip() for p in ports) or "aucun des ports testés"))
        if CAMERA & set(ports):
            print("→ Caméra probable : teste son flux avec le skill camera-ip (sonde.py " + ip + ").")
        return
    print(f"Ce Mac : {me} ({iface}) · box : {gateway} · réseau : {net}\n")
    with ThreadPoolExecutor(64) as ex:
        up = [ip for ip in ex.map(alive, (str(h) for h in net.hosts())) if ip]
    macs = names()
    up = sorted(set(up) | {ip for ip in macs if ipaddress.ip_address(ip) in net and macs[ip] != "ff:ff:ff:ff:ff:ff"},
                key=lambda x: ipaddress.ip_address(x))
    print(f"{'Adresse':<16}{'Nom':<26}{'Type':<24}Ports ouverts")
    for ip in up:
        ports = open_ports(ip)
        name = "ce Mac" if ip == me else host(ip)
        print(f"{ip:<16}{name[:25]:<26}{kind(ports, ip, gateway, me):<24}" + ", ".join(f"{p} {PORTS[p]}" for p in ports))
    print(f"\n{len(up)} appareils qui répondent.\n\nCe que les appareils annoncent (même les appareils qui ne répondent pas au ping) :")
    show_announced(announced())


if __name__ == "__main__":
    main()
