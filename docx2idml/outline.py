"""The book's outline, built across all input files: front matter, parts, chapters, back matter.

Headings are found in each file by the first of these that finds any (in order of trust):
1. the style map (styles whose role is chapter or part, including custom styles based on them
   or given outline level 1);
2. Word's own running heads: the style a STYLEREF field in a header points to;
3. paragraphs given outline level 1 directly;
4. section breaks (the first line after each page break of a section is the title);
5. the whole file as one unit, titled by its first line.
Units are then classified by title (Preface, Bibliography, Part II...) in English and Spanish.
The manuscript doesn't need running heads set up in Word.
"""

import re
import unicodedata
from dataclasses import dataclass, field

from .stylemap import StyleMap, norm

# Normalized title -> (kind, type). "display" pages carry no folio.
_FRONT = {
    "dedication": ("display", "dedication"), "dedicatoria": ("display", "dedication"),
    "epigraph": ("display", "epigraph"), "epígrafe": ("display", "epigraph"),
    "copyright": ("display", "copyright"),
    "contents": ("front", "contents"), "table of contents": ("front", "contents"),
    "contenido": ("front", "contents"), "contenidos": ("front", "contents"),
    "índice general": ("front", "contents"), "tabla de contenido": ("front", "contents"),
    "foreword": ("front", "foreword"), "prólogo": ("front", "foreword"),
    "presentación": ("front", "foreword"),
    "preface": ("front", "preface"), "prefacio": ("front", "preface"),
    "acknowledgments": ("front", "acknowledgments"), "acknowledgements": ("front", "acknowledgments"),
    "agradecimientos": ("front", "acknowledgments"),
    "abbreviations": ("front", "abbreviations"), "abreviaturas": ("front", "abbreviations"),
    "siglas y abreviaturas": ("front", "abbreviations"),
    "list of illustrations": ("front", "illustrations"), "list of figures": ("front", "illustrations"),
    "list of tables": ("front", "tables"),
}
_BACK = {
    "bibliography": "bibliography", "select bibliography": "bibliography",
    "works cited": "bibliography", "references": "bibliography", "bibliografía": "bibliography",
    "obras citadas": "bibliography", "referencias": "bibliography",
    "glossary": "glossary", "glosario": "glossary",
    "notes": "notes", "notas": "notes",
    "afterword": "afterword", "epílogo": "afterword",
    "index": "index", "subject index": "index", "scripture index": "index",
    "author index": "index", "index of ancient sources": "index", "índice analítico": "index",
    "índice de autores": "index", "índice de citas": "index", "índice onomástico": "index",
    "about the author": "about", "sobre el autor": "about", "acerca del autor": "about",
}
_APPENDIX = re.compile(r"^(appendix|appendices|apéndice|apéndices|anexo)\b")
_PART = re.compile(r"^(part|parte|book|libro)\s+(\S+)")
_PART_WORDS = {"one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
               "first", "second", "third", "fourth", "fifth", "uno", "dos", "tres", "cuatro",
               "cinco", "primera", "segunda", "tercera", "cuarta", "quinta", "i", "ii", "iii",
               "iv", "v", "vi", "vii", "viii", "ix", "x"}
_BY = re.compile(r"^(by|por)\s+(.+)$", re.I)


def title_key(text):
    """A title for matching: lower case, no trailing punctuation or numbers ("Notes:", "PREFACE")."""
    s = " ".join(text.split()).casefold()
    s = re.sub(r"[\s.:;,\-–—]+$", "", s)
    return unicodedata.normalize("NFC", s)


def classify(title, chapter_seen):
    """(kind, type) for a chapter-level heading."""
    key = title_key(title)
    if key in _FRONT and not chapter_seen:
        return _FRONT[key]
    if key == "índice":   # Spanish: the contents at the front, an index at the back
        return ("back", "index") if chapter_seen else ("front", "contents")
    if key in _BACK:
        return ("back", _BACK[key])
    if _APPENDIX.match(key):
        return ("back", "appendix")
    m = _PART.match(key)
    if m and (m.group(2).strip(".:") in _PART_WORDS or m.group(2).strip(".:").isdigit()):
        return ("part", "part")
    return ("chapter", "chapter")


