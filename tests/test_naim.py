"""Naim's regression tests: what broke once must not break again. No model, no engine needed.

    python3 -m unittest discover -s tests -v
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import llamacpp  # noqa: E402
import naimtools  # noqa: E402

llamacpp.note_error = lambda *a: None  # tests never write to the user's error log


class ToolArguments(unittest.TestCase):
    """A small model often breaks the JSON of its tool calls: what can be mended is, the rest is said."""

    def test_valid(self):
        self.assertEqual(llamacpp._args('{"path": "a.py", "content": "x"}'), {"path": "a.py", "content": "x"})

    def test_raw_line_break(self):
        self.assertEqual(llamacpp._args('{"content": "a\nb"}')["content"], "a\nb")

    def test_lone_backslash(self):
        self.assertEqual(llamacpp._args(r'{"pattern": "\d+", "path": "C:\dossier"}'), {"pattern": r"\d+", "path": r"C:\dossier"})

    def test_escaped_backslash_kept(self):
        self.assertEqual(llamacpp._args(r'{"a": "\\d"}'), {"a": r"\d"})

    def test_cut_call_closed_and_flagged(self):
        args = llamacpp._args('{"path": "a.html", "content": "<p>fin')
        self.assertEqual(args["content"], "<p>fin")
        self.assertTrue(args["_maybe_cut"])

    def test_unreadable_is_said(self):
        self.assertIn("_unreadable", llamacpp._args('{"a": "x" "y"}'))


class EngineSlots(unittest.TestCase):
    """Chat (0) and Agent (1) keep what they have read: side requests never land in their slot."""

    def setUp(self):
        self._n, llamacpp.total_slots = llamacpp.total_slots, lambda: 3

    def tearDown(self):
        llamacpp.total_slots = self._n

    def slot(self, messages, options):
        return llamacpp._payload(messages, None, False, False, options, False).get("id_slot")

    def test_main_conversations_keep_their_slot(self):
        sysmsg = [{"role": "system", "content": "s"}, {"role": "user", "content": "x"}]
        self.assertEqual(self.slot(sysmsg, {"slot": 0}), 0)
        self.assertEqual(self.slot(sysmsg, {"slot": 1}), 1)

    def test_side_request_goes_to_background(self):
        self.assertEqual(self.slot([{"role": "user", "content": "résume"}], {"slot": 1}), 2)

    def test_no_slot_goes_to_background(self):
        self.assertEqual(self.slot([{"role": "system", "content": "s"}], {}), 2)


class Compaction(unittest.TestCase):
    """A compaction re-reads the whole prompt: it must free real room (down to ~40%), keep calls before their results
    and leave the last step whole."""

    def test_frees_room(self):
        a = naimtools.Agent.__new__(naimtools.Agent)
        a.options, a._task_idx, a.todos, a.tools = {"num_ctx": 32768}, 1, [], []
        a._room = lambda: 32768
        a._written_summary = lambda old: "résumé"
        a.messages = [{"role": "system", "content": "s " * 8000}, {"role": "user", "content": "tâche"}]
        for i in range(8):
            a.messages += [{"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "read_file", "arguments": {"path": f"f{i}"}}}]},
                           {"role": "tool", "tool_name": "read_file", "content": "x " * 12000}]
        a._compact_history()
        self.assertLess(a._ctx_tokens(), 32768 * 0.6)
        self.assertEqual(a.messages[-1]["content"], "x " * 12000)
        for i, m in enumerate(a.messages):
            if m["role"] == "tool":
                self.assertIn(a.messages[i - 1]["role"], ("assistant", "tool"))


class AutoMode(unittest.TestCase):
    """Mode Auto (« Tout autoriser »): no question at each step; only what is typed or paid on screen stays asked."""

    def agent(self, asked):
        a = naimtools.Agent.__new__(naimtools.Agent)
        a.scheduled, a.power, a._allow_once, a.auto_yes = False, False, False, True
        a.auto_writes = a.auto_commands = a.auto_mcp = a.auto_computer = False
        a.approver = lambda action, detail: asked.append(action) or False
        return a

    def test_nothing_asked(self):
        asked = []
        a = self.agent(asked)
        for kind in ("write", "command", "mcp", "computer"):
            self.assertTrue(a.approve("Exécuter", "$ ls", kind=kind), kind)
        self.assertEqual(asked, [])

    def test_sensitive_screen_action_still_asked(self):
        asked = []
        self.assertFalse(self.agent(asked).approve("⚠ Action sensible à l'écran", "carte", kind="sensitive"))
        self.assertEqual(len(asked), 1)


class AdaptiveThinking(unittest.TestCase):
    """Naim thinks where it pays (planning, after a failure), briefly; routine steps go straight on."""

    def agent(self, step, results=(), think=False):
        a = naimtools.Agent.__new__(naimtools.Agent)
        a.think, a.features, a._step = think, {}, step
        a.messages = [{"role": "user", "content": "fais l'app"}, {"role": "assistant", "content": "", "tool_calls": []}]
        a.messages += [{"role": "tool", "content": r} for r in results]
        return a

    def test_plans_first(self):
        self.assertTrue(self.agent(1)._think_now())

    def test_routine_goes_on(self):
        self.assertFalse(self.agent(4, ["exit code 0\nok", "wrote app.py"])._think_now())

    def test_failure_makes_it_think(self):
        for r in ("exit code 1\nboom", "error: file not found", "Traceback (most recent call last):\n  x",
                  "===== 2 FAILED, 3 passed =====", "BUILD FAILED"):
            self.assertTrue(self.agent(5, ["wrote a.py", r])._think_now(), r)

    def test_switch_on_means_always(self):
        self.assertTrue(self.agent(7, ["exit code 0"], think=True)._think_now())

    def test_budget_sent_only_for_a_short_thought(self):
        msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "x"}]
        short = llamacpp._payload(msgs, None, True, False, {"think_budget": 800}, False)
        self.assertEqual(short["reasoning_budget_tokens"], 800)
        self.assertNotIn("reasoning_budget_tokens", llamacpp._payload(msgs, None, True, False, {}, False))
        self.assertNotIn("reasoning_budget_tokens", llamacpp._payload(msgs, None, False, False, {"think_budget": 800}, False))


class StartAndCompactHooks(unittest.TestCase):
    """A new conversation knows where the git project stands; SessionStart and PreCompact hooks are heard."""

    def test_project_state(self):
        with tempfile.TemporaryDirectory() as d:
            run = lambda *a: subprocess.run(["git", *a], cwd=d, capture_output=True)  # noqa: E731
            run("init", "-b", "main"); run("-c", "user.name=t", "-c", "user.email=t@t", "commit", "--allow-empty", "-m", "premier")
            Path(d, "app.py").write_text("x = 1\n")
            a = naimtools.Agent.__new__(naimtools.Agent)
            a.root = Path(d)
            state = a._project_state()
            self.assertIn("Branche : main", state)
            self.assertIn("app.py", state)
            self.assertIn("premier", state)

    def test_session_start_hook_adds_context(self):
        import hooks
        h = {"SessionStart": [{"matcher": "", "command": "echo tickets ouverts : 3", "timeout": 10, "source": "t"}]}
        blocked, _, ctx = hooks.run(h, "SessionStart", {"source": "startup"}, tempfile.gettempdir())
        self.assertFalse(blocked)
        self.assertEqual(ctx, "tickets ouverts : 3")

    def test_pre_compact_hook_kept_in_summary(self):
        import time
        a = naimtools.Agent.__new__(naimtools.Agent)
        a.options, a._task_idx, a.todos, a.tools, a.run_id, a.root = {"num_ctx": 32768}, 1, [], [], "t", Path(tempfile.gettempdir())
        a._hk, a._hk_at = {"PreCompact": [{"matcher": "", "command": "echo ne pas toucher a la base de prod", "timeout": 10, "source": "t"}]}, time.time() + 60
        a.emit = lambda ev: None
        a._room = lambda: 32768
        a._written_summary = lambda old: "résumé"
        a.messages = [{"role": "system", "content": "s " * 8000}, {"role": "user", "content": "tâche"}]
        for i in range(8):
            a.messages += [{"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "read_file", "arguments": {"path": f"f{i}"}}}]},
                           {"role": "tool", "tool_name": "read_file", "content": "x " * 12000}]
        a._compact_history()
        summary = next(m["content"] for m in a.messages if str(m.get("content", "")).startswith("(Résumé"))
        self.assertIn("ne pas toucher a la base de prod", summary)


class ScriptsInCommands(unittest.TestCase):
    """A script with quotes squeezed into python -c breaks in the shell: Naim is told to use a heredoc, which works."""

    def test_heredoc_hint_and_heredoc_works(self):
        with tempfile.TemporaryDirectory() as d:
            a = naimtools.Agent(d, "naim", auto_yes=True, emit=lambda e: None, approver=lambda *x: True)
            bad = 'python3 -c "\ncours = [(\'Intro\', "print(\'Bonjour\')")]\nprint(len(cours))\n"'
            r = a.run_command(bad)
            self.assertTrue(r.startswith("exit code 2"), r)
            self.assertIn("heredoc", r)
            good = "python3 - <<'EOF'\ncours = [(\"L'apprentissage\", 'print(\"x\") et $var')]\nprint(cours[0][0])\nEOF"
            self.assertEqual(a.run_command(good), "exit code 0\nL'apprentissage")


class SelfInstall(unittest.TestCase):
    """Asked to, Naim adds to its own library any MCP server (checked by starting it) and the user's hooks."""

    SCRIPT = """
import os, sys, tempfile
sys.path.insert(0, sys.argv[1])
import extensions as ext, naimtools
a = naimtools.Agent(tempfile.mkdtemp(), "naim", auto_yes=True, emit=lambda e: None, approver=lambda *x: True)
print(a.install_mcp("Mémoire Test", "python3", [os.path.join(sys.argv[1], "plugins_builtin/naim-mem/serveur.py")])[:37])
print("memoire-test" in ext.MCP.config())
print(a.install_mcp("casse", "python3", ["-c", "import sys; sys.exit(1)"])[:31], "casse" in ext.MCP.config())
print(a.add_hook("PostToolUse", "echo vu par le hook", matcher="write_file")[:20])
print(a.call_tool("write_file", {"path": "x.py", "content": "print(1)"}).splitlines()[-1])
"""

    def test_mcp_and_hook(self):
        with tempfile.TemporaryDirectory() as home:
            r = subprocess.run([sys.executable, "-c", self.SCRIPT, str(ROOT)], capture_output=True, text=True,
                               env={**os.environ, "NAIM_HOME": home}, timeout=120)
            out = r.stdout.splitlines()
            self.assertEqual(out[0], "ok: MCP server memoire-test installed", r.stderr[-500:])
            self.assertEqual(out[1], "True")
            self.assertEqual(out[2], "error: the server did not start False")
            self.assertEqual(out[3], "ok: PostToolUse hook")
            self.assertEqual(out[4], "[Hook après write_file] vu par le hook")


