"""Naim's regression tests: what broke once must not break again. No model, no engine needed.

    python3 -m unittest discover -s tests -v
"""
import json
import os
import subprocess
import sys
import tempfile
import time
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


class EngineGrowsOnly(unittest.TestCase):
    """A smaller request is served by the bigger context already there: no restart (a periodic 8k check once shrank the
    engine under a running answer — « Connection refused », 6 restarts in 2 minutes). Only a bigger one restarts it."""

    def test_no_shrink(self):
        s = llamacpp.Server(port=1)
        s.proc = type("Running", (), {"poll": lambda self: None})()  # an engine that runs
        s.ctx, s.cfg = 32768, dict(llamacpp.CONFIG)
        s.healthy = lambda: True
        stops = []
        s.stop = lambda: stops.append(1) or (_ for _ in ()).throw(RuntimeError("restart"))
        s.ensure(8192)
        s.ensure(32768)
        self.assertEqual(stops, [])
        with self.assertRaises(RuntimeError):
            s.ensure(65536)  # bigger: it restarts
        self.assertEqual(stops, [1])


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


class ReadARange(unittest.TestCase):
    """The middle or the end of a long file, without reading all of it: lines numbered, and where to go on."""

    def test_offset_and_limit(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "log.txt").write_text("".join(f"ligne {i}\n" for i in range(1, 1001)))
            a = naimtools.Agent(d, "naim", auto_yes=True, emit=lambda e: None, approver=lambda *x: True)
            r = a.call_tool("read_file", {"path": "log.txt", "offset": 998, "limit": 10})
            self.assertTrue(r.startswith("[log.txt · lignes 998–1000 sur 1000. (fin du fichier)]"), r)
            self.assertIn("   999\tligne 999", r)
            r = a.read_file("log.txt", offset=10, limit=2)
            self.assertIn("Suite : offset=12.", r)
            self.assertNotIn("ligne 12", r)
            self.assertTrue(a.read_file("log.txt", offset=5000).startswith("error:"))
            self.assertEqual(a.read_file("log.txt").count("\n"), 1000)  # without a range: the whole file, as before


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
      hooks.run({"UserPromptSubmit": [h]}, "UserPromptSubmit", {}, ".")[2].count("/plugins/revue"))  # printed: read there
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
            self.assertEqual(out[3], "1")      # its hooks are on at once, like the reference agent
            self.assertEqual(out[4], "True True 2")  # the folder in the command and in $AGENT_PLUGIN_ROOT
            self.assertEqual(out[5], "True")


class SelfExtend(unittest.TestCase):
    """Naim installs a plugin itself (install_plugin) and its instructions tell it to extend itself instead of saying it
    cannot."""

    SCRIPT = """
import json, shutil, sys, tempfile
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import plugins, naimtools
src = Path(tempfile.mkdtemp()) / "depot"
(src / ".agent-plugin").mkdir(parents=True)
(src / ".agent-plugin/plugin.json").write_text(json.dumps({"name": "outils-revue", "version": "1.0"}))
(src / "commands").mkdir()
(src / "commands/relire.md").write_text("---\\ndescription: Relire\\n---\\nRelis : $ARGUMENTS")
plugins._clone = lambda url, dst: shutil.copytree(src, dst)  # offline: the « repository » is a local folder
a = naimtools.Agent(tempfile.mkdtemp(), "naim", auto_yes=True, emit=lambda e: None, approver=lambda *x: True)
print(a.install_plugin("https://github.com/exemple/outils-revue").split(":")[0])
print([c["cmd"] for c in plugins.commands() if c["plugin"] == "outils-revue"])
print("You extend yourself" in a.messages[0]["content"], "install_plugin" in {t["function"]["name"] for t in a.tools})
"""

    def test_install_plugin(self):
        with tempfile.TemporaryDirectory() as home:
            r = subprocess.run([sys.executable, "-c", self.SCRIPT, str(ROOT)], capture_output=True, text=True,
                               env={**os.environ, "NAIM_HOME": home}, timeout=60)
            out = r.stdout.splitlines()
            self.assertEqual(out[0], "ok", r.stderr[-800:])
            self.assertEqual(out[1], "['/outils-revue:relire']")
            self.assertEqual(out[2], "True True")


class OneServerPerProject(unittest.TestCase):
    """A new server of a project replaces the one already running there (it once left four servers running);
    another project's server is never touched; replace=false keeps a second, different one."""

    def test_replace(self):
        from naimtools import PROCESSES
        srv = lambda port: f"python3 -c \"print('Running on http://127.0.0.1:{port}', flush=True); import time; time.sleep(30)\""  # noqa: E731
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            a = naimtools.Agent(d1, "naim", auto_yes=True, emit=lambda e: None, approver=lambda *x: True)
            b = naimtools.Agent(d2, "naim", auto_yes=True, emit=lambda e: None, approver=lambda *x: True)
            try:
                p1 = a.start_process(srv(5050), "site", keep=True).split()[1]
                other = b.start_process(srv(7000), "autre", keep=True).split()[1]
                r = a.start_process(srv(5051), "site v2", keep=True)
                self.assertIn(f"stopped first (replaced by this one): {p1}", r)
                api = a.start_process(srv(8000), "api", keep=True, replace=False)
                running = {p.id for p in PROCESSES.procs.values() if p.proc.poll() is None}
                self.assertNotIn(p1, running)
                self.assertIn(other, running)
                self.assertIn(api.splitlines()[0].split()[1], running)
            finally:
                for p in list(a.started) + list(b.started):
                    PROCESSES.stop(p.id)


class DesignFollowUp(unittest.TestCase):
    """« c'est pas enrichi », « le site n'a pas changé » right after work on a site keep the design skill."""

    def test_follow_up(self):
        import extensions as ext
        if not any(s["name"] == "frontend-design" for s in ext.list_skills()):
            self.skipTest("frontend-design n'est pas installé sur ce Mac")
        recent = "lance le serveur et le site. Le serveur est lancé sur http://127.0.0.1:5050"
        for t in ("c'est pas enrichi du tout !!!", "Le site na pas changé !", "améliore plus le css"):
            self.assertEqual((ext.design_follow_up(t, recent) or {}).get("name"), "frontend-design", t)
        self.assertIsNone(ext.design_follow_up("merci", recent))
        self.assertIsNone(ext.design_follow_up("c'est pas enrichi du tout", "explique la boucle for"))


class LocalSkill(unittest.TestCase):
    """« installe ce skill ~/Downloads/SKILL.md »: a skill from a file of this Mac, active at once."""

    SCRIPT = """
import sys, tempfile
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import naimtools, extensions as ext
f = Path(tempfile.mkdtemp()) / "SKILL.md"
f.write_text("---\\nname: style-test\\ndescription: Un style de test\\n---\\n\\n# Style\\nBordures noires.")
a = naimtools.Agent(tempfile.mkdtemp(), "naim", auto_yes=True, emit=lambda e: None, approver=lambda *x: True)
print(a.install_skill(str(f)).split(":")[0])
print([s["name"] for s in ext.list_skills() if s["name"] == "style-test" and s["enabled"]])
print(a.install_skill(str(f)).split(":")[0], (ext.HOME / "skills" / ".anciens").is_dir())  # again: the old one kept aside
"""

    def test_local_file(self):
        with tempfile.TemporaryDirectory() as home:
            r = subprocess.run([sys.executable, "-c", self.SCRIPT, str(ROOT)], capture_output=True, text=True,
                               env={**os.environ, "NAIM_HOME": home}, timeout=60)
            self.assertEqual(r.stdout.splitlines(), ["ok", "['style-test']", "ok True"], r.stderr[-600:])


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


class ProByDefault(unittest.TestCase):
    """A PDF made from text or Markdown has the pdf-pro look; a whole HTML page keeps its own design."""

    def test_markdown_gets_the_pro_look(self):
        import docs
        if not docs.PDFPRO.exists():
            self.skipTest("pdf-pro not installed")
        page = docs.pro_html("# Mon rapport\n\nTexte.", "r")
        self.assertIn('class="prohead"', page)
        self.assertIn("--clay", page)  # the theme's colours

    def test_whole_page_kept(self):
        import chatfiles
        from unittest import mock
        seen = {}
        with tempfile.TemporaryDirectory() as t, mock.patch("docs.convert", lambda page, dst: (seen.setdefault("p", Path(page).read_text()), Path(dst).write_text("pdf"))):
            chatfiles.create("a.pdf", "<html><head><style>body{color:red}</style></head><body><p>x</p></body></html>", folder=t)
        self.assertNotIn("prohead", seen["p"])
        self.assertNotIn("--clay", seen["p"])


class AttachedFilesKept(unittest.TestCase):
    """The file the user attached is never replaced, moved or deleted; the files card shows only what was asked."""

    def setUp(self):
        from unittest import mock
        self.t = tempfile.mkdtemp()
        self.p = mock.patch("naimtools.JOINTS", Path(self.t))
        self.p.start()
        self.d = Path(self.t) / "c1"; self.d.mkdir()
        import server
        (self.d / "Lettre.pdf").write_bytes(b"%PDF original")
        server._read_only(self.d / "Lettre.pdf")
        (self.d / "copie.pdf").write_bytes(b"%PDF mine")
        self.a = naimtools.Agent(str(self.d), auto_yes=True)

    def tearDown(self):
        self.p.stop()

    def test_commands_onto_it_refused(self):
        L, C = f'"{self.d}/Lettre.pdf"', f'"{self.d}/copie.pdf"'
        for cmd in (f"mv {C} {L}", f"cp {C} {L}", f"rm {L}", f"echo x > {L}", f"sed -i '' s/a/b/ {L}", f"mv {L} {self.d}/autre.pdf"):
            self.assertTrue(str(self.a.call_tool("run_command", {"command": cmd})).startswith("refused"), cmd)
        for cmd in (f"cp {L} {self.d}/travail.pdf", f"pdftotext {L} {self.d}/t.txt", f"ls {self.d}"):
            self.assertIsNone(self.a._joint_hit(cmd), cmd)
        self.assertEqual((self.d / "Lettre.pdf").read_bytes(), b"%PDF original")

    def test_write_onto_it_refused(self):
        with self.assertRaises(ValueError):
            self.a.resolve(str(self.d / "Lettre.pdf"))
        self.assertEqual(self.a.resolve(str(self.d / "Lettre.pdf"), read=True), (self.d / "Lettre.pdf").resolve())
        self.assertEqual(self.a.resolve(str(self.d / "copie.pdf")), (self.d / "copie.pdf").resolve())

    def test_card_shows_only_the_result(self):
        files = [{"path": "Lettre_pro.pdf"}, {"path": "Lettre.docx.png"}, {"path": "faire_doc.py"}, {"path": "parti.pdf"}]
        (self.d / "Lettre_pro.pdf").write_text("x"); (self.d / "faire_doc.py").write_text("x"); (self.d / "Lettre.docx.png").write_text("x")
        self.assertEqual([f["path"] for f in naimtools.finals(files, self.d)], ["Lettre_pro.pdf"])


class WebPages(unittest.TestCase):
    """A page read like a pro tool: its main text without menu noise, its titles and its links; a page built by
    JavaScript is read again in the real browser."""

    def test_text_titles_and_links(self):
        import extensions as e
        page = ('<html><nav><a href="/x">Menu</a></nav><main><h2>Offres</h2><ul><li></li><li>Poste A</li></ul>'
                + "<p>" + "texte " * 400 + '</p><a href="/offre/1">Voir l\'offre 1</a><a hreflang="en" href="https://en.x/">English</a></main></html>')
        t = e.html_to_text(e._main_part(page))
        self.assertIn("## Offres", t)
        self.assertNotIn("\n- \n", t)
        self.assertNotIn("Menu", t)
        links = e._links(e._main_part(page), "https://site.fr/liste")
        self.assertEqual(links, ["- Voir l'offre 1 → https://site.fr/offre/1"])

    def test_javascript_page_read_in_the_browser(self):
        from unittest import mock
        a = naimtools.Agent(tempfile.mkdtemp(), auto_yes=True)

        class FakeBrowser:
            def send(self, cmd, **k):
                return {"title": "Offres", "url": "https://site.fr", "text": "7 offre(s) trouvée(s)\nPoste A\nPoste B " * 20,
                        "textLength": 900, "elements": ["[1] lien « Ouvrir Poste A »"]}
        with mock.patch("extensions.web_fetch", return_value="Offres\nhttps://site.fr\n\n- \n- "), \
                mock.patch("browser.Browser", FakeBrowser), mock.patch("time.sleep"):
            r = a.web_fetch("https://site.fr")
        self.assertIn("lue avec le navigateur", r)
        self.assertIn("[1] lien « Ouvrir Poste A »", r)
        with mock.patch("extensions.web_fetch", return_value="Doc\nhttps://d.fr\n\n" + "mot " * 300):
            self.assertNotIn("navigateur", a.web_fetch("https://d.fr"))  # a page with its text: no browser


