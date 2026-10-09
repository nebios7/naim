"""Hooks: commands the user sets to run by themselves at precise moments of Naim's work.

Files (same shape as the hooks of other coding agents, so they can be reused as they are):
  ~/.naim/hooks.json            for every project
  <project>/.naim/hooks.json    for this project only

  {"hooks": {
     "PreToolUse":       [{"matcher": "run_command|Bash", "hooks": [{"type": "command", "command": "…", "timeout": 30}]}],
     "PostToolUse":      [{"matcher": "write_file|edit_file", "hooks": [{"type": "command", "command": "…"}]}],
     "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "…"}]}],
     "Stop":             [{"hooks": [{"type": "command", "command": "…"}]}]
  }}
  (a group may also give "command" directly instead of "hooks").

Each command receives a JSON on its standard input (hook_event_name, tool_name, tool_input, tool_response, prompt,
last_answer, cwd, session_id) and runs in the project folder.
  exit 0  → fine; what it prints is added to Naim's context (UserPromptSubmit) or shown with the step
  exit 2  → blocks: the action is not done (PreToolUse), the message is not sent (UserPromptSubmit), Naim goes back
            to work (Stop) or reads it as a remark (PostToolUse) — the text printed on stderr says why
  a JSON on stdout {"decision": "block", "reason": "…"} or {"additionalContext": "…"} works too.
"""
import json
import os
import re
import subprocess
from pathlib import Path

import extensions as ext

EVENTS = ("PreToolUse", "PostToolUse", "UserPromptSubmit", "Stop")
# the names other agents give to the same tools: their hooks work here unchanged
ALIASES = {"run_command": "Bash", "write_file": "Write", "edit_file": "Edit", "multi_edit": "Edit", "read_file": "Read",
           "web_fetch": "WebFetch", "web_search": "WebSearch", "list_files": "LS", "search": "Grep", "find_files": "Glob",
           "notebook_edit": "NotebookEdit", "delegate": "Task", "update_todos": "TodoWrite"}


def files(root):
    return [ext.HOME / "hooks.json", Path(root or ".").expanduser() / ".naim" / "hooks.json"]


def load(root):
    """{event: [{matcher, command, timeout, source}]} from the user's and the project's hooks files."""
    out = {}
    for f in files(root):
        try:
            data = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        for event, groups in (data.get("hooks") or {}).items():
            if event not in EVENTS or not isinstance(groups, list):
                continue
            for g in groups:
                if not isinstance(g, dict):
                    continue
                hs = g.get("hooks") if isinstance(g.get("hooks"), list) else ([g] if g.get("command") else [])
                for h in hs:
                    if isinstance(h, dict) and h.get("command"):
                        out.setdefault(event, []).append({"matcher": str(g.get("matcher") or ""), "command": str(h["command"]),
                                                          "timeout": float(h.get("timeout") or 60), "source": str(f)})
    return out


def _matches(matcher, tool):
    if not tool or matcher in ("", "*"):
        return True
    try:
        return any(re.fullmatch(matcher, t) for t in (tool, ALIASES.get(tool, "")) if t)
    except re.error:
        return matcher in (tool, ALIASES.get(tool))


def run(hooks, event, payload, root, tool=""):
    """Runs the hooks of an event. Returns (blocked, message, context)."""
    blocked, msgs, ctx = False, [], []
    for h in hooks.get(event, []):
        if not _matches(h["matcher"], tool):
            continue
        data = {**payload, "hook_event_name": event, "cwd": str(root)}
        try:
            r = subprocess.run(h["command"], shell=True, cwd=str(root), input=json.dumps(data, ensure_ascii=False, default=str),
                               capture_output=True, text=True, timeout=h["timeout"],
                               env={**os.environ, "NAIM_HOOK_EVENT": event, "NAIM_PROJECT": str(root)})
        except subprocess.TimeoutExpired:
            msgs.append(f"hook « {h['command'][:60]} » trop long ({h['timeout']:.0f} s) : ignoré")
            continue
        except OSError as e:
            msgs.append(f"hook « {h['command'][:60]} » impossible à lancer : {e}")
            continue
        out, err = (r.stdout or "").strip(), (r.stderr or "").strip()
        dec = None
        if out.startswith("{"):
            try:
                dec = json.loads(out)
            except ValueError:
                dec = None
        if r.returncode == 2 or (isinstance(dec, dict) and dec.get("decision") == "block"):
            blocked = True
            msgs.append(((dec or {}).get("reason") if isinstance(dec, dict) else None) or err or out or "bloqué par un hook")
        elif isinstance(dec, dict):
            if dec.get("additionalContext"):
                ctx.append(str(dec["additionalContext"]))
        elif out:
            ctx.append(out[:4000])
        elif r.returncode not in (0, 2) and err:
            msgs.append(f"hook « {h['command'][:60]} » : erreur {r.returncode} — {err[:300]}")
    return blocked, "\n".join(msgs), "\n".join(ctx)