class PluginMarketplace(unittest.TestCase):
    """« /plugin install » of a plugin made for another coding agent: skills, agents, commands, MCP and hooks (off)
    translated for Naim."""

    SCRIPT = """
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import plugins, hooks, skills_bibliotheque as lib
mk = plugins.MARKETS / "outils"
(mk / ".agent-plugin").mkdir(parents=True)
(mk / ".agent-plugin/marketplace.json").write_text(json.dumps({"name": "outils", "plugins": [{"name": "revue", "source": "./revue"}]}))
pl = mk / "revue"
(pl / ".agent-plugin").mkdir(parents=True)
(pl / ".agent-plugin/plugin.json").write_text(json.dumps({"name": "revue", "version": "1.2"}))
(pl / "skills/relire").mkdir(parents=True)
(pl / "skills/relire/SKILL.md").write_text("---\\nname: relire\\ndescription: Relire du code\\n---\\nLis le diff.")
(pl / "agents").mkdir()
(pl / "agents/critique.md").write_text("---\\nname: critique\\ndescription: Un relecteur sévère\\n---\\nSois exigeant.")
(pl / "commands").mkdir()
(pl / "commands/plan.md").write_text("---\\ndescription: Planifier\\nargument-hint: <tâche>\\n---\\nPlanifie : $ARGUMENTS")
(pl / "hooks").mkdir()
(pl / "hooks/hooks.json").write_text(json.dumps({"hooks": {"PostToolUse": [{"matcher": "Write", "hooks": [{"type": "command", "command": "echo ${AGENT_PLUGIN_ROOT} $AGENT_PLUGIN_ROOT"}]}]}}))
(pl / ".mcp.json").write_text(json.dumps({"mcpServers": {"docs": {"command": "${AGENT_PLUGIN_ROOT}/srv"}}}))
r = plugins.install_from_market("revue")
print(r["skills"], r["agents"], r["commands"], r["mcp"], r["hooks"], r["library"])
c = [x for x in plugins.commands() if x["plugin"] == "revue"][0]
print(c["cmd"], c["prompt"])
print(sorted(s for s in plugins.skill_dirs() if "revue" in s[0]) != [])
print(sum(1 for h in hooks.load(".").get("PostToolUse", []) if "revue" in h["source"]))
plugins.set_hooks("revue", True)
h = [h for h in hooks.load(".").get("PostToolUse", []) if "revue" in h["source"]][0]
print("/plugins/revue $AGENT" in h["command"], h["root"].endswith("/plugins/revue"),
      hooks.run({"PostToolUse": [h]}, "PostToolUse", {}, ".", "Write")[2].count("/plugins/revue"))
print(plugins.mcp_servers()["revue-docs"]["command"].endswith("/plugins/revue/srv"))
"""

    def test_install_translates(self):
        with tempfile.TemporaryDirectory() as home:
            r = subprocess.run([sys.executable, "-c", self.SCRIPT, str(ROOT)], capture_output=True, text=True,
                               env={**os.environ, "NAIM_HOME": home}, timeout=60)
            out = r.stdout.splitlines()
            self.assertEqual(out[0], "1 1 1 1 1 False", r.stderr[-800:])
            self.assertEqual(out[1], "/revue:plan Planifie : $ARGUMENTS")
            self.assertEqual(out[2], "True")   # a small plugin: its skills are listed like Naim's own
            self.assertEqual(out[3], "0")      # its hooks come turned off
            self.assertEqual(out[4], "True True 2")  # the folder in the command and in $AGENT_PLUGIN_ROOT
            self.assertEqual(out[5], "True")


