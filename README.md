# docx-to-idml (working name)

Turns a Word book manuscript (one .docx or several) into an IDML file that opens in InDesign,
Affinity or DesignCraft with most of the book already laid out: page geometry, masters, styles,
front matter, running heads and pagination. The plan is in [PLAN.md](PLAN.md).

**Status:** step 0 of the build order. Preflight works: it reads the manuscript and reports what
it holds. It doesn't write IDML yet.

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