class Navigation(unittest.TestCase):
    """Searching and reading the web like a person: another engine when one says « no result », a long page read part
    after part, Cmd-F inside a page, and a skills library that weighs rare words."""

    def test_search_falls_back_to_other_engines(self):
        from unittest import mock
        import extensions as e
        one = [{"title": "A", "url": "https://a.fr", "snippet": ""}]
        bing = [{"title": "A", "url": "https://a.fr", "snippet": ""}, {"title": "B", "url": "https://b.fr", "snippet": ""},
                {"title": "C", "url": "https://c.fr", "snippet": ""}]
        with mock.patch("extensions._ddg_html", return_value=[]), mock.patch("extensions._ddg_lite", side_effect=OSError("429")), \
                mock.patch("extensions._bing", return_value=bing):
            self.assertEqual([r["url"] for r in e.web_search("prix iphone")], ["https://a.fr", "https://b.fr", "https://c.fr"])
        with mock.patch("extensions._ddg_html", return_value=one), mock.patch("extensions._ddg_lite", return_value=one), \
                mock.patch("extensions._bing", return_value=[]):
            self.assertEqual(len(e.web_search("x")), 1)  # the same page met twice is given once
        with mock.patch("extensions._ddg_html", side_effect=OSError("down")), mock.patch("extensions._ddg_lite", side_effect=OSError("down")), \
                mock.patch("extensions._bing", side_effect=OSError("down")):
            with self.assertRaises(RuntimeError):
                e.web_search("x")

    def test_bing_real_address(self):
        from unittest import mock
        import base64, extensions as e
        u = "a1" + base64.urlsafe_b64encode(b"https://www.fnac.com/iphone").decode().rstrip("=")
        page = (f'<ol><li class="b_algo"><h2><a href="https://www.bing.com/ck/a?!&amp;p=1&amp;u={u}&amp;ntb=1">iPhone '
                '- Fnac</a></h2><p>Le prix</p></li></ol>')
        with mock.patch("extensions._get", return_value=(page, "text/html", "")):
            self.assertEqual(e._bing("iphone", 6), [{"title": "iPhone - Fnac", "url": "https://www.fnac.com/iphone", "snippet": "Le prix"}])

    def test_long_page_read_part_after_part(self):
        from unittest import mock
        import extensions as e
        page = "<html><title>Doc</title><main><p>" + "mot " * 7000 + "FIN</p></main></html>"
        with mock.patch("extensions._get", return_value=(page, "text/html", "https://d.fr/doc")):
            first = e.web_fetch("https://d.fr/doc")
            self.assertIn("web_fetch https://d.fr/doc#suite=12000", first)
            second = e.web_fetch("https://d.fr/doc#suite=24000")
            self.assertIn("FIN", second)
            self.assertNotIn("la page continue", second)
            self.assertIn("fin de la page", e.web_fetch("https://d.fr/doc#suite=99000"))

    def test_find_in_page_and_next_part(self):
        import browser as br
        r = {"title": "T", "url": "https://t.fr", "text": "intro " * 3000 + "Le tarif réduit est de 4,50 euros. " + "fin " * 10,
             "elements": ["[1] lien « Tarifs »", "[2] bouton « OK »"]}
        found = br.find_in(r, "tarif reduit")
        self.assertIn("4,50 euros", found)
        self.assertIn("[1] lien « Tarifs »", found)
        self.assertNotIn("[2]", found)
        self.assertIn("rien sur cette page", br.find_in(r, "abonnement"))
        self.assertIn("action=page target=12000", br.describe(r, full_text=True, limit=12000))
        self.assertIn("(suite : caractères 12000", br.describe(r, full_text=True, limit=12000, start=12000))

    def test_library_weighs_rare_words_and_ignores_small_talk(self):
        import skills_bibliotheque as lib
        data = [({"name": n, "dir": n, "description": d}, (frozenset(n.split("-")), frozenset(d.split()), frozenset()))
                for n, d in (("data-tools", "data data"), ("arduino-board", "arduino sensor data"), ("lex", "ca lex"))]
        w = lib._rarity(["data", "arduino", "ca"], data)
        self.assertGreater(w["arduino"], w["data"])
        self.assertLess(w["ca"], w["arduino"])  # « ça va » says nothing about the task

    def test_library_gives_a_skill_once(self):
        from unittest import mock
        import skills_bibliotheque as lib
        s = {"name": "pdf", "dir": "pdf", "description": "Work with PDF files", "head": ""}
        bags = (frozenset({"pdf"}), frozenset({"work", "with", "pdf", "files"}), frozenset())
        with mock.patch("skills_bibliotheque._tokens", return_value=[(s, bags), (dict(s), bags)]):
            self.assertEqual(len(lib.search("convertir un pdf")), 1)


class VisualInTheChat(unittest.TestCase):
    """« l'heure dans un carré beau », « affiche-le dans le chat »: a live visual drawn in the conversation (a ```visuel
    block), not HTML code to open in the preview."""

    def test_trigger(self):
        import re
        m = json.loads((ROOT / "plugins_builtin/visuel/plugin.json").read_text())
        t = m["triggers"]["visuel"]
        for yes in ("affiche moi l’heure dans un carré visuel beau", "non tu affcihe sa dans le chat le carré",
                    "fais une horloge", "un compte à rebours jusqu'à noël"):
            self.assertRegex(yes, re.compile(t, re.I))
        for no in ("fais-moi un logo pour ma boutique", "affiche moi l'heure", "afficher les fichiers du dossier"):
            self.assertNotRegex(no, re.compile(t, re.I))

    def test_skill_example_is_a_visual_block(self):
        text = (ROOT / "plugins_builtin/visuel/skills/visuel/SKILL.md").read_text()
        self.assertIn("```visuel", text)
        self.assertIn("setInterval", text)  # alive: the time is computed, never written in
        page = (ROOT / "web/index.html").read_text()
        script = page[page.index("<script>") + 8:]
        self.assertNotIn("`<script>", script)  # a literal tag there ends Naim's own script in the HTML parser


class SimulationInTheChat(unittest.TestCase):
    """« montre-moi le tri avec une simulation visuel »: a ```simulation block played in the conversation by the tested
    engine (not a visual made by hand), its example right, and a frame that does not shake the page."""

    def test_trigger_and_inline(self):
        import re
        t = json.loads((ROOT / "plugins_builtin/algorithmique/plugin.json").read_text())["triggers"]["animation-algorithme"]
        for yes in ("Non j’ai besoin que tu me montre le tri avec une simulation visuel", "fais une simulation du tri rapide",
                    "montre-moi comment marche le tri par insertion en Python"):
            self.assertRegex(yes, re.compile(t, re.I))
        self.assertNotRegex("explique le tri", re.compile(t, re.I))
        self.assertIn("sim_here", (ROOT / "server.py").read_text())

    def test_skill_example_is_right(self):
        sk = ROOT / "plugins_builtin/algorithmique/skills/animation-algorithme"
        self.assertIn("```simulation", (sk / "SKILL.md").read_text())
        r = subprocess.run([sys.executable, str(sk / "simulation.py"), "verifier", str(sk / "exemples/tri-insertion.js")],
                           capture_output=True, text=True, timeout=60)
        self.assertIn("La simulation est juste.", r.stdout + r.stderr)

    def test_creative_examples_are_right(self):
        sk = ROOT / "plugins_builtin/algorithmique/skills/animation-algorithme"
        text = (sk / "SKILL.md").read_text()
        for name in ("produit-matrices", "pythagore", "dijkstra"):
            self.assertIn(f"exemples/{name}.js", text)  # the skill points to it
            body = (sk / f"exemples/{name}.js").read_text()
            self.assertIn("dessiner(t, zone)", body)  # a drawing of its own, not bars
            r = subprocess.run([sys.executable, str(sk / "simulation.py"), "verifier", str(sk / f"exemples/{name}.js")],
                               capture_output=True, text=True, timeout=60)
            self.assertIn("La simulation est juste.", r.stdout + r.stderr, name)

    def test_a_wrong_block_is_caught(self):
        import server
        naim_block = """const ALGO = { titre: "Produit", type: "autre", matriceA: [[1, 2]], code: `
def f(A):
    return A`, dessiner(etape, zone) { zone.innerHTML = C.length; } };"""  # what Naim wrote: no build, an undefined C
        self.assertIn("build", server.check_simulation(naim_block))
        drawing_breaks = """const ALGO = { titre: "x", type: "autre", valeurs: [1, 2], code: `
a = 1
b = 2`, build(a, P) { P(1, "un", { dessin: {} }); P(2, "deux", { dessin: {} }); },
          dessiner(t, zone) { zone.innerHTML = "<svg>" + C.length + "</svg>"; } };"""
        self.assertIn("dessiner() plante", server.check_simulation(drawing_breaks))
        sk = ROOT / "plugins_builtin/algorithmique/skills/animation-algorithme/exemples"
        self.assertEqual(server.check_simulation((sk / "produit-matrices.js").read_text()), "")
        self.assertIn("Corrige et redonne ta réponse entière", (ROOT / "server.py").read_text())

    def test_the_closest_example_comes_with_the_request(self):
        import server
        for m, want in (("simule le produit de deux matrices", "produit-matrices"), ("montre pythagore en animation", "pythagore"),
                        ("une simulation de dijkstra", "dijkstra"), ("simule la recherche dichotomique", "recherche-dichotomique"),
                        ("montre le tri avec une simulation", "tri-insertion")):
            name, text = server.sim_example(m)
            self.assertEqual(name, want, m)
            self.assertIn("const ALGO", text)

    def test_the_right_skill_is_chosen(self):
        import extensions as e
        for m, want in (("Non j’ai besoin que tu me montre le tri avec une simulation visuel", "animation-algorithme"),
                        ("simule le produit de deux matrices", "animation-algorithme"),
                        ("montre pythagore avec une animation", "animation-algorithme"),
                        ("affiche moi l’heure dans un carré visuel beau", "visuel"),
                        ("utilise le skill visuel pour un compteur", "visuel")):
            sk = e.match_skill(m)
            self.assertEqual(sk and sk["name"], want, m)

    def test_page_side(self):
        page = (ROOT / "web/index.html").read_text()
        self.assertIn('fetch("/api/moteur-algo")', page)
        self.assertIn("function algoFrame(", page)
        self.assertIn("h > now + 3", page)  # it only grows: an animation no longer shakes the conversation
        self.assertIn("quillText(body.length)", page)  # the quill moves while the block is written
        self.assertIn('a.getAttribute("srcdoc") === b.getAttribute("srcdoc")', page)  # kept while the answer goes on
        self.assertIn("name=[\"']?viewport", page)  # no zoom of the frame in Naim's web view
        self.assertIn("r.style.width = w + ", page)  # under Naim's zoom, WebKit laid the frame's page out too narrow
        self.assertIn("data-simbig", page)  # « Agrandir »: the simulation at full size in the preview panel
        self.assertIn("function simBig(", page)


class CourseFolderToPdf(unittest.TestCase):
    def test_situation_said_before_the_method(self):
        import extensions as e
        with tempfile.TemporaryDirectory() as t:
            for n in ("README.md", "01-a.md", "02-b.md"):
                (Path(t) / n).write_text("# x")
            note = e.skill_situation("pdf-pro", t, "fais-moi le PDF du cours")
            self.assertIn('convert_document source="README.md"', note)
            self.assertEqual(e.skill_situation("pdf-pro", t, "mets ce texte en pdf : réunion"), "")
            self.assertEqual(e.skill_situation("cobol", t, "le cours"), "")
            a = naimtools.Agent(t, auto_yes=True)
            r = a.convert_document("README.md", "cours.pdf") if (Path.home() / ".naim/plugins/pdf-pro").exists() else "Cours complet"
            self.assertIn("Cours complet", r)


class InstallAlone(unittest.TestCase):
    """A missing module or program: the exact way to install it (right package name, in the project's environment or
    with Homebrew); install requests go to the installer skill."""

    def test_hints(self):
        a = naimtools.Agent(tempfile.mkdtemp(), auto_yes=True)
        self.assertIn("opencv-python", a._install_hint("ModuleNotFoundError: No module named 'cv2'"))
        self.assertIn(".venv", a._install_hint("No module named 'pandas'"))
        self.assertIn("brew install ffmpeg", a._install_hint("zsh: command not found: ffmpeg"))
        self.assertIn("brew install gnucobol", a._install_hint("bash: cobc: command not found"))
        self.assertEqual(a._install_hint("zsh: command not found: monoutil"), "")

    def test_routing(self):
        import extensions as e
        name = lambda t: (e.match_skill(t) or {}).get("name")  # noqa: E731
        if "installer" not in __import__("plugins").triggers():
            self.skipTest("installer plugin not installed")
        self.assertEqual(name("installe ffmpeg"), "installer")
        self.assertEqual(name("installe ce qu'il faut pour lire des fichiers Excel en Python"), "installer")
        self.assertNotEqual(name("installe le skill pdf"), "installer")