class LiveProgress(unittest.TestCase):
    """While a long file is written or Naim thinks, the live line says how far it got (lines, tokens)."""

    def test_file_in_lines(self):
        w = {"name": "write_file", "path": "tests/test_maths.py", "chars": 5000, "lines": 120}
        self.assertEqual(naimtools.writing_text(w), "Naim écrit test_maths.py · 120 lignes")

    def test_thinking_in_tokens(self):
        self.assertEqual(naimtools.writing_text({"think": True, "tokens": 2140}), "Naim réfléchit · 2,1k jetons")
        self.assertEqual(naimtools.writing_text({"think": True, "tokens": 640}), "Naim réfléchit · 640 jetons")


class Interface(unittest.TestCase):
    """A CSS comment left open hides every style after it (it broke the home page once): never again."""

    def test_css_comments_closed(self):
        import re
        css = "".join(re.findall(r"<style>(.*?)</style>", (ROOT / "web" / "index.html").read_text(), re.S))
        i = 0
        while (a := css.find("/*", i)) >= 0:
            b, n = css.find("*/", a + 2), css.find("/*", a + 2)
            self.assertTrue(b >= 0 and (n < 0 or b < n), "commentaire CSS non fermé : " + css[a:a + 80])
            i = b + 2


class ToolCallsWrittenAsText(unittest.TestCase):
    def test_xml(self):
        c = naimtools.raw_tool_calls("<tool_call>\n<function=read_file>\n<parameter=path>\nx.py\n</parameter>\n</function>\n</tool_call>")
        self.assertEqual(c, [{"function": {"name": "read_file", "arguments": {"path": "x.py"}}}])

    def test_xml_cut(self):
        c = naimtools.raw_tool_calls("Je lis.\n<tool_call>\n<function=read_file>\n<parameter=path>\nx.py\n</parameter>\n")
        self.assertEqual(c[0]["function"]["arguments"], {"path": "x.py"})

    def test_json(self):
        c = naimtools.raw_tool_calls('<tool_call>\n{"name": "run_command", "arguments": {"command": "ls"}}\n</tool_call>')
        self.assertEqual(c, [{"function": {"name": "run_command", "arguments": {"command": "ls"}}}])

    def test_none(self):
        self.assertEqual(naimtools.raw_tool_calls("une réponse normale"), [])


