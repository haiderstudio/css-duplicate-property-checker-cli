# css-duplicate-property-checker-cli

Check CSS rules for the same property declared twice in one rule, fail CI when any are found.

[![CI](https://github.com/haiderstudio/css-duplicate-property-checker-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/haiderstudio/css-duplicate-property-checker-cli/actions/workflows/ci.yml) [![Licence: MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)

## What it does

`css_duplicate_property_checker` reads the CSS files in a
project folder and looks inside every rule block for a property
name that appears more than once:

- A duplicated property inside one rule is almost always a
  copy-paste slip or a leftover from an edit — the second value
  silently wins and the first one is dead, so the stylesheet
  says two things and means one. This tool reports every
  repeat with the file, the line of the repeat, and the line of
  the first declaration, so the dead one is easy to find and
  delete. It exits 1 when any duplicate is found, so it can
  fail a CI run. A project with no duplicates exits 0.
- Property names are compared without case — `Padding` and
  `padding` are the same property — and custom properties
  (`--brand`) count too. A property repeated in two different
  rules is fine: only repeats inside one block are reported.
  A rule inside a media query is its own block, and a nested
  rule is its own block too, so the same property in the outer
  rule and the inner rule is not a duplicate.
- Comments are stripped first, so a property-like line in a
  comment is never reported. A `;` or `}` inside a quoted
  value (like `content: "; }"`) never ends a declaration or a
  block, and a `;` inside parentheses (like a `url(data:...)`
  value) never splits a declaration.
- A project folder is given on the command line, and it is
  walked recursively by default (`--no-recursive` stops at
  the top level). A single CSS file can be given instead —
  only that file is checked. `.git`, `__pycache__`, and
  `node_modules` folders are never walked, and directory
  links are never followed, so a link cycle cannot loop the
  check.
- `--ignore PROPERTY` allows a property to repeat, for
  deliberate fallback declarations — writing `display` twice
  so old browsers get the first value and new browsers get
  the second, for example. It can be repeated, and it matches
  without case. Only use it for repeats you mean — every
  ignored property is one the tool stops checking.
- `--exclude PATTERN` skips walked files by glob, for example
  `--exclude 'vendor-*'`. It can be repeated. A file passed
  directly on the command line is always checked, even if it
  matches an exclude pattern.
- `--json` prints the result as machine-readable JSON (the
  summary goes to standard error, so standard output stays
  clean JSON).
- It is report-only and runs fully offline: it never edits a
  file, sends nothing anywhere, and needs no API key. Python
  standard library only — plain-text parsing, no CSS parser.

## What it does NOT do

- It does not check unused classes. That job is
  css-class-checker-cli (repo #74 in the same series), which
  reports classes nothing references. This tool's one job is
  repeated properties inside one rule.
- It does not check duplicate or similar classes. That job
  is owned by ruilisi/css-checker, 588 stars — a Go CLI
  built for it. This tool does not try to do that job.
- It does not delete or fix duplicated properties. A
  duplicate is reported with its file and line; removing it
  is your job.
- It does not read stylesheets loaded from a URL. Every
  input is a local file or folder.
- It does not understand every corner of CSS: a property
  written with an empty value (`color:;`) is not counted as
  a declaration, and a declaration split across a line
  inside a string is read as written. Plain stylesheets,
  which is what projects actually ship, are all covered.

## Who it is for

Anyone with a stylesheet that has been edited by hand over
time and wants the dead declarations out: a developer
tidying a site before a redesign, a team adding a CI step
that fails the build when a rule gains a property twice, or
anyone who has ever stared at a rule wondering which of its
two values the browser actually uses. Every duplicate is
named with its file and both line numbers — the delete is
safe.

## How this differs from similar tools

The exact name `css-duplicate-property-checker-cli` matches 0
repositories on GitHub (checked Nov 11, 2026), and the wider
field `css duplicate property checker` also matches 0. The
field is empty for this job.

The closest tools do different jobs on the same files.
css-class-checker-cli (repo #74 in the same series) checks
for UNUSED classes — a class nothing references. It never
looks inside a rule block at properties. The 588-star
ruilisi/css-checker checks duplicate and similar CLASSES
(`.btn` written twice, or `.btn` and `.button` meaning the
same thing) — not a property repeated inside one rule.
colour-contrast-checker-cli (repo #18 in the same series)
checks colour pairs, not declarations. None of them reports
a property declared twice in one rule with its file and
line, or exits 1 for CI. This tool does that one job: a
Python standard-library-only CLI that finds duplicate
properties inside CSS rules — no install beyond Python, no
website, no network.

## Install

Python standard library only — no packages to download. You need
Python 3.8 or newer. Clone the repo and run it in place:

```
git clone https://github.com/haiderstudio/css-duplicate-property-checker-cli.git
cd css-duplicate-property-checker-cli
python3 src/css_duplicate_property_checker.py examples/clean.css
```

```
examples/clean.css: OK — 12 property declaration(s), none duplicated
OK — 1 CSS file(s) checked, 12 property declaration(s), none duplicated.
```

## Usage

Check one clean stylesheet:

```
python3 src/css_duplicate_property_checker.py examples/clean.css
```

```
examples/clean.css: OK — 12 property declaration(s), none duplicated
OK — 1 CSS file(s) checked, 12 property declaration(s), none duplicated.
```

Check a stylesheet with duplicated properties — `color` in
`.card`, `margin` in `.btn`, `padding` in `.title` (written
once as `Padding`), `width` in `.sidebar` inside the media
query, and the custom property `--brand` in `:root`:

```
python3 src/css_duplicate_property_checker.py examples/messy.css
```

```
FAIL examples/messy.css:5: duplicate property 'color' — first declared on line 3 in the same rule
FAIL examples/messy.css:10: duplicate property 'margin' — first declared on line 9 in the same rule
FAIL examples/messy.css:17: duplicate property 'padding' — first declared on line 15 in the same rule
FAIL examples/messy.css:23: duplicate property 'width' — first declared on line 22 in the same rule
FAIL examples/messy.css:29: duplicate property '--brand' — first declared on line 28 in the same rule
Checked 1 CSS file(s) (13 property declaration(s)), 5 problem(s) in 1 file(s).
```

Check a whole folder:

```
python3 src/css_duplicate_property_checker.py examples
```

```
examples/clean.css: OK — 12 property declaration(s), none duplicated
FAIL examples/messy.css:5: duplicate property 'color' — first declared on line 3 in the same rule
FAIL examples/messy.css:10: duplicate property 'margin' — first declared on line 9 in the same rule
FAIL examples/messy.css:17: duplicate property 'padding' — first declared on line 15 in the same rule
FAIL examples/messy.css:23: duplicate property 'width' — first declared on line 22 in the same rule
FAIL examples/messy.css:29: duplicate property '--brand' — first declared on line 28 in the same rule
Checked 2 CSS file(s) (25 property declaration(s)), 5 problem(s) in 1 file(s).
```

Allow a deliberate repeat with `--ignore` — here `color` is
allowed, so only the other four duplicates are reported:

```
python3 src/css_duplicate_property_checker.py --ignore color examples/messy.css
```

```
FAIL examples/messy.css:10: duplicate property 'margin' — first declared on line 9 in the same rule
FAIL examples/messy.css:17: duplicate property 'padding' — first declared on line 15 in the same rule
FAIL examples/messy.css:23: duplicate property 'width' — first declared on line 22 in the same rule
FAIL examples/messy.css:29: duplicate property '--brand' — first declared on line 28 in the same rule
Checked 1 CSS file(s) (13 property declaration(s)), 4 problem(s) in 1 file(s).
```

Machine-readable output with `--json` (the summary goes to
standard error, so standard output stays clean JSON):

```
python3 src/css_duplicate_property_checker.py --json examples/messy.css
```

```
{
  "files": [
    {
      "file": "examples/messy.css",
      "declarations": 13,
      "problems": [
        {
          "file": "examples/messy.css",
          "line": 5,
          "reason": "duplicate property 'color' \u2014 first declared on line 3 in the same rule"
        },
        {
          "file": "examples/messy.css",
          "line": 10,
          "reason": "duplicate property 'margin' \u2014 first declared on line 9 in the same rule"
        },
        {
          "file": "examples/messy.css",
          "line": 17,
          "reason": "duplicate property 'padding' \u2014 first declared on line 15 in the same rule"
        },
        {
          "file": "examples/messy.css",
          "line": 23,
          "reason": "duplicate property 'width' \u2014 first declared on line 22 in the same rule"
        },
        {
          "file": "examples/messy.css",
          "line": 29,
          "reason": "duplicate property '--brand' \u2014 first declared on line 28 in the same rule"
        }
      ]
    }
  ],
  "summary": {
    "checked": 1,
    "declarations": 13,
    "files_with_problems": 1,
    "problems": 5
  }
}
```

Exit codes: 0 when no rule repeats a property, 1 when any
duplicate property is found, 2 for a usage problem (no paths
given, a bad flag, or a missing file or folder).

## Examples

### 1. A clean stylesheet

`examples/clean.css` repeats `color` in different rules and
puts `color` next to `background-color` in one rule — neither
is a duplicate, because only repeats inside one rule block
count:

```
python3 src/css_duplicate_property_checker.py examples/clean.css
```

```
examples/clean.css: OK — 12 property declaration(s), none duplicated
OK — 1 CSS file(s) checked, 12 property declaration(s), none duplicated.
```

### 2. A stylesheet with five duplicates

`examples/messy.css` has five duplicates across five rules,
including one inside a media query and one written with a
different capital letter:

```
python3 src/css_duplicate_property_checker.py examples/messy.css
```

```
FAIL examples/messy.css:5: duplicate property 'color' — first declared on line 3 in the same rule
FAIL examples/messy.css:10: duplicate property 'margin' — first declared on line 9 in the same rule
FAIL examples/messy.css:17: duplicate property 'padding' — first declared on line 15 in the same rule
FAIL examples/messy.css:23: duplicate property 'width' — first declared on line 22 in the same rule
FAIL examples/messy.css:29: duplicate property '--brand' — first declared on line 28 in the same rule
Checked 1 CSS file(s) (13 property declaration(s)), 5 problem(s) in 1 file(s).
```

### 3. The bundled examples, all at once

```
sh examples/run-example.sh
```

The script checks the whole `examples/` folder (fail, on
purpose — the example stylesheet has five duplicated
properties). Its full output is in
`examples/sample-output.md`, ending with `Checked 2 CSS
file(s) (25 property declaration(s)), 5 problem(s) in 1 file(s).`
The failing run exits 1, which is the expected result — the
script ends with exit 0 so it can be run as a demo.

## How it is tested

Tests, standard library `unittest` only, no packages to install:

```
python3 tests/test_css_duplicate_property_checker.py
```

The tests cover: parsing (a simple duplicate, no duplicate,
the same property in different rules, three occurrences of
one property, case-insensitive names, custom properties,
vendor prefixes as different properties, `color` versus
`background-color`, a duplicate-looking line in a comment,
a comment between declarations, a string holding `;` and
`}`, a media-query rule, the same property in the outer
rule and the media rule, a nested rule as its own block, a
declaration after a nested rule, keyframes steps as their
own blocks, a duplicate inside one keyframe step, a last
declaration with no semicolon, an empty value, a
declaration with no colon, a `;` inside a `url(data:...)`
value, an `!important` value, an `@import` line, line
numbers across a multi-line file, an empty stylesheet, an
ignored property with and without matching case, and an
unclosed block), the check itself (all clean, a duplicate
found with its exact report line, an unreadable CSS file,
several files in path order), file collection (a folder
walk, `.git` and `node_modules` skipped, `--no-recursive`,
`--exclude`, a direct CSS file checked alone, a direct
non-CSS file ignored, a missing path, an empty folder,
uppercase `.CSS` extensions), the CLI (exit 0/1/2, each
flag, `--json` output, `--version`, bad flags, missing
paths, a folder summary count, a run from a different
working directory checked by path suffix, and every bundled
example file read back with its expected problems), the
bundled examples (sample output compared byte-for-byte
against a fresh run, and the README-quoted outputs checked
against it, including the JSON block), and hygiene checks
(no placeholder text, no absolute paths, stdlib imports
only, `.env` first in `.gitignore`, CI file checked with
substring markers only).

## Contributing

Small, focused improvements are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT — see [LICENSE](LICENSE).

## Original work

This tool was written from scratch for this repo. The idea
of checking stylesheets is not new — the similar tools named
above (the 588-star css-checker for duplicate classes, and
css-class-checker-cli for unused classes) are listed in "How
this differs" — but every line of code here is original, and
the tool builds on nothing but Python's standard library.
The unused-classes job is deliberately left to
css-class-checker-cli, and the duplicate-classes job to
ruilisi/css-checker, which own them.