class Converters(unittest.TestCase):
    C = Path(__file__).resolve().parents[1] / "plugins_builtin/convertisseurs/skills/convertisseurs/convertir.py"

    def run_conv(self, *a):
        return subprocess.run([sys.executable, str(self.C), *map(str, a)], capture_output=True, text=True)

    def test_tables_and_safety(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            (t / "n.csv").write_text("Nom;Note\nAlice;15\n")
            self.assertEqual(self.run_conv(t / "n.csv", t / "n.json").returncode, 0)
            self.assertEqual(json.loads((t / "n.json").read_text()), [{"Nom": "Alice", "Note": "15"}])
            r = self.run_conv(t / "n.csv", t / "n.csv")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("jamais écrasé", r.stderr + r.stdout)
            self.assertIn("pas pris en charge", self.run_conv(t / "n.csv", t / "n.mp3").stderr)

    def test_routing(self):
        import extensions as e
        if "convertisseurs" not in __import__("plugins").triggers():
            self.skipTest("plugin not installed")
        name = lambda x: (e.match_skill(x) or {}).get("name")  # noqa: E731
        self.assertEqual(name("convertis cette photo heic en jpg"), "convertisseurs")
        self.assertEqual(name("mets ce word en markdown"), "convertisseurs")
        self.assertEqual(name("fais un document word sur la sécurité"), "word")


class ChatFolder(unittest.TestCase):
    """A conversation with attached files works beside them, not in the last Agent project."""

    def test_joints_of(self):
        import server
        from unittest import mock
        with tempfile.TemporaryDirectory() as t, mock.patch("naimtools.JOINTS", Path(t)):
            (Path(t) / "c1").mkdir(); (Path(t) / "c2").mkdir(); (Path(t) / "c2" / "cv.docx").write_text("x")
            self.assertIsNone(server.joints_of("c1"))  # empty: nothing attached
            self.assertIsNone(server.joints_of("../c2"))
            self.assertIsNone(server.joints_of("absent"))
            self.assertEqual(server.joints_of("c2"), Path(t) / "c2")

    def test_result_folder_is_writable(self):
        with tempfile.TemporaryDirectory() as t:
            a = naimtools.Agent(t, auto_yes=True)
            out = naimtools.JOINTS.parent / "Lettre.pdf"
            self.assertEqual(a.resolve(str(out)), out.resolve())
            with self.assertRaises(ValueError):
                a.resolve(str(naimtools.JOINTS.parent.parent / "autre.pdf"))


class ChatOrAgent(unittest.TestCase):
    """A real piece of work asked in the Chat goes to the Agent's loop; a question stays an answer."""

    @classmethod
    def setUpClass(cls):
        import server
        cls.h = server.Handler.__new__(server.Handler)
        cls.dir = tempfile.mkdtemp()

    def work(self, text):  # the hand-over to the Agent, when the user turned it on (off by default: the Chat works itself)
        return self.h.big_work({"message": text, "settings": {"project": self.dir, "auto_agent": True}, "history": []})

    def test_off_by_default(self):
        self.assertIsNone(self.h.big_work({"message": "Écris DDL.sql, RETRAIT.cbl puis RETRAIT.jcl",
                                           "settings": {"project": self.dir}, "history": []}))

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


class CheckBeforeDone(unittest.TestCase):
    """Code changed and not run since: Naim checks it (the project's tests, else the program) before saying it is done,
    in the Chat and the Agent; a command that only looks (ls, cat) is not a check."""

    def setUp(self):
        self.t = tempfile.mkdtemp()
        self.a = naimtools.Agent(self.t, auto_yes=True)

    def test_an_edit_needs_a_run(self):
        self.a.call_tool("write_file", {"path": "app.py", "content": "print('ok')\n"})
        self.assertEqual(self.a._code_dirty, "app.py")
        self.a.call_tool("run_command", {"command": "ls"})
        self.assertEqual(self.a._code_dirty, "app.py")  # looking is not checking
        self.assertIn("python3 -m py_compile app.py", self.a.check_note())
        self.a.call_tool("run_command", {"command": "python3 app.py"})
        self.assertIsNone(self.a._code_dirty)

    def test_the_projects_tests_first(self):
        Path(self.t, "tests").mkdir()
        self.a.call_tool("write_file", {"path": "lib.py", "content": "x = 1\n"})
        self.assertIn("pytest", self.a.check_note())
        Path(self.t, "package.json").write_text('{"scripts": {"test": "jest"}}')
        self.a.call_tool("write_file", {"path": "a.js", "content": "let x = 1\n"})
        self.assertIn("npm test", self.a.check_note())

    def test_not_code_needs_nothing(self):
        for f in ("notes.md", "page.html", "data.csv"):
            self.a.call_tool("write_file", {"path": f, "content": "x\n"})
        self.assertIsNone(self.a._code_dirty)

    def test_wired_in_chat_and_agent(self):
        self.assertIn("helper.check_note()", (ROOT / "server.py").read_text())
        self.assertIn("self.check_note()", (ROOT / "naimtools.py").read_text())


class WorksLikeAColleague(unittest.TestCase):
    """It says where it is after silent steps, stops trying at random after two failures, and looks at a page it made
    (measured in the browser) before calling it done."""

    def setUp(self):
        self.t = tempfile.mkdtemp()
        self.a = naimtools.Agent(self.t, auto_yes=True)

    def test_says_where_it_is(self):
        calls = [{"function": {"name": "read_file"}}]
        self.assertEqual(self.a.speak_note("", calls), "")
        self.assertEqual(self.a.speak_note("", calls), "")
        self.assertIn("UNE phrase", self.a.speak_note("", calls))  # the third silent step
        self.assertEqual(self.a.speak_note("Serveur prêt.", calls), "")  # it spoke: the count starts again

    def test_no_third_try_at_random(self):
        r1 = self.a.call_tool("run_command", {"command": "python3 -c 'import sys; sys.exit(3)'"})
        self.assertNotIn("Deux essais", r1)
        r2 = self.a.call_tool("run_command", {"command": "python3 -c 'import sys; sys.exit(4)'"})
        self.assertIn("Deux essais d'affilée ont échoué", r2)
        self.a.call_tool("run_command", {"command": "true"})
        self.assertEqual(self.a._fail_streak, 0)

    def test_looks_at_its_page(self):
        from unittest import mock
        self.a.call_tool("write_file", {"path": "index.html", "content": "<p>x</p>"})
        with mock.patch("browser.audit", return_value=["La page déborde à droite de 320 px"]) as au:
            note = self.a.look_note()
        self.assertIn("déborde", note)
        self.assertTrue(au.call_args[0][0].startswith("file://"))
        self.assertEqual(self.a.look_note(), "")  # nothing changed since: not looked at again
        self.a.call_tool("write_file", {"path": "index.html", "content": "<p>y</p>"})
        with mock.patch("browser.audit", return_value=[]):
            self.assertEqual(self.a.look_note(), "")  # it looks right: nothing to say

    def test_looks_at_its_page_folder_written_twice(self):
        from unittest import mock
        name = self.a.root.name  # « site/site/index.html » when already in « site »: the tools find it, so does the look
        r = self.a.call_tool("write_file", {"path": f"{name}/index.html", "content": "<p>x</p>"})
        self.assertTrue(r.startswith("ok"), r)
        with mock.patch("browser.audit", return_value=["1 image(s) cassée(s) : a.jpg"]) as au:
            self.assertIn("cassée", self.a.look_note())
        self.assertTrue(au.call_args[0][0].endswith("/index.html"))

    def test_lost_path_keeps_the_content(self):
        # 957 lines sent without their path: kept, then saved with the path alone — never generated a second time
        page = "<html>\n" + "<p>ligne</p>\n" * 900 + "</html>\n"
        r = self.a.call_tool("write_file", {"content": page})
        self.assertIn("is kept", r)
        r = self.a.call_tool("write_file", {"path": "landing.html", "content": ""})
        self.assertTrue(r.startswith("ok"), r)
        self.assertEqual((Path(self.a.root) / "landing.html").read_text(), page)
        r = self.a.call_tool("write_file", {"path": "vide.txt", "content": ""})  # kept once only
        self.assertEqual((Path(self.a.root) / "vide.txt").read_text(), "")

    def test_long_page_seen_screen_by_screen(self):
        # a landing page is 4 to 8 screens high: squeezed into one image it was 147 px wide, unreadable (« page incomplète »);
        # and the capture grows the window to the whole page, so a 100vh hero must stay one screen high
        import docs
        page = Path(self.a.root) / "long.html"
        page.write_text("<style>body{margin:0}.hero{min-height:100vh;background:#fce}section{height:900px}</style>"
                        "<div class=hero><h1>Haut</h1></div>" + "<section>bloc</section>" * 5)
        out, note = docs.preview_png(page, 1)
        self.assertIn("écran 1 sur", note)
        self.assertIn("page=2", note)
        w, h = docs._png_size(out)
        self.assertGreater(w, 600)
        _, last = docs.preview_png(page, 99)
        self.assertIn("fin de la page", last)
        short = Path(self.a.root) / "court.html"
        short.write_text("<p>une ligne</p>")
        self.assertNotIn("écran", docs.preview_png(short)[1])

    def test_each_brick_checked(self):
        self.a.update_todos([{"text": "serveur", "status": "in_progress"}, {"text": "page", "status": "pending"}])
        self.a.call_tool("write_file", {"path": "app.py", "content": "print(1)\n"})
        r = self.a.update_todos([{"text": "serveur", "status": "done"}, {"text": "page", "status": "pending"}])
        self.assertIn("vérifie-le maintenant", r)
        self.a.call_tool("run_command", {"command": "python3 app.py"})
        r = self.a.update_todos([{"text": "serveur", "status": "done"}, {"text": "page", "status": "done"}])
        self.assertNotIn("vérifie-le", r)

    def test_summary_checked_against_real_changes(self):
        page = ('<input id="ip" placeholder="192.0.2.99"><input id="port" value="554"><input id="path" placeholder="stream1">'
                '<select id="transport"><option value="tcp">TCP (stable)</option><option value="udp">UDP</option></select>')
        self.a.call_tool("write_file", {"path": "index.html", "content": page})
        self.a.call_tool("edit_file", {"path": "index.html", "old_text": '<input id="ip" placeholder', "new_text": '<input id="ip" value="192.0.2.10" placeholder'})
        fix = self.a.verify_summary("Pré-rempli : adresse (192.0.2.10), port (554), chemin (stream1), transport (TCP).\n"
                                    "À remplir toi-même : identifiant (admin) et mot de passe.")
        self.assertIn("« stream1 » n'est pas", fix)  # only a placeholder: not filled
        for there in ("192.0.2.10", "554", "TCP", "admin"):
            self.assertNotIn(there, fix)  # really there (a select's first option counts) — or the user's own part
        self.assertIsNone(self.a.verify_summary("Pré-rempli : chemin (stream1)."))  # checked once per request
        b = naimtools.Agent(self.t, auto_yes=True)
        self.assertIsNone(b.verify_summary("J'ai modifié le chemin (stream1)."))  # nothing changed: nothing to check against

    def test_wired(self):
        self.assertIn("helper.look_note()", (ROOT / "server.py").read_text())
        self.assertIn("helper.speak_note(", (ROOT / "server.py").read_text())
        self.assertIn("self.look_note()", (ROOT / "naimtools.py").read_text())
        self.assertIn("helper.verify_summary(content)", (ROOT / "server.py").read_text())
        self.assertIn("self.verify_summary(content)", (ROOT / "naimtools.py").read_text())


class DebuggingMethod(unittest.TestCase):
    """A bug without an error message (a wrong result, a button that does nothing) gets the debug method too, in the
    Chat as well; a bug in the user's code is debugging whatever its subject."""

    def test_chosen(self):
        import extensions as e
        for m in ("le bouton ne marche pas sur ma page", "pourquoi ma fonction moyenne renvoie un mauvais résultat",
                  "ma page reste blanche", "mon script plante avec une erreur bizarre"):
            self.assertEqual((e.match_skill(m) or {}).get("name"), "debug", m)
        for m, other in (("explique-moi la moyenne", "maths-affichage"), ("le site de la mairie ne marche pas aujourd'hui", None)):
            self.assertEqual((e.match_skill(m) or {}).get("name"), other, m)

    def test_method_and_chat(self):
        import skills_pro
        text = skills_pro.SKILLS["debug"][1] if hasattr(skills_pro, "SKILLS") else (ROOT / "skills_pro.py").read_text()
        self.assertIn("Sans message d'erreur", text)
        self.assertIn("UN changement à la fois", text)
        self.assertNotIn('not in ("debug", "application-web"', (ROOT / "server.py").read_text())  # loaded in the Chat too


class RightQuestions(unittest.TestCase):
    """It decides when a sensible default exists, asks (one card, a few choices) when it cannot know, and never asks leave
    to do what was just asked."""

    def test_permission_question_is_not_a_question(self):
        import server
        self.assertTrue(server.asks_permission("Je peux créer le fichier notes.txt avec ta liste. Veux-tu que je le fasse ?"))
        self.assertFalse(server.asks_permission("Voici le fichier. Veux-tu que j'ajoute une colonne ou un graphique ?"))  # a real choice
        self.assertFalse(server.asks_permission("Lequel veux-tu : 1) Paul Martin 2) Paul Durand ?"))
        self.assertIn("asks_permission(content)", (ROOT / "server.py").read_text())

    def test_asks_which_of_several_files(self):
        d = Path(tempfile.mkdtemp())
        (d / "clients").mkdir()
        for n in ("paul_martin.txt", "paul_durand.txt", "rapport.txt"):
            (d / ("clients" if n.startswith("paul") else ".") / n).write_text("Bonjour\n")
        a = naimtools.Agent(str(d), auto_yes=True)
        a.request_text = "ajoute le rapport à la fin du fichier de Paul"
        r = a.call_tool("edit_file", {"path": "clients/paul_durand.txt", "old_text": "Bonjour", "new_text": "Bonjour Paul"})
        self.assertIn("plusieurs fichiers correspondent à « paul »", r)
        self.assertIn("paul_martin.txt", r)
        self.assertEqual((d / "clients/paul_durand.txt").read_text(), "Bonjour\n")  # nothing changed at random
        r = a.call_tool("edit_file", {"path": "clients/paul_durand.txt", "old_text": "Bonjour", "new_text": "Bonjour Paul"})
        self.assertTrue(r.startswith("ok"), r)  # asked once: the chosen one is done
        b = naimtools.Agent(str(d), auto_yes=True)
        b.request_text = "ajoute une ligne à paul_martin.txt"
        self.assertTrue(b.call_tool("edit_file", {"path": "clients/paul_martin.txt", "old_text": "Bonjour", "new_text": "Salut"}).startswith("ok"))

    def test_speak_note_never_glued_to_a_result(self):
        for f in ("server.py", "naimtools.py"):
            self.assertNotIn('["content"] += say', (ROOT / f).read_text())

    def test_rule_in_the_chat_note(self):
        import server
        note = server.Handler.CHAT_TOOLS_NOTE
        self.assertIn("never ask leave", note)
        self.assertIn("ONE question with ask_user", note)


class KnowledgeSpeedAmbiguity(unittest.TestCase):
    """An API that is not what it was thought: the installed documentation first. A long code file: its head and plan
    first, whole when asked again (texts always whole). Several contacts: asked before a message or a call."""

    def setUp(self):
        self.t = tempfile.mkdtemp()
        self.a = naimtools.Agent(self.t, auto_yes=True)

    def test_api_error_sends_to_the_docs(self):
        r = self.a.call_tool("run_command", {"command": "python3 -c 'from math import pell'"})
        self.assertRegex(r, r"doc\.py|help\(m\.f\)")  # the documentation tool (or Python's help without the plugin)
        r = self.a.call_tool("run_command", {"command": "python3 -c 'from math import pell'"})
        self.assertNotRegex(r, r"doc\.py|help\(m\.f\)")  # once is enough

    def test_long_code_by_its_plan_then_whole(self):
        body = "\n".join(["<html>", "<head>"] + [f"<p>ligne {i} " + "x" * 40 + "</p>" for i in range(300)] + ['<section id="galerie">']
                         + [f"<p>suite {i} " + "x" * 40 + "</p>" for i in range(300)] + ["<script>", "function demarrer() {}", "</script>"])
        Path(self.t, "page.html").write_text(body)
        r = self.a.read_file("page.html")
        self.assertIn("les 150 premières sont montrées", r)
        self.assertIn('<section id="galerie">', r)  # in the plan, with its line number
        self.assertIn("function demarrer", r)
        self.assertNotIn("suite 299", r)
        self.assertIn("suite 299", self.a.read_file("page.html"))  # asked again: whole — nothing is ever refused
        self.assertIn("suite 299", naimtools.Agent(self.t, auto_yes=True).read_file("page.html", offset=550, limit=100))

    def test_texts_and_short_files_whole(self):
        Path(self.t, "long.txt").write_text("".join(f"ligne {i} du livre à résumer\n" for i in range(1, 2001)))
        self.assertIn("ligne 2000", self.a.read_file("long.txt"))  # a text to read: always whole
        Path(self.t, "court.py").write_text("x = 1\n" * 40)
        self.assertEqual(self.a.read_file("court.py"), "x = 1\n" * 40)

    def test_two_contacts_asked_before_sending(self):
        from unittest import mock
        people = [{"nom": "Paul Martin", "email": "pm@example.com"}, {"nom": "Paul Durand", "email": "pd@example.com"}]
        self.a.request_text = "envoie le rapport à Paul"
        with mock.patch("mailer.find_contact", return_value=people):
            self.assertIn("ask_user", self.a.chercher_contact("Paul"))
        r = self.a.call_tool("send_email", {"to": "pd@example.com", "subject": "Rapport", "body": "x"})
        self.assertIn("plusieurs personnes correspondent", r)
        self.a._which_person = None  # what ask_user does: the next sending follows the answer
        b = naimtools.Agent(self.t, auto_yes=True)
        b.request_text = "envoie le rapport à Paul Durand"
        with mock.patch("mailer.find_contact", return_value=people):
            b.chercher_contact("Paul")
        self.assertIsNone(getattr(b, "_which_person", None))  # named in full: no question


class Documentation(unittest.TestCase):
    """Checked in the documentation instead of guessed: the installed Python's own help, a name that does not exist with
    the near ones, a command's manual."""
    DOC = ROOT / "plugins_builtin/documentation/skills/documentation/doc.py"

    def run_doc(self, *a):
        return subprocess.run([sys.executable, str(self.DOC), *a], capture_output=True, text=True, timeout=60)

    def test_installed_python(self):
        r = self.run_doc("python", "datetime.datetime.strftime")
        self.assertIn("strftime", r.stdout)
        r = self.run_doc("python", "datetime.datetime.format_date")
        self.assertIn("n existe pas", r.stdout + r.stderr)

    def test_command_manual(self):
        self.assertIn("interpreted", self.run_doc("cmd", "python3").stdout.lower())  # its manual

    def test_skill_and_hint(self):
        import re
        t = json.loads((ROOT / "plugins_builtin/documentation/plugin.json").read_text())["triggers"]["documentation"]
        self.assertRegex("quels sont les paramètres de la fonction round", re.compile(t, re.I))
        self.assertIn("documentation/doc.py", (ROOT / "naimtools.py").read_text())


class ThreeD(unittest.TestCase):
    """3D in a web page with three.js: a verified model (fixed version, size that follows, reduced motion, cleanup), chosen
    when 3D is asked, even inside a page design request."""

    def test_model_and_skill(self):
        d = ROOT / "plugins_builtin/threejs/skills/threejs-3d"
        m = (d / "modele.html").read_text()
        self.assertIn("three@0.185.0", m)  # a fixed version, never « latest »
        for must in ("setAnimationLoop", "ResizeObserver", "prefers-reduced-motion", "dispose()", "THREE.Timer"):
            self.assertIn(must, m)
        self.assertIn("modele.html", (d / "SKILL.md").read_text())

    def test_chosen(self):
        import extensions as e, plugins
        plugins.ensure_builtin()
        for m in ("fais-moi un système solaire en 3D", "une landing page avec un globe qui tourne en 3d"):
            self.assertEqual((e.match_skill(m) or {}).get("name"), "threejs-3d", m)
        self.assertNotEqual((e.match_skill("affiche-moi l'heure dans un beau carré") or {}).get("name"), "threejs-3d")


class ShopWebsite(unittest.TestCase):
    """« une landing page pour mon salon »: a sober editorial model copied and adapted, not 900 lines written from
    nothing in the generated look (pink gradients, emoji icons, invented figures)."""

    def test_model_and_skill(self):
        d = ROOT / "plugins_builtin/site-vitrine/skills/site-vitrine"
        m = (d / "modele.html").read_text()
        for must in ("--papier", "--encre", "--accent", "prefers-reduced-motion", ":focus-visible", "@media (max-width"):
            self.assertIn(must, m)
        for never in ("linear-gradient", "unsplash", "★", "5000+"):
            self.assertNotIn(never, m)
        s = (d / "SKILL.md").read_text()
        self.assertIn("modele.html", s)
        self.assertIn("edit_file", s)

    def test_chosen(self):
        import extensions as e, plugins
        plugins.ensure_builtin()
        for m in ("fais-moi une landing page moderne pour mon salon de coiffure à Bordeaux", "un site vitrine pour mon restaurant",
                  "crée un site web pour mon cabinet d'architecte"):
            self.assertEqual((e.match_skill(m) or {}).get("name"), "site-vitrine", m)
        self.assertEqual((e.match_skill("une landing page avec un globe qui tourne en 3d") or {}).get("name"), "threejs-3d")
        self.assertNotEqual((e.match_skill("améliore le design de mon application") or {}).get("name"), "site-vitrine")


class NetworkAndCamera(unittest.TestCase):
    """« analyse mon réseau », « une app pour ma caméra »: a read-only scan of the user's own network, a probe for the RTSP
    path, and a verified camera app to copy (one ffmpeg, its messages in a file so that it never freezes)."""

    def test_triggers(self):
        import re
        t = json.loads((ROOT / "plugins_builtin/reseau/plugin.json").read_text())["triggers"]
        for m in ("analyse mon réseau", "quels appareils sont connectés sur mon réseau", "trouve ma caméra"):
            self.assertRegex(m, re.compile(t["reseau-local"], re.I))
        for m in ("fais une application pour voir ma caméra", "ma caméra IP en rtsp", "vidéosurveillance de la maison"):
            self.assertRegex(m, re.compile(t["camera-ip"], re.I))
        self.assertNotRegex("explique les réseaux de neurones", re.compile(t["reseau-local"], re.I))

    def test_scan_stays_local_and_read_only(self):
        src = (ROOT / "plugins_builtin/reseau/skills/reseau-local/scan.py").read_text()
        self.assertIn("is_private", src)  # never a public address
        for bad in ("requests.post", "subprocess.run([\"sudo", "nmap"):
            self.assertNotIn(bad, src)

    def test_camera_template(self):
        d = ROOT / "plugins_builtin/reseau/skills/camera-ip"
        srv = (d / "modele/server.py").read_text()
        self.assertIn("ffmpeg.log", srv)  # not a pipe nobody reads (ffmpeg froze)
        self.assertNotIn("stderr=subprocess.PIPE", srv)
        self.assertIn("SIGINT", srv)  # the MP4 closed properly
        self.assertNotRegex(srv, r"192\.168\.\d+\.\d+")  # no address written in
        self.assertIn("CAM_PASS", (d / "sonde.py").read_text())  # the login from the environment, never in a file
        self.assertIn("modele/", (d / "SKILL.md").read_text())
        import importlib.util
        spec = importlib.util.spec_from_file_location("cam_modele", d / "modele/server.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        self.assertEqual(m.hide("input rtsp://user:secret@192.0.2.10:554/."), "input rtsp://•••@192.0.2.10:554/.")  # never on screen
        self.assertIn("stream1", m.PATHS)  # an empty path is found by itself
        self.assertIn("camera.json", (d / "SKILL.md").read_text())  # pre-filled without reading the long page (4 min)
        self.assertIn("/api/config", (d / "modele/index.html").read_text())
        page = (ROOT / "web/index.html").read_text()
        self.assertIn("&& !reply.appUrl)", page)  # the running app stays in the preview, its bare page not opened over it
        self.assertIn("x.cwd === dir", page)  # a click on the page of a running app opens the app


class NoLoopsInAnswers(unittest.TestCase):
    """« La solution est … est faux. / La solution est … ? » forty times: a cycle of lines is cut (the first round kept),
    the answer goes on with the tools to compute the result for real, and the old loop is shortened when read again."""

    def test_cycle_detected_and_cut(self):
        import server
        t = "Intro.\nLa solution est (1, 2) est faux.\nLa solution est (1, 2) ?\n" * 5 + "La sol"
        self.assertEqual(t[:server.loop_start(t)], "Intro.\nLa solution est (1, 2) est faux.\nLa solution est (1, 2) ?\n")
        self.assertIsNone(server.loop_start("une première ligne\nune deuxième ligne\nune troisième ligne\n"))
        self.assertIsNone(server.loop_start("ok\nok\nok\nok\n"))  # short lines (a list of « ok ») are not a loop

    def test_old_loop_shortened(self):
        import server
        out = server.collapse_repeats("Début\n" + "La solution est faux.\n" * 40)
        self.assertEqual(out.count("La solution est faux."), 2)
        self.assertIn("lignes répétées retirées", out)

    def test_maths_recipes_are_right(self):
        text = (ROOT / "plugins_builtin/mathematiques/skills/maths-affichage/SKILL.md").read_text()
        code = text.split("```python\n", 1)[1].split("```", 1)[0]
        ns = {}
        exec(code, ns)
        self.assertEqual(ns["pell"](61), (1766319049, 226153980))
        self.assertEqual(ns["bezout"](240, 46), (2, -9, 47))
        self.assertEqual(ns["facteurs"](360), [2, 2, 2, 3, 3, 5])

    def test_compute_maths_gets_the_tools(self):
        import server
        h = server.Handler.__new__(server.Handler)
        q = lambda m: h.quick_answer({"message": m, "history": []}, False, False, False, False, None)
        self.assertFalse(q("Trouve tous les couples d'entiers strictement positifs (x,y) qui vérifient x^2 - 61y^2 = 1"))
        self.assertFalse(q("donne la plus petite solution entière"))
        self.assertTrue(q("explique-moi le théorème de Pythagore"))
        src = (ROOT / "server.py").read_text()
        self.assertIn('"_verify": True', src)  # a loop in a quick answer goes on with the tools


class ChatActsUnlessLesson(unittest.TestCase):
    """The Chat may change files for any request; only a lesson or a question is answered in the conversation
    (a rule that waited for a work word left « mets le bouton en rouge » without the tools to do it)."""

    def lesson(self, m):
        import server as s
        file_work = bool(s.FILE_WORK_RE.search(m))
        return not file_work and bool(s.pure_question(m) or s.LESSON_RE.search(m)
                                      or (s.MATH_ASK_RE.search(m) and not s.FILE_NAMED_RE.search(m)))

    def test_work_without_a_work_word_can_act(self):
        for m in ("fais que le bouton soit rouge", "mets le titre en gras dans index.html", "le menu doit être à gauche",
                  "passe le port du serveur à 9000", "tu peux mettre le fond en noir ?", "vas-y"):
            self.assertFalse(self.lesson(m), m)

    def test_lessons_stay_in_the_conversation(self):
        for m in ("montre-moi comment marche le tri par insertion en Python", "explique-moi les closures",
                  "c'est quoi une API REST ?", "donne-moi un exemple de boucle for", "pourquoi mon code est lent",
                  "quelle est la différence entre une liste et un tuple ?", "pose la multiplication 234 × 12"):
            self.assertTrue(self.lesson(m), m)

    def test_the_server_uses_it(self):
        src = (ROOT / "server.py").read_text()
        self.assertIn("if lesson and name not in ANSWER_TOOLS", src)

    def test_a_follow_up_on_a_file_keeps_the_tools(self):
        import server
        h = server.Handler.__new__(server.Handler)
        hist = [{"role": "user", "content": "crée un script calcul.py qui fait la moyenne d'une liste de notes"},
                {"role": "assistant", "content": "J'ai créé le script calcul.py."}]
        body = {"message": "je veux que la moyenne soit arrondie à 2 chiffres", "history": hist}
        self.assertFalse(h.quick_answer(body, False, False, False, False, None))  # not the path without tools
        self.assertTrue(h.quick_answer({**body, "history": []}, False, False, False, False, None))  # alone: maths
        self.assertTrue(h.quick_answer({**body, "message": "explique-moi comment marche une boucle for"}, False, False, False, False, None))


class AnswerHere(unittest.TestCase):
    """« écris directement dans la session chat »: no switch to the Agent, no file — even for a long course (it once
    wrote 8 files twice despite it); « test » of maths is not a code test."""

    MSG = ("faite moi une révision pour les equiations compexe avec la géométrie, cours test et excercie et leur "
           "correction ecrit directement dans la sesssion chat")

    def test_detected(self):
        for t in (self.MSG, "écris-le ici, pas de fichier", "ne crée aucun fichier", "dans le chat"):
            self.assertTrue(naimtools.answer_here(t), t)
        for t in ("fais-moi un site flask", "crée le fichier app.py", "une session de sport à 18h ?"):
            self.assertFalse(naimtools.answer_here(t), t)

    def test_no_agent_no_file(self):
        import server
        import server
        h = server.Handler.__new__(server.Handler)
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(h.big_work({"message": self.MSG, "settings": {"project": d}, "history": []}))
            self.assertIsNone(h.big_work({"message": "continue", "settings": {"project": d},
                                          "history": [{"role": "user", "content": self.MSG}]}))
            a = naimtools.Agent(d, "naim", auto_yes=True, emit=lambda e: None, approver=lambda *x: True)
            a._answer_here = True
            self.assertTrue(a._dispatch("write_file", {"path": "x.md", "content": "a"}, None).startswith("refused"))

    def test_maths_not_code_tests(self):
        import extensions as ext
        self.assertNotEqual((ext.match_skill(self.MSG) or {}).get("name"), "tests-unitaires")
        self.assertEqual(ext.match_skill("ajoute des tests unitaires au projet")["name"], "tests-unitaires")


class QuickAnswers(unittest.TestCase):
    """Explain, write, revise, maths: answered like a plain chat app (no tools, seconds before the first word);
    files, the web, a mail, a server, the Mac keep the tools."""

    def test_routing(self):
        import server
        import server
        h = server.Handler.__new__(server.Handler)
        q = lambda m: h.quick_answer({"message": m, "history": []}, False, bool(server.WEB_NEED_RE.search(m)), False, False, "")  # noqa: E731
        for m in ("explique-moi les nombres complexes", "Pose et calcule 234,56 × 12,3", "c'est quoi une boucle for ?",
                  "rédige un poème sur la mer", "salut"):
            self.assertTrue(q(m), m)
        for m in ("cherche sur internet le prix du bitcoin", "crée le fichier app.py", "lance le serveur", "envoie un mail à Paul",
                  "fais ma lettre de motivation en pdf", "corrige le bug de mon app"):
            self.assertFalse(q(m), m)


class LightConversation(unittest.TestCase):
    """Pages and files already used keep only their beginning (a few web searches once made 42,000 tokens to read
    again, each word then written at 6/s): the newest result stays whole for the step that reads it."""

    def test_shorten(self):
        import server
        msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "cherche"},
                {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "web_fetch"}}]}, {"role": "tool", "content": "A" * 9000},
                {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "web_fetch"}}]}, {"role": "tool", "content": "B" * 9000}]
        server.shorten_used_results(msgs)
        sizes = [len(m["content"]) for m in msgs if m["role"] == "tool"]
        self.assertLess(sizes[0], 1600)
        self.assertEqual(sizes[1], 9000)
        server.shorten_used_results(msgs)
        self.assertEqual([len(m["content"]) for m in msgs if m["role"] == "tool"], sizes)


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
            (t / "p.json").write_text(json.dumps([["Jean Dupont", "Marie Curie"], ["Poste chez ACME en 2020", "Chercheuse"], ["absent", "x"], ["a", "b", "c"]]))
            r = subprocess.run([sys.executable, "-I", str(self.D / "remplir_modele.py"), "m.html", "p.json", "o.html"], cwd=t,
                               check=True, capture_output=True, text=True)
            out = (t / "o.html").read_text()
            self.assertIn("Marie Curie", out)
            self.assertIn("Chercheuse", out)
            self.assertIn("2 texte(s) remplacé(s) sur 4", r.stdout)
            self.assertIn("ignoré", r.stdout)  # a line of three texts: told, not a crash
            self.assertIn(".carte{border:2px solid}", out)
            self.assertIn("PDF", r.stdout.splitlines()[-1])  # the PDF in the same step (or how to make it)

    def test_cv_from_facts(self):
        # three jobs, two diplomas, a projects section: everything kept, in the source's order (the model has 2 jobs)
        cv = {"nom": "Marie Curie", "titre": "Chercheuse", "contact": [["E-mail", "m@c.fr"]], "profil": "Physicienne.",
              "experiences": [{"quand": str(y), "poste": f"Poste {y}", "ou": "Labo", "points": [f"Fait {y}"]} for y in (2020, 2010, 2000)],
              "formations": [{"quand": "1995", "diplome": "Doctorat"}, {"quand": "1990", "diplome": "Licence"}],
              "sections": [{"titre": "Projets", "items": [{"titre": "Radium"}]}],
              "competences": ["Physique", "Chimie"], "langues": [["Polonais", "natif"]],
              "ordre": ["profil", "competences", "experiences", "Projets", "formations"]}
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            (t / "cv.json").write_text(json.dumps(cv))
            r = subprocess.run([sys.executable, "-I", str(self.D / "cv_pro.py"), "cv.json", "cv.html"], cwd=t, check=True, capture_output=True, text=True)
            out = (t / "cv.html").read_text()
        self.assertIn("3 expérience(s), 2 formation(s)", r.stdout)
        for x in ("Poste 2020", "Poste 2010", "Poste 2000", "Doctorat", "Licence", "Radium", "Polonais", "Chimie"):
            self.assertIn(x, out)
        self.assertNotIn("Intitulé du poste", out)  # nothing of the model's sample texts
        self.assertLess(out.index("Compétences"), out.index("Expérience"))
        self.assertLess(out.index("Projets"), out.index("Formation"))

    def test_cv_keys_named_otherwise_are_kept(self):
        # Naim wrote its own names (entreprise, periode, missions, projets, skill groups, contact dict): nothing is lost,
        # and the photo of the Word CV beside cv.json comes along
        import zipfile
        cv = {"nom": "Marie Curie", "contact": {"telephone": "06", "email": "m@c.fr"},
              "competences": {"programmation": ["Python", "C"], "bases_de_donnees": ["DB2"], "langues": ["anglais (courant)"]},
              "experiences": [{"poste": "Chercheuse", "entreprise": "Institut", "periode": "1900", "missions": ["Radium"]}],
              "projets": [{"nom": "Polonium", "description": "Découverte."}], "publications": "Thèse 1903",
              "formations": [{"diplome": "Doctorat", "etablissement": "Sorbonne", "periode": "1903"}],
              "ordre": ["profil", "competences", "experiences", "projets", "publications", "formations"]}
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            with zipfile.ZipFile(t / "source.docx", "w") as z:
                z.writestr("word/media/image1.png", b"\x89PNG fake photo")
            (t / "cv.json").write_text(json.dumps(cv))
            r = subprocess.run([sys.executable, "-I", str(self.D / "cv_pro.py"), "cv.json", "cv.html"], cwd=t, check=True, capture_output=True, text=True)
            out = (t / "cv.html").read_text()
        for x in ("Institut", "1900", "Radium", "Polonium", "Découverte.", "Thèse 1903", "Sorbonne", "Bases de données",
                  "Python, C", "Anglais", "courant", "m@c.fr", 'class="photo"'):
            self.assertIn(x, out)
        self.assertIn("3 compétence(s), 1 langue(s), autres rubriques : Projets (1), Publications, photo : oui", r.stdout)
        self.assertLess(out.index("Projets"), out.index("Publications"))
        self.assertLess(out.index("Publications"), out.index("Formation"))

    def test_cv_photo_from_the_word_file(self):
        import zipfile
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            with zipfile.ZipFile(t / "cv.docx", "w") as z:
                z.writestr("word/document.xml", "<w/>")
                z.writestr("word/media/image1.png", b"\x89PNG fake photo")
            (t / "cv.json").write_text(json.dumps({"nom": "Marie Curie", "photo": str(t / "cv.docx")}))
            subprocess.run([sys.executable, "-I", str(self.D / "cv_pro.py"), "cv.json", "cv.html"], cwd=t, check=True, capture_output=True, text=True)
            self.assertIn('class="photo" alt="" src="data:image/png;base64,', (t / "cv.html").read_text())

    def test_word_given_is_still_a_cv(self):
        import extensions
        t = "le pdf du cv n'est pas fidèle a ce que j'ai fourni, le voici à nouveau format word, tu vas générer le pdf"
        self.assertEqual((extensions.match_skill(t, extensions.HOME, set()) or {}).get("name"), "cv-lettre")
        self.assertEqual((extensions.match_skill("utilise le skill word pour ce rapport", extensions.HOME, set()) or {}).get("name"), "word")
        t = "Fais mon CV en PDF avec le style pdf-pro à partir de ce Word, avec ma photo à droite"
        self.assertEqual((extensions.match_skill(t, extensions.HOME, set()) or {}).get("name"), "cv-lettre")  # a style, not the method

    def test_markdown_course_to_one_pdf(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("pp2", Path(__file__).resolve().parents[1] / "plugins_builtin/pdf-pro/skills/pdf-pro/pdfpro.py")
        pp = importlib.util.module_from_spec(spec); spec.loader.exec_module(pp)
        h = pp.md_html("## Titre\n\nUn **mot**.\n\n- a\n- b\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n```cobol\n       MOVE 1 TO X.\n```\n\n> Note")
        for x in ("<h3>Titre</h3>", "<strong>mot</strong>", "<ul><li>a</li><li>b</li></ul>", "<th>A</th>", '<pre class="code cobol">', 'callout info'):
            self.assertIn(x, h)
        self.assertIn('<span class="k">MOVE</span>', pp.highlight("       MOVE 1 TO X.", "cobol"))
        from unittest import mock
        with tempfile.TemporaryDirectory() as t, mock.patch.object(pp, "render", lambda src, out, c="": None):
            t = Path(t)
            (t / "README.md").write_text("# Cours X\n\nUn cours sur X couvre :\n\n- a")
            (t / "01-a.md").write_text("# Cours X - Début\n\nTexte.")
            (t / "02-b.md").write_text("# Cours X - Suite\n\nTexte.")
            pp.render_md([t / "README.md", t / "01-a.md", t / "02-b.md"], t / "c.pdf")
            page = (t / "c.html").read_text()
        self.assertIn("<h1>Cours X</h1>", page)
        self.assertIn("Un cours sur X couvre.", page)
        self.assertIn('<span class="num">01</span>Début', page)
        self.assertIn('<span class="num">02</span>Suite', page)

    def test_any_document_to_pro_pdf(self):
        import importlib.util
        from unittest import mock
        spec = importlib.util.spec_from_file_location("pp3", Path(__file__).resolve().parents[1] / "plugins_builtin/pdf-pro/skills/pdf-pro/pdfpro.py")
        pp = importlib.util.module_from_spec(spec); spec.loader.exec_module(pp)
        self.assertEqual(pp._caps_titles("PROFIL\nTexte normal.\n06 52 90 96 62"), "## Profil\nTexte normal.\n06 52 90 96 62")
        with tempfile.TemporaryDirectory() as t, mock.patch.object(pp, "render", lambda src, out, c="": None):
            t = Path(t)
            (t / "notes.csv").write_text("Nom;Note\nAlice;15\n")
            (t / "compte_rendu.txt").write_text("RÉUNION\n\nTexte.\n")
            pp.render_docs([t / "notes.csv"], t / "notes.pdf")
            self.assertIn("<th>Nom</th>", (t / "notes.html").read_text())
            pp.render_docs([t / "compte_rendu.txt"], t / "cr.pdf")
            page = (t / "cr.html").read_text()
            self.assertIn("<h1>Compte rendu</h1>", page)
            self.assertIn("<h2>Réunion</h2>", page)

    def test_quiz_to_pro_pdf(self):
        import importlib.util
        from unittest import mock
        spec = importlib.util.spec_from_file_location("pp4", Path(__file__).resolve().parents[1] / "plugins_builtin/pdf-pro/skills/pdf-pro/pdfpro.py")
        pp = importlib.util.module_from_spec(spec); spec.loader.exec_module(pp)
        with tempfile.TemporaryDirectory() as t, mock.patch.object(pp, "render", lambda src, out, c="": None):
            t = Path(t)
            (t / "quiz.json").write_text(json.dumps({"titre": "Q", "questions": [{"q": "A ?", "choix": ["x", "y"], "bonne": 1,
                                                    "indice": "i", "explication": "parce que"}], "cartes": [{"recto": "r", "verso": "v"}]}))
            pp.render_quiz(t / "quiz.json", t / "q.pdf")
            page = (t / "q.html").read_text()
        for x in ('class="qz"', "break-inside:avoid", "<b>A</b>", "Corrigé", "1. B", "parce que", 'class="card"'):
            self.assertIn(x, page)

    def test_colour_asked(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("pp", Path(__file__).resolve().parents[1] / "plugins_builtin/pdf-pro/skills/pdf-pro/pdfpro.py")
        pp = importlib.util.module_from_spec(spec); spec.loader.exec_module(pp)
        self.assertEqual(pp.accent_css(""), "")
        self.assertIn("--clay:#7a7a74", pp.accent_css("gris"))
        self.assertIn("--clay:#123456", pp.accent_css("#123456"))
        page = pp.page('<html><head><style>:root{--clay:#7a7a74;--clay-soft:#eee}</style></head><body>x</body></html>')
        self.assertGreater(page.rindex("--clay:#7a7a74"), page.index("--clay: #c96442"))  # the colour asked wins over the theme

    def test_any_pdf_to_make_is_pdf_pro(self):
        import extensions
        name = lambda t: (extensions.match_skill(t, extensions.HOME, set()) or {}).get("name")  # noqa: E731
        # the attached file's name says what it is, the user's words alone are only « le pdf »
        self.assertEqual(name("Document joint « Lettre_motivation_Professeur.pdf » :\n[PDF]\n\nMadame,\n\ndonne moi le pdf merci"), "cv-lettre")
        for t in ("donne moi le pdf", "fais un pdf de ce texte : bonjour à tous", "mets ce texte en pdf"):
            self.assertEqual(name(t), "pdf-pro", t)
        self.assertEqual(name("crée moi un cv"), "cv-lettre")
        for t in ("fusionne ces deux pdf", "extrais la page 3 du pdf"):  # operations on PDFs stay with the PDF tool
            self.assertNotEqual(name(t), "pdf-pro", t)

    def test_word_tells_its_pictures(self):
        import zipfile
        import docs
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / "cv.docx"
            with zipfile.ZipFile(f, "w") as z:
                z.writestr("word/media/image1.png", b"x" * 3000)
            self.assertIn("Images dans ce document : image1.png", docs.pictures_of(f))

    def test_typographic_apostrophe(self):
        with tempfile.TemporaryDirectory() as t:
            real = Path(t) / "Capture d\u2019écran 1.png"
            real.write_bytes(b"png")
            a = naimtools.Agent(t, "naim")
            self.assertEqual(a.resolve(str(Path(t) / "Capture d'écran 1.png")), real.resolve())
            self.assertIn(str(real), a._apostrophe_hint(f'cp "{t}/Capture d\'écran 1.png" /tmp/x.png'))



class FinishTheWork(unittest.TestCase):
    def test_write_it_here(self):
        self.assertTrue(naimtools.answer_here("ecrit le cv ici"))
        self.assertFalse(naimtools.answer_here("viens ici demain ?"))

    def test_ends_announcing(self):
        import server
        self.assertTrue(server.ends_announcing("J'ai lu le CV. Je vais maintenant le reformuler."))
        self.assertFalse(server.ends_announcing("Je vais bien, merci !"))
        self.assertFalse(server.ends_announcing("Voici ton CV complet."))

    def test_broken_quote_hint(self):
        """« Je l'ai » inside osascript -e '…' cuts the command: Naim is told to pass the text apart, not to type input."""
        with tempfile.TemporaryDirectory() as d:
            a = naimtools.Agent(d, "naim", auto_yes=True, emit=lambda e: None, approver=lambda *x: True)
            r = a.run_command("echo 'Je l'ai fini'")
            self.assertIn("APART", r)
            self.assertNotIn("keyboard input", r)



class FollowThePlan(unittest.TestCase):
    """A long task (a book) stops far more often than three times: while it moves forward, it goes on to the end of
    its list; once it no longer moves, it stops instead of going round in circles."""

    def run_pages(self, pages, progress=True):
        from unittest import mock
        with tempfile.TemporaryDirectory() as d:
            a = naimtools.Agent(d, "naim", auto_yes=True, emit=lambda e: None, approver=lambda *x: True)
            a.todos = [{"text": f"Traduire la page {i}", "status": "pending"} for i in range(1, pages + 1)]
            calls = []

            def fake(model, messages, **kw):
                calls.append(1)
                left = [t for t in a.todos if t["status"] != "done"]
                if len(calls) % 2 and left and progress:  # it writes a page…
                    n = a.todos.index(left[0]) + 1
                    return {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "write_file",
                            "arguments": {"path": f"p{n}.md", "content": f"Page {n} traduite en entier, fidèlement."}}}]}
                if left and progress:  # …ticks it off, then stops as if it were finished
                    left[0]["status"] = "done"
                return {"role": "assistant", "content": "La page est traduite."}

            with mock.patch.object(naimtools, "chat_watched", fake):
                a.run("traduis le livre")
            return a, len(calls)

    def test_goes_to_the_end(self):
        a, _ = self.run_pages(8)
        self.assertEqual([t["status"] for t in a.todos], ["done"] * 8)

    def test_announces_then_does(self):
        """After a restart its list is empty: « 6 pages à traiter. Je continue avec la page 188. » is not an end."""
        from unittest import mock
        with tempfile.TemporaryDirectory() as d:
            a = naimtools.Agent(d, "naim", auto_yes=True, emit=lambda e: None, approver=lambda *x: True)
            pages = []

            def fake(model, messages, **kw):
                last = str(messages[-1].get("content") or "")
                if len(pages) >= 6:
                    return {"role": "assistant", "content": "Les 193 pages sont traduites."}
                if last.startswith("ok: wrote") or "Fais-le maintenant" in last or "traduis" in last:
                    if "Fais-le" in last or "traduis" in last:
                        pages.append(188 + len(pages))
                        return {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "write_file",
                                "arguments": {"path": f"p{pages[-1]}.md", "content": f"Page {pages[-1]} traduite en entier."}}}]}
                return {"role": "assistant", "content": f"{6 - len(pages)} pages à traiter. Je continue avec la page {188 + len(pages)}."}

            with mock.patch.object(naimtools, "chat_watched", fake):
                a.run("continue : traduis les pages 188 à 193")
            self.assertEqual(pages, list(range(188, 194)))

    def test_what_is_an_announcement(self):
        for s in ("Je la traduis maintenant.", "Je l'écris maintenant.", "J'écris la suite.", "Je continue avec l'étape suivante.",
                  "Je reprends là où j'en étais.", "Je vais continuer.", "Je vais traiter les 4 étapes restantes.",
                  "Je l'assemble maintenant.", "Je vais l'assembler."):
            self.assertTrue(naimtools.ANNOUNCE_RE.search(s), s)
        for s in ("Tout est fini : le fichier est dans Fichiers.", "Si tu veux, je continue demain.", "Je te l'envoie si tu veux.",
                  "Je vais bien, merci !", "Voici le fichier.", "Dis-moi si je dois continuer."):
            self.assertFalse(naimtools.ANNOUNCE_RE.search(s), s)

    def test_stops_when_nothing_moves(self):
        _, n = self.run_pages(8, progress=False)
        self.assertLess(n, 10)