class SkillRouting(unittest.TestCase):
    """The method loaded for a request (only skills shipped with Naim, so the result does not depend on this Mac)."""

    @classmethod
    def setUpClass(cls):
        import extensions
        cls.ext = extensions

    def name(self, text):
        s = self.ext.match_skill(text)
        return s and s["name"]

    def test_plain_question_loads_nothing(self):
        self.assertIsNone(self.name("explique la boucle for"))

    def test_cv(self):
        self.assertEqual(self.name("fais ma lettre de motivation en pdf"), "cv-lettre")

    def test_report(self):
        self.assertEqual(self.name("fais un pdf du rapport"), "rapport")

    def test_animation(self):
        self.assertEqual(self.name("anime le tri par sélection en python"), "animation-algorithme")

    def test_pseudo_code(self):
        self.assertEqual(self.name("écris l'algorithme du pgcd en pseudo-code"), "pseudo-code")

    def test_named_skill_wins(self):
        self.assertEqual(self.name("utilise la skill pseudo-code pour ce tri"), "pseudo-code")

    def test_typographic_apostrophe(self):
        self.assertEqual(self.name("qu’est-ce que j’avais demandé hier ?"), "mem-search")

    def test_maths(self):
        for t in ("Corrige en posant les calculs : 234,56 × 12,3", "les sujets de maths du concours IFSI avec la correction",
                  "calcule le périmètre d'un cercle de rayon 3 cm", "calcule le déterminant de cette matrice",
                  "trace la courbe de f(x) = x^2 - 3", "dérivée de ln(x)", "probabilité de tirer deux as"):
            self.assertEqual(self.name(t), "maths-affichage", t)

    def test_memory(self):
        self.assertEqual(self.name("la dernière fois on avait corrigé la facture, tu te souviens ?"), "mem-search")


