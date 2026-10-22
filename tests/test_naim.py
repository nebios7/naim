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
