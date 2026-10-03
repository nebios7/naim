"""Naim vs local models of the same size: HumanEval (code), tool calling (agent), speed. Same conditions for all:
Ollama, temperature 0, same prompts. Results -> results.json (resumable: finished model/task pairs are skipped)."""
import json
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import os

HERE = Path(__file__).parent  # put HumanEval.jsonl here (github.com/openai/human-eval, data/HumanEval.jsonl.gz)
OLLAMA = "http://localhost:11434"
# NAIM_BENCH_MODELS / NAIM_BENCH_OUT / NAIM_BENCH_HUMANEVAL: used by the automatic training to examine a candidate
MODELS = [m for m in os.environ.get("NAIM_BENCH_MODELS", "").split(",") if m] or [
    "naim:latest", "mimo:latest", "qwen2.5-coder:7b-instruct", "llama3.1:8b", "gemma4:e4b", "mistral-nemo:latest", "gemma3:12b"]
HUMANEVAL = Path(os.environ.get("NAIM_BENCH_HUMANEVAL", HERE / "HumanEval.jsonl"))
PROBLEMS = [json.loads(l) for l in HUMANEVAL.read_text().splitlines()][::4]  # 41 of 164
RES = Path(os.environ.get("NAIM_BENCH_OUT", HERE / "results.json"))
res = json.loads(RES.read_text()) if RES.exists() else {}


def chat(model, messages, tools=None, num_predict=900):
    for attempt in range(4):  # Ollama may drop the connection while swapping models
        try:
            return _chat(model, messages, tools, num_predict)
        except (ConnectionError, OSError) as e:
            if isinstance(e, urllib.error.HTTPError):
                raise
            time.sleep(10 * (attempt + 1))
    return {"error": "connexion perdue"}


