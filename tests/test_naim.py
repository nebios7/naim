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
            (t / "p.json").write_text(json.dumps([["Jean Dupont", "Marie Curie"], ["Poste chez ACME en 2020", "Chercheuse"], ["absent", "x"]]))
            r = subprocess.run([sys.executable, "-I", str(self.D / "remplir_modele.py"), "m.html", "p.json", "o.html"], cwd=t,
                               check=True, capture_output=True, text=True)
            out = (t / "o.html").read_text()
            self.assertIn("Marie Curie", out)
            self.assertIn("Chercheuse", out)
            self.assertIn("2 texte(s) remplacé(s) sur 3", r.stdout)
            self.assertIn(".carte{border:2px solid}", out)



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

if __name__ == "__main__":
    unittest.main()