@dataclass
class Unit:
    kind: str           # display, front, part, chapter, back
    type: str           # preface, contents, chapter, part, bibliography, opening...
    title: str
    file: str
    start: int          # body paragraph index of the heading in its file
    detected_by: str
    words: int = 0
    note_refs: int = 0
    endnote_refs: int = 0
    subheads: list = field(default_factory=list)   # first-level section titles
    page_break_before: bool = True   # starts at a section break or at the top of a file


@dataclass
class Outline:
    units: list = field(default_factory=list)
    title: str = None
    title_source: str = None
    subtitle: str = None
    author: str = None
    author_source: str = None
    file_creator: str = None        # docProps creator: usually whoever made the file
    copyright_found: bool = False
    toc_field: bool = False         # a Word contents field (it will be replaced)
    notes: list = field(default_factory=list)
    first_heading: dict = field(default_factory=dict)   # file name -> first heading text

    @property
    def words(self):
        return sum(u.words for u in self.units)

    def present(self):
        types = {u.type for u in self.units}
        if self.title:
            types.add("title page")
        if self.copyright_found:
            types.add("copyright")
        if self.toc_field:
            types.add("contents")
        return types


def plural(n, word, words=None):
    return "%d %s" % (n, word if n == 1 else (words or word + "s"))


def _word_count(text):
    return len(text.split())


class _FileOutline:
    def __init__(self, doc, sm):
        self.doc, self.sm = doc, sm
        self.maps = {}
        self.paras = [p for p in doc.paragraphs]

    def mapping(self, p):
        sid = self.doc.para_style(p)
        if sid not in self.maps:
            self.maps[sid] = self.sm.paragraph_style(self.doc, sid)
        return self.maps[sid]

    def usable(self, p):
        return not p.in_table and not p.in_toc_field and \
            self.mapping(p).role not in ("toc", "toc_title", "skip")

    def heads(self):
        """[(paragraph index, role, detected_by)] by the first method that finds any."""
        doc = self.doc
        found = []
        for p in self.paras:
            m = self.mapping(p)
            if self.usable(p) and m.role in ("chapter", "part") and p.text.strip():
                by = "style %s" % m.word if m.source in ("default", "profile") else \
                    "style %s (%s)" % (m.word, m.source)
                found.append((p.index, m.role, by))
        if found:
            return found
        for ref in doc.styleref:
            if ref.isdigit():
                ids = {sid for sid, st in doc.styles.items()
                       if norm(st.name) == "heading %s" % ref}
            else:
                ids = {sid for sid, st in doc.styles.items()
                       if norm(st.name) == norm(ref) or sid == ref}
            found = [(p.index, "chapter", 'Word running head (STYLEREF "%s")' % ref)
                     for p in self.paras
                     if self.usable(p) and doc.para_style(p) in ids and p.text.strip()]
            if found:
                return found
        found = [(p.index, "chapter", "outline level 1") for p in self.paras
                 if self.usable(p) and p.outline_level == 0 and p.text.strip()]
        if found:
            return found
        starts = [0]
        for p in self.paras:
            if p.ends_section and p.section + 1 < len(doc.sections) and \
                    doc.sections[p.section + 1].break_type != "continuous":
                starts.append(p.index + 1)
        by = "section break" if len(starts) > 1 else "whole file"
        for s in starts:
            for p in self.paras[s:]:
                if p.text.strip() and self.usable(p):
                    if not found or found[-1][0] != p.index:
                        found.append((p.index, "chapter", by))
                    break
        if by == "section break" and found:
            found[0] = (found[0][0], "chapter", "section break (start of file)")
        return found

    def page_break_before(self, index):
        if index == 0 or not any(p.text.strip() for p in self.paras[:index]):
            return True
        prev = self.paras[index - 1]
        if prev.ends_section and prev.section + 1 < len(self.doc.sections):
            return self.doc.sections[prev.section + 1].break_type != "continuous"
        return False


