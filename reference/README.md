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
| 01-footnotes | Notes at the page foot; numbers restart at 1 in chapter two; the long note splits (or is kept whole); marker style still "Footnote Reference" | Yes. Notes at the page foot. Footnotes have no paragraph style in Affinity. Numbering restarts at the next chapter. | Long note splits (but I think this is a setting in Affinity).|
| 02-section-marker-heads | Recto heads change with each section; the long title; Affinity's Section Name field | Works. | But note that chapter opening pages should have no headings. If those were only set for test purposes, that is fine, but only regular pages in the chapter should have running headers. |
| 03-section-numbering | Folio on the contents page reads "v"; chapter one reads "1"; no folio on display pages | Correct. | On this one, the pages are a bit scattered in the layout relative to one another. The internal content is fair, though. |
| 04-parent-child-masters | B-Opener still based on A-Body (Master panel); no heads on opener pages; folio at the foot | Correct. Though a blank page should have no text content, neither a page number nor a header. | |
| 05-primary-text-frame | Pages and threading kept; text flows on when more is added (does Affinity add pages?) | No. | Affinity does not automatically add pages, even in native Affinity files. But output is identical to the InDesign output, at least superficially.|
| 06-toc | Entries, bold, dot leader and page numbers at the tab; can the TOC be updated in Affinity? | Formatting is inconsistent, and page numbers inexact or missing. Dot leader appears with number. Cannot be updated, only replaced using styles, but no hierarchy via indents appears; all headings appear at the same level in the TOC. | |
| 07-table | Styles; header row repeats on page 2; merged cells | No header, but maybe I don't know what you mean. Merged cells are there. | |
| 08-opentype | Each feature in turn: ligatures, figures, small caps, fractions, ordinals, hyphenation, optical margins, balanced heading | Works. | |
| 09-baseline-grid | Grid shown at the same place; text on the grid; the off-grid block quote | Correct. | |
| 10-hebrew-greek | Expect Hebrew to fail (letters reversed). Check that Greek is kept and the English around the Hebrew is not disturbed | Hebrew fails as expected. | This is Affinity's fault, not the converter's. |
| 11-images | Inline image stays anchored and moves with the text; caption; wrap on the free image | All correct. | |
| 12-character-styles | Each styled word keeps the paragraph's font and size and changes only its own attribute | Looks right. | |
| 13-chapter-stories | Overset in chapter one reported; chapter two on its own page; blank verso kept | Yes. | |

DesignCraft is checked later by script (its CLI exports each page as PNG).

## Keeping them

Put the `.idml` files (and `images/`) in `reference/idml/` in this repository. They are the
standard the generator is compared against. Check each one with
`python tools/idml_check.py reference/idml/*.idml` (structure and Adobe's schema), and
summarize one with `python tools/idml_inspect.py`. The `.indd` and PDFs can stay on your machine.

## Footnote variants (October 21)

Affinity mishandles the footnotes in 01 even though the IDML is clean: body text after a
callout shows "Footnote Reference", note 1 loses its formatting at the italic, and later notes
lose the Footnote style. To find the structure Affinity reads correctly,
`python tools/make_footnote_variants.py` makes fifteen variants of 01 in `reference/variants/`,
each changing one thing (all pass the schema):

| File | What changes | Affinity: body text after callouts plain? | Note 1 right through the italic? | Notes 2-3 keep Footnote style or look right? | Notes |
|---|---|---|---|---|---|
| fn-0-base | Nothing (01 as InDesign wrote it) | | | | |
| fn-a-plain-callout | Callout runs have no character style; the marker style is left to the footnote options | | | | |
| fn-b-local-superscript | Callouts plain with local superscript; no marker style in the options (the Assumption article's pattern) | | | | |
| fn-c-note-formatting | Note text also carries the Footnote style's settings (size, indent, font) directly | | | **Formatting kept; only note 1 keeps the style name "Footnote"** | |
| fn-d-note-local-italic | Italic inside notes as local formatting, not the Italic style | | | | |
| fn-e-all | b + c + d together | | | **Formatting kept; only note 1 keeps the style name "Footnote"** | |
| fn-f-note-break | Each note paragraph ends with a paragraph break (InDesign writes none) | | | | |
| fn-g-renamed-styles | Note styles renamed "Note Text" and "Note Callout" (in case Affinity's own "Footnote" style takes over) | | | | |
| fn-h-renamed-break | f + g together | | | | |
| fn-i-split-number | The footnote number and separator in a text run of their own, so every note has at least two runs | | | | |
| fn-j-split-plain-callout | i + callout runs with no character style | | | | |
| fn-k-split-no-italic | i, with no character style anywhere in the notes (note 1's italic made plain) | | | | |
| fn-l-split-local-italic | i, with italic in notes as local formatting instead of the Italic style | | | | |
| fn-m-split-formatting | i, plus the Footnote style's font, size, leading and indent written directly on all note text | | | | |
| fn-n-split-root-arno10 | Diagnostic: i, with the root style "[No paragraph style]" changed from Minion Pro 12 pt to Arno Pro 10 pt | | | | |

For each: open in Affinity, click into the body text after the first callout and look at the
character style; click into notes 1, 2 and 3 and look at the paragraph style and size (9 pt);
check that the callout numbers are superscript and the notes still restart at 1 in chapter two.

**Finding (October 21):** in both 01 and the Assumption article, Affinity read a note as a proper
footnote (settings available, style applied) only when the note's text had two or more text
runs (e.g. it contained italic); notes written as a single run were broken. fn-i and fn-j test
the workaround: the number in its own run. Check every note: settings available, Footnote style
shown, and a change to the document-wide footnote style reaching all notes.

**Result (October 21):** fn-m (number in its own run, Footnote settings also written on the note
text) works in Affinity and InDesign, and editing the Footnote style reaches every note in both.
The generator writes footnotes that way. fn-n confirmed the cause of the rest: Affinity lays the
root style `[No paragraph style]` over note text.

### Footnote rule and spacing

| File | Settings | InDesign | Affinity |
|---|---|---|---|
| fn-o-rule-spaced | Rule above the notes and above continued notes; 12 pt above the notes; first baseline at least 16 pt below the rule | Works | Works |
| fn-p-space-only | No rules; 12 pt between body text and notes | Works | Works |
| fn-q-continuation-rule | Rule only above the note continued onto page 2; 12 pt above the notes | Works | Works |

Both rules are now 1 inch (the continuation rule was first the full text width).

Check: the space between body text and rule (or notes), the space between rule and note text,
whether the continuation rule appears only on page 2 (the long note 3 runs over), and whether
Affinity shows the same.
