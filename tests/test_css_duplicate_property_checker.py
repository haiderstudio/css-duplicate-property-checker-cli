"""Tests for css_duplicate_property_checker: parsing, checks, CLI, examples, hygiene.

Every subprocess run pins its working directory to the repo root,
and every assertion on a path the CLI prints checks a suffix, not
an absolute path — so the suite passes from any working directory.
"""

import ast
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import css_duplicate_property_checker as checker

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "css_duplicate_property_checker.py"
EXAMPLES = ROOT / "examples"
README = ROOT / "README.md"


def dups(text, path="s.css", ignored=()):
    """(problems, declaration count) for one CSS document."""
    problems, count = checker.find_duplicates(text, path, ignored)
    return ([(p.line, p.reason) for p in problems], count)


class TestParsing(unittest.TestCase):
    def test_simple_duplicate(self):
        problems, count = dups(
            ".card {\n  color: red;\n  color: blue;\n}\n")
        self.assertEqual(count, 2)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0][0], 3)
        self.assertIn("duplicate property 'color'", problems[0][1])
        self.assertIn("first declared on line 2", problems[0][1])

    def test_no_duplicate(self):
        problems, count = dups(".a {\n  color: red;\n  margin: 0;\n}\n")
        self.assertEqual((problems, count), ([], 2))

    def test_same_property_in_different_rules_is_fine(self):
        text = ".a {\n  color: red;\n}\n.b {\n  color: blue;\n}\n"
        problems, count = dups(text)
        self.assertEqual((problems, count), ([], 2))

    def test_triple_occurrence_reports_two(self):
        text = ".a {\n  color: red;\n  color: blue;\n  color: green;\n}\n"
        problems, count = dups(text)
        self.assertEqual(count, 3)
        self.assertEqual([line for line, _ in problems], [3, 4])
        self.assertIn("first declared on line 2", problems[1][1])

    def test_case_insensitive(self):
        text = ".a {\n  Padding: 10px;\n  padding: 2px;\n}\n"
        problems, _ = dups(text)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0][0], 3)

    def test_custom_property(self):
        text = ":root {\n  --brand: #06c;\n  --brand: #09f;\n}\n"
        problems, _ = dups(text)
        self.assertEqual(len(problems), 1)
        self.assertIn("'--brand'", problems[0][1])

    def test_vendor_prefix_is_a_different_property(self):
        text = (".a {\n  -webkit-transform: none;\n"
                "  transform: none;\n}\n")
        problems, count = dups(text)
        self.assertEqual((problems, count), ([], 2))

    def test_color_and_background_color_are_different(self):
        text = ".a {\n  color: red;\n  background-color: blue;\n}\n"
        problems, _ = dups(text)
        self.assertEqual(problems, [])

    def test_comment_with_duplicate_text_ignored(self):
        text = "/* color: red;\n color: blue; */\n.a {\n  color: red;\n}\n"
        problems, count = dups(text)
        self.assertEqual((problems, count), ([], 1))

    def test_comment_between_declarations_ignored(self):
        text = ".a {\n  color: red;\n  /* color: blue; */\n  margin: 0;\n}\n"
        problems, count = dups(text)
        self.assertEqual((problems, count), ([], 2))

    def test_string_with_semicolon_and_brace(self):
        text = '.a {\n  content: "; }";\n  content: "x";\n}\n'
        problems, count = dups(text)
        self.assertEqual(count, 2)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0][0], 3)

    def test_media_query_inner_rule_checked(self):
        text = ("@media (min-width: 600px) {\n"
                "  .a {\n    width: 200px;\n    width: 240px;\n  }\n}\n")
        problems, count = dups(text)
        self.assertEqual(count, 2)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0][0], 4)

    def test_same_property_in_media_and_outer_rule_is_fine(self):
        text = (".a {\n  width: 100px;\n}\n"
                "@media (min-width: 600px) {\n"
                "  .a {\n    width: 200px;\n  }\n}\n")
        problems, count = dups(text)
        self.assertEqual((problems, count), ([], 2))

    def test_nested_rule_is_its_own_block(self):
        text = (".a {\n  color: red;\n  &:hover {\n"
                "    color: blue;\n  }\n}\n")
        problems, count = dups(text)
        self.assertEqual((problems, count), ([], 2))

    def test_declaration_after_nested_rule_still_counts(self):
        text = (".a {\n  color: red;\n  &:hover {\n"
                "    color: blue;\n  }\n  color: green;\n}\n")
        problems, count = dups(text)
        self.assertEqual(count, 3)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0][0], 6)

    def test_keyframes_each_step_is_its_own_block(self):
        text = ("@keyframes spin {\n  from {\n    opacity: 0;\n  }\n"
                "  to {\n    opacity: 1;\n  }\n}\n")
        problems, count = dups(text)
        self.assertEqual((problems, count), ([], 2))

    def test_keyframes_duplicate_inside_one_step(self):
        text = ("@keyframes spin {\n  from {\n    opacity: 0;\n"
                "    opacity: 0.5;\n  }\n}\n")
        problems, _ = dups(text)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0][0], 4)

    def test_last_declaration_without_semicolon(self):
        text = ".a {\n  color: red;\n  color: blue\n}\n"
        problems, count = dups(text)
        self.assertEqual(count, 2)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0][0], 3)

    def test_empty_value_is_not_a_declaration(self):
        text = ".a {\n  color:;\n  color: red;\n}\n"
        problems, count = dups(text)
        self.assertEqual((problems, count), ([], 1))

    def test_declaration_without_colon_skipped(self):
        text = ".a {\n  broken-declaration;\n  color: red;\n}\n"
        problems, count = dups(text)
        self.assertEqual((problems, count), ([], 1))

    def test_url_with_semicolon_in_value(self):
        text = (".a {\n  background: url(data:image/png;base64,AAA);\n"
                "  background: red;\n}\n")
        problems, count = dups(text)
        self.assertEqual(count, 2)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0][0], 3)

    def test_important_value_still_one_declaration(self):
        text = ".a {\n  color: red !important;\n  color: blue;\n}\n"
        problems, count = dups(text)
        self.assertEqual(count, 2)
        self.assertEqual(len(problems), 1)

    def test_import_at_rule_skipped(self):
        text = '@import url("other.css");\n.a {\n  color: red;\n}\n'
        problems, count = dups(text)
        self.assertEqual((problems, count), ([], 1))

    def test_line_numbers_across_file(self):
        text = ".a {\n  color: red;\n}\n\n\n.b {\n  margin: 0;\n  margin: 1px;\n}\n"
        problems, count = dups(text)
        self.assertEqual(count, 3)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0][0], 8)

    def test_empty_stylesheet(self):
        self.assertEqual(dups(""), ([], 0))
        self.assertEqual(dups("/* nothing here */\n"), ([], 0))

    def test_ignored_property(self):
        text = ".a {\n  display: block;\n  display: flex;\n}\n"
        problems, _ = dups(text, ignored=["display"])
        self.assertEqual(problems, [])
        problems, _ = dups(text, ignored=["DISPLAY"])
        self.assertEqual(problems, [])

    def test_ignored_only_ignores_that_property(self):
        text = ".a {\n  display: block;\n  display: flex;\n  color: red;\n  color: blue;\n}\n"
        problems, _ = dups(text, ignored=["display"])
        self.assertEqual(len(problems), 1)
        self.assertIn("'color'", problems[0][1])

    def test_unclosed_block_still_reports(self):
        text = ".a {\n  color: red;\n  color: blue;\n"
        problems, count = dups(text)
        self.assertEqual(count, 2)
        self.assertEqual(len(problems), 1)


