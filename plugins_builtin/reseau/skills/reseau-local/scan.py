#!/usr/bin/env python3
"""The devices of the user's OWN local network, read-only: who answers, their name, their open service ports.

    python3 scan.py                 the whole local network (the Mac's own /24), about 10 s
    python3 scan.py 192.168.1.140   one device, its ports in detail

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
         8554: "RTSP (flux vidéo)", 8899: "ONVIF (caméra)", 9100: "imprimante", 37777: "caméra Dahua", 34567: "caméra (DVR)"}
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


def open_ports(ip, ports=PORTS):
    def one(p):
        return p if knock(ip, p, 0.35) else None
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
    if {80, 443, 8080, 8000} & set(ports):
        return "appareil avec page web"
    return ""


def main():
    me, gateway, iface, net = own_network()
    if len(sys.argv) > 1:
        ip = sys.argv[1]
        if not ipaddress.ip_address(ip).is_private:
            sys.exit("Seules les adresses du réseau local (privées) sont testées.")
        ports = open_ports(ip, {**PORTS, **{p: "" for p in (21, 23, 81, 88, 3000, 5543, 7070, 8001, 8081, 8088, 10554)}})
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
    print(f"\n{len(up)} appareils. Un appareil peut ne pas répondre au ping (téléphone en veille) : il n'apparaît alors pas.")


if __name__ == "__main__":
    main()
