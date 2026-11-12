# Sample output

Output of `sh examples/run-example.sh` — the checker run over
the whole `examples/` folder (2 CSS files, 25 declarations,
5 problems in 1 file):

```
examples/clean.css: OK — 12 property declaration(s), none duplicated
FAIL examples/messy.css:5: duplicate property 'color' — first declared on line 3 in the same rule
FAIL examples/messy.css:10: duplicate property 'margin' — first declared on line 9 in the same rule
FAIL examples/messy.css:17: duplicate property 'padding' — first declared on line 15 in the same rule
FAIL examples/messy.css:23: duplicate property 'width' — first declared on line 22 in the same rule
FAIL examples/messy.css:29: duplicate property '--brand' — first declared on line 28 in the same rule
Checked 2 CSS file(s) (25 property declaration(s)), 5 problem(s) in 1 file(s).
```

The five duplicates are `color` in `.card`, `margin` in `.btn`,
`padding` in `.title` (written once as `Padding` — property
names are compared without case), `width` in `.sidebar` inside
the media query, and the custom property `--brand` in `:root`.
The clean stylesheet repeats `color` in different rules and
`color` next to `background-color` in one rule — neither is a
duplicate, because only repeats inside one rule block count.