class TestCheckFiles(unittest.TestCase):
    def run_check(self, css_text, ignored=()):
        with tempfile.TemporaryDirectory() as tmp:
            css_path = Path(tmp) / "s.css"
            css_path.write_text(css_text)
            return checker.check_files([str(css_path)], ignored)

    def test_all_clean(self):
        results, total = self.run_check(".a {\n  color: red;\n}\n")
        self.assertEqual(total, 1)
        self.assertEqual(results[0][2], [])

    def test_duplicate_found(self):
        results, total = self.run_check(
            ".a {\n  color: red;\n  color: blue;\n}\n")
        self.assertEqual(total, 2)
        self.assertEqual(len(results[0][2]), 1)
        problem = results[0][2][0]
        self.assertEqual(problem.line, 3)
        self.assertTrue(problem.text().endswith(
            ":3: duplicate property 'color' — first declared "
            "on line 2 in the same rule"))

    def test_problem_as_dict(self):
        results, _ = self.run_check(
            ".a {\n  color: red;\n  color: blue;\n}\n")
        problem = results[0][2][0]
        self.assertEqual(problem.as_dict()["line"], 3)
        self.assertIn("color", problem.as_dict()["reason"])

    def test_unreadable_css_file(self):
        results, _ = checker.check_files(["/nonexistent-dir-xyz/s.css"])
        self.assertEqual(len(results[0][2]), 1)
        self.assertIn("cannot read file", results[0][2][0].reason)

    def test_multiple_files_in_path_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "a.css"
            second = root / "b.css"
            first.write_text(".a {\n  color: red;\n  color: blue;\n}\n")
            second.write_text(".b {\n  margin: 0;\n}\n")
            results, total = checker.check_files(
                [str(first), str(second)])
            self.assertEqual(total, 3)
            self.assertEqual(results[0][0], str(first))
            self.assertEqual(results[1][0], str(second))


