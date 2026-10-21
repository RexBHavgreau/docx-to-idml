# docx-to-idml (working name)

Turns a Word book manuscript (one .docx or several) into an IDML file that opens in InDesign,
Affinity or DesignCraft with most of the book already laid out: page geometry, masters, styles,
front matter, running heads and pagination. The plan is in [PLAN.md](PLAN.md).

**Status:** step 7 of the build order (the window, .exe and updater), not yet released. Preflight reports what the manuscript holds; export
writes the text, styles, footnotes, Hebrew and Greek, tables and images as IDML, with margins,
masters, roman/arabic page numbers and recto rules. Running heads and generated front matter
(half-title, title, copyright, contents) come next (step 6).

## The window

```
pip install -r requirements.txt
python run_app.py            # or: python -m docx2idml
```

Add the .docx files (or drop them, with tkinterdnd2 installed), put them in order, fill in the
book details and running heads, choose or adjust the layout profile, then Export IDML. File >
Save book keeps all of it for a re-export after corrections. `build_exe.bat` builds the
Windows program (`dist\docx-to-idml-X.Y.Z.exe`).

## Export

```
python -m docx2idml export "Chapter 1.docx" "Chapter 2.docx" --out books
python -m docx2idml export manuscript-folder --out books --profile "Series A"
```

Each export is a folder of its own (named after the book title, or `--name`) holding the IDML
and a `Links` folder with the images, linked relative to the IDML, so the folder can be moved
or sent on.

## Preflight

```
pip install -r requirements.txt
python -m docx2idml preflight "Chapter 1.docx" "Chapter 2.docx"   # files in book order
python -m docx2idml preflight manuscript-folder                   # a folder, natural name order
python -m docx2idml preflight manuscript-folder --save-book book.json
python -m docx2idml preflight --book book.json --json --out report.json
```

The report covers:

- the files in book order
- the outline (front matter, parts, chapters, back matter) and how each unit was found
- the title, subtitle and author it detected
- the paragraph and character styles in use, and the IDML style each one maps to
- direct formatting, with the hotspots listed
- fonts
- Hebrew and Greek
- style conflicts between files
- everything version 1 doesn't carry over: text boxes, shapes, equations, comments, XE fields
  and endnotes

Tracked changes and unusual fields are also listed.

## Profiles

```
python -m docx2idml profile new "Series A"
python -m docx2idml profile show "Series A"
python -m docx2idml profile export "Series A" "Series A.json"
python -m docx2idml profile import "Series A.json"
python -m docx2idml preflight ms-folder --profile "Series A"
```

Profiles are saved in `%APPDATA%\docx-to-idml\profiles` (on Linux and Mac,
`~/.config/docx-to-idml/profiles`).

## Tests

```
python tests/test_reader.py
python tests/test_outline.py
python tests/test_preflight.py    # includes a LibreOffice round trip when soffice is installed
python tests/test_idml_tools.py
python tests/test_writer.py
python tests/test_export.py
python tests/test_layout.py
python tests/test_updates.py
python tests/test_gui.py      # needs a display (xvfb-run on Linux)
```

## Development tools

```
pip install -r requirements-dev.txt      # jing and trang for schema validation (needs Java)
python tools/idml_check.py file.idml      # structure, then Adobe's schema (jing)
python tools/idml_inspect.py file.idml    # masters, pages, overrides, sections, stories, styles
python tools/prepare_schema.py            # rebuild idml-schema/rng after an InDesign update
python tools/make_base.py                 # rebuild the writer's base from reference 01
python tools/make_generated_files.py      # the generator's feature files, reference/generated/
```
