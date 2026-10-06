"""Send an email with the Mail app of this Mac (uses the accounts already configured in Mail).

The addresses, subject and body are passed as AppleScript arguments (never pasted into the script), so any
text can be sent safely. The first time, macOS asks to allow Naim to control Mail.
"""
import re
import subprocess
from pathlib import Path

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")

SCRIPT = '''on run argv
    set theSubject to item 1 of argv
    set theBody to item 2 of argv
    set nFiles to (item 3 of argv) as integer
    tell application id "com.apple.mail"
        set msg to make new outgoing message with properties {subject:theSubject, content:theBody, visible:false}
        tell msg
            repeat with i from (4 + nFiles) to count of argv
                make new to recipient at end of to recipients with properties {address:item i of argv}
            end repeat
            repeat with i from 4 to (3 + nFiles)
                make new attachment with properties {file name:(POSIX file (item i of argv))} at after the last paragraph
            end repeat
        end tell
        delay 1
        send msg
    end tell
    return "ok"
end run'''


class MailError(Exception):
    pass


CONTACT_SCRIPT = '''on run argv
    set out to ""
    tell application "Contacts"
        repeat with q in argv
            repeat with p in (every person whose name contains (q as text))
                if (count of emails of p) is 0 and (count of phones of p) is 0 then set out to out & (name of p) & tab & linefeed
                repeat with e in emails of p
                    set out to out & (name of p) & tab & (value of e) & linefeed
                end repeat
                repeat with t in phones of p
                    set out to out & (name of p) & tab & "tel:" & (value of t) & tab & (label of t) & linefeed
                end repeat
            end repeat
        end repeat
    end tell
    return out
end run'''


_OWN = []


def own_addresses():
    """The addresses of the Mail accounts of this Mac (the user's own), read once."""
    if not _OWN:
        r = subprocess.run(["osascript", "-e", 'tell application id "com.apple.mail" to get email addresses of every account'],
                           capture_output=True, text=True, timeout=30)
        _OWN.extend(addresses(r.stdout) or ["?"])
    return [a for a in _OWN if a != "?"]


def find_contact(name):
    """Email addresses of the Contacts app people whose name contains `name` (with and without accents).
    The first time, macOS asks to allow Naim to read the Contacts."""
    import unicodedata
    q = (name or "").strip()
    if not q:
        return []
    plain = "".join(c for c in unicodedata.normalize("NFD", q) if unicodedata.category(c) != "Mn")
    args = ["osascript", "-e", CONTACT_SCRIPT, q] + ([plain] if plain != q else [])
    r = subprocess.run(args, capture_output=True, text=True, timeout=60)
    if r.returncode != 0 and "-600" in r.stderr:  # Contacts is not running: start it in the background, then ask again
        subprocess.run(["open", "-g", "-j", "-a", "Contacts"], capture_output=True, timeout=20)
        import time
        for _ in range(10):
            time.sleep(1)
            r = subprocess.run(args, capture_output=True, text=True, timeout=60)
            if r.returncode == 0 or "-600" not in r.stderr:
                break
    if r.returncode != 0:
        raise MailError("Contacts inaccessibles : " + (r.stderr.strip()[-200:] or "autorisation refusée ?"))
    seen, out = set(), []
    for line in r.stdout.splitlines():
        if "\t" in line:
            parts = line.split("\t")
            n, a = parts[0].strip(), parts[1].strip()
            key = a.lower() or n.lower()
            if key not in seen:
                seen.add(key)
                if a.startswith("tel:"):  # a phone number (for an SMS, an iMessage or a call)
                    out.append({"nom": n, "email": "", "tel": a[4:].strip(), "label": (parts[2] if len(parts) > 2 else "").strip("_$!<>")})
                else:
                    out.append({"nom": n, "email": a})  # email "" = in Contacts without an address
    return out


def addresses(text):
    return sorted({a.lower() for a in EMAIL_RE.findall(text or "")})


SIMULATED = None  # a list while Naim checks itself: emails are recorded there instead of being sent