class TestCollection(unittest.TestCase):
    def test_folder_walk(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.css").write_text(".a {\n}\n")
            (root / "b.html").write_text("hi")
            (root / "sub").mkdir()
            (root / "sub" / "c.css").write_text(".c {\n}\n")
            css, missing = checker.collect([str(root)])
            self.assertEqual(missing, [])
            self.assertEqual(css, [str(root / "a.css"),
                                   str(root / "sub" / "c.css")])

    def test_git_and_node_modules_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / ".git" / "g.css").write_text(".g {\n}\n")
            (root / "node_modules").mkdir()
            (root / "node_modules" / "n.css").write_text(".n {\n}\n")
            (root / "a.css").write_text(".a {\n}\n")
            css, _ = checker.collect([str(root)])
            self.assertEqual(css, [str(root / "a.css")])

    def test_no_recursive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.css").write_text(".a {\n}\n")
            (root / "sub").mkdir()
            (root / "sub" / "b.css").write_text(".b {\n}\n")
            css, _ = checker.collect([str(root)], recursive=False)
            self.assertEqual(css, [str(root / "a.css")])

    def test_exclude_pattern(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "vendor-x.css").write_text(".v {\n}\n")
            (root / "main.css").write_text(".m {\n}\n")
            css, _ = checker.collect([str(root)], exclude=["vendor-*"])
            self.assertEqual(css, [str(root / "main.css")])

    def test_direct_css_file_checked_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "one.css").write_text(".one {\n}\n")
            (root / "two.css").write_text(".two {\n}\n")
            css, _ = checker.collect([str(root / "one.css")])
            self.assertEqual(css, [str(root / "one.css")])

    def test_direct_non_css_file_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "page.html").write_text("hi")
            css, _ = checker.collect([str(root / "page.html")])
            self.assertEqual(css, [])

    def test_missing_path_reported(self):
        css, missing = checker.collect(["/no-such-path-xyz"])
        self.assertEqual(css, [])
        self.assertEqual(missing, ["/no-such-path-xyz"])

    def test_empty_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            css, missing = checker.collect([tmp])
            self.assertEqual((css, missing), ([], []))

    def test_uppercase_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "UP.CSS").write_text(".a {\n}\n")
            css, _ = checker.collect([str(root)])
            self.assertEqual(css, [str(root / "UP.CSS")])