class HooksOfOtherAgents(unittest.TestCase):
    """A plugin's hooks written for another agent: its names, its JSON answers, its background hooks."""

    def run_hook(self, cmd, event="PreToolUse", foreign=True, payload=None, **h):
        import hooks
        hk = {event: [{"matcher": "", "command": cmd, "timeout": 10, "source": "t", "root": "", "foreign": foreign, **h}]}
        with tempfile.TemporaryDirectory() as d:
            return hooks.run(hk, event, payload or {"tool_name": "write_file", "tool_input": {"path": "a.py", "content": "x"}},
                             d, tool="write_file"), d

    def test_their_names(self):
        (b, m, c), d = self.run_hook('python3 -c "import json,sys; d=json.load(sys.stdin); '
                                     'print(json.dumps({\'additionalContext\': d[\'tool_name\'] + \' \' + d[\'tool_input\'][\'file_path\']}))"')
        self.assertTrue(c.startswith("Write ") and c.endswith("/a.py"), c)

    def test_deny_and_quiet_stdout(self):
        (b, m, c), _ = self.run_hook('echo \'{"hookSpecificOutput": {"permissionDecision": "deny", "permissionDecisionReason": "non"}}\'')
        self.assertTrue(b)
        self.assertEqual(m, "non")
        (b, m, c), _ = self.run_hook("echo bavard", event="PostToolUse")
        self.assertEqual((b, m, c), (False, "", ""))  # what it prints after an action does not fill Naim's memory
        (b, m, c), _ = self.run_hook("echo vu", event="PostToolUse", foreign=False)
        self.assertEqual(c, "vu")  # Naim's own hooks: read as before
        (b, m, c), _ = self.run_hook("echo contexte", event="UserPromptSubmit", payload={"prompt": "x"})
        self.assertEqual(c, "contexte")

    def test_async_does_not_wait(self):
        import time
        t = time.time()
        (b, m, c), _ = self.run_hook("sleep 3", **{"async": True})
        self.assertLess(time.time() - t, 1)

    def test_settings_given(self):
        (b, m, c), _ = self.run_hook('python3 -c "import os,json; print(json.dumps({\'additionalContext\': os.environ[\'ECC_GATEGUARD\']}))"',
                                     env={"ECC_GATEGUARD": "off"})
        self.assertEqual(c, "off")