class ChatOrAgent(unittest.TestCase):
    """A real piece of work asked in the Chat goes to the Agent's loop; a question stays an answer."""

    @classmethod
    def setUpClass(cls):
        import server
        cls.h = server.Handler.__new__(server.Handler)
        cls.dir = tempfile.mkdtemp()

    def work(self, text):
        return self.h.big_work({"message": text, "settings": {"project": self.dir}, "history": []})

    def test_project_goes_to_agent(self):
        for t in ("lance toi le test et corrige si une erreur", "toujours code erreur 1 $ dotnet test",
                  "Écris DDL.sql, RETRAIT.cbl puis RETRAIT.jcl"):
            self.assertEqual(str(self.work(t)), self.dir, t)

    def test_questions_stay(self):
        for t in ("comment je lance le programme pour le test ?", "c'est quoi une boucle for ?", "fais-moi la table de 80",
                  "envoie un mail à Paul", "corrige l'orthographe de ce texte"):
            self.assertIsNone(self.work(t), t)


class NoFalseClaims(unittest.TestCase):
    """« J'ai installé le skill » with no tool used is caught (it said so once and nothing was installed); a question
    or a plain answer is not."""

    def test_claims(self):
        import server
        for t in ("J'ai installé le skill Leonxlnx/unlazy. Ce skill ajoute…", "Le skill est maintenant installé.",
                  "Installé avec succès !", "J'ai ajouté le hook à ton projet."):
            self.assertTrue(server.claims_done(t), t)
        for t in ("J'ai compris ta question.", "Voici un code Python qui crée un anneau.", "Le fichier a été créé hier par toi ?"):
            self.assertFalse(server.claims_done(t), t)