class TestCLI(unittest.TestCase):
    def run_cli(self, *args, cwd=None):
        return subprocess.run(
            [sys.executable, str(SRC), *args],
            capture_output=True, text=True,
            cwd=str(cwd) if cwd else str(ROOT),
        )

    def test_clean_file_exit_0(self):
        result = self.run_cli("examples/clean.css")
        self.assertEqual(result.returncode, 0)
        self.assertIn("12 property declaration(s), none duplicated",
                      result.stdout)
        self.assertIn("none duplicated.", result.stdout)

    def test_bad_file_exit_1(self):
        result = self.run_cli("examples/messy.css")
        self.assertEqual(result.returncode, 1)
        self.assertTrue(any(
            line.endswith("messy.css:5: duplicate property 'color' — "
                          "first declared on line 3 in the same rule")
            for line in result.stdout.splitlines()))

    def test_folder_exit_1_and_summary(self):
        result = self.run_cli("examples")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Checked 2 CSS file(s) (25 property "
                      "declaration(s)), 5 problem(s) in 1 file(s).",
                      result.stdout)

    def test_no_args_exit_2(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 2)

    def test_missing_path_exit_2(self):
        result = self.run_cli("no-such-file.css")
        self.assertEqual(result.returncode, 2)
        self.assertIn("no such file or folder", result.stderr)

    def test_folder_without_css_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "page.html").write_text("hi")
            result = self.run_cli(tmp)
        self.assertEqual(result.returncode, 2)
        self.assertIn("no CSS files found", result.stderr)

    def test_bad_flag_exit_2(self):
        result = self.run_cli("--nope", "examples")
        self.assertEqual(result.returncode, 2)

    def test_ignore_flag(self):
        result = self.run_cli("--ignore", "color",
                              "examples/messy.css")
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("duplicate property 'color'", result.stdout)
        self.assertIn("4 problem(s)", result.stdout)

    def test_ignore_case_insensitive(self):
        result = self.run_cli("--ignore", "COLOR",
                              "examples/messy.css")
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("duplicate property 'color'", result.stdout)

    def test_exclude_flag(self):
        result = self.run_cli("--exclude", "messy.css", "examples")
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("messy.css", result.stdout)

    def test_json_output(self):
        result = self.run_cli("--json", "examples/messy.css")
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["summary"]["problems"], 5)
        self.assertEqual(payload["summary"]["declarations"], 13)
        self.assertTrue(payload["files"][0]["file"].endswith(
            "examples/messy.css"))
        self.assertEqual(payload["files"][0]["problems"][0]["line"], 5)
        self.assertIn("Checked 1 CSS file(s)", result.stderr)

    def test_json_clean(self):
        result = self.run_cli("--json", "examples/clean.css")
        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["summary"]["problems"], 0)

    def test_version(self):
        result = self.run_cli("--version")
        self.assertEqual(result.returncode, 0)
        self.assertIn("1.0.0", result.stdout)

    def test_runs_from_a_different_working_directory(self):
        # CWD robustness: the CLI is run from an unrelated folder
        # with absolute paths, and the report is checked by suffix.
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_cli(str(EXAMPLES / "messy.css"), cwd=tmp)
            self.assertEqual(result.returncode, 1)
            self.assertTrue(any(
                line.endswith("messy.css:5: duplicate property 'color' "
                              "— first declared on line 3 in the same "
                              "rule")
                for line in result.stdout.splitlines()),
                result.stdout)
            self.assertIn("5 problem(s)", result.stdout)