class RewriteForReal(unittest.TestCase):
    def test_same_text_again(self):
        import server
        old = "Profil. " + "Programmeur titulaire d'un Master MIAGE, expert en bases de donnees. " * 6
        self.assertTrue(server.same_again("ecrit le ici avec du style", "Voici. " + old, [old]))
        self.assertFalse(server.same_again("ajoute mon permis B", "Voici. " + old, [old]))



class SafeSavesAndEngines(unittest.TestCase):
    def test_whole_writes_never_mix(self):
        import threading
        import server
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "c.json"
            texts = [json.dumps({"n": i, "pad": "x" * (5000 - i * 200)}) for i in range(20)]
            ts = [threading.Thread(target=server.write_whole, args=(f, x)) for x in texts]
            [x.start() for x in ts]
            [x.join() for x in ts]
            self.assertIn(f.read_text(), texts)  # one whole save, never the end of another left behind
            self.assertEqual([x.name for x in Path(d).iterdir()], ["c.json"])

    def test_only_orphans_on_this_port(self):
        import llamacpp
        from unittest import mock
        ps = ("  101     1 /Users/u/.naim/models/llama-server-naim -m m.gguf --port 8081 -c 8\n"
              "  102  4000 /Users/u/.naim/models/llama-server-naim -m m.gguf --port 8081 -c 8\n"
              "  103     1 /Users/u/.naim/models/llama-server-naim -m m.gguf --port 8082 -c 8\n"
              "  104     1 /usr/local/bin/llama-server --port 8081\n")
        killed = []
        with mock.patch.object(llamacpp.subprocess, "run", return_value=mock.Mock(stdout=ps)), \
                mock.patch.object(llamacpp.os, "kill", side_effect=lambda pid, sig: killed.append(pid)):
            self.assertEqual(llamacpp.reap_orphans(8081), 1)
        self.assertEqual(killed, [101])  # not this Naim's engine (102), not the images one (103), not another program (104)

    def test_copied_translation_is_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            a = naimtools.Agent(d, "naim", auto_yes=True, emit=lambda e: None, approver=lambda *x: True)
            src = "\n".join(f"This is the original English sentence number {i} of the old book." for i in range(12))
            (Path(d) / "page.txt").write_text(src)
            a.read_file("page.txt")
            r = a.write_file("page_fr.md", "CHAPITRE I.\n" + src)
            self.assertIn("NOT done", r)
            fr = "\n".join(f"Ceci est la phrase française numéro {i} du vieux livre, enfin traduite." for i in range(12))
            self.assertNotIn("NOT done", a.write_file("page_fr2.md", fr))