class MathsInTheConversation(unittest.TestCase):
    """« Corrige en posant les calculs » is maths answered in the conversation (formulas, operations drawn there),
    not a file to correct; a named file or a PDF still is file work."""

    def file_work(self, m):
        import server as s
        return bool(s.FILE_WORK_RE.search(m)) and not (s.MATH_ASK_RE.search(m) and not s.FILE_NAMED_RE.search(m))

    def test_maths_stays_an_answer(self):
        for m in ("Corrige en posant les calculs : 234,56 × 12,3 et 789,01 : 9,2",
                  "je veux l'énoncé complet puis la correction complète des maths"):
            self.assertFalse(self.file_work(m), m)

    def test_files_stay_files(self):
        for m in ("corrige le bug de mon app", "corrige le fichier calcul.py", "crée un pdf du corrigé de l'exercice"):
            self.assertTrue(self.file_work(m), m)


class SessionMemory(unittest.TestCase):
    """naim-mem: the hook keeps what was done, the MCP server finds it."""

    def test_capture_and_search(self):
        d = ROOT / "plugins_builtin" / "naim-mem"
        with tempfile.TemporaryDirectory() as home:
            env = {**os.environ, "NAIM_HOME": home}
            for ev in ({"hook_event_name": "UserPromptSubmit", "prompt": "Corrige la facture TVA", "cwd": "/x/compta"},
                       {"hook_event_name": "PostToolUse", "tool_name": "edit_file", "tool_input": {"path": "f.py"},
                        "tool_response": "ok: TVA 20%", "cwd": "/x/compta"}):
                r = subprocess.run([sys.executable, str(d / "capture.py")], input=json.dumps(ev), text=True,
                                   capture_output=True, env=env)
                self.assertEqual((r.returncode, r.stdout), (0, ""))  # silent, never blocks
            req = "\n".join(json.dumps(m) for m in (
                {"jsonrpc": "2.0", "id": 1, "method": "initialize"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "chercher", "arguments": {"requete": "tva"}}}))
            out = subprocess.run([sys.executable, str(d / "serveur.py")], input=req + "\n", text=True, capture_output=True, env=env).stdout
            found = json.loads(out.strip().split("\n")[-1])["result"]["content"][0]["text"]
            self.assertIn("facture", found.lower())
            self.assertIn("edit_file", found)


class SkillScripts(unittest.TestCase):
    MODEL = """<!doctype html><html><head><style>.carte{border:2px solid}</style></head><body><main class="feuille">
<header class="entete"><h1>Jean<br>Dupont</h1><p class="soustitre">Développeur</p></header>
<section class="carte"><h2 class="badge">Expérience</h2><p>Poste chez <b>ACME</b> en 2020</p></section></main></body></html>"""
    D = ROOT / "plugins_builtin" / "candidature" / "skills" / "cv-lettre"

    def test_letter_keeps_style_not_cv(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            (t / "cv.html").write_text(self.MODEL)
            (t / "l.txt").write_text("Paris, le 1er mars\n\nSociété X\n\nObjet : candidature\n\nMadame,\n\nJe postule.\n\nCordialement.\n\nJean Dupont\n")
            subprocess.run([sys.executable, "-I", str(self.D / "lettre_depuis_cv.py"), "cv.html", "l.txt", "out.html"], cwd=t, check=True, capture_output=True)
            out = (t / "out.html").read_text()
            self.assertIn(".carte{border:2px solid}", out)
            self.assertIn("Jean<br>Dupont", out)
            self.assertIn("Je postule.", out)
            self.assertNotIn("ACME", out)

    def test_fill_model(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            (t / "m.html").write_text(self.MODEL)
            (t / "p.json").write_text(json.dumps([["Jean Dupont", "Marie Curie"], ["Poste chez ACME en 2020", "Chercheuse"], ["absent", "x"]]))
            r = subprocess.run([sys.executable, "-I", str(self.D / "remplir_modele.py"), "m.html", "p.json", "o.html"], cwd=t,
                               check=True, capture_output=True, text=True)
            out = (t / "o.html").read_text()
            self.assertIn("Marie Curie", out)
            self.assertIn("Chercheuse", out)
            self.assertIn("2 texte(s) remplacé(s) sur 3", r.stdout)
            self.assertIn(".carte{border:2px solid}", out)


if __name__ == "__main__":
    unittest.main()
