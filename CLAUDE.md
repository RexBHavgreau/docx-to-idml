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
| `docx2idml/content.py` | The text of a .docx for the exporter: runs with formatting features, notes, tables, images, list numbers; paragraph indexes match `docx_reader`'s |
| `docx2idml/export.py` | Step 4, the exporter core: book styles, Word styles kept by name, runs to character styles, Hebrew/Greek, one story and section per outline unit, page estimate; `export()` writes the export folder |
| `docx2idml/cli.py` | `python -m docx2idml preflight / export / profile` |
| `docx2idml/idml/` | The IDML writer: `model.py` (the book as pages, styles, stories, sections), `writer.py`, `images.py` (image size and resolution from file headers), `base/` (InDesign's own settings and root styles, made by `tools/make_base.py` from reference 01; `snippets.xml` holds elements the writer clones) |
| `reference/` | `make_reference_files.jsx` (builds the InDesign reference files), README with the Affinity checklist; reference IDMLs go in `reference/idml/` |
| `idml-schema/` | Adobe's IDML schema for InDesign 2026 (21.6.0.57, DOM 21.5): `rnc/` as InDesign wrote it, `rng/` converted by `tools/prepare_schema.py` |
| `tools/make_generated_files.py` | Step 3: the generator's versions of the reference files, in `reference/generated/` |
| `tools/idml_check.py`, `tools/idml_inspect.py` | Development tools: structural check of an IDML package plus jing against the schema; summary of a package (masters, pages, overrides, sections, stories, styles) for comparing with references |
| `tools/make_sample_book.py` | Step 4: a sample manuscript (`reference/manuscript/`, three .docx) exported to `reference/generated/e01-sample-book/` |
| `tests/docx_builder.py` | Builds test .docx files from raw WordprocessingML (images, tables, numbering too); the test runner |

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
- Footnotes are written as in `reference/variants/fn-m-split-formatting.idml` (decided after
  Affinity tests, see PLAN.md): Footnote paragraph style; the number `<?ACE 4?>` and separator in
  a run of their own (Affinity breaks single-run notes); the Footnote style's font, size,
  leading, indent and alignment also on every note run (Affinity otherwise lays the root style
  `[No paragraph style]` over note text). Style edits still reach every note in both programs.
- designmap.xml must start with InDesign's `<?aid style="50" type="document" ...?>` line before
  `<Document>`; without it InDesign says it "may not support the file format". The schema
  doesn't require it; `idml_check.py` does. Write parts with `writer.serialize()` (whole
  document, double-quoted XML declaration), never `tostring(root)`, which drops the line.
- `DocumentPreference PagesPerDocument` stays 1 (the new-document default InDesign writes); set
  to the real page count, InDesign adds that many pages at the start when opening the file.
- In facing documents a page's side follows its number (odd = recto), as in InDesign; a recto
  after a recto stands alone on its spread (reference 03). The writer works out spreads that way.
- IDML sections, as InDesign writes them (g01's first version broke these and wouldn't open
  in InDesign, though it validated and opened in Affinity): the alternate layout's name
  (`AlternateLayout="Custom V"`) on the first section only, `""` on the others;
  `AlternateLayoutLength` = pages from the section's start to the end; pages'
  `AppliedAlternateLayout` = the first section's id. A spread's `BindingLocation` is 0 when it
  starts with a recto, 1 when it starts with a verso (a lone last verso too). Each page carries a
  `Descriptor` (prefix, numbering style, continue numbering, include prefix, number, number,
  marker). Validating against the schema is not enough: compare with the reference files.
- Tables: write every row's `SingleRowHeight` (an estimate; InDesign grows a short row).
  Without it Affinity can't break a table across frames and runs it off the page (g07).
- An export is a folder of its own (`writer.export_book`): `<name>/<name>.idml` and
  `<name>/Links/` with the images, linked relative to the IDML (`file:Links/x.jpg`), so the
  folder can be moved or sent on: both InDesign and Affinity find them (decided October 21).
  Full paths (InDesign's own way) broke when the folder moved. Frames are cloned from reference 11.
  `tests/data/sample.jpg` is the test image (450 x 300 px, 150 ppi).
- IDML: a page frame made from a master frame is linked on the `<Page>` element,
  `OverrideList="<master item> <page item> ..."` (pairs), not on the frame; the frame itself is
  an ordinary `TextFrame` (reference file 05).
- The two InDesign files from the brief (the Assumption article and its cut-down) are a real
  article: use them for analysis only; don't commit them.
- Export (step 4): direct italic, bold, small caps, capitals, super/subscript, underline and
  strikethrough become character styles (Italic, Bold, Bold Italic, Small Caps...), worked out
  against the paragraph style (italic in a bold heading is Bold Italic; Word's toggle rule for
  a character style inside an italic paragraph is kept). Other direct formatting gives way to
  the book's styles. Body after a heading, a centered line or at a story's start is Body First.
  List and heading numbers are static text for now (IDML auto-numbering not yet tested in
  Affinity). Images that aren't JPEG or PNG are left out with a placeholder line and reported.
- Styles are matched by name (Word writes built-in names in English, lower case, in the file);
  `stylemap.display_name` gives the name as Word shows it.

## Tests

```
python tests/test_reader.py
python tests/test_outline.py
python tests/test_preflight.py
python tests/test_idml_tools.py
python tests/test_writer.py
python tests/test_export.py
```

Run them all before pushing; CI (`.github/workflows/tests.yml`) runs them on Windows and Linux.
On Windows set `PYTHONUTF8=1`. `test_preflight` includes a LibreOffice round trip when
`soffice` is installed; LibreOffice refuses a theme without a color scheme, so the test builder
writes one.

## Not yet checked
- Step 2: Affinity done (all files; footnotes settled as fn-m, rule and spacing as fn-o/p/q).
  DesignCraft not yet.
- Step 3: g01 (footnotes) opens in Affinity and looks right; confirmed in InDesign and Affinity.
  g02-g04 confirmed in both programs. g05-g10, g12, g13 (primary text frame, contents style,
  table, OpenType, baseline grid, Hebrew/Greek, character styles, chapter stories) validate and
  match their references in the inspector (masters named A-Body where InDesign defaults to
  A-Parent; g06 writes the contents style and a reserved page, no generated contents, as
  decided). Beaux: all right in InDesign; contents placed by hand from the style in both programs
  (as intended); all right in Affinity except g07's table, which doesn't break across pages
  even with row heights (parked: tables uncommon; reference 07 does break, so compare again
  later). g11 (images) right in both; with the linked path missing, both programs find the image
  in the file's folder, else warn and leave a placeholder. Step 3 done. The base's Fonts.xml is InDesign's from reference 01 (Minion, Myriad,
  Kozuka, Arno); generating it from the fonts used is still to do. `reference/make_reference_files.jsx` v3 made the last file (05); all 13
  are in `reference/idml/` and validate. ExtendScript is
  ES3: no let/const, arrow functions, forEach/indexOf/map, trim. The file is saved as UTF-8
  with a byte-order mark.

- Step 4: e01 (sample book) validates; not yet opened in InDesign or Affinity. Not yet run on a
  real manuscript.
- Preflight on a real manuscript from Word (only generated files and a LibreOffice re-save so far).
