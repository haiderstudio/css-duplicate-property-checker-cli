"""css-duplicate-property-checker-cli: check CSS rules for the same property declared twice in one rule, fail CI when any are found.

Reads the CSS files in a project folder and looks inside every
rule block for a property name that appears more than once — for
example `color: red;` followed later in the same rule by
`color: blue;`. The second value silently wins and the first one
is dead, so the stylesheet says two things and means one. Every
duplicate is reported with the file, the line of the repeat, and
the line of the first declaration. Report-only: it never rewrites
a file. Exit 0 when no rule repeats a property, 1 when any
duplicate is found, 2 for a usage error.

This is a different job from repo #74 (css-class-checker-cli),
which checks for UNUSED classes, and from ruilisi/css-checker
(588 stars), which checks duplicate and similar CLASSES. Neither
of them looks for a repeated property inside one rule block.

Property names are compared without case — `Padding` and
`padding` are the same property — and custom properties
(`--brand`) count too. A property repeated in two different
rules is fine: only repeats inside one block are reported.
"""

import argparse
import fnmatch
import json
import os
import re
import sys
from pathlib import Path

__version__ = "1.0.0"

CSS_SUFFIX = ".css"
SKIPPED_DIRS = (".git", "__pycache__", "node_modules")

COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
PROPERTY_RE = re.compile(r"^-{0,2}[A-Za-z][A-Za-z0-9-]*$")


class Problem:
    """One duplicate property: path, line number, plain reason."""

    def __init__(self, path, line, reason):
        self.path = path
        self.line = line
        self.reason = reason

    def text(self):
        return f"{self.path}:{self.line}: {self.reason}"

    def as_dict(self):
        return {"file": self.path, "line": self.line, "reason": self.reason}


def blank_out(match):
    """Replace a comment with spaces, keeping its newlines."""
    return "".join("\n" if char == "\n" else " "
                   for char in match.group(0))


def strip_comments(text):
    """Remove /* ... */ comments without moving later line numbers."""
    return COMMENT_RE.sub(blank_out, text)


def line_of(text, offset):
    """Line number (1-based) of a character offset in text."""
    return text.count("\n", 0, offset) + 1


class _Frame:
    """One open rule block: its declarations, in order.

    A frame holds (name as written, lowercased name, line) for
    every property declared directly in that block. A nested
    block (a rule inside a media query, or a nested rule) gets
    its own frame, so a property in the inner block never counts
    against the same property in the outer block.
    """

    def __init__(self):
        self.declarations = []
        self.segment = ""
        self.segment_start = 0


def _finish_segment(text, frame, ignored):
    """Turn the frame's pending segment into a declaration, if it is one.

    A segment is a declaration when it holds `name: value` with a
    real property name and a non-empty value. Selector text (which
    has no colon, or a colon followed by selector text) never
    qualifies: a property name has no spaces and starts with a
    letter or a dash.
    """
    segment = frame.segment
    frame.segment = ""
    stripped = segment.strip()
    if not stripped or ":" not in stripped:
        return
    name, _, value = stripped.partition(":")
    name = name.strip()
    if not PROPERTY_RE.match(name):
        return
    if not value.strip():
        return
    start = frame.segment_start
    for index, char in enumerate(segment):
        if not char.isspace():
            start = frame.segment_start + index
            break
    line = line_of(text, start)
    frame.declarations.append((name, name.lower(), line))


def _frame_problems(frame, path, ignored):
    """Duplicate problems for one finished block, in file order."""
    seen = {}
    problems = []
    for name, lowered, line in frame.declarations:
        if lowered in ignored:
            continue
        if lowered in seen:
            first_line = seen[lowered]
            problems.append(Problem(
                path, line,
                f"duplicate property '{name}' — first declared "
                f"on line {first_line} in the same rule",
            ))
        else:
            seen[lowered] = line
    return problems


def find_duplicates(text, path, ignored=()):
    """Find duplicate properties in one CSS document.

    Returns (problems, declaration_count). Comments are blanked
    first so a property-like word in a comment is never read as a
    declaration, and strings are tracked so a `;` or `}` inside
    a quoted value never ends a declaration or a block.
    """
    text = strip_comments(text)
    ignored = {name.strip().lower() for name in ignored if name.strip()}
    root = _Frame()
    stack = [root]
    problems = []
    total = 0
    quote = None
    paren_depth = 0
    index = 0
    while index < len(text):
        char = text[index]
        frame = stack[-1]
        if quote is not None:
            frame.segment += char
            if char == "\\" and index + 1 < len(text):
                frame.segment += text[index + 1]
                index += 2
                continue
            if char == quote:
                quote = None
            index += 1
            continue
        if char in ("'", '"'):
            if not frame.segment:
                frame.segment_start = index
            frame.segment += char
            quote = char
            index += 1
            continue
        if char == "(":
            paren_depth += 1
        elif char == ")":
            paren_depth = max(0, paren_depth - 1)
        if char == "{":
            frame.segment = ""
            stack.append(_Frame())
            index += 1
            continue
        if char == "}":
            _finish_segment(text, frame, ignored)
            total += len(frame.declarations)
            if len(stack) > 1:
                finished = stack.pop()
                problems.extend(
                    _frame_problems(finished, path, ignored))
                stack[-1].segment = ""
            index += 1
            continue
        if char == ";" and paren_depth == 0:
            _finish_segment(text, frame, ignored)
            index += 1
            continue
        if not frame.segment:
            frame.segment_start = index
        frame.segment += char
        index += 1
    while stack:
        frame = stack.pop()
        _finish_segment(text, frame, ignored)
        total += len(frame.declarations)
        problems.extend(_frame_problems(frame, path, ignored))
    problems.sort(key=lambda problem: problem.line)
    return problems, total


