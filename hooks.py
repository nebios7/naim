"""Hooks: commands the user sets to run by themselves at precise moments of Naim's work.

Files (same shape as the hooks of other coding agents, so they can be reused as they are):
  ~/.naim/hooks.json            for every project
  <project>/.naim/hooks.json    for this project only

  {"hooks": {
     "PreToolUse":       [{"matcher": "run_command|Bash", "hooks": [{"type": "command", "command": "…", "timeout": 30}]}],
     "PostToolUse":      [{"matcher": "write_file|edit_file", "hooks": [{"type": "command", "command": "…"}]}],
     "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "…"}]}],
     "Stop":             [{"hooks": [{"type": "command", "command": "…"}]}],
     "SessionStart":     [{"hooks": [{"type": "command", "command": "…"}]}],
     "PreCompact":       [{"hooks": [{"type": "command", "command": "…"}]}]
  }}
  (a group may also give "command" directly instead of "hooks").

Each command receives a JSON on its standard input (hook_event_name, tool_name, tool_input, tool_response, prompt,
last_answer, source, trigger, summary, cwd, session_id) and runs in the project folder.
  SessionStart: at the first message of a conversation; what it prints is added to Naim's context from the start.
  PreCompact:   just before Naim sums up its older steps; what it prints is kept in the summary.
  PostToolUseFailure: after an action that failed.   SessionEnd: when Naim has finished a task.
  exit 0  → fine; what it prints is added to Naim's context (UserPromptSubmit) or shown with the step. A plugin's
            hook written for another agent is read only at UserPromptSubmit, SessionStart and PreCompact, as that
            agent does (its other prints would fill Naim's memory at every action)
  exit 2  → blocks: the action is not done (PreToolUse), the message is not sent (UserPromptSubmit), Naim goes back
            to work (Stop) or reads it as a remark (PostToolUse) — the text printed on stderr says why
  a JSON on stdout {"decision": "block", "reason": "…"} or {"additionalContext": "…"} works too, and the
  {"hookSpecificOutput": {"permissionDecision": "deny", "permissionDecisionReason": "…", "additionalContext": "…"}} form.
  "async": true on a hook → started in the background, Naim does not wait for it.
Hooks of a plugin made for another agent receive its names: tool_name Bash/Write/Edit…, tool_input.file_path,
old_string/new_string, last_assistant_message.
"""
import threading
import json
import os
import re
import subprocess
from pathlib import Path

import extensions as ext

EVENTS = ("PreToolUse", "PostToolUse", "PostToolUseFailure", "UserPromptSubmit", "Stop", "SessionStart", "PreCompact",
          "SessionEnd")
TALKING = ("UserPromptSubmit", "SessionStart", "PreCompact")  # where another agent's hook prints for the agent to read
# the names other agents give to the same tools: their hooks work here unchanged
ALIASES = {"run_command": "Bash", "write_file": "Write", "edit_file": "Edit", "multi_edit": "Edit", "read_file": "Read",
           "web_fetch": "WebFetch", "web_search": "WebSearch", "list_files": "LS", "search": "Grep", "find_files": "Glob",
           "notebook_edit": "NotebookEdit", "delegate": "Task", "update_todos": "TodoWrite"}
FIELDS = {"path": "file_path", "old_text": "old_string", "new_text": "new_string"}  # their names for the same fields


def _foreign(payload, tool, root):
    """The payload under the names a hook written for another agent reads (Naim's own names kept alongside)."""
    data = dict(payload)
    if data.get("tool_name"):
        data["tool_name"] = ALIASES.get(tool, tool)
    a = data.get("tool_input")
    if isinstance(a, dict):
        a = dict(a)
        for k, v in FIELDS.items():
            if k in a and v not in a:
                a[v] = a[k]
        if isinstance(a.get("file_path"), str) and not os.path.isabs(os.path.expanduser(a["file_path"])):
            a["file_path"] = str(Path(root) / a["file_path"])
        data["tool_input"] = a
    if "last_answer" in data:
        data.setdefault("last_assistant_message", data["last_answer"])
    data.setdefault("permission_mode", "default")
    return data


def files(root):
    return [ext.HOME / "hooks.json", Path(root or ".").expanduser() / ".naim" / "hooks.json"]


def load(root):
    """{event: [{matcher, command, timeout, source}]} from the user's and the project's hooks files."""
    out = {}
    sources = []
    for f in files(root):
        try:
            sources.append((str(f), json.loads(f.read_text())))
        except (OSError, ValueError):
            continue
    try:  # the hooks of the plugins that are on
        import plugins
        sources += plugins.hook_sets()
    except Exception:  # noqa: BLE001 — a broken plugin never stops the user's own hooks
        pass
    for f, data in sources:
        root = str(data.get("root") or "")  # a plugin's hooks: its folder, in PLUGIN_DIR and the *_PLUGIN_ROOT they read
        foreign, extra_env = bool(data.get("foreign")), data.get("env") if isinstance(data.get("env"), dict) else {}
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
                                                          "timeout": float(h.get("timeout") or 60), "source": str(f), "root": root,
                                                          "foreign": foreign, "async": h.get("async") is True,
                                                          "env": extra_env})
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
        data = {**(_foreign(payload, tool, root) if h.get("foreign") else payload), "hook_event_name": event, "cwd": str(root)}
        stdin = json.dumps(data, ensure_ascii=False, default=str)
        env = {**os.environ, **h.get("env", {}), "NAIM_HOOK_EVENT": event, "NAIM_PROJECT": str(root),
               **({v: h["root"] for v in {"PLUGIN_DIR", *re.findall(r"\b([A-Z]+_PLUGIN_ROOT)\b", h["command"])}}
                  if h.get("root") else {})}
        if h.get("async"):  # in the background: Naim goes on at once
            try:
                p = subprocess.Popen(h["command"], shell=True, cwd=str(root), env=env, text=True, stdin=subprocess.PIPE,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                threading.Thread(target=p.communicate, args=(stdin,), kwargs={"timeout": h["timeout"]}, daemon=True).start()
            except OSError:
                pass
            continue
        try:
            r = subprocess.run(h["command"], shell=True, cwd=str(root), input=stdin, capture_output=True, text=True,
                               timeout=h["timeout"], env=env)
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
        dec = dec if isinstance(dec, dict) else None
        spec = (dec or {}).get("hookSpecificOutput")
        spec = spec if isinstance(spec, dict) else {}
        if (r.returncode == 2 or (dec and (dec.get("decision") == "block" or dec.get("continue") is False))
                or spec.get("permissionDecision") == "deny"):
            blocked = True
            msgs.append(spec.get("permissionDecisionReason") or (dec or {}).get("reason") or (dec or {}).get("stopReason")
                        or err or out or "bloqué par un hook")
        elif dec:
            if extra := dec.get("additionalContext") or spec.get("additionalContext"):
                ctx.append(str(extra)[:4000])
        elif out and (event in TALKING or not h.get("foreign")):
            ctx.append(out[:4000])
        elif r.returncode not in (0, 2) and err and not h.get("foreign"):  # another agent's hook failing on its own
            msgs.append(f"hook « {h['command'][:60]} » : erreur {r.returncode} — {err[:300]}")
    return blocked, "\n".join(msgs), "\n".join(ctx)
