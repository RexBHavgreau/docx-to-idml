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
| `docx2idml/layout.py` | Step 5: margins and measure (65 characters, floors, KDP gutter by page count), pagination (roman front matter, recto rules, masters per page) |
| `docx2idml/frontmatter.py` | Step 6: book details (settings, then detected, else bracketed placeholders), half-title, title, copyright (English/Spanish, notices from the profile's library), contents entries and reserved pages |
| `docx2idml/fonts.py` | Installed fonts (system and user folders) and a font's average character width (fontTools), for the measure |
| `docx2idml/cli.py` | `python -m docx2idml preflight / export / profile`; no arguments opens the window |
| `docx2idml/gui.py` | Step 7, the window (ttk): Files, Book details, Running heads, Layout profile, Style map, Report tabs; forms declared as field tables bound to the profile and book settings; work in threads, results through a queue polled by the window |
| `docx2idml/updates.py`, `appsettings.py` | Update check and install (as Indicat's: versioned .exe beside the running one, SHA-256 digest, Downloads fallback, older copies offered for deletion); the program's own settings.json |
| `run_app.py`, `build_exe.bat`, `.github/workflows/build.yml` | The .exe (PyInstaller, one file, "docx-to-idml-X.Y.Z.exe", with `docx2idml/idml/base`); the workflow builds and releases on a `vX.Y.Z` tag, or by hand |
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
  Settings the run's own character style sets (Italic's face, Greek/Hebrew fonts) are left off
  the run, or the local copy overrides the style (italics in notes were lost until 0.2.0).
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
- Layout (step 5): masters A-Body, B-Opener, C-Front each have their own primary text frames
  (and a folio for now); D-Display and E-Blank are empty. Each unit is a story and a section;
  display and front units are LowerRoman from i, the first chapter or part restarts Arabic 1.
  Spare pages per chapter as the profile says (default none); blank versos before recto
  openers get E-Blank.
- Keeps (October 21): widow/orphan control is KeepLinesTogether="true" with KeepFirstLines and
  KeepLastLines 2 (InDesign ignores the line counts without KeepLinesTogether); headings keep
  all their lines together and with the next paragraph; no hyphen in a paragraph's last word
  or at the foot of a page. Short last lines (runts) are prevented without GREP styles, which
  Affinity lacks: the exporter puts the last words of each running-text paragraph in the
  "No Break" character style (or NoBreak="true" on a run that has a style already) so the last
  line has at least `typography.last_line_min_chars` (10) characters.
- Front matter and heads (step 6): the book is a list of `export.Block`s: generated half-title
  (i), title (recto), copyright (the verso after it, set at the foot), the manuscript's display
  pages, reserved contents (recto; its page count estimated or set), then front matter, text,
  back matter. The manuscript's title page is replaced (copyright lines from it go on the
  copyright page; other lines on a display page of their own); its typed contents is dropped.
  Running heads: recto = section marker (short title from `settings["short_titles"]`), verso =
  book title / author / chapter / custom on A-Body; C-Front shows the marker both sides; B, D, E
  none unless the profile's suppress toggles are off. Verso "part": one copy of A-Body per part
  (P1-Body...), not a child master, so linked page frames point at its own primary frames. Book
  settings (`Book.settings`): "front" (see frontmatter.py) and "short_titles".
- Bibliographies (0.2.0): Body paragraphs are set in Bibliography from a heading whose title is
  a bibliography title (outline `_BACK`) at any level until the next heading of the same or a
  higher level, a new unit or a new file. Outline: text before a file's first chapter heading
  is a unit of its own (titled by a Title-style line, else its first line) when it has a title
  line, headings or more than 150 words; in the first file, a short opening without headings
  is the title page; a stray line or two in a later file stays with the previous unit. In a
  chapter, Title/Subtitle/Author lines are set as Chapter Title, Chapter Subtitle, Chapter Author.