class TestExamples(unittest.TestCase):
    def test_messy_expected_problems(self):
        text = (EXAMPLES / "messy.css").read_text()
        problems, total = checker.find_duplicates(text, "messy.css")
        self.assertEqual(total, 13)
        got = [(p.line, p.reason.split(" ")[2]) for p in problems]
        self.assertEqual(got, [(5, "'color'"), (10, "'margin'"),
                               (17, "'padding'"), (23, "'width'"),
                               (29, "'--brand'")])

    def test_clean_expected_no_problems(self):
        text = (EXAMPLES / "clean.css").read_text()
        problems, total = checker.find_duplicates(text, "clean.css")
        self.assertEqual(total, 12)
        self.assertEqual(problems, [])

    def test_sample_output_matches_fresh_run(self):
        result = subprocess.run(
            ["sh", "examples/run-example.sh"],
            capture_output=True, text=True, cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0)
        sample = (EXAMPLES / "sample-output.md").read_text()
        block = sample.split("```\n")[1]
        self.assertEqual(result.stdout, block)

    def test_readme_quoted_outputs_are_real(self):
        readme = README.read_text()
        for line in [
            "examples/clean.css: OK — 12 property declaration(s), none duplicated",
            "OK — 1 CSS file(s) checked, 12 property declaration(s), none duplicated.",
            "FAIL examples/messy.css:5: duplicate property 'color' — first declared on line 3 in the same rule",
            "FAIL examples/messy.css:10: duplicate property 'margin' — first declared on line 9 in the same rule",
            "FAIL examples/messy.css:17: duplicate property 'padding' — first declared on line 15 in the same rule",
            "FAIL examples/messy.css:23: duplicate property 'width' — first declared on line 22 in the same rule",
            "FAIL examples/messy.css:29: duplicate property '--brand' — first declared on line 28 in the same rule",
            "Checked 1 CSS file(s) (13 property declaration(s)), 5 problem(s) in 1 file(s).",
            "Checked 2 CSS file(s) (25 property declaration(s)), 5 problem(s) in 1 file(s).",
        ]:
            self.assertIn(line, readme, line)

    def test_readme_json_matches_real_json(self):
        result = subprocess.run(
            [sys.executable, str(SRC), "--json",
             "examples/messy.css"],
            capture_output=True, text=True, cwd=ROOT,
        )
        readme = README.read_text()
        start = readme.index("```\n{\n  \"files\": [")
        end = readme.index("```", start + 10)
        block = readme[start + 4:end].strip()
        self.assertEqual(result.stdout.strip(), block)


class TestHygiene(unittest.TestCase):
    def test_no_placeholder_text(self):
        banned = ["TODO", "FIXME", "XXX", "coming soon", "lorem"]
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            if ".git" in path.parts or "__pycache__" in path.parts:
                continue
            if "tests" in path.parts:
                continue
            text = path.read_text(errors="replace")
            for word in banned:
                self.assertNotIn(word, text,
                                 f"{word} in {path.relative_to(ROOT)}")

    def test_no_absolute_paths(self):
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            if ".git" in path.parts or "__pycache__" in path.parts:
                continue
            if "tests" in path.parts:
                continue
            text = path.read_text(errors="replace")
            self.assertNotIn("/home/hatch", text,
                             f"absolute path in {path.relative_to(ROOT)}")
            self.assertNotIn("/Users/", text,
                             f"absolute path in {path.relative_to(ROOT)}")
            self.assertNotIn("/tmp/", text,
                             f"absolute path in {path.relative_to(ROOT)}")

    def test_stdlib_only_imports(self):
        allowed_src = {
            "argparse", "fnmatch", "json", "os", "re", "sys", "pathlib",
        }
        allowed_tests = allowed_src | {
            "ast", "subprocess", "tempfile", "unittest",
            "css_duplicate_property_checker",
        }
        for path, allowed in [(SRC, allowed_src),
                              (Path(__file__), allowed_tests)]:
            tree = ast.parse(path.read_text())
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(a.name.split(".")[0]
                                    for a in node.names)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imported.add(node.module.split(".")[0])
            self.assertTrue(imported <= allowed,
                            f"{path.name} imports non-stdlib: "
                            f"{imported - allowed}")
            self.assertNotIn("yaml", imported)

    def test_no_yaml_anywhere_in_source(self):
        text = SRC.read_text()
        self.assertNotIn("yaml", text)

    def test_no_secrets_in_repo(self):
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            if ".git" in path.parts or "__pycache__" in path.parts:
                continue
            if "tests" in path.parts:
                continue
            text = path.read_text(errors="replace").lower()
            for marker in ["api_key", "api-key", "password =", "secret ="]:
                self.assertNotIn(marker, text,
                                 f"possible secret in {path.relative_to(ROOT)}")

    def test_gitignore_env_first(self):
        lines = (ROOT / ".gitignore").read_text().splitlines()
        self.assertEqual(lines[0], ".env")

    def test_ci_uses_substring_markers(self):
        # CI-CHECK RULE (Nov 10): substring markers only — never an
        # exact-equality test against another repo's ci.yml, and
        # never a read of another repo's files by absolute path.
        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
        for marker in ["actions/checkout", "setup-python",
                       "test_css_duplicate_property_checker.py",
                       "push", "pull_request"]:
            self.assertIn(marker, ci, marker)


if __name__ == "__main__":
    unittest.main()