def build_outline(docs, stylemap=None):
    sm = stylemap or StyleMap()
    out = Outline()
    chapter_seen = False
    for doc in docs:
        fo = _FileOutline(doc, sm)
        heads = fo.heads()
        if any(f.code == "TOC" for f in doc.fields):
            out.toc_field = True
        if heads:
            out.first_heading[doc.name] = fo.paras[heads[0][0]].text.strip()
        if doc.core.get("creator") and not out.file_creator:
            out.file_creator = doc.core["creator"]

        # Title material anywhere before the first chapter.
        for p in fo.paras:
            m = fo.mapping(p)
            text = " ".join(p.text.split())
            if not text:
                continue
            if m.role == "book_title" and not out.title:
                out.title, out.title_source = text, "style %s in %s" % (m.word, doc.name)
            elif m.role == "subtitle" and not out.subtitle:
                out.subtitle = text
            elif m.role == "author" and not out.author:
                out.author, out.author_source = text, "style %s in %s" % (m.word, doc.name)

        boundaries = [h[0] for h in heads] + [len(fo.paras)]
        lead = fo.paras[:boundaries[0]]
        lead_text = [p for p in lead if p.text.strip() and fo.usable(p)]
        if lead_text:
            if not out.units:
                is_title = any(fo.mapping(p).role in ("book_title", "subtitle") for p in lead)
                unit = Unit("display", "title page" if is_title else "opening",
                            "(title page)" if is_title else "(text before the first heading)",
                            doc.name, 0, "start of book")
                out.units.append(unit)
                _fill(unit, fo, lead)
                _scan_opening(out, lead)
            else:
                prev = out.units[-1]
                _fill(prev, fo, lead)
                out.notes.append("%s starts with %s of text before its first heading; %s "
                                 "kept with the previous unit (\"%s\")."
                                 % (doc.name, plural(len(lead_text), "paragraph"),
                                    "it is" if len(lead_text) == 1 else "they are", prev.title))
        if not heads:
            continue
        for i, (idx, role, by) in enumerate(heads):
            title = " ".join(fo.paras[idx].text.split())
            if role == "part":
                kind, typ = "part", "part"
            else:
                kind, typ = classify(title, chapter_seen)
            if kind == "chapter":
                chapter_seen = True
            unit = Unit(kind, typ, title, doc.name, idx, by,
                        page_break_before=fo.page_break_before(idx))
            body = fo.paras[idx:boundaries[i + 1]]
            _fill(unit, fo, body)
            if kind == "display" or (kind == "front" and not out.units):
                _scan_opening(out, body)
            out.units.append(unit)
    if not out.title:
        for doc in docs:
            if doc.core.get("title"):
                out.title, out.title_source = doc.core["title"], \
                    "document properties of %s (check it)" % doc.name
                break
    _check_outline(out)
    return out


def _fill(unit, fo, paras):
    for p in paras:
        if p.in_toc_field or fo.mapping(p).role in ("toc", "toc_title", "skip"):
            continue
        unit.words += _word_count(p.text)
        unit.note_refs += p.footnotes
        unit.endnote_refs += p.endnotes
        m = fo.mapping(p)
        if m.role == "heading" and m.level == 1 and p.text.strip():
            unit.subheads.append(" ".join(p.text.split()))


def _scan_opening(out, paras):
    for p in paras:
        text = " ".join(p.text.split())
        if not text:
            continue
        if "©" in text or re.match(r"^copyright\b", text, re.I) or "derechos reservados" in text.lower():
            out.copyright_found = True
        m = _BY.match(text)
        if m and not out.author and len(text) < 80:
            out.author, out.author_source = m.group(2).strip(), "title page text"


def _check_outline(out):
    chapters = [u for u in out.units if u.kind == "chapter"]
    if not chapters:
        out.notes.append("No chapters were found. Check the style map: the style used for "
                         "chapter titles should have the role \"chapter\".")
    by = {u.detected_by.split(" (")[0] for u in out.units if u.kind != "display"}
    if any(b.startswith(("section break", "whole file")) for b in by):
        out.notes.append("Some files have no recognized headings; their units were found by "
                         "section breaks or taken as whole files. Map the chapter-title style "
                         "to make this reliable.")
    titles = {}
    for u in chapters:
        titles.setdefault(title_key(u.title), []).append(u)
    for key, us in titles.items():
        if len(us) > 1:
            out.notes.append('"%s" is the title of %d chapters; running heads will repeat.'
                             % (us[0].title, len(us)))