class WorkOutsideTheProject(unittest.TestCase):
    def test_write_in_attachments_folder_and_undo(self):
        """The book's pages are written in the attachments' folder (not the project): the write works, the undo too."""
        import extensions as ext
        with tempfile.TemporaryDirectory() as proj, tempfile.TemporaryDirectory() as fake_joints:
            old = naimtools.JOINTS
            naimtools.JOINTS = Path(fake_joints)
            try:
                a = naimtools.Agent(proj, "naim", auto_yes=True, emit=lambda e: None, approver=lambda *x: True)
                f = Path(fake_joints) / "conv" / "fr" / "p001.md"
                self.assertTrue(a.write_file(str(f), "# Titre\n\nTexte.\n").startswith("ok"))
                self.assertEqual(ext.restore_checkpoint(a.run_id), [str(f.resolve())])
                self.assertFalse(f.exists())
            finally:
                naimtools.JOINTS = old



class McpFollowsTheProject(unittest.TestCase):
    def test_projet_placeholder(self):
        import extensions as ext
        m = ext.MCPManager()
        cfg = {"command": "serena", "args": ["--project", "${PROJET}"], "env": {"ROOT": "${PROJECT}"}}
        m.project = "/tmp/a"
        self.assertEqual(m._with_project(cfg)["args"], ["--project", "/tmp/a"])
        self.assertEqual(m._with_project(cfg)["env"], {"ROOT": "/tmp/a"})
        m.project = "/tmp/b"  # another folder: another config, so the running server is restarted on it
        self.assertNotEqual(m._with_project(cfg), {**cfg, "args": ["--project", "/tmp/a"], "env": {"ROOT": "/tmp/a"}})
        self.assertEqual(cfg["args"], ["--project", "${PROJET}"])  # the saved config keeps its placeholder



class NoCopyLoop(unittest.TestCase):
    def test_same_text_into_new_files_is_stopped(self):
        """948 files « p001…p948.md » with the same two lines in one night: the third copy is refused (not progress)."""
        with tempfile.TemporaryDirectory() as d:
            a = naimtools.Agent(d, "naim", auto_yes=True, emit=lambda e: None, approver=lambda *x: True)
            txt = "Les sept anges de l'imagination sont : l'ange de la lumiere et l'ange du feu."
            r = [a.write_file(f"fr/p{n:03d}.md", txt) for n in range(1, 4)]
            self.assertTrue(r[0].startswith("ok") and r[1].startswith("ok"))
            self.assertTrue(r[2].startswith("refused"))
            self.assertFalse((Path(d) / "fr/p003.md").exists())



class OwnToolIsNotSelfChange(unittest.TestCase):
    """Running Naim's own tool (naim-pdf) to make a user's PDF is not changing Naim: no « modifie Naim » question."""

    def test_own_tool(self):
        t = naimtools.touches_own_text
        self.assertFalse(t('/Users/x/Library/Application\\ Support/Naim/bin/naim-pdf /Users/x/Documents/l.html /Users/x/Documents/l.pdf A4'))
        self.assertFalse(t('"/Users/x/Library/Application Support/Naim/bin/naim-pdf" a.html b.pdf'))
        self.assertTrue(t('"/Users/x/Library/Application Support/Naim/.venv/bin/pip" install requests'))
        self.assertTrue(t('cp x.py "/Users/x/Library/Application Support/Naim/app/naimtools.py"'))
        self.assertTrue(t('naim-pdf a.html "/Users/x/Library/Application Support/Naim/app/out.pdf"'))


class Mods(unittest.TestCase):
    """~/.naim/mods/<nom>/: listed with their code when on; /mods off keeps the files and stops loading the code."""

    def test_list_and_switch(self):
        import mods
        with tempfile.TemporaryDirectory() as d:
            old = mods.DIR, mods.OFF
            mods.DIR, mods.OFF = Path(d), Path(d) / ".eteints.json"
            try:
                m = Path(d) / "compteur"
                m.mkdir()
                (m / "mod.json").write_text('{"description": "compte"}')
                (m / "mod.js").write_text("naim.band('x', 'ok');")
                (Path(d) / "vide").mkdir()  # no code: not a mod
                got = mods.listing(with_code=True)
                self.assertEqual([x["name"] for x in got], ["compteur"])
                self.assertEqual(got[0]["js"], "naim.band('x', 'ok');")
                self.assertTrue(mods.switch("compteur", False)["ok"])
                got = mods.listing(with_code=True)[0]
                self.assertFalse(got["enabled"])
                self.assertNotIn("js", got)
                self.assertTrue((m / "mod.js").exists())
                self.assertTrue(mods.listing()[0]["description"] == "compte")
                self.assertIn("error", mods.switch("../x", True))
                mods.switch("compteur", True)
                self.assertTrue(mods.listing()[0]["enabled"])
            finally:
                mods.DIR, mods.OFF = old


class ChangeAContactNumber(unittest.TestCase):
    """modifier_contact: the old number found by its digits (any form), the right phone changed, no guessing in AppleScript."""

    def test_change_and_add(self):
        import mailer
        from unittest import mock
        people = [{"nom": "DUPONT Jean", "email": "", "tel": "+33 6 11 22 33 44", "label": "mobile"},
                  {"nom": "DUPONT Jean", "email": "", "tel": "+33762550718", "label": "maison"},
                  {"nom": "Jean Dupontel", "email": "", "tel": "+33600000000", "label": ""}]
        calls = []
        def run(args, **kw):
            calls.append(args)
            return mock.Mock(returncode=0, stdout="+33 6 11 22 33 44\n+33652909662\n", stderr="")
        with mock.patch.object(mailer, "find_contact", return_value=people), mock.patch.object(mailer.subprocess, "run", run):
            who, nums = mailer.set_contact_phone("dupont jean", "07 62 55 07 18", "+33652909662")
            self.assertEqual(who, "DUPONT Jean")
            self.assertEqual(calls[-1][3:], ["DUPONT Jean", "2", "+33652909662"])
            self.assertIn("+33652909662", nums)
            mailer.set_contact_phone("DUPONT Jean", "", "+33699999999")
            self.assertEqual(calls[-1][4], "0")  # no old number: added
            with self.assertRaises(mailer.MailError):
                mailer.set_contact_phone("DUPONT Jean", "+33 1 00 00 00 00", "+33652909662")  # not one of his numbers
            with self.assertRaises(mailer.MailError):
                mailer.set_contact_phone("Jean", "", "+33652909662")  # two people: the exact name is asked