def _chat(model, messages, tools=None, num_predict=900):
    body = {"model": model, "messages": messages, "stream": False, "think": False, "keep_alive": "10m",
            "options": {"temperature": 0, "seed": 1, "num_ctx": 8192, "num_predict": num_predict}}
    if tools:
        body["tools"] = tools
    req = urllib.request.Request(OLLAMA + "/api/chat", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        msg = e.read().decode()[:300]
        if e.code == 400 and "think" in body and "think" in msg.lower():  # models without a thinking mode refuse the flag
            body.pop("think")
            req = urllib.request.Request(OLLAMA + "/api/chat", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=600) as r:
                    return json.load(r)
            except urllib.error.HTTPError as e2:
                msg = e2.read().decode()[:300]
        return {"error": msg}


def extract_code(text, entry):
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", text, re.S)
    for b in blocks:
        if f"def {entry}" in b:
            return b
    return blocks[0] if blocks else text


def run_tests(code, prob):
    prog = code + "\n\n" + prob["test"] + f"\n\ncheck({prob['entry_point']})\n"
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(prog)
    try:
        r = subprocess.run([sys.executable, f.name], capture_output=True, timeout=15)
        return r.returncode == 0
    except subprocess.TimeoutExpired:
        return False


def save():
    RES.write_text(json.dumps(res, indent=1))


# ---------------------------------------------------------------- tool calling tasks (agent ability)
def T(name, desc, props, req):
    return {"type": "function", "function": {"name": name, "description": desc,
            "parameters": {"type": "object", "properties": {k: {"type": "string", "description": v} for k, v in props.items()}, "required": req}}}


TOOLS = [
    T("write_file", "Create or overwrite a file with the given content", {"path": "file path", "content": "full content"}, ["path", "content"]),
    T("read_file", "Read a text file", {"path": "file path"}, ["path"]),
    T("run_command", "Run a shell command and return its output", {"command": "shell command"}, ["command"]),
    T("web_search", "Search the web", {"query": "search query"}, ["query"]),
    T("send_email", "Send an email", {"to": "recipient address", "subject": "subject", "body": "message"}, ["to", "subject", "body"]),
    T("start_process", "Start a long-running program (web server) in the background", {"command": "shell command"}, ["command"]),
    T("get_weather", "Current weather for a city", {"city": "city name"}, ["city"]),
]
# (instruction, expected tool, {arg: regex that must match})
TASKS = [
    ("Crée un fichier hello.py qui affiche Bonjour.", "write_file", {"path": r"hello\.py", "content": r"print"}),
    ("Lis le fichier config.yaml.", "read_file", {"path": r"config\.ya?ml"}),
    ("Liste les fichiers du dossier courant.", "run_command", {"command": r"\bls\b"}),
    ("Cherche sur le web la dernière version de Python.", "web_search", {"query": r"(?i)python"}),
    ("Envoie un email à marie@exemple.com pour lui dire que la réunion est reportée à jeudi.", "send_email",
     {"to": r"marie@exemple\.com", "body": r"(?i)jeudi|thursday"}),
    ("Lance le serveur Flask avec python app.py pour que je puisse l'utiliser.", "start_process", {"command": r"python3? app\.py"}),
    ("Quel temps fait-il à Lyon ?", "get_weather", {"city": r"(?i)lyon"}),
    ("Installe le paquet requests avec pip.", "run_command", {"command": r"pip3? install .*requests"}),
    ("Écris un fichier README.md avec le titre « Mon projet ».", "write_file", {"path": r"README\.md", "content": r"Mon projet"}),
    ("Montre-moi le contenu de src/main.swift.", "read_file", {"path": r"src/main\.swift"}),
    ("Lance les tests avec pytest.", "run_command", {"command": r"pytest"}),
    ("Trouve la documentation officielle de SwiftUI NavigationStack.", "web_search", {"query": r"(?i)navigationstack"}),
    ("Create a file named notes.txt containing the word todo.", "write_file", {"path": r"notes\.txt", "content": r"(?i)todo"}),
    ("What's the weather like in Tokyo right now?", "get_weather", {"city": r"(?i)tokyo"}),
    ("Start the dev server with npm run dev.", "start_process", {"command": r"npm run dev"}),
    ("Envoie à paul@test.fr un email avec l'objet « Facture » et le texte « Voici la facture de septembre ».", "send_email",
     {"to": r"paul@test\.fr", "subject": r"(?i)facture"}),
    ("Affiche la version de git installée.", "run_command", {"command": r"git (--)?version"}),
    ("Crée un fichier .gitignore qui ignore le dossier node_modules.", "write_file", {"path": r"\.gitignore", "content": r"node_modules"}),
    ("Recherche les nouveautés de Swift 6.", "web_search", {"query": r"(?i)swift ?6"}),
    ("Ouvre et lis le fichier data/clients.csv.", "read_file", {"path": r"data/clients\.csv"}),
]


def tool_score(model):
    ok = 0
    detail = []
    for q, name, checks in TASKS:
        r = chat(model, [{"role": "system", "content": "You are an assistant that uses tools. Call exactly one tool."},
                         {"role": "user", "content": q}], tools=TOOLS, num_predict=400)
        if "error" in r:
            if "does not support tools" in r["error"]:
                return None, r["error"]  # the model has no tool calling at all
            detail.append(False)  # one malformed answer rejected by Ollama: this task fails
            continue
        calls = r.get("message", {}).get("tool_calls") or []
        good = False
        if calls:
            fn = calls[0]["function"]
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except ValueError:
                    args = {}
            good = fn.get("name") == name and all(re.search(rx, str(args.get(k, ""))) for k, rx in checks.items())
        ok += good
        detail.append(good)
    return ok, detail


PROMPT = ("Complete the following Python function. Answer with the complete function (with its imports) in a single "
          "```python code block, and nothing else.\n\n{prompt}")

for model in MODELS:
    m = res.setdefault(model, {})
    print(f"\n=== {model}", flush=True)
    if "code" not in m:
        passed, toks, secs, t0 = 0, 0, 0.0, time.time()
        for i, p in enumerate(PROBLEMS):
            r = chat(model, [{"role": "user", "content": PROMPT.format(prompt=p["prompt"])}])
            text = r.get("message", {}).get("content", "")
            code = extract_code(text, p["entry_point"])
            if f"def {p['entry_point']}" not in code:
                code = p["prompt"] + code
            passed += run_tests(code, p)
            toks += r.get("eval_count", 0)
            secs += r.get("eval_duration", 0) / 1e9
            print(f"  code {i + 1}/{len(PROBLEMS)} : {passed} réussis", end="\r", flush=True)
        m["code"] = {"passed": passed, "total": len(PROBLEMS), "tok_s": round(toks / secs, 1) if secs else None,
                     "minutes": round((time.time() - t0) / 60, 1)}
        save()
        print(f"  code : {passed}/{len(PROBLEMS)} · {m['code']['tok_s']} tok/s", flush=True)
    if "tools" not in m:
        score, detail = tool_score(model)
        m["tools"] = {"passed": score, "total": len(TASKS), "detail": detail}
        save()
        print(f"  outils : {score}/{len(TASKS)}", flush=True)
    # free memory before the next model
    urllib.request.urlopen(urllib.request.Request(OLLAMA + "/api/generate", data=json.dumps({"model": model, "keep_alive": 0}).encode()))
print("\nTERMINÉ", flush=True)
