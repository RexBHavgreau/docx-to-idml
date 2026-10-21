# Changelog

## 0.2.0 (October 21, 2026)

- Fonts are chosen from dropdowns of the fonts installed on the computer (you can still type a
  name, or leave the box blank to use Word's). The Hebrew and Greek lists show only fonts that
  have Hebrew or Greek letters.
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