class ModsStatsAndSecurity(unittest.TestCase):
    """naim.stats() and naim.security(): computed from the saved conversations, read only."""

    def test_counts(self):
        import mods
        import time
        now = time.time() * 1000
        with tempfile.TemporaryDirectory() as d:
            conv = {"mode": "agent", "messages": [
                {"role": "user", "content": "x", "time": now},
                {"role": "assistant", "content": "y", "time": now + 1, "ttft": 2.0, "stats": {"total": 10},
                 "changes": [{"path": "a"}], "steps": [{"type": "tool", "name": "run_command", "result": "refused: no"},
                                                       {"type": "tool", "name": "run_command", "result": "denied by the user"}]},
                {"role": "user", "content": "old", "time": now - 90 * 86400 * 1000}]}
            (Path(d) / "c.json").write_text(json.dumps(conv))
            s = mods.stats(Path(d), 30)
            today = s["jours"][-1]
            self.assertEqual((today["messages"], today["reponses"], today["outils"], today["fichiers"]), (1, 1, 2, 1))
            self.assertEqual(sum(j["messages"] for j in s["jours"]), 1)  # the old one is out of the 30 days
            self.assertEqual(s["outils"], [("run_command", 2)])
            self.assertEqual((s["conversations"], s["modes"], s["temps_reponse_median_s"]), (1, {"agent": 1}, 10))
            sec = mods.security({"auto_yes": True, "blocked": ["rm"]}, Path(d),
                                [{"name": "ecc", "hooks": ["x"], "hooks_off": False}], {"screen": True})
            self.assertEqual(sec["actions_30_jours"], {"refusees": 1, "refusees_par_toi": 1})
            self.assertEqual((sec["autorisations"], sec["commandes_interdites"]), ({"auto_yes": True}, 1))
            self.assertEqual(sec["plugins_hooks"], [{"nom": "ecc", "hooks_allumes": True}])


class PdfPro(unittest.TestCase):
    """pdf-pro: the theme joins the content, code is coloured, charts come out as SVG, the right requests pick it."""

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("pdfpro", Path(__file__).resolve().parents[1] / "plugins_builtin/pdf-pro/skills/pdf-pro/pdfpro.py")
        self.p = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.p)

    def test_page_and_code(self):
        out = self.p.page('<h1>Cours</h1><pre class="code python"><span class="file">a.py</span>def f(x):\n    return "ok"  # fin</pre>')
        self.assertIn("<title>Cours</title>", out)
        self.assertIn("@page { size: A4", out)
        self.assertIn('<span class="file">a.py</span>', out)
        self.assertIn('<span class="k">def</span>', out)
        self.assertIn('<span class="s">&quot;ok&quot;</span>', out)
        self.assertIn('<span class="c"># fin</span>', out)

    def test_charts(self):
        for svg in (self.p.bars([["a", 1], ["b", 3]], "T"), self.p.bars({"a": 2}, horizontal=True),
                    self.p.line({"series": {"x": [["1", 1], ["2", 4]], "y": [["1", 2], ["2", 3]]}}), self.p.donut([["a", 1], ["b", 1]])):
            self.assertTrue(svg.startswith("<svg") and svg.endswith("</svg>"))
        self.assertIn("#c96442", self.p.bars([["a", 1]]))

    def test_requests_pick_it(self):
        trig = json.loads((Path(__file__).resolve().parents[1] / "plugins_builtin/pdf-pro/plugin.json").read_text())["triggers"]["pdf-pro"]
        # nobody has to know the skill's name: making a new PDF picks it, acting on an existing one does not
        for t in ("crée-moi un cours complet sur python en pdf", "fais les 4 séances suivantes ? une fois fini tu fournis que le pdf avec son sommaire",
                  "je veux un pdf sur l'histoire de l'algérie", "un tutoriel pdf sur git", "explique moi les fractions dans un pdf pour mon fils"):
            self.assertRegex(t, trig)
        for t in ("envoie-moi cours-cobol/document.pdf par mail", "fusionne ces deux pdf", "lis le fichier cours.pdf", "fais un plan de maison en pdf",
                  "résume ce pdf", "traduis ce pdf en anglais"):
            self.assertNotRegex(t, trig)

    def test_content_only_page_gets_the_theme(self):
        # convert_document on a pdf-pro page (only the content) renders with pdf-pro, and keeps the PDF it replaces
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as home:
            tool = Path(home, "plugins/pdf-pro/skills/pdf-pro/pdfpro.py")
            tool.parent.mkdir(parents=True)
            tool.write_text("import sys; open(sys.argv[3], 'w').write('THEMED'); print('PDF : ok')\n")
            Path(d, "page.html").write_text('<section class="cover"><h1>Cours</h1></section>')
            Path(d, "document.pdf").write_text("BEFORE")
            a = naimtools.Agent(d, "naim", auto_yes=True, emit=lambda e: None, approver=lambda *x: True)
            from unittest import mock
            with mock.patch.object(naimtools.ext, "HOME", Path(home)):
                res = a.convert_document("page.html", "document.pdf")
            self.assertIn("pdf-pro", res)
            self.assertEqual(Path(d, "document.pdf").read_text(), "THEMED")
            self.assertIn("document.pdf", a.checkpoint.manifest["files"])

    def test_only_the_pdf_is_shown(self):
        files = [{"path": p} for p in ("c/document.pdf", "c/page.html", "c/page.pro.html", "c/document.page1.png", "c/fig.svg")]
        self.assertEqual([f["path"] for f in naimtools.finals(files)], ["c/document.pdf", "c/fig.svg"])
        self.assertEqual(naimtools.finals([{"path": "site/index.html"}]), [{"path": "site/index.html"}])
        cv = [{"path": p} for p in ("j/lettre.txt", "j/textes.json", "j/CV.pdf", "j/Lettre.pdf", "notes.txt")]
        self.assertEqual([f["path"] for f in naimtools.finals(cv)], ["j/CV.pdf", "j/Lettre.pdf", "notes.txt"])

    def test_drafts_hidden_whatever_the_case_of_the_folder(self):
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "naim").mkdir(); (Path(t) / "naim" / "CV.pdf").write_text("x"); (Path(t) / "naim" / "cv.json").write_text("{}")
            files = [{"path": f"{t}/naim/CV.pdf"}, {"path": f"{t}/Naim/cv.json"}]  # the Mac ignores case: one folder
            self.assertEqual([f["path"] for f in naimtools.finals(files)], [f"{t}/naim/CV.pdf"])

    def test_a_pdf_made_outside_the_project_is_shown(self):
        # a CV written in the attachment's folder by a command, while the app's folder is another project
        with tempfile.TemporaryDirectory() as proj, tempfile.TemporaryDirectory() as joint:
            a = naimtools.Agent(proj, "naim")
            since = time.time()
            pdf = Path(joint) / "Mon CV.pdf"
            pdf.write_bytes(b"%PDF-1.4")
            old = Path(joint) / "ancien.pdf"
            old.write_bytes(b"%PDF-1.4")
            os.utime(old, (since - 3600, since - 3600))
            said = f'python3 pdfpro.py render "{joint}/cv.html" "{pdf}"\nPDF : {old} (1 pages)'
            self.assertEqual([f["ext"] for f in a._named_outputs(said, since)], ["pdf"])
            self.assertTrue(a._named_outputs(said, since)[0]["path"].endswith("Mon CV.pdf"))


class WritesItsOwnExtensions(unittest.TestCase):
    """A mod, a skill, a plugin go in ~/.naim/mods|skills|plugins from any project; the rest of ~/.naim stays closed."""

    def test_paths(self):
        with tempfile.TemporaryDirectory() as d:
            a = naimtools.Agent(d, "naim")
            home = naimtools.ext.HOME
            for rel in ("mods/x/mod.js", "skills/y/SKILL.md", "plugins/z/plugin.json"):
                self.assertEqual(a.resolve(str(home / rel)), (home / rel).resolve())
            for rel in ("settings.json", "mcp.json", "models/m.gguf"):
                with self.assertRaises(ValueError):
                    a.resolve(str(home / rel))


class SkillFromThisMac(unittest.TestCase):
    """« Depuis mon Mac » : a .skill / .zip archive (its folder and files) or a SKILL.md; nothing written outside."""

    def test_archive_and_file(self):
        import io
        import zipfile
        import skill_hub
        with tempfile.TemporaryDirectory() as d:
            b = io.BytesIO()
            with zipfile.ZipFile(b, "w") as z:
                z.writestr("polices/SKILL.md", "---\nname: polices-retro\ndescription: d\n---\nfais ceci")
                z.writestr("polices/exemples/a.html", "<p>x</p>")
                z.writestr("__MACOSX/polices/._SKILL.md", "junk")
            self.assertEqual(skill_hub.install_file(b.getvalue(), "polices.skill", d, "projet"), ["polices-retro"])
            got = Path(d) / ".naim/skills/polices-retro"
            self.assertEqual(sorted(str(p.relative_to(got)) for p in got.rglob("*") if p.is_file()), ["SKILL.md", "exemples/a.html"])
            evil = io.BytesIO()
            with zipfile.ZipFile(evil, "w") as z:
                z.writestr("x/SKILL.md", "---\nname: x\n---\nhi")
                z.writestr("x/../../dehors.txt", "non")
            with self.assertRaises(skill_hub.SkillError):
                skill_hub.install_file(evil.getvalue(), "x.skill", d, "projet")
            self.assertFalse((Path(d) / ".naim/dehors.txt").exists())
            self.assertEqual(skill_hub.install_file(b"---\nname: seul\n---\nfais", "SKILL.md", d, "projet"), ["seul"])
            with self.assertRaises(skill_hub.SkillError):
                skill_hub.install_file(b"rien", "vide.md", d, "projet")


class WriteInParts(unittest.TestCase):
    """A long file written in parts (append) and a clear way out when a call too long loses its path or content."""

    def test_append_and_lost_argument(self):
        with tempfile.TemporaryDirectory() as d:
            a = naimtools.Agent(d, "naim", auto_yes=True)
            a.write_file("page.html", "<section>1</section>")
            a.write_file("page.html", "<section>2</section>", append=True)
            self.assertEqual((Path(d) / "page.html").read_text(), "<section>1</section>\n<section>2</section>")
            a.tools = [{"function": {"name": "write_file"}}]
            out = a.call_tool("write_file", {"content": "x" * 50})
            self.assertIn('write_file(path="page.html", content="", append=true)', out)  # the file it was writing
            a.call_tool("write_file", {"path": "page.html", "content": "", "append": True})  # the part kept, added
            self.assertTrue((Path(d) / "page.html").read_text().endswith("x" * 50))
            (Path(d) / "page.html").write_text("<p>ligne</p>\n" * 200)
            out = a.write_file("page.html", "<section>3</section>")
            self.assertTrue(out.startswith("refused") and "append=true" in out)
            out = a.write_file("page.html", "<section>3</section>", append=True)
            self.assertIn("now has 201 lines", out)
            b = naimtools.Agent(d, "naim", auto_yes=True)  # « continue »: a new run, the same file
            out = b.write_file("page.html", "<p>fin du chapitre 4</p>\n" * 300)
            self.assertTrue(out.startswith("refused") and "erase its beginning" in out)
            self.assertIn("ok", b.write_file("page.html", "<p>ligne</p>\n<p>tout réécrit</p>\n" * 300))


class RunawayCallIsCut(unittest.TestCase):
    """A tool call still being written after max_seconds is cut (the stream closed), and arrives marked as cut."""

    def test_cut(self):
        from unittest import mock
        import itertools
        import json as _j

        def lines():
            yield b'data: ' + _j.dumps({"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"name": "write_file", "arguments": '{"path": "c.html", "content": "'}}]}}]}).encode()
            for _ in range(10000):
                yield b'data: ' + _j.dumps({"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": "<p>x</p>"}}]}}]}).encode()

        class Resp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def __iter__(self): return lines()

        clock = itertools.count(0, 1.0)  # each read moves the clock one second
        with mock.patch.object(llamacpp.urllib.request, "urlopen", return_value=Resp()), \
             mock.patch.object(llamacpp.SERVER, "ensure", return_value=None), \
             mock.patch.object(llamacpp.time, "time", side_effect=lambda: next(clock)):
            out = list(llamacpp.chat([{"role": "user", "content": "x"}], tools=[], stream=True, options={"max_seconds": 30}))
        calls = [c for c in out if c.get("message", {}).get("tool_calls")]
        self.assertTrue(calls, "the cut call is still given")
        args = calls[-1]["message"]["tool_calls"][0]["function"]["arguments"]
        self.assertTrue(args.get("_maybe_cut") or "_unreadable" in args or "content" not in args or "path" in args)
        self.assertLess(sum(1 for c in out if "writing" in c), 100)  # stopped after about 30 reads, not 10 000


