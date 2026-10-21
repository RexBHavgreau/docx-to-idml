# Reference files (build steps 1 and 2)

One small InDesign file per feature the converter needs. Each is the **reference**: what
InDesign itself writes in IDML for that feature. Opening the reference IDML in Affinity and
DesignCraft answers "does the program support this at all?"; later the generator's own file for
the same feature is compared against it.

## Making them

1. Copy `make_reference_files.jsx` into InDesign's Scripts folder: in InDesign, Window >
   Utilities > Scripts, right-click **User**, choose **Reveal in Explorer**, and copy the file
   there.
2. Double-click it in the Scripts panel and choose an empty folder.
3. For each file it saves `NN-name.indd`, `NN-name.idml` and `NN-name (InDesign).pdf`
   (spreads), plus `images/sample.jpg` and `reference-log.txt`.

The script only creates new documents. It uses Arno Pro if installed (else Minion Pro, Adobe
Garamond Pro, Times New Roman), Taamey David CLM for Hebrew, and logs which fonts it used.
`reference-log.txt` lists every file as OK or FAILED and anything it could not set. **Send me
that log**; the script has been checked for errors only outside InDesign, so a first run may
need a fix.

**Rerunning some files:** the script's `ONLY` list (near the end) names the files to build;
leave it empty (`[]`) to build all. Version 2 is set to rebuild only 05 and 06, the two that
failed in the first run.

Look over each file in InDesign before going on. If one isn't right, fix it by hand, save,
and export the IDML again (File > Export > InDesign Markup).

| File | What it shows |
|---|---|
| 01-footnotes | Footnotes using a "Footnote Reference" character style (not local superscript), numbering restarting with each section, one long note split across pages |
| 02-section-marker-heads | Recto running heads from section markers (three sections, one title too long), verso heads as static text; page numbers continuing |
| 03-section-numbering | Front matter in roman from i, chapter 1 in arabic from 1; display pages (D master) with no folio; blank versos (E master) |
| 04-parent-child-masters | B-Opener based on A-Body: running heads removed and folio dropped to the foot |
| 05-primary-text-frame | A document made with "Primary Text Frame": page frames overridden from the master frame and threaded; smart text reflow on. The log says whether InDesign added pages |
| 06-toc | TOC style with two levels, a dot-leader tab, bold level 1; generated contents on page 1 |
| 07-table | Table, cell and paragraph styles; 40 rows with the header row repeating on each page; two merged cells |
| 08-opentype | Ligatures, old-style vs lining figures, small caps and all small caps, fractions, ordinals, single-line vs paragraph composer, hyphenation, optical margin alignment, a balanced heading |
| 09-baseline-grid | Baseline grid; body and headings aligned to it; a heading with half a line before; a block quote off the grid |
| 10-hebrew-greek | Pointed and cantillated Hebrew inline (World-Ready and Paragraph composers) and as a right-to-left paragraph; polytonic Greek. Direction and language are in the styles this time |
| 11-images | An inline anchored image with a caption (as Word's inline pictures will become), and a free image with a text wrap |
| 12-character-styles | Character styles that set only one thing (italic, bold, small caps, superscript, underline, no break) inside different paragraph styles; one local italic override |
| 13-chapter-stories | One story per chapter on B-Opener pages; chapter one overset; a blank verso with no master; chapter two still starts on its own page |

Already covered by the Assumption article tests (October 21): section-marker heads (kept),
InDesign text variables (lost), dropped folios and blank versos (kept), footnotes kept whole
in Affinity, linked image with wrap (kept), table (kept), TOC losing bold and tab position.
These files repeat some of that on purpose, one feature per file, so each result is clear.

## Checking them in Affinity (step 2)

Open each `.idml` in Affinity. Export a PDF of spreads named `NN-name (Affinity).pdf`. Compare it
with the InDesign PDF. Note what the PDF can't show (a field still live or turned into text,
masters still linked, styles still applied). Fill in the table below and send it back; it
becomes the compatibility table in PLAN.md.

Affinity version: ________   InDesign version: ________   Date: ________

Result: **works**, **partly** (say what differs) or **lost**.

| File | What to check in Affinity | Result | Notes |
|---|---|---|---|
| 01-footnotes | Notes at the page foot; numbers restart at 1 in chapter two; the long note splits (or is kept whole); marker style still "Footnote Reference" | | |
| 02-section-marker-heads | Recto heads change with each section; the long title; Affinity's Section Name field | | |
| 03-section-numbering | Folio on the contents page reads "v"; chapter one reads "1"; no folio on display pages | | |
| 04-parent-child-masters | B-Opener still based on A-Body (Master panel); no heads on opener pages; folio at the foot | | |
| 05-primary-text-frame | Pages and threading kept; text flows on when more is added (does Affinity add pages?) | | |
| 06-toc | Entries, bold, dot leader and page numbers at the tab; can the TOC be updated in Affinity? | | |
| 07-table | Styles; header row repeats on page 2; merged cells | | |
| 08-opentype | Each feature in turn: ligatures, figures, small caps, fractions, ordinals, hyphenation, optical margins, balanced heading | | |
| 09-baseline-grid | Grid shown at the same place; text on the grid; the off-grid block quote | | |
| 10-hebrew-greek | Expect Hebrew to fail (letters reversed). Check that Greek is kept and the English around the Hebrew is not disturbed | | |
| 11-images | Inline image stays anchored and moves with the text; caption; wrap on the free image | | |
| 12-character-styles | Each styled word keeps the paragraph's font and size and changes only its own attribute | | |
| 13-chapter-stories | Overset in chapter one reported; chapter two on its own page; blank verso kept | | |

DesignCraft is checked later by script (its CLI exports each page as PNG).

## Keeping them

Put the `.idml` files (and `images/`) in `reference/idml/` in this repository. They are the
standard the generator is compared against. Check each one with
`python tools/idml_check.py reference/idml/*.idml` (structure and Adobe's schema), and
summarize one with `python tools/idml_inspect.py`. The `.indd` and PDFs can stay on your machine.
