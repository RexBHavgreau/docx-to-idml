# Changelog

## 0.3.1 (not yet released)

- After an update, the new version offers to delete the old copy and to point desktop and
  Start-menu shortcuts and taskbar pins that opened it at itself (as Indicat does). A copy
  you choose to keep isn't asked about again.
- Fixed: the update check at startup ran at most once a day, so a release made after the
  day's check wasn't noticed until the next day (0.2.0 missed 0.3.0). It now checks at every
  start, quietly unless there's a newer version. If you decline a version, the startup check
  doesn't ask about it again; Help > Check for updates always does.

## 0.3.0 (October 22, 2026)

- Endorsements ("Endorsements", "Praise for...", "Advance Praise", "What Others Are Saying",
  and the Spanish "Elogios", "Recomendaciones") are recognized and set first, before the
  half-title, as display pages without folios or running heads.
- Nothing of Word's formatting is carried into the book's styles. Word's paragraph styles
  still say which styles the book needs and what each is (heading, quotation, note...), but
  a custom Word style is now based on the book style for its role without Word's alignment,
  indents, spacing or sizes; change its look in InDesign or with a style template. Fonts not
  set in the profile are book fonts installed on the computer (Minion, Arno, Garamond,
  Caslon, Palatino, Georgia...), never Word's; Hebrew and Greek fonts likewise (SBL Hebrew,
  SBL Greek, Gentium...), when the body font lacks the letters. Italic, bold, small caps
  and Word's character styles in the text are kept, as are centered lines (scene breaks).
- A custom Word style with no book counterpart (a special paragraph the author set up, based
  on Normal) keeps what makes it distinct, in book terms: alignment, indents in proportion
  to the book's line, italic or bold, capitals, and size and spacing in proportion to the
  body size; never Word's fonts. Custom styles based on a heading, quotation or the like
  follow the book style. The Style map tab shows each style's look and can switch it.
- The first text paragraph of a chapter is set flush (Body First) after an epigraph or any
  other opening matter, not only after a heading.
- Body size and leading (Layout profile > Type): a body size (11 pt by default) and leading
  chosen as tight, standard or open, with the suggested range for each shown for the size
  (at 11 pt about 12.5-13, 13.5-14, 14.5-15), shifted for the body font's x-height and the
  line length; an exact leading still wins. The export report says what it used.
- Baseline grid (Layout profile > Type): body text on a grid of the body leading; block
  quotes, notes and captions stay off it.
- The Type tab reads down each column: fonts, size and leading on the left, typographic
  switches on the right.
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
