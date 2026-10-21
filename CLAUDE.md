# docx-to-idml: notes for Claude

Converts a Word book manuscript (one .docx or several) into IDML for InDesign, Affinity and
DesignCraft. The tool's name is undecided ("docx-to-idml" and the package name `docx2idml` are
placeholders; `APP_NAME` in `docx2idml/__init__.py` sets the settings folder). Python, CLI
first, then a Tkinter GUI built into one .exe with PyInstaller. The full plan is in `PLAN.md`;
keep it up to date when decisions change.

## Working with Beaux

- Keep reports short and plain: what changed, what was tested, what wasn't.
- He works on Windows. Build for Windows.
- Ask before merging to `main` or tagging a release. Work on a branch and push it; Beaux merges.
- He is an editor and Hebrew/OT scholar; conventions follow the Chicago Manual of Style. When an
  editorial choice is unclear, ask rather than guess.

## Rules from the plan

- **Nothing that works only in InDesign.** Every feature must work in InDesign, Affinity and
  DesignCraft, or have a fallback that does. IDML is the only output, complete without scripts.
- Hebrew needs InDesign (Affinity reverses it); preflight says so whenever Hebrew is found.
- Word is read with lxml directly; python-docx is not used.
- Every IDML the tool writes must validate against Adobe's schema (jing, during development
  and tests only; the shipped .exe doesn't validate). Write `DOMVersion="21.5"`.
- Nothing disappears silently: whatever isn't carried over is listed in preflight.
- The user's files are never modified.
- User-facing text is plain and specific: say what to do.

## Layout

| Path | What it is |
|---|---|
| `docx2idml/docx_reader.py` | Reads a .docx: styles, paragraphs, notes, sections, fields, scripts, unsupported items |
| `docx2idml/stylemap.py` | Word style -> IDML style and role; defaults for Word's built-ins |
| `docx2idml/outline.py` | Units across files (front, part, chapter, back); title/author detection |
| `docx2idml/preflight.py` | The preflight report (text and JSON) |
| `docx2idml/profile.py` | Profiles: defaults, save/load, export/import, `PROFILE_VERSION` + `MIGRATIONS` |
| `docx2idml/book.py` | Input files: drop/folder collection, natural order, saved order |
| `docx2idml/cli.py` | `python -m docx2idml preflight / profile` |
| `reference/` | `make_reference_files.jsx` (builds the InDesign reference files), README with the Affinity checklist; reference IDMLs go in `reference/idml/` |
| `idml-schema/` | Adobe's IDML schema for InDesign 2026 (21.6.0.57, DOM 21.5): `rnc/` as InDesign wrote it, `rng/` converted by `tools/prepare_schema.py` |
| `tools/idml_check.py`, `tools/idml_inspect.py` | Development tools: structural check of an IDML package plus jing against the schema; summary of a package (masters, pages, overrides, sections, stories, styles) for comparing with references |
| `tests/docx_builder.py` | Builds test .docx files from raw WordprocessingML; the test runner |

## Conventions

- When the profile layout changes, bump `PROFILE_VERSION` and add a step to `MIGRATIONS` in
  `profile.py`, so saved profiles are upgraded, not lost.
- In Word, a section's `w:type` says how *that* section starts; it sits in the sectPr that ends
  the section.
- The schema is strict about element order (e.g. in designmap.xml, idPkg:Styles comes before
  idPkg:Preferences, and many settings are child `<Properties>` elements, not attributes).
  Check the generator's output with `tools/idml_check.py`; jing needs Java and
  `pip install -r requirements-dev.txt`.
- IDML composer names: `HL Composer` (Adobe Paragraph Composer), `HL Single` (Single-line),
  `HL Composer Optyca` (World-Ready). They are InDesign's own, not plug-ins.
- IDML: a parent-master item removed on a child master, or a master item removed on a page,
  is an `OverrideList` pair with `n` as the page item.
- IDML: a page frame made from a master frame is linked on the `<Page>` element,
  `OverrideList="<master item> <page item> ..."` (pairs), not on the frame; the frame itself is
  an ordinary `TextFrame` (reference file 05).
- The two InDesign files from the brief (the Assumption article and its cut-down) are a real
  article: use them for analysis only; don't commit them.
- Styles are matched by name (Word writes built-in names in English, lower case, in the file);
  `stylemap.display_name` gives the name as Word shows it.

## Tests

```
python tests/test_reader.py
python tests/test_outline.py
python tests/test_preflight.py
python tests/test_idml_tools.py
```

Run them all before pushing; CI (`.github/workflows/tests.yml`) runs them on Windows and Linux.
On Windows set `PYTHONUTF8=1`. `test_preflight` includes a LibreOffice round trip when
`soffice` is installed; LibreOffice refuses a theme without a color scheme, so the test builder
writes one.

## Not yet checked
- Step 2: Affinity done (compatibility table in PLAN.md) except footnotes: Affinity mishandles
  InDesign's footnote structure; the six variants in `reference/variants/`
  (`tools/make_footnote_variants.py`) are waiting on Beaux's check. 08, 10, 12 rebuilt (v4)
  and clean; their Affinity check is still to redo. DesignCraft not yet. `reference/make_reference_files.jsx` v3 made the last file (05); all 13
  are in `reference/idml/` and validate. ExtendScript is
  ES3: no let/const, arrow functions, forEach/indexOf/map, trim. The file is saved as UTF-8
  with a byte-order mark.

- Preflight on a real manuscript from Word (only generated files and a LibreOffice re-save so far).