def check_files(css_files, ignored=()):
    """Check CSS files for duplicate properties.

    Returns (results, total_declarations) where results is a list
    of (path, declaration_count, [Problem]) per CSS file, in path
    order.
    """
    results = []
    total_declarations = 0
    for css_path in css_files:
        try:
            text = Path(css_path).read_text(encoding="utf-8",
                                            errors="replace")
        except OSError as exc:
            results.append((css_path, 0, [Problem(
                css_path, 0,
                f"cannot read file: {exc.strerror or exc}",
            )]))
            continue
        problems, count = find_duplicates(text, css_path, ignored)
        total_declarations += count
        results.append((css_path, count, problems))
    return results, total_declarations


def is_excluded(name, patterns):
    """True when a file name matches any --exclude glob pattern."""
    return any(fnmatch.fnmatchcase(name, pattern)
               for pattern in patterns)


def collect(paths, recursive=True, exclude=()):
    """Gather CSS files from the given paths.

    A folder contributes its .css files (recursively unless
    --no-recursive). A CSS file passed directly is always
    checked. .git, __pycache__, and node_modules folders are
    never walked, and directory links are never followed.
    Returns (css_files, missing) with files sorted and
    deduplicated.
    """
    css_files = []
    missing = []

    def walk(folder):
        for root, dirs, names in os.walk(folder):
            dirs[:] = sorted(
                name for name in dirs
                if name not in SKIPPED_DIRS
                and not os.path.islink(os.path.join(root, name))
            )
            if not recursive:
                dirs[:] = []
            for name in sorted(names):
                if is_excluded(name, exclude):
                    continue
                if name.lower().endswith(CSS_SUFFIX):
                    css_files.append(str(Path(root) / name))

    for raw in paths:
        path = Path(raw)
        if not path.exists():
            missing.append(raw)
            continue
        if path.is_file():
            if path.name.lower().endswith(CSS_SUFFIX):
                css_files.append(str(path))
            continue
        walk(str(path))
    return sorted(set(css_files)), missing


def build_parser():
    parser = argparse.ArgumentParser(
        prog="css_duplicate_property_checker",
        description="Check CSS rules for the same property "
                    "declared twice in one rule block.",
    )
    parser.add_argument(
        "paths", nargs="*", metavar="PATH",
        help="CSS file(s) or folder(s) to check",
    )
    parser.add_argument(
        "--exclude", action="append", default=[], metavar="PATTERN",
        help="skip walked files whose name matches this glob "
             "(repeatable; direct files are always checked)",
    )
    parser.add_argument(
        "--ignore", action="append", default=[], metavar="PROPERTY",
        help="allow this property to repeat in a rule "
             "(repeatable; for deliberate fallback declarations, "
             "such as display written twice for old browsers)",
    )
    parser.add_argument(
        "--no-recursive", action="store_true",
        help="do not walk into subfolders",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="print the result as machine-readable JSON "
             "(the summary goes to standard error)",
    )
    parser.add_argument(
        "--version", action="version", version="%(prog)s " + __version__,
    )
    return parser


def report_text(results, checked, total_declarations, total):
    """Print the plain-text report. Returns the exit code."""
    files_with_problems = sum(1 for _, _, probs in results if probs)
    for path, count, problems in results:
        if problems:
            for problem in problems:
                print(f"FAIL {problem.text()}")
        elif count == 0:
            print(f"{path}: OK — no properties found")
        else:
            print(f"{path}: OK — {count} property declaration(s), "
                  "none duplicated")
    if total == 0:
        print(f"OK — {checked} CSS file(s) checked, "
              f"{total_declarations} property declaration(s), "
              "none duplicated.")
        return 0
    print(f"Checked {checked} CSS file(s) "
          f"({total_declarations} property declaration(s)), "
          f"{total} problem(s) in {files_with_problems} file(s).")
    return 1


def report_json(results, checked, total_declarations, total):
    """Print the JSON report. Returns the exit code."""
    files_with_problems = sum(1 for _, _, probs in results if probs)
    payload = {
        "files": [
            {
                "file": path,
                "declarations": count,
                "problems": [problem.as_dict() for problem in problems],
            }
            for path, count, problems in results
        ],
        "summary": {
            "checked": checked,
            "declarations": total_declarations,
            "files_with_problems": files_with_problems,
            "problems": total,
        },
    }
    print(json.dumps(payload, indent=2))
    print(f"Checked {checked} CSS file(s) "
          f"({total_declarations} property declaration(s)), "
          f"{total} problem(s) in {files_with_problems} file(s).",
          file=sys.stderr)
    return 1 if total else 0


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.paths:
        parser.error("give at least one PATH")
    css_files, missing = collect(
        args.paths,
        recursive=not args.no_recursive,
        exclude=args.exclude,
    )
    if missing:
        for raw in missing:
            print(f"error: no such file or folder: {raw}",
                  file=sys.stderr)
        return 2
    if not css_files:
        print("error: no CSS files found", file=sys.stderr)
        return 2
    results, total_declarations = check_files(css_files, args.ignore)
    total = sum(len(problems) for _, _, problems in results)
    if args.json:
        return report_json(results, len(css_files),
                           total_declarations, total)
    return report_text(results, len(css_files),
                       total_declarations, total)


if __name__ == "__main__":
    sys.exit(main())