def send(to, subject, body, attachments=()):
    rcpt = addresses(to)
    if not rcpt:
        raise MailError("aucune adresse email valide")
    files = [str(Path(f).expanduser().resolve()) for f in attachments or ()]
    missing = [f for f in files if not Path(f).is_file()]
    if missing:
        raise MailError("pièce jointe introuvable : " + ", ".join(missing))
    if SIMULATED is not None:  # Naim's self-check: everything is verified, nothing leaves the Mac
        SIMULATED.append({"to": rcpt, "subject": subject, "attachments": files})
        return rcpt
    r = subprocess.run(["osascript", "-e", SCRIPT, subject or "(sans objet)", body or "", str(len(files)), *files, *rcpt],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        err = r.stderr.strip()
        if "-1743" in err or "not allowed" in err.lower():
            raise MailError("macOS n'autorise pas encore Naim à piloter Mail : Réglages Système → Confidentialité et "
                            "sécurité → Automatisation → Naim → coche « Mail »")
        if "-600" in err or "isn't running" in err:
            raise MailError("l'app Mail ne répond pas : ouvre-la une fois et vérifie qu'un compte email y est configuré")
        raise MailError(err[-300:] or "échec de l'envoi")
    return rcpt


# ---------------------------------------------------------------------- reading the inbox, drafts, junk
# Naim reads mail and prepares REPLY DRAFTS; it never sends a reply by itself and never deletes anything
# (spam is moved to Junk, which the user can undo). Processed messages are remembered in ~/.naim/mail_vus.json
# so an hourly task does not handle the same mail twice (the user's unread state is left untouched).
import json as _json
import os as _os

SEEN = Path(_os.environ.get("NAIM_HOME", Path.home() / ".naim")) / "mail_vus.json"
RS, US = "\x1e", "\x1f"  # record / field separators (never found in normal text)

READ_SCRIPT = '''on run argv
    set maxCount to (item 1 of argv) as integer
    set unreadOnly to (item 2 of argv) is "1"
    set RS to (character id 30)
    set US to (character id 31)
    set out to ""
    tell application id "com.apple.mail"
        if unreadOnly then
            set msgs to (messages of inbox whose read status is false)
        else
            set msgs to messages of inbox
        end if
        set n to count of msgs
        if n > maxCount then set n to maxCount
        repeat with i from 1 to n
            set m to item i of msgs
            set body to ""
            try
                set body to content of m
            end try
            if (length of body) > 4000 then set body to text 1 thru 4000 of body
            set acct to ""
            try
                set acct to name of account of mailbox of m
            end try
            set out to out & (id of m as string) & US & (sender of m) & US & (subject of m) & US & ((date received of m) as string) & US & acct & US & body & RS
        end repeat
    end tell
    return out
end run'''

DRAFT_SCRIPT = '''on run argv
    set mid to (item 1 of argv) as integer
    set replyText to item 2 of argv
    tell application id "com.apple.mail"
        set m to first message of inbox whose id is mid
        set r to reply m opening window false
        set content of r to replyText
        save r
    end tell
    return "ok"
end run'''

JUNK_SCRIPT = '''on run argv
    set mid to (item 1 of argv) as integer
    tell application id "com.apple.mail"
        set m to first message of inbox whose id is mid
        set junk mail status of m to true
        move m to junk mailbox
    end tell
    return "ok"
end run'''


def _osa(script, *args, timeout=180):
    r = subprocess.run(["osascript", "-e", script, *map(str, args)], capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        err = r.stderr.strip()
        if "-1743" in err or "not allowed" in err.lower():
            raise MailError("macOS n'autorise pas encore Naim à piloter Mail : Réglages Système → Confidentialité et "
                            "sécurité → Automatisation → Naim → coche « Mail »")
        if "-1719" in err or "-1728" in err:
            raise MailError("message introuvable (déjà déplacé ou supprimé ?)")
        raise MailError(err[-300:] or "Mail ne répond pas")
    return r.stdout


def _seen():
    try:
        return set(_json.loads(SEEN.read_text()))
    except (OSError, ValueError):
        return set()


def mark_seen(mid):
    ids = _seen() | {str(mid)}
    SEEN.parent.mkdir(parents=True, exist_ok=True)
    SEEN.write_text(_json.dumps(sorted(ids)[-5000:]))


def inbox(limit=20, unread_only=True, include_seen=False):
    """New messages of the inbox (all accounts): [{id, from, subject, date, account, body}]."""
    raw = _osa(READ_SCRIPT, max(1, min(int(limit or 20), 100)), "1" if unread_only else "0")
    seen = set() if include_seen else _seen()
    out = []
    for rec in raw.split(RS):
        parts = rec.strip("\n").split(US)
        if len(parts) < 6 or parts[0] in seen or parts[2].startswith("[Naim]"):
            continue  # Naim's own recaps are never processed again
        out.append({"id": parts[0], "from": parts[1], "subject": parts[2], "date": parts[3], "account": parts[4],
                    "body": parts[5].strip()})
    return out


def draft_reply(mid, text):
    """Create a reply DRAFT (saved in Drafts, not sent) and remember the message as processed."""
    _osa(DRAFT_SCRIPT, int(mid), text)
    mark_seen(mid)


def to_junk(mid):
    """Move a message to Junk (reversible) and remember it as processed."""
    _osa(JUNK_SCRIPT, int(mid))
    mark_seen(mid)
