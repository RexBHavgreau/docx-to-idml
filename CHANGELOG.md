# Changelog

## 0.6.0 (not yet released)

- Book Details is now a bibliographic record for the book (modelled on Zotero's Book item):
  title, subtitle, short title; contributors; series and number in the series, volume and
  number of volumes, edition, publisher, place, copyright year and holder, ISBNs, call number
  (blank: no line), credits, printed in. Contributors are a list in title-page order, each an
  author, editor, translator, writer of the foreword, afterword, preface or introduction,
  contributor or series editor (Add, Change, Remove, Move up, Move down). The title page has
  a byline per role in that order: the authors' names, "Edited by ...", "Translated by ...",
  "With a foreword by ..." (afterword, preface, introduction likewise; Chicago style: "A, B,
  and C"); a unit titled "Foreword by ..." in the manuscript fills that role; the wording comes from the
  book's language (English, and Spanish, so other languages can be added). The copyright
  holder and the "author" running head use the authors, else the editors. The series goes on
  the half-title, the volume ("Volume 2 of 3") on the title page, the call number on the
  copyright page. "Fill from the manuscript" fills the contributors (editors from a copyright
  page's "Edited by" line). Saved books are upgraded: the old Author field becomes an author.
  The tab is in sections: Title, Contributors, Pages, Publication.
- Headings set by formatting: a manuscript without heading styles (headings made bigger,
  bold, centered or in capitals by hand) has its headings found by their look. Paragraphs
  that look alike form a group ("[16 pt bold centered]", "[bold]"...), ranked by prominence:
  the strongest becomes chapter titles, the next Heading A, and so on. Groups show in the
  Style Map tab, marked as guessed, to confirm or change; changes are saved with the book.
  The bold or size that made a paragraph a heading is left to the heading style. Bold lines
  in the text, italic titles of works, title-page lines and a typed contents' title are not
  taken for headings. Only what the styles don't give is guessed: a manuscript with heading
  styles is read by its styles as before. Preflight says when headings were found this way.
  Levels are ranked across the whole book, so a look means the same level in every file. In a
  book sent as several files, each file's most prominent opening line is its title (PREFACE,
  Contributors, Foreword by...), and a line of names under a chapter title is its author line.
- Front matter sent as files: a file of copyright lines (a copyright notice, "All rights
  reserved", an ISBN) is used as the book's copyright page instead of a generated one, so its
  information isn't duplicated; its "Edited by ..." line gives the editors, and its other
  lines fill the empty Book Details fields: copyright year and holder, publisher, web
  address, ISBNs (print and ebook by their labels), "Printed in ...", the edition line.
  Copyright lines on a manuscript's title page are read the same way. Permissions for Bible
  versions ("Copyright \u00a9 1982 by Thomas Nelson") are passed over.
  The book's title, when it opens several files, is taken as the title and left out where it
  repeats at the top of a file. A file whose first line isn't a title (an abbreviations
  list) is titled from its file name ("00.5 Abbreviations" -> Abbreviations). "Foreword by
  ..." and "Contributors" are recognized as front matter.
- Fixed: Hebrew inside italic text was set upright: the Hebrew style fixed the face. It now
  takes the face of the text around it (italic in italic text, bold in a bold heading), by the
  Hebrew font's own name for that face (the Culmus fonts call theirs "Medium" and "Medium
  Oblique"). If the Hebrew font has no such face, the Hebrew is set upright and the report
  says so.
- Running heads with Hebrew or Greek: a running head taken from the chapter title can use
  only one font. When a head has Hebrew or Greek and the running-head font lacks those
  letters (or isn't installed, so it can't be checked), the report says so: choose a font that
  has them, or turn on the new "Separate masters for heads with Hebrew or Greek" (Running
  Heads > Running Head Style), which gives each such chapter a master of its own (R1-Body...)
  with the head as text in the Hebrew or Greek font. Off by default. Profile version 7.
- Page Margins: the line length field says it's a multiple of the type size, and shows what
  that comes to in inches and picas (30 at 11 pt: 4.58 in, 27.5 picas); the note under the
  margins gives it too, with the characters per line.

## 0.5.0 (October 23, 2026)

- The Style Map tab is now the one view of every style found in the manuscript, with the
  IDML style, role and look of each as dropdowns (it replaces the list with a dialog per
  style and the separate window). "Apply the mapping" reads the manuscript again with it;
  changes not yet applied are still used by the export. The tab is shown after the
  manuscript is first read. The manuscript's own contents (Word's TOC styles) isn't listed:
  a new contents replaces it.
- Tabs are in title case (Book Details, Running Heads, Layout Profile, Style Map; Page
  Layout, Notes and Contents).
- The Page Layout tab (was Page) is in three sections: Page Size, Page Organization and Page
  Margins.
- Narrower default margins: the line length is now about 30 times the type size (Bringhurst;
  a setting in Page Margins, 20–40), kept between 45 and 80 characters, instead of 65
  characters. At 11 pt on 6 x 9 the margins are about 0.82 in inside, 0.6 in outside and top,
  0.76 in bottom, and lines run about 71 characters. The outside margin is never wider than
  the inside unless you set it so.
- The running heads' style can be set in the Running Heads tab: small caps, all caps or as
  typed; italic; size; letter-spacing; font.
- Profile version 6 (line length, running-head style); saved profiles are upgraded. Two
  settings that did nothing are dropped (OpenType small caps; endnotes: "ask").
- Preflight reports tables inside tables: their text is kept in the outer table's cell, but
  the inner table's rows and columns are not (they went unreported before).
- Housekeeping: unused code removed; the reference folder keeps only what the tests and tools
  use (the InDesign files, PDFs and footnote experiments are in the history).
- Fixed: when a chapter ran longer than estimated, InDesign added one page, which pushed
  the next chapter's opening page (B-Opener) onto a left-hand page; the chapter title then
  jumped to the following right-hand page, which had the A-Body master. InDesign now adds
  pages two at a time (Smart Text Reflow's "Preserve Facing-Page Spreads"), so openers stay
  on right-hand pages with their master.
- Fixed: Hebrew and Greek in text the program writes itself (the book's title on the
  half-title and title pages, the title or author in a running head, a part's title) were set
  in the style's own font. They now get the Hebrew and Greek styles and fonts, as in the
  manuscript's text, and a line with Hebrew uses the World-Ready composer. Running heads taken
  from the chapter title can't change font partway; when one has Hebrew or Greek, the report
  says so (give the chapter a short title in the Running heads tab).
- Fonts whose normal face isn't called "Regular" (the Culmus Hebrew fonts such as Taamey
  David CLM call it "Medium") are asked for by the face's own name, so InDesign doesn't report
  a missing font.
- A paper's cover page (from a real manuscript): a line or two above the title, such as a
  school's name, is now part of the title page rather than a page of endorsements (text above
  the title still counts as endorsements when it runs to sentences or is a quotation); a Word
  style named "Author" (or "Autor") gives the author; a bare "by" line and the title of a
  typed contents are left out with the contents. Other lines of the manuscript's title page
  (a school, a place, a date) are left out too, and listed in the report; anything that
  belongs in the book goes in Book details.

## 0.4.0 (October 22, 2026)

- Style mapping in one window (as InDesign's style mapping when placing a Word file): after
  the automatic mapping, every paragraph and character style found in the manuscript is
  listed with how often it's used and the IDML style it becomes. Choose another book style,
  keep the style under its own name, or leave its paragraphs out; for paragraph styles also
  the role (heading, quotation, note...) and the look. Styles the program had to guess are
  marked ⚠. It opens the first time a set of files is read, and from "Map styles..." (Files
  tab) or the Style map tab. "Back to the automatic mapping" forgets the choices. Choices
  are saved in the profile.
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

## 0.2.0 (October 21, 2026)

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
