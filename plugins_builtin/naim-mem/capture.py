"""naim-mem hook: keeps each request, each action that changes something, and each final answer. Never blocks Naim,
prints nothing (a UserPromptSubmit hook's output would be added to Naim's context)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import memoire  # noqa: E402

# what is worth remembering: actions that change things or bring something new (reading a file is not an event)
KEEP = {"write_file", "edit_file", "multi_edit", "delete_file", "move_file", "run_command", "start_process",
        "creer_fichier", "convert_document", "make_diagram", "send_email", "web_search", "web_fetch", "install_skill",
        "use_skill", "remember", "planifier", "use_mcp", "confier_tache", "computer", "simulator"}


def main():
    try:
        d = json.load(sys.stdin)
    except ValueError:
        return
    ev, session, projet = d.get("hook_event_name"), d.get("session_id", ""), d.get("cwd", "")
    if ev == "UserPromptSubmit":
        text = str(d.get("prompt") or "").strip()
        if text:
            memoire.add(session, projet, "demande", "", text.split("\n")[0][:200], text[:2000])
    elif ev == "PostToolUse":
        tool = d.get("tool_name") or ""
        if tool not in KEEP and not tool.startswith("mcp__"):
            return
        a = d.get("tool_input") or {}
        a = a if isinstance(a, dict) else {}
        what = a.get("path") or a.get("output") or a.get("nom") or a.get("command") or a.get("query") or a.get("url") or a.get("name") or ""
        res = str(d.get("tool_response") or "")
        memoire.add(session, projet, "action", tool, f"{tool} {str(what)[:160]}".strip(), res[:1500])
    elif ev == "Stop":
        text = str(d.get("last_answer") or "").strip()
        if text:
            memoire.add(session, projet, "résumé", "", text.split("\n")[0][:200], text[:3000])


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 — memory is a help: it never stops Naim's work
        pass
    sys.exit(0)