class LongTaskKeepsTheRequest(unittest.TestCase):
    """Chat: when a long task outgrows the engine's room, the request stays word for word and the steps are summed up."""

    def test_lighten(self):
        import server
        msgs = [{"role": "system", "content": "SYS"}, {"role": "user", "content": "fais un cours sur COBOL"},
                {"role": "assistant", "content": "voilà le cours"},
                {"role": "user", "content": "les 4 séances suivantes, peu d'exercices, que le PDF"}]
        for i in range(30):
            msgs.append({"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "web_search", "arguments": {"query": f"cobol {i}"}}}]})
            msgs.append({"role": "tool", "content": "x" * 9000})
        msgs.append({"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "write_file", "arguments": {"path": "c/page.html"}}}]})
        msgs.append({"role": "tool", "content": "ok"})
        out, at = server.lighten_conversation(msgs, 3)
        self.assertEqual(out[0]["content"], "SYS")
        self.assertEqual(at, 1)
        self.assertIn("les 4 séances suivantes, peu d'exercices, que le PDF", out[1]["content"])
        self.assertIn("fais un cours sur COBOL", out[1]["content"])
        self.assertIn("cherché « cobol 0 »", out[2]["content"])
        self.assertLessEqual(len(out), 9)
        again, at2 = server.lighten_conversation(out + msgs[-4:], at)  # a second time: the request and the first summary stay
        self.assertIn("que le PDF", again[1]["content"])
        self.assertIn("cobol 0", again[2]["content"])


class ConnectATool(unittest.TestCase):
    """connecter-outil: « branche Stripe à Naim » installs the official CLI and writes a global skill; other requests do not pick it."""

    def test_triggers(self):
        trig = json.loads((Path(__file__).resolve().parents[1] / "plugins_builtin/connecteurs/plugin.json").read_text())["triggers"]["connecter-outil"]
        for t in ("branche stripe à naim", "intègre supabase dans naim", "installe le cli de vercel", "connect-tool aws"):
            self.assertRegex(t, trig)
        for t in ("connecte-toi au wifi", "branche l'imprimante", "intègre ce chapitre dans le cours", "installe python"):
            self.assertNotRegex(t, trig)


class ImproveTheSystem(unittest.TestCase):
    """/ameliore-systeme: a digest of the conversations (long tasks, failing tools, unhappy follow-ups), nothing changed."""
    P = Path(__file__).resolve().parents[1] / "plugins_builtin/ameliore-systeme"

    def test_triggers(self):
        trig = json.loads((self.P / "plugin.json").read_text())["triggers"]["ameliore-systeme"]
        for t in ("/ameliore-system", "/ameliore-systeme 30", "fais un rapport d'amélioration", "analyse mes conversations pour les automatiser"):
            self.assertRegex(t, trig)
        for t in ("améliore le style du site", "crée un rapport PDF des ventes", "lis mes mails"):
            self.assertNotRegex(t, trig)

    def test_digest(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("analyse", self.P / "skills/ameliore-systeme/analyse.py")
        a = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(a)
        conv = {"id": "c1", "title": "sms", "messages": [
            {"role": "user", "content": "envoie un sms à Paul pour demain", "time": 1793440000000},
            {"role": "assistant", "content": "ok", "stats": {"total": 600, "reason": "stop"}, "steps": [
                {"type": "event", "text": "Skill utilisé : mac"},
                {"type": "tool", "name": "run_command", "args": {"command": "osascript -e x"}, "result": "exit code 1\nboom"},
                {"type": "tool", "name": "run_command", "args": {"command": "osascript -e x"}, "result": "exit code 1\nboom"}]},
            {"role": "user", "content": "il a pas envoyé, ça ne marche pas"}]}
        with tempfile.TemporaryDirectory() as d:
            a.REPORTS = Path(d)
            out = a.digest([conv, {**conv, "id": "c2"}], 7)
        self.assertIn("4× run_command osascript", out)  # 2 failures × 2 conversations, grouped by command
        self.assertIn("1 refaits", out)
        self.assertIn("ça ne marche pas", out)
        self.assertIn("mac (2)", out)
        self.assertIn("Demandes qui reviennent", out)


class AskTheUser(unittest.TestCase):
    """ask_user: options with their explanation reach the card; « Passer » lets Naim choose and say which."""

    def test_skip_and_options(self):
        with tempfile.TemporaryDirectory() as d:
            seen = []
            a = naimtools.Agent(d, "naim", auto_yes=True, emit=lambda e: None, approver=lambda *x: True,
                                asker=lambda q, c, m: (seen.append(c), "__passe__")[1])
            self.assertIn("ask_user", {t["function"]["name"] for t in a.tools})
            res = a.ask_user("Quel style ?", [{"label": "pdf-pro", "description": "comme tes cours"}, "Sobre"])
            self.assertEqual(seen[0], ["pdf-pro — comme tes cours", "Sobre"])
            self.assertIn("skipped", res)
            a.asker = lambda q, c, m: "Sobre"
            self.assertEqual(a.ask_user("Quel style ?", ["pdf-pro", "Sobre"]), "The user answered: Sobre")

if __name__ == "__main__":
    unittest.main()


class Dreaming(unittest.TestCase):
    """At night Naim reads back the user's corrections and proposes rules: only rules with a real source, never one
    it already follows or one refused before, and nothing written to NAIM.md without the user's yes."""

    def setUp(self):
        import dreaming
        import memory
        import naim_check
        self.d, self.mem, self.nc = dreaming, memory, naim_check
        self.tmp = Path(tempfile.mkdtemp())
        self.saved = (dreaming.DIR, dreaming.NAIM_MD, memory.FILE, memory.LEGACY, naim_check.LESSONS, dreaming.ext.HOME)
        dreaming.DIR, dreaming.NAIM_MD = self.tmp / "reves", self.tmp / "NAIM.md"
        memory.FILE, memory.LEGACY, naim_check.LESSONS = self.tmp / "memory.json", self.tmp / "memory.md", self.tmp / "lecons.md"
        dreaming.ext.HOME = self.tmp
        dreaming.NAIM_MD.write_text("# Consignes\n\n- Réponds toujours en français, de façon directe et concise.\n")
        self.convs = self.tmp / "conversations"
        self.convs.mkdir()
        t = int(time.time() * 1000)
        conv = {"id": "c1", "title": "Lettre de motivation", "messages": [
            {"role": "user", "content": "fais ma lettre en PDF", "time": t},
            {"role": "assistant", "content": "Voici la lettre en style simple.", "time": t},
            {"role": "user", "content": "non il a pas mis le style pro !!! je veux toujours le style pro", "time": t},
            {"role": "assistant", "content": "D'accord.", "time": t},
            {"role": "user", "content": "merci", "time": t}]}
        (self.convs / "c1.json").write_text(json.dumps(conv))
        (self.convs / "s1.json").write_text(json.dumps({**conv, "id": "s1", "scheduled": "x"}))

    def tearDown(self):
        (self.d.DIR, self.d.NAIM_MD, self.mem.FILE, self.mem.LEGACY, self.nc.LESSONS, self.d.ext.HOME) = self.saved

    def test_moments_are_corrections_only(self):
        m = self.d.moments(self.convs)
        self.assertEqual(len(m), 1)  # not the first request, not « merci », not the scheduled run
        self.assertIn("style pro", m[0]["user"])
        self.assertIn("style simple", m[0]["naim"])

    def test_rule_needs_a_real_source(self):
        reply = '{"regles": [{"regle": "Fais toujours les PDF avec le style pro", "sources": [1]},' \
                ' {"regle": "Invente une règle sans source", "sources": []}, {"regle": "Source hors liste", "sources": [9]}]}'
        self.assertEqual([r["rule"] for r in self.d._parse(reply, 1)], ["Fais toujours les PDF avec le style pro"])

    def test_dream_then_accept_writes_naim_md(self):
        rule = "Fais toujours les PDF avec le style pro, sans attendre qu'on le redemande."
        known = "Réponds toujours en français, de façon directe et concise."
        reply = json.dumps({"regles": [{"regle": rule, "pourquoi": "Il l'a demandé", "sources": [1]},
                                       {"regle": known, "sources": [1]}]})
        d = self.d.dream(self.convs, lambda msgs: reply)
        rules = [p for p in d["proposals"] if p["kind"] == "regle"]
        self.assertEqual([p["text"] for p in rules], [rule])  # the rule it already follows is not proposed again
        self.assertIn("style pro", rules[0]["evidence"][0]["user"])  # the proof is what the user really wrote
        self.assertNotIn(rule, self.d.NAIM_MD.read_text())  # nothing written before the user's yes
        self.assertTrue(self.d.answer(d["date"], rules[0]["id"], True))
        text = self.d.NAIM_MD.read_text()
        self.assertIn(self.d.SECTION, text)
        self.assertIn(f"- {rule}", text)
        self.assertTrue(any(self.tmp.glob("NAIM.md.avant-reve-*")))  # the old NAIM.md is kept aside
        self.assertIsNone(self.d.answer(d["date"], rules[0]["id"], True))  # answered once only

    def test_refused_never_proposed_again(self):
        reply = json.dumps({"regles": [{"regle": "Mets toujours le style pro dans les PDF", "sources": [1]}]})
        d = self.d.dream(self.convs, lambda msgs: reply, since=0)
        p = next(p for p in d["proposals"] if p["kind"] == "regle")
        self.d.answer(d["date"], p["id"], False)
        d2 = self.d.dream(self.convs, lambda msgs: reply, since=0)
        self.assertEqual(sum(x["kind"] == "regle" for x in d2["proposals"]), 1)
        self.assertEqual(self.d.pending(), [x | {"date": d2["date"]} for x in d2["proposals"] if x["status"] == "attente"])

    def test_due_at_night_only_when_idle(self):
        from datetime import datetime, timedelta
        yesterday = {"date": "2000-01-01", "date_time": (datetime.now() - timedelta(hours=20)).strftime("%Y-%m-%d %H:%M")}
        self.assertTrue(self.d.due({}, yesterday, idle_s=3600, awake_s=3600, hour=3))
        self.assertFalse(self.d.due({}, yesterday, idle_s=600, awake_s=3600, hour=3))   # someone is using the Mac
        self.assertFalse(self.d.due({}, yesterday, idle_s=3600, awake_s=300, hour=3))   # it has just woken up
        self.assertFalse(self.d.due({}, yesterday, idle_s=3600, awake_s=3600, hour=15))  # daytime, dreamt recently
        self.assertFalse(self.d.due({"dreaming": False}, yesterday, idle_s=3600, awake_s=3600, hour=3))
        today = {"date": datetime.now().strftime("%Y-%m-%d"), "date_time": "2000-01-01 03:00"}
        self.assertFalse(self.d.due({}, today, idle_s=9999, awake_s=9999, hour=3))


class Simulations(unittest.TestCase):
    """A simulation page = the fixed engine + a small algorithm file Naim writes; the checker runs it for real and
    says exactly what is wrong (a broken page used to be rewritten by hand and never animated)."""
    SK = ROOT / "plugins_builtin/algorithmique/skills/animation-algorithme"

    def run_sim(self, *args):
        return subprocess.run([sys.executable, str(self.SK / "simulation.py"), *args], capture_output=True, text=True, timeout=120)

    def test_examples_are_right(self):
        for ex in ("tri-bulles.js", "recherche-dichotomique.js"):
            with tempfile.TemporaryDirectory() as d:
                r = self.run_sim("creer", str(self.SK / "exemples" / ex), f"{d}/page.html")
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertIn("La simulation est juste", r.stdout)
                page = Path(d, "page.html").read_text()
                self.assertIn("const ALGO", page)
                self.assertIn("function makeTrace", page)

    def test_python_in_build_is_caught(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "a.js").write_text('const ALGO={titre:"x",type:"tri",code:"x",build(a,P){ while (a and P) {} }};')
            r = self.run_sim("verifier", f"{d}/a.js")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("syntaxe", r.stdout)

    def test_sort_that_does_not_sort_is_caught(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "a.js").write_text('const ALGO={titre:"x",type:"tri",valeurs:[3,1,2],code:"for\\nswap",'
                                       'build(a,P){P(1,"on regarde");P(2,"on échange")}};')
            r = self.run_sim("verifier", f"{d}/a.js")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("FAUX", r.stdout)

    def test_html_in_code_and_bad_line_are_caught(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "a.js").write_text('const ALGO={titre:"x",code:"<span class=\\"k\\">for</span>",build(a,P){P(1,"x")}};')
            self.assertIn("texte simple", self.run_sim("verifier", f"{d}/a.js").stdout)
            Path(d, "b.js").write_text('const ALGO={titre:"x",code:"a\\nb",build(a,P){P(7,"x")}};')
            self.assertIn("la ligne 7 n'existe pas", self.run_sim("verifier", f"{d}/b.js").stdout)

    def test_one_value_needs_no_special_case(self):
        # a right insertion sort does nothing on [7]: no FAUX for that (Naim went round in circles on it)
        with tempfile.TemporaryDirectory() as d:
            Path(d, "a.js").write_text('const ALGO={titre:"x",type:"tri",valeurs:[3,1,2],code:"for\\nwhile\\nplace",'
                                       'build(a,P){for(let i=1;i<a.length;i++){const v=a[i];let j=i-1;P(1,"on prend");'
                                       'while(j>=0&&a[j]>v){P(2,"décale");a[j+1]=a[j];j--}a[j+1]=v;P(3,"place")}}};')
            r = self.run_sim("verifier", f"{d}/a.js")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("OK   valeurs [7]", r.stdout)

    def test_page_made_by_a_command_is_shown(self):
        # the page comes from simulation.py, not write_file: without this only the .js was shown, no page, no preview
        with tempfile.TemporaryDirectory() as d:
            Path(d, "tri.html").write_text("x")
            a = naimtools.Agent(d, "naim", auto_yes=True, emit=lambda e: None)
            said = f"Page créée : {Path(d).resolve()}/tri.html\nLa simulation est juste."
            self.assertEqual([f["path"] for f in a._named_outputs(said, 0, pages=True)], ["tri.html"])
            self.assertEqual(a._named_outputs(said, 0), [])

    def test_algo_file_not_a_deliverable(self):
        with tempfile.TemporaryDirectory() as d:
            for f in ("tri.js", "tri.html", "app.js"):
                Path(d, f).write_text("x")
            shown = [Path(f["path"]).name for f in naimtools.finals([{"path": f"{d}/{x}"} for x in ("tri.js", "tri.html", "app.js")])]
            self.assertEqual(shown, ["tri.html", "app.js"])


class TypographicEdits(unittest.TestCase):
    """The model writes ' where the file has ’ (or - for —): the edit finds the real text instead of failing (a failed
    edit made Naim rewrite a whole page by hand)."""

    def test_apostrophe_and_dash(self):
        text = "<title>Tri à bulles — le robot met de l’ordre</title>"
        self.assertEqual(naimtools.Agent._typo_find(text, "<title>Tri à bulles - le robot met de l'ordre</title>"), text)

    def test_ambiguous_or_absent_stays_an_error(self):
        self.assertIsNone(naimtools.Agent._typo_find("l’a et l’a", "l'a"))
        self.assertIsNone(naimtools.Agent._typo_find("rien", "l'autre"))

    def test_edit_file_uses_it(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "p.html").write_text("<h1>Le robot met de l’ordre</h1>\n")
            a = naimtools.Agent(d, "naim", auto_yes=True, emit=lambda e: None)
            self.assertTrue(a.edit_file("p.html", "<h1>Le robot met de l'ordre</h1>", "<h1>Tri par insertion</h1>").startswith("ok"))
            self.assertEqual(Path(d, "p.html").read_text(), "<h1>Tri par insertion</h1>\n")
