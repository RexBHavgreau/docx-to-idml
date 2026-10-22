# Changelog

## 0.3.0 (not yet released)

- Endorsements ("Endorsements", "Praise for...", "Advance Praise", "What Others Are Saying",
  and the Spanish "Elogios", "Recomendaciones") are recognized and set first, before the
  half-title, as display pages without folios or running heads.
- Text before the title page (endorsements, which seldom have a heading) is set as
  endorsements, before the half-title; so is a file of it placed before the title-page file.
- Layout profile > Page: each margin field shows the margin the export would calculate (for
  the trim, the body font and the book's page count, once preflight has run), with a button
  to fill them in. Blank fields keep following the page count; typed values are fixed. The
  Page tab is now one column, so the margins read together.
- Running heads tab: double-click a unit's kind to change what it is (chapter, part, front
  matter, back matter, display page, endorsements); the choice is saved with the book.
- Book details: "Fill from the manuscript" is at the top of the tab, and after filling it says
  where each value was found (which style in which file, or the title page's "by" line), or
  that it wasn't found.

## 0.2.0 (October 21, 2026, released)

- Fonts are chosen from dropdowns of the fonts installed on the computer (you can still type a
  name, or leave the box blank to use Word's). The Hebrew and Greek lists show only fonts that
  have Hebrew or Greek letters.
- Styles from an IDML file (Layout profile > Type): the template's paragraph and character
  styles replace the tool's of the same name, and its other styles are added. Settings that
  point at things the export doesn't carry (most colour swatches, lists, nested and GREP
  styles) are left out and listed in the report.
- Spare pages after each chapter are a setting: none (the default), one, or two.
- Chapter titles are set to start on the next odd page (the next page when chapters open on
  the next page), so the rule holds if chapters are joined into one story in InDesign.
- Fixed: Hebrew could come out reversed in InDesign: the styles used the Adobe Paragraph
  Composer. They now use the World-Ready Composer (the same paragraph composer, with
  right-to-left support), so Hebrew sets right everywhere, including Hebrew added later in
  InDesign. The profile's single-line option is ignored when the book has Hebrew.
- Fixed: after a bibliography, the rest of the book was set in the Bibliography style.
  Bibliography styling now runs from a heading titled Bibliography (Works Cited, References...)
  at any level to the next heading of the same or higher level, so a bibliography can end a
  chapter. A file whose text starts before its first chapter heading (an article with a title
  line, headings or a page or more of text) is a unit of its own, not added to the previous
  file's last unit; a title line opening a chapter is set as its Chapter Title.
- Fixed: italics in footnotes were lost (the footnote settings written on each note run
  overrode the Italic style), and so were the Greek and Hebrew fonts inside notes.

## 0.1.0 (October 21, 2026)

First version with a window and an .exe.

- The window: files in book order (add, drop, move, sort), book details for the title and
  copyright pages, running heads with short titles, the layout profile, the style map,
  preflight and export.
- Export to IDML (InDesign, Affinity): styles, character formatting, footnotes, Hebrew and
  Greek, tables, images, margins and measure, masters, roman and arabic page numbers, recto
  rules, half-title, title, copyright and reserved contents pages, running heads, widow,
  orphan and short-last-line control.
- Update check at startup (once a day, can be turned off) and in the Help menu; the new
  version is saved beside the running one.