- Composer (0.2.0): the book's styles use the World-Ready composer (`HL Composer Optyca`) by
  default; the Adobe Paragraph Composer (`HL Composer`) reversed Hebrew in InDesign (Beaux).
  Profile `paragraph_composer` off = single-line (`HL Single`), unless the book has Hebrew.
- Style template (0.2.0, `docx2idml/template.py`, profile `styles_template`): an IDML's
  paragraph and character styles replace the tool's by name (model level, so note runs and
  estimates use them); its other styles are added; attributes referring to swatches beyond
  InDesign's standard ones, lists, styles, and nested/GREP styles are dropped and reported.
  Its Body/Chapter Title/Footnote fonts count as chosen fonts; World-Ready kept if Hebrew.
- Spare pages: profile `page.spare_pages` 0 (default, Beaux), 1 or 2. Chapter Title has
  StartParagraph NextOddPage (NextPage for chapters on the next page); Chapter Subtitle resets
  it to Anywhere. Profile version 4.
- Unit kinds (0.3.0): the user can set a unit's kind (outline `KINDS`: chapter, part, front,
  back, display, endorsements) in the Running heads tab; saved as book settings
  `unit_kinds` {unit title: key}, applied by `outline.apply_kinds` after the outline is built.
  Endorsements (display, type "endorsements") are detected by title and placed before the
  half-title; so is text before the title line (outline: the title page is found by its
  Title-style line when no style-detected unit came before; units before it become
  endorsements). The window shows the calculated margins beside the margin fields
  (`export.calculated_margins`), with a button to fill them in.
- Font fields in the window are editable dropdowns of the installed families
  (`fonts.families()`; Hebrew and Greek lists filtered by a look at each regular font's
  character map, once, cached); read in a background thread at startup.
- Styles are matched by name (Word writes built-in names in English, lower case, in the file);
  `stylemap.display_name` gives the name as Word shows it.

## Releases

- Version in `docx2idml/__init__.py` (`EXE_BASE` and `REPO` there too); a dated entry at the
  top of `CHANGELOG.md`. Pushing a tag `vX.Y.Z` (matching `__version__`) runs
  `.github/workflows/build.yml` on Windows: tests, the .exe, a check that it carries the IDML
  base files, and a GitHub Release with the .exe (its SHA-256 digest is what the updater
  checks). **Ask Beaux before tagging.** Tag the merge commit on `main` (after the branch is
  merged): v0.1.0 was put on an older commit without the workflow, so nothing was built.

## Tests

```
python tests/test_reader.py
python tests/test_outline.py
python tests/test_preflight.py
python tests/test_idml_tools.py
python tests/test_writer.py
python tests/test_export.py
python tests/test_layout.py
python tests/test_updates.py
python tests/test_gui.py             # needs a display: on Linux, xvfb-run (and python3-tk)
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

- Step 4: e01 (sample book) opens in InDesign and Affinity and looks right (Beaux). Not yet run
  on a real manuscript.
- Step 5: e01 with the layout: text flows right, text width fine, folios right (Beaux). Spare
  pages the text doesn't reach keep their folio (they are text pages). Bleed not yet checked.
- Step 6: e01 with front matter and running heads: validates, not yet opened.
- Step 7: the window tested under Xvfb here and by its tests on GitHub's Windows runner.
  Released: v0.2.0 (October 21, the first release with the .exe, docx-to-idml-0.2.0.exe,
  built by the tag's workflow from main). The updater's real run (0.2.0 finding a later
  release, download, digest, old-copy cleanup) waits for the next release.
- Keeps and runts in e01: does Affinity keep KeepLinesTogether/KeepFirstLines/KeepLastLines,
  the No Break style and the local NoBreak attribute?
- 0.2.0 additions not yet opened: StartParagraph NextOddPage on Chapter Title (does Affinity
  keep it, and does InDesign leave a title already at the top of a recto where it is?); a
  style template's styles in InDesign and Affinity.
- Preflight on a real manuscript from Word (only generated files and a LibreOffice re-save so far).
