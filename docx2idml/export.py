"""The exporter core (build step 4): Word manuscript -> the IDML model -> an export folder.

    files -> docx_reader (styles, outline) + content (text) -> Document -> writer.export_book

What it does now:
- Styles: a book set (Body, Body First, Chapter Title, Heading A-C, Block Quote, Footnote...)
  with the profile's fonts, falling back to Word's; custom Word styles kept under their own
  names, based on their role's style, carrying what Word sets on them (alignment, indents,
  spacing, italic/bold, size relative to the body).
- Text: italic, bold, small caps, capitals, superscript, subscript, underline and strikethrough
  become character styles (Italic, Bold, Small Caps...), so they survive a change of font;
  Word's own character styles are mapped by the style map. Other direct formatting (fonts,
  sizes, colours) gives way to the book's styles; preflight lists it.
- Hebrew and Greek runs are found by Unicode range and put in "Hebrew" and "Greek" character
  styles (font, language, right-to-left for Hebrew); paragraphs with Hebrew get the World-Ready
  composer.
- Footnotes as decided (fn-m, in the writer); endnotes are converted to footnotes.
- Tables (Book Table style; header rows; merged cells across), images (JPEG, PNG; others are
  listed and left as a placeholder line), list and heading numbers as static text.
- One story per unit of the outline, each on new pages, in one section per unit so footnote
  numbers restart per chapter. Pages are a rough estimate with a page to spare; trim, margins,
  masters and recto rules are step 5, running heads and front matter step 6.
"""

import math
from dataclasses import dataclass
import os
import shutil
import tempfile

from . import fonts, frontmatter, layout
from . import profile as profiles
from .content import read_content, save_image
from .docx_reader import is_greek, is_hebrew, read_docx
from .idml.images import image_info
from .idml.model import (CellStyle, Document, Frame, Image, Master, Paragraph, Run, Section,
                         Story, Style, Table, TableStyle, TOCStyle)
from .outline import _BACK, Unit, apply_kinds, build_outline, title_key
from .stylemap import StyleMap, norm
from .template import TemplateError, apply_template, read_template

BLEED = 9                   # 0.125 in, KDP's bleed
TRIMS = {"5x8": (5, 8), "5.25x8": (5.25, 8), "5.5x8.5": (5.5, 8.5), "6x9": (6, 9),
         "7x10": (7, 10), "8.5x11": (8.5, 11), "A5": (5.83, 8.27)}
LANGUAGES = {"en": "$ID/English: USA", "es": "$ID/Spanish: Castilian"}
FONT_STYLES = {(False, False): "Regular", (False, True): "Italic", (True, False): "Bold",
               (True, True): "Bold Italic"}
# Character styles the exporter makes from Word's formatting.
CHAR_STYLES = {
    "Italic": {"FontStyle": "Italic"}, "Bold": {"FontStyle": "Bold"},
    "Bold Italic": {"FontStyle": "Bold Italic"}, "Small Caps": {"Capitalization": "SmallCaps"},
    "All Caps": {"Capitalization": "AllCaps"}, "Superscript": {"Position": "Superscript"},
    "Subscript": {"Position": "Subscript"}, "Underline": {"Underline": True},
    "Strikethrough": {"StrikeThru": True}, "Footnote Reference": {"Position": "Superscript"},
    "Hyperlink": {}, "No Break": {"NoBreak": True},
}
RESET = {"FontStyle": None, "Capitalization": "Normal", "Position": "Normal",
         "Underline": False, "StrikeThru": False}
# Roles whose paragraphs are followed by an unindented first paragraph.
# Styles whose paragraphs are not running text (no runt control), with those based on them.
NO_RUNT_SKIP = {"Chapter Title", "Part Title", "Heading A", "Heading B", "Heading C",
                "Book Title", "Book Subtitle", "Author", "Verse", "Figure", "Table", "Caption",
                "Table Body", "Table Head", "Folio"}
HEAD_ROLES = {"chapter", "part", "heading", "book_title", "subtitle", "author", "toc_title",
              "centered"}
ROLE_BASE = {"body": "Body", "quote": "Block Quote", "verse": "Verse", "list": "List",
             "caption": "Caption", "note": "Footnote", "chapter": "Chapter Title",
             "part": "Part Title", "book_title": "Book Title", "subtitle": "Book Subtitle",
             "author": "Author"}


@dataclass
class Block:
    """One story of the book: a unit of the manuscript or a generated page."""
    unit: object
    paras: list
    opens: str = None             # "recto", "next", or None for the rule by kind
    spare: int = None             # spare pages; None = by kind
    sink: float = None            # None = by kind
    pages: int = None             # fixed page count (reserved contents), else estimated
    valign: str = None            # e.g. "BottomAlign" (copyright page)

    @property
    def kind(self):
        return self.unit.kind if self.unit else "chapter"

    @property
    def title(self):
        return self.unit.title if self.unit else ""


BODY_SIZE = 11


def body_size(profile):
    try:
        size = float(profile.get("body_size") or BODY_SIZE)
    except (TypeError, ValueError):
        return BODY_SIZE
    return size if 6 <= size <= 24 else BODY_SIZE


def leading_for(profile, size=None, x_height=None, cpl=layout.TARGET_CPL):
    """The body leading in points: the profile's value (points, a multiple or a percent), else
    the middle of the suggested range for its feel (tight, standard, open), shifted for the
    font's x-height and the line length."""
    size = size or body_size(profile)
    lead = profile.get("leading") or {}
    v, unit = lead.get("value"), lead.get("unit", "pt")
    if not v:
        feel = lead.get("feel") if lead.get("feel") in layout.LEADING_RATIOS else "standard"
        return layout.leading_suggestions(size, x_height, cpl)[0][feel][2]
    if unit == "multiple":
        return _half(size * v)
    if unit == "percent":
        return _half(size * v / 100)
    return v


def calculated_margins(profile, pages=200, text=None):
    """The margins the export would calculate (before any set in the profile), for showing
    the user: (layout.Geometry, body font found installed?)."""
    page = profile["page"]
    if page.get("trim") == "custom" and page.get("custom_width") and page.get("custom_height"):
        w, h = page["custom_width"], page["custom_height"]
    else:
        w, h = TRIMS.get(page.get("trim"), TRIMS["6x9"])
    found = fonts.find_font((profile.get("fonts") or {}).get("body") or fonts.book_font())
    avg, xh = fonts.FALLBACK_WIDTH, None
    if found:
        try:
            avg = fonts.average_width(found, text)
            xh = fonts.x_height(found)
        except Exception:
            found = None
    size = body_size(profile)
    return layout.geometry(_half(w * 72), _half(h * 72), size,
                           leading_for(profile, size, xh), avg, pages), bool(found)


class ExportError(Exception):
    """Something that stops the export. The message is shown to the user."""


def _half(v):
    return round(v * 2) / 2


def _prop(props, key):
    for part in (props or "").split():
        k, _, v = part.partition("=")
        if k == key:
            return v
    return None


def _toggle(props):
    return props is not None and (props == "on" or _prop(props, "val") not in
                                  ("0", "false", "off", "none"))


def segments(text):
    """Split text into (script, part): script is "hebrew", "greek" or None. Spaces and
    punctuation between two words of the same script stay with them; combining marks go with
    the letter before."""
    out = []
    pending = ""
    for ch in text:
        o = ord(ch)
        if is_hebrew(ch):
            script = "hebrew"
        elif is_greek(ch):
            script = "greek"
        elif 0x0300 <= o <= 0x036F and out and not pending:
            script = out[-1][0]
        elif not ch.isalpha():
            pending += ch
            continue
        else:
            script = None
        if out and out[-1][0] == script:
            out[-1][1] += pending + ch
        else:
            if pending:
                if out and out[-1][0] is None:
                    out[-1][1] += pending
                else:
                    out.append([None, pending])
            if out and out[-1][0] == script:
                out[-1][1] += ch
            else:
                out.append([script, ch])
        pending = ""
    if pending:
        if out and out[-1][0] is None:
            out[-1][1] += pending
        else:
            out.append([None, pending])
    return [tuple(s) for s in out]


class Exporter:
    def __init__(self, paths, profile=None, settings=None):
        """settings: the book's own settings (Book.settings): "front" (book details, see
        frontmatter) and "short_titles" ({unit title: running head})."""
        self.paths = [str(p) for p in paths]
        self.profile = profile or profiles.default_profile()
        self.settings = settings or {}
        self.x_height = None
        self.tpl = None
        path = self.profile.get("styles_template")
        if path:
            try:
                self.tpl = read_template(path)
            except TemplateError as e:
                raise ExportError(str(e)) from None
        self.sm = StyleMap.from_profile(self.profile)
        self.report = []
        self.tmp = None

    # ---- the whole export ----

    def build(self):
        if not self.paths:
            raise ExportError("No .docx files to export.")
        self.docs = [read_docx(p) for p in self.paths]
        self.outline = apply_kinds(build_outline(self.docs, self.sm),
                                   self.settings.get("unit_kinds"))
        self.doc = Document(name=self.outline.title or os.path.splitext(
            os.path.basename(self.paths[0]))[0])
        self.tmp = tempfile.mkdtemp(prefix="docx2idml-")
        self._fonts()
        self._page()
        self._book_styles()
        self._measure_font()
        # Geometry depends on the page count (KDP's gutter steps) and the page count on the
        # geometry: repeat until the count stays in the same step.
        base_report = list(self.report)
        pages = self._first_guess()
        for _ in range(4):
            self.report = list(base_report)
            self._geometry(pages)
            self.used_char, self.custom = {}, {}
            self._book_styles()
            stories = self._stories()
            new = self._paginate(self._front_matter(stories))
            if layout.kdp_band(new) == layout.kdp_band(pages):
                break
            pages = new
        self.report += self.geo.notes + layout.page_count_notes(self.doc.page_count)
        self._finish_styles()
        return self.doc

    def cleanup(self):
        if self.tmp:
            shutil.rmtree(self.tmp, ignore_errors=True)
            self.tmp = None

    # ---- page and fonts ----

    def _page(self):
        page = self.profile["page"]
        if page.get("trim") == "custom" and page.get("custom_width") and page.get("custom_height"):
            w, h = page["custom_width"], page["custom_height"]
        else:
            w, h = TRIMS.get(page.get("trim"), TRIMS["6x9"])
        doc = self.doc
        doc.width, doc.height = _half(w * 72), _half(h * 72)
        doc.facing = page.get("facing", True)
        doc.bleed = BLEED if page.get("bleed") else 0
        doc.footnotes = dict(self.profile["footnotes"])
        # Until the geometry is worked out (the styles need a measure for nothing yet).
        self.measure, self.text_height = doc.width - 108, doc.height - 117

    def _measure_font(self):
        """The body font's average character width, from the manuscript's own text."""
        text = []
        n = 0
        for d in self.docs:
            for p in d.paragraphs:
                if n > 20000:
                    break
                text.append(p.text)
                n += len(p.text)
        found = fonts.find_font(self.fonts["body"])
        self.x_height = None
        if found:
            try:
                self.avg_width = fonts.average_width(found, " ".join(text))
                self.x_height = fonts.x_height(found)
                return
            except Exception:
                pass
        self.avg_width = fonts.FALLBACK_WIDTH
        self.report.append("%s isn't installed on this computer, so the text width was worked out "
                           "for an average book font. Install the font, or check the line length "
                           "in InDesign or Affinity." % self.fonts["body"])

    def _first_guess(self):
        """Page count from the words, for the first geometry."""
        chars = sum(len(p.text) for d in self.docs for p in d.paragraphs)
        notes = sum(len(p.text) for d in self.docs for p in d.note_paragraphs)
        g = layout.geometry(self.doc.width, self.doc.height, self.body_size, self.body_lead,
                            self.avg_width, 100)
        per_page = g.cpl * g.lines
        return int((chars + notes * 0.8) / per_page) + 2 * len(self.outline.units) + 4

    def _geometry(self, pages):
        doc = self.doc
        g = layout.geometry(doc.width, doc.height, self.body_size, self.body_lead,
                            self.avg_width, pages, self.profile["page"].get("margins"))
        self.geo = g
        doc.margins = g.margins
        self.measure, self.text_height = g.measure, g.text_height

    def _fonts(self):
        pf = dict(self.profile["fonts"])
        # A style template's fonts count as chosen (the profile's own still win).
        for role, style in (("body", "Body"), ("headings", "Chapter Title"),
                            ("notes", "Footnote")):
            if not pf.get(role) and self._template_font(style):
                pf[role] = self._template_font(style)
        # Fonts not set in the profile (or a template) are book fonts installed here, never
        # Word's: a manuscript's fonts are its author's or its template's, not the book's.
        body = pf.get("body")
        if not body:
            body = fonts.book_font()
            self.report.append("Body font: %s (no font set in the profile; a book font "
                               "installed on this computer). Choose another in Layout profile "
                               "> Type." % body)
        heads = pf.get("headings") or body
        notes = pf.get("notes") or body
        display = pf.get("display") or heads
        heb = pf.get("hebrew")
        if not heb:
            heb = fonts.script_font("hebrew")
            if any(d.scripts["hebrew"].chars for d in self.docs):
                self.report.append("Hebrew font: %s (none set in the profile)." % heb)
        grk = pf.get("greek")
        if not grk and any(d.scripts["greek"].chars for d in self.docs):
            # The body font if it has Greek letters (polytonic too), else a Greek font.
            found = fonts.find_font(body)
            if not (found and fonts.has_char(found, 0x1F00)):
                grk = fonts.script_font("greek")
                self.report.append("Greek font: %s (the body font has no polytonic Greek; "
                                   "none set in the profile)." % grk)
        self.fonts = {"body": body, "headings": heads, "notes": notes, "display": display,
                      "hebrew": heb, "greek": grk}

    # ---- styles ----

    def _composer(self, typo):
        """The World-Ready composer (InDesign's "HL Composer Optyca") by default: the paragraph
        composer with right-to-left support, so Hebrew is set right in every style, including
        Hebrew added later in InDesign; Latin and Greek text set the same. Single-line only if
        the profile asks for it and the book has no Hebrew."""
        if typo["paragraph_composer"]:
            return "HL Composer Optyca"
        if any(d.scripts["hebrew"].chars for d in self.docs):
            if not getattr(self, "_composer_noted", False):
                self.report.append("The book has Hebrew, so the World-Ready composer is used "
                                   "although the profile asks for the single-line composer "
                                   "(Hebrew needs it).")
                self._composer_noted = True
            return "HL Composer Optyca"
        return "HL Single"

    def _leading(self, size):
        cpl = self.geo.cpl if getattr(self, "geo", None) else layout.TARGET_CPL
        return leading_for(self.profile, size, self.x_height, cpl)

    def _book_styles(self):
        typo = self.profile["typography"]
        f = self.fonts
        size = body_size(self.profile)
        lead = self._leading(size)
        self.body_size, self.body_lead = size, lead
        indent = _half(size * 1.5)
        lang = LANGUAGES.get(self.profile["front_matter"].get("language"), LANGUAGES["en"])
        body = {"FontStyle": "Regular", "PointSize": size, "FirstLineIndent": indent,
                "Justification": "LeftJustified", "Hyphenation": bool(typo["hyphenation"]),
                "Composer": self._composer(typo),
                "AppliedLanguage": lang, "Ligatures": bool(typo["ligatures"])}
        if typo["oldstyle_figures"]:
            body["OTFFigureStyle"] = "ProportionalOldstyle"
        # Widows and orphans: InDesign applies KeepFirstLines/KeepLastLines only with
        # KeepLinesTogether on (and KeepAllLinesTogether off).
        if typo["widow_orphan_control"]:
            body.update({"KeepLinesTogether": True, "KeepFirstLines": 2, "KeepLastLines": 2})
        else:
            body.update({"KeepLinesTogether": False, "KeepFirstLines": 1, "KeepLastLines": 1})
        # No hyphen in a paragraph's last word, nor at the foot of a page or column.
        body.update({"HyphenateLastWord": False, "HyphenateAcrossColumns": False})
        balance = {"BalanceRaggedLines": ("enumeration", "VeeShape")} \
            if typo["balance_ragged_headings"] else {}
        head = {"FirstLineIndent": 0, "Hyphenation": False, "KeepWithNext": 2,
                "KeepLinesTogether": True, "KeepAllLinesTogether": True}
        note_size, note_lead = size - 2, _half((size - 2) * 1.22)
        # Chapter titles start a page: the next odd page when chapters open on a recto. Each
        # chapter is a story of its own on its recto already; this keeps the rule if chapters
        # are joined into one story in InDesign.
        start = "NextOddPage" if self.profile.get("chapters_open", "recto") == "recto" \
            else "NextPage"
        hang = [("LeftAlign", 18, "")]
        S = Style
        self.doc.paragraph_styles = [
            S("Body", font=f["body"], leading=lead, attrs=body),
            S("Body First", "Body", {"FirstLineIndent": 0}),
            S("Chapter Title", "Body", dict(head, PointSize=_half(size * 1.8),
                                             Justification="CenterAlign", SpaceAfter=lead * 2,
                                             StartParagraph=start),
              font=f["headings"], leading=_half(size * 2.2), next_style="Body First", props=balance),
            S("Part Title", "Chapter Title", {"PointSize": _half(size * 2.2)},
              leading=_half(size * 2.6), next_style="Body First"),
            S("Heading A", "Body", dict(head, PointSize=size + 1, FontStyle="Bold",
                                         Justification="LeftAlign", SpaceBefore=lead,
                                         SpaceAfter=_half(lead / 2)),
              font=f["headings"], leading=lead, next_style="Body First", props=balance),
            S("Heading B", "Heading A", {"PointSize": size, "FontStyle": "Bold Italic"},
              next_style="Body First"),
            S("Heading C", "Heading A", {"PointSize": size, "FontStyle": "Italic"},
              next_style="Body First"),
            S("Book Title", "Body", dict(head, PointSize=_half(size * 2.4),
                                          Justification="CenterAlign", SpaceAfter=lead),
              font=f["display"], leading=_half(size * 2.8), props=balance),
            S("Chapter Subtitle", "Chapter Title", {"PointSize": _half(size * 1.3),
                                                    "FontStyle": "Italic",
                                                    "StartParagraph": "Anywhere",
                                                    "SpaceAfter": lead * 2},
              leading=_half(size * 1.7), next_style="Body First"),
            S("Chapter Author", "Chapter Subtitle", {"FontStyle": "Regular",
                                                     "PointSize": size + 1},
              leading=_half(size * 1.5), next_style="Body First"),
            S("Book Subtitle", "Book Title", {"PointSize": _half(size * 1.4),
                                              "FontStyle": "Italic"}, leading=_half(size * 1.8)),
            S("Author", "Book Title", {"PointSize": _half(size * 1.3), "SpaceBefore": lead * 2},
              leading=_half(size * 1.7)),
            S("Block Quote", "Body", {"PointSize": size - 1, "FirstLineIndent": 0,
                                      "LeftIndent": indent, "SpaceBefore": _half(lead / 2),
                                      "SpaceAfter": _half(lead / 2)}, leading=lead - 1),
            S("Verse", "Block Quote", {"Justification": "LeftAlign", "Hyphenation": False}),
            S("List", "Body", {"FirstLineIndent": -18, "LeftIndent": 18,
                               "Justification": "LeftAlign"}, tabs=hang),
            S("List Bullet", "List"),
            S("List Number", "List"),
            S("Bibliography", "Body", {"FirstLineIndent": -indent, "LeftIndent": indent,
                                       "Justification": "LeftAlign"}),
            S("Footnote", font=f["notes"], leading=note_lead,
              attrs={"FontStyle": "Regular", "PointSize": note_size, "FirstLineIndent": size - 2,
                     "Justification": "LeftJustified", "AppliedLanguage": lang,
                     "Hyphenation": bool(typo["hyphenation"]),
                     "Composer": body["Composer"], "HyphenateLastWord": False,
                     **{k: body[k] for k in ("KeepLinesTogether", "KeepFirstLines",
                                             "KeepLastLines")}}),
            S("Caption", "Body", {"PointSize": size - 2, "FirstLineIndent": 0,
                                  "FontStyle": "Italic", "Justification": "CenterAlign",
                                  "SpaceAfter": _half(lead / 2)}, leading=note_lead),
            S("Figure", "Body", {"FirstLineIndent": 0, "Justification": "CenterAlign",
                                 "SpaceBefore": _half(lead / 2), "SpaceAfter": 4}),
            S("Table", "Body", {"FirstLineIndent": 0, "SpaceBefore": _half(lead / 2),
                                "SpaceAfter": _half(lead / 2)}),
            S("Table Body", "Body", {"FirstLineIndent": 0, "PointSize": size - 1.5,
                                     "Justification": "LeftAlign", "Hyphenation": False},
              leading=_half((size - 1.5) * 1.26)),
            S("Table Head", "Table Body", {"FontStyle": "Bold"}),
            S("Folio", font=f["body"], leading=lead,
              attrs={"PointSize": size - 2, "Justification": "CenterAlign"}),
            S("Running Head", font=f["body"], leading=lead,
              attrs={"PointSize": size - 2, "Justification": "CenterAlign",
                     "Capitalization": "SmallCaps", "Tracking": 20, "Hyphenation": False}),
            S("Half Title", "Book Title", {"PointSize": _half(size * 1.6)},
              leading=_half(size * 2)),
            S("Publisher", "Book Title", {"PointSize": size, "SpaceBefore": lead * 6},
              leading=lead),
            S("Copyright", "Body", {"PointSize": size - 2, "FirstLineIndent": 0,
                                    "Justification": "LeftAlign", "Hyphenation": False,
                                    "SpaceAfter": _half(lead / 2)}, leading=note_lead),
            S("Contents Title", "Chapter Title", next_style="Contents 1"),
            S("Contents 1", "Body", {"FirstLineIndent": 0, "Justification": "LeftAlign",
                                     "SpaceBefore": 6, "Hyphenation": False},
              tabs=[("RightAlign", self.measure, ". ")]),
            S("Contents 2", "Contents 1", {"LeftIndent": 18, "SpaceBefore": 0}),
        ]
        self.doc.colors = [("Table Grey", (0, 0, 0, 12))]
        insets = {"TextTopInset": 3, "TextLeftInset": 4, "TextBottomInset": 3,
                  "TextRightInset": 4, "TopInset": 3, "BottomInset": 3, "LeftInset": 4,
                  "RightInset": 4}
        self.doc.cell_styles = [CellStyle("Head Cell", "Table Head", "Table Grey", dict(insets)),
                                CellStyle("Body Cell", "Table Body", None, dict(insets))]
        self.doc.table_styles = [TableStyle("Book Table", "Head Cell", "Body Cell",
                                            {"TopBorderStrokeWeight": 1,
                                             "BottomBorderStrokeWeight": 1,
                                             "LeftBorderStrokeWeight": 0,
                                             "RightBorderStrokeWeight": 0})]
        self.builtin = {s.name for s in self.doc.paragraph_styles}
        if self.tpl:
            apply_template(self.doc.paragraph_styles, self.tpl[0])
            self._keep_world_ready()
            attrs, _font, leading = self.doc.resolved("Body")
            self.body_size = attrs.get("PointSize", self.body_size)
            if isinstance(leading, (int, float)):
                self.body_lead = leading

    def _resolved_attrs(self, name):
        attrs, _font, _lead = self.doc.resolved(name)
        return attrs

    def _word_style(self, name):
        """(DocxFile, style id) of the first file defining this Word style name."""
        key = norm(name)
        for d in self.docs:
            for sid, st in d.styles.items():
                if norm(st.name) == key:
                    return d, sid
        return None, None

    def _custom_paragraph_style(self, mapping, docx, style_id):
        """A Word style kept under its own name, based on its parent's IDML style (or its
        role's book style)."""
        name = mapping.idml
        if name in self.builtin or name in self.custom:
            return
        st = docx.styles.get(style_id)
        base = ROLE_BASE.get(mapping.role, "Body")
        if mapping.role == "heading":
            base = "Heading " + "ABC"[max(1, min(mapping.level, 3)) - 1]
        if st and st.based_on and st.based_on in docx.styles:
            pm = self.sm.paragraph_style(docx, st.based_on)
            if pm.idml and pm.idml not in self.builtin and pm.idml != name:
                self._custom_paragraph_style(pm, docx, st.based_on)
                base = pm.idml
            elif pm.idml in self.builtin:
                base = pm.idml if pm.role == mapping.role else base
        # Only the name and the place in the book come from Word: the look is the book
        # style's it is based on (Word's alignment, indents, spacing and sizes are a
        # manuscript's, not a book's). Change it in InDesign, or with a style template.
        self.custom[name] = Style(name, base)
        self.doc.paragraph_styles.append(self.custom[name])

    def _char_style(self, name, docx=None, style_id=None):
        """Make sure a character style exists; returns its attributes."""
        if name in self.used_char:
            return self.used_char[name].attrs
        if name in CHAR_STYLES:
            st = Style(name, attrs=dict(CHAR_STYLES[name]))
        elif name == "Hebrew":
            st = Style(name, font=self.fonts["hebrew"],
                       attrs={"FontStyle": "Regular", "AppliedLanguage": "$ID/Hebrew",
                              "CharacterDirection": "RightToLeftDirection"})
        elif name == "Greek":
            st = Style(name, font=self.fonts["greek"], attrs={"AppliedLanguage": "$ID/Greek"})
        else:
            attrs, font = {}, None
            if docx is not None and style_id in docx.styles:
                ws = docx.styles[style_id]
                p = ws.props
                b, i = _toggle(p.get("b")), _toggle(p.get("i"))
                if b or i:
                    attrs["FontStyle"] = FONT_STYLES[(b, i)]
                if _toggle(p.get("caps")):
                    attrs["Capitalization"] = "AllCaps"
                elif _toggle(p.get("smallCaps")):
                    attrs["Capitalization"] = "SmallCaps"
                va = _prop(p.get("vertAlign"), "val")
                if va in ("superscript", "subscript"):
                    attrs["Position"] = va.capitalize()
                if p.get("u") and _prop(p["u"], "val") != "none":
                    attrs["Underline"] = True
                if _toggle(p.get("strike")):
                    attrs["StrikeThru"] = True
                font = ws.fonts.get("ascii") or ws.fonts.get("hAnsi")
            st = Style(name, attrs=attrs, font=font)
        self.used_char[name] = st
        return st.attrs

    def _template_font(self, name):
        """The font a template style ends up with (through its based-on styles), or None."""
        if not self.tpl:
            return None
        seen = set()
        st = self.tpl[0].get(name)
        while st is not None and st.name not in seen:
            seen.add(st.name)
            if st.font:
                return st.font
            st = self.tpl[0].get(st.based_on) if st.based_on else None
        return None

    def _keep_world_ready(self):
        """A template's composer gives way to World-Ready when the book has Hebrew."""
        if not any(d.scripts["hebrew"].chars for d in self.docs):
            return
        changed = False
        for s in self.doc.paragraph_styles:
            if s.attrs.get("Composer") not in (None, "HL Composer Optyca"):
                s.attrs["Composer"] = "HL Composer Optyca"
                changed = True
        if changed and not getattr(self, "_tpl_composer_noted", False):
            self.report.append("The template's styles use another composer; the book has "
                               "Hebrew, so they use the World-Ready composer instead (Hebrew "
                               "needs it).")
            self._tpl_composer_noted = True

    def _template_styles(self):
        """The template's styles over the book's (custom ones too), and its other styles
        added for use by hand. Reported."""
        tp, tc, notes = self.tpl
        replaced = set(apply_template(self.doc.paragraph_styles, tp))
        self._keep_world_ready()
        chars = list(self.doc.character_styles)
        replaced |= set(apply_template(chars, tc))
        self.doc.character_styles = chars
        have_p = {s.name for s in self.doc.paragraph_styles}
        have_c = {s.name for s in chars}
        added = [n for n in tp if n not in have_p] + [n for n in tc if n not in have_c]
        for n in tp:
            if n not in have_p:
                self.doc.paragraph_styles.append(tp[n])
        for n in tc:
            if n not in have_c:
                self.doc.character_styles.append(tc[n])
        own = sorted((have_p | have_c) - replaced)
        self.report.append("Styles from %s: %d of the book's styles taken from it; %d more "
                           "added for use by hand; the tool's own kept for %s." % (
                               os.path.basename(self.profile["styles_template"]), len(replaced),
                               len(added), ", ".join(own) if own else "none"))
        self.report += notes
        return set(tp)

    def _baseline_grid(self):
        """Body text on a baseline grid of the body leading, from the top margin (as g09);
        styles with other leading (block quotes, notes, captions, headings) stay off it."""
        m = self.doc.margins
        self.doc.baseline_grid = {"start": m["top"], "division": self.body_lead, "shown": False}
        body = self.doc.style("Body")
        if body is not None:
            body.attrs["GridAlignment"] = "AlignBaseline"
        for s in self.doc.paragraph_styles:
            attrs, _font, lead = self.doc.resolved(s.name)
            if attrs.get("GridAlignment") == "AlignBaseline" and lead != self.body_lead:
                s.attrs["GridAlignment"] = "None"

    def _finish_styles(self):
        self._char_style("Footnote Reference")
        order = list(CHAR_STYLES) + ["Hebrew", "Greek"]
        self.doc.character_styles = sorted(
            self.used_char.values(),
            key=lambda s: (order.index(s.name) if s.name in order else len(order), s.name))
        tpl_names = self._template_styles() if self.tpl else set()
        if self.profile.get("baseline_grid"):
            self._baseline_grid()
        # Only the styles the book uses, plus the ones every book has (and the template's).
        used = set(self.para_used) | {"Body", "Body First", "Footnote", "Folio", "Running Head"}
        used |= tpl_names
        for st in self.doc.stories:
            used |= {p.style for p in st.paragraphs}
        if self.doc.toc_styles:
            used |= {"Contents Title", "Contents 1", "Contents 2"}
        keep, changed = [], True
        styles = {s.name: s for s in self.doc.paragraph_styles}
        while changed:
            changed = False
            for name in list(used):
                s = styles.get(name)
                for dep in (s.based_on, s.next_style) if s else ():
                    if dep and dep not in used:
                        used.add(dep)
                        changed = True
        for cs in self.doc.cell_styles:
            if self.tables_used:
                used.add(cs.paragraph_style)
        keep = [s for s in self.doc.paragraph_styles if s.name in used]
        self.doc.paragraph_styles = keep
        if not self.tables_used:
            self.doc.cell_styles, self.doc.table_styles, self.doc.colors = [], [], []

    # ---- text ----

    def _run_attrs(self, crun, para_style, docx, note):
        """(character style, local attributes) for a run's features in a paragraph style."""
        pattrs = self._resolved_attrs(para_style)
        pfs = pattrs.get("FontStyle", "Regular")
        p_bold, p_italic = "Bold" in pfs, "Italic" in pfs
        cs_feats = {}
        mapped = None
        if crun.char_style and crun.char_style in docx.styles:
            m = self.sm.character_style(docx, crun.char_style)
            if m.role != "skip":
                mapped = m.idml
            for sid in reversed(docx.style_chain(crun.char_style)):
                p = docx.styles[sid].props
                for key, feat in (("i", "italic"), ("b", "bold")):
                    if key in p:
                        cs_feats[feat] = _toggle(p[key])
        f = crun.feats

        def eff(feat, para_on):
            if feat in f:
                return f[feat]
            if feat in cs_feats:
                return para_on != cs_feats[feat] if cs_feats[feat] else para_on
            return para_on
        fs = FONT_STYLES[(eff("bold", p_bold), eff("italic", p_italic))]
        want = {}
        if fs != pfs:
            want["FontStyle"] = fs
        if f.get("caps"):
            want["Capitalization"] = "AllCaps"
        elif f.get("smallcaps"):
            want["Capitalization"] = "SmallCaps"
        if f.get("position"):
            want["Position"] = f["position"].capitalize()
        if f.get("underline"):
            want["Underline"] = True
        if f.get("strike"):
            want["StrikeThru"] = True
        if mapped:
            sattrs = self._char_style(mapped, docx, crun.char_style)
            if "FontStyle" in sattrs and "FontStyle" not in want and fs == pfs:
                want["FontStyle"] = fs        # the style's face is right for this run
            return mapped, self._local(want, sattrs, pfs)
        style = None
        if want.get("FontStyle") in ("Italic", "Bold", "Bold Italic"):
            style = want["FontStyle"]
        elif "Capitalization" in want:
            style = {"SmallCaps": "Small Caps", "AllCaps": "All Caps"}[want["Capitalization"]]
        elif "Position" in want:
            style = want["Position"]
        elif "Underline" in want:
            style = "Underline"
        elif "StrikeThru" in want:
            style = "Strikethrough"
        if style is None:
            return None, want
        return style, self._local(want, self._char_style(style), pfs)

    @staticmethod
    def _local(want, sattrs, pfs):
        local = {k: v for k, v in want.items() if sattrs.get(k) != v}
        for k, v in sattrs.items():
            if k in RESET and k not in want:
                local[k] = RESET[k] if RESET[k] is not None else pfs
        return local

    def _runs(self, cruns, para_style, docx, note=False):
        out = []
        for cr in cruns:
            if cr.footnote is not None:
                out.append(Run(footnote=self._note(cr.footnote, docx)))
                continue
            if cr.image is not None or not cr.text:
                continue
            style, local = self._run_attrs(cr, para_style, docx, note)
            for script, part in segments(cr.text):
                if script:
                    name = "Hebrew" if script == "hebrew" else "Greek"
                    sattrs = self._char_style(name)
                    want = dict(local)
                    if style and style in self.used_char:
                        for k, v in self.used_char[style].attrs.items():
                            want.setdefault(k, v)
                    if script == "hebrew":
                        want.pop("FontStyle", None)
                    out.append(Run(part, name, {k: v for k, v in want.items()
                                                if sattrs.get(k) != v}))
                else:
                    out.append(Run(part, style, dict(local)))
        merged = []
        for r in out:
            if merged and r.footnote is None and merged[-1].footnote is None and \
                    merged[-1].style == r.style and merged[-1].attrs == r.attrs:
                merged[-1].text += r.text
            else:
                merged.append(r)
        return merged

    def _runt_style(self, name):
        """Paragraphs of running text (Body, notes, quotations...), not headings or display."""
        seen = set()
        while name and name not in seen:
            seen.add(name)
            if name in NO_RUNT_SKIP:
                return False
            if name in ("Body", "Footnote"):
                return True
            s = self.doc.style(name)
            name = s.based_on if s else None
        return False

    def _no_runt(self, para, min_chars):
        """Keep the last words of a paragraph together (No Break), so its last line has at
        least min_chars characters: no short word alone on the last line. Works in every
        program, unlike a GREP style."""
        if not min_chars or not self._runt_style(para.style):
            return
        texts = [(i, r) for i, r in enumerate(para.runs)
                 if r.footnote is None and r.table is None and r.image is None and not r.special]
        full = "".join(r.text for _i, r in texts)
        end = len(full.rstrip())
        if end < 4 * min_chars:
            return                      # a line or so: nothing to gain
        start = full.rfind(" ", 0, end) + 1
        if not start or end - start >= min_chars:
            return                      # a long last word is not a runt
        while end - start < min_chars:
            space = full.rfind(" ", 0, start - 1)
            if space < 0 or "\t" in full[space:end] or "\n" in full[space:end]:
                return
            start = space + 1
        if end - start > 3 * min_chars:
            return
        # Split the runs at start; mark everything from there on.
        pos, out = 0, []
        text_ids = {i for i, _r in texts}
        for i, r in enumerate(para.runs):
            if i not in text_ids:
                out.append(r)
                continue
            a, b = pos, pos + len(r.text)
            pos = b
            if b <= start:
                out.append(r)
                continue
            if a < start:
                out.append(Run(r.text[:start - a], r.style, dict(r.attrs)))
                r = Run(r.text[start - a:], r.style, dict(r.attrs))
            if r.style is None:
                r.style = "No Break"
                self._char_style("No Break")
            else:
                r.attrs["NoBreak"] = True
            out.append(r)
        para.runs = out

    def _note(self, cparas, docx):
        paras = []
        for cp in cparas:
            if cp.empty:
                continue
            paras.append(Paragraph("Footnote", self._runs(cp.runs, "Footnote", docx, True),
                                   self._para_attrs(cp, "Footnote")))
        return paras or [Paragraph("Footnote", [])]

    def _para_attrs(self, cp, style):
        attrs = {}
        text = cp.text
        if cp.align in ("center", "right"):
            attrs["Justification"] = "CenterAlign" if cp.align == "center" else "RightAlign"
            if cp.align == "center":
                attrs["FirstLineIndent"] = 0
        heb = sum(1 for c in text if is_hebrew(c))
        if heb:
            attrs["Composer"] = "HL Composer Optyca"
            latin = sum(1 for c in text if c.isalpha() and not is_hebrew(c))
            if cp.bidi or heb > latin:
                attrs["ParagraphDirection"] = "RightToLeftDirection"
                just = attrs.get("Justification") or \
                    self._resolved_attrs(style).get("Justification", "LeftAlign")
                attrs["Justification"] = {"LeftJustified": "RightJustified",
                                          "LeftAlign": "RightAlign"}.get(just, just)
        return attrs

    def _mapping(self, docx, style_id):
        sid = style_id if style_id in docx.styles else docx.default_style.get("paragraph")
        m = self.sm.paragraph_style(docx, sid)
        if m.idml and m.idml not in self.builtin and m.role not in ("skip", "toc", "toc_title"):
            self._custom_paragraph_style(m, docx, sid)
        return m

    def _bibliography_state(self, cp, docx, bib):
        """Bibliography styling runs from a heading titled Bibliography (Works Cited,
        References...) at any level to the next heading of the same or a higher level, so a
        bibliography ending a chapter doesn't spill into what follows."""
        if cp.table is not None:
            return bib
        m = self._mapping(docx, cp.style_id)
        if m.role in ("chapter", "part", "book_title"):
            level = 0
        elif m.role == "heading":
            level = max(1, m.level)
        else:
            return bib
        if _BACK.get(title_key(cp.text)) == "bibliography":
            return level
        return bib if bib is not None and level > bib else None

    def _paragraphs(self, cp, docx, unit, prev_role, first, bib=False, body_seen=True):
        """Model paragraphs for one content paragraph (an image splits it), with its role.
        bib: the paragraph is in a bibliography section (body text set as entries).
        body_seen: the unit already has body text (the first text paragraph of a unit, after
        an epigraph say, is set flush: Body First)."""
        if cp.table is not None:
            return [Paragraph("Table", [Run(table=self._table(cp.table, docx))])], "table"
        m = self._mapping(docx, cp.style_id)
        if m.role in ("skip", "toc", "toc_title") or cp.empty:
            return [], prev_role
        style = m.idml or "Body"
        runs = list(cp.runs)
        if m.role == "part" or (unit is not None and unit.kind == "part" and first and
                                m.role == "chapter"):
            style = "Part Title"
        elif unit is not None and unit.kind != "display" and \
                m.role in ("book_title", "subtitle", "author"):
            # A title line opening a chapter (an article's title, say) titles that chapter,
            # not the book's title page.
            style = {"book_title": "Chapter Title", "subtitle": "Chapter Subtitle",
                     "author": "Chapter Author"}[m.role]
        if cp.label:
            if m.role in ("chapter", "part", "heading"):
                runs.insert(0, _label_run(cp.label + " "))
            else:
                if style in ("Body", "List"):
                    style = "List Bullet" if cp.list_format == "bullet" else "List Number"
                runs.insert(0, _label_run(cp.label + (cp.label_suffix or "\t")))
        if style == "Body" and bib:
            style = "Bibliography"
        if style == "Body" and (first or prev_role in HEAD_ROLES or not body_seen):
            style = "Body First"
        attrs = self._para_attrs(cp, style)
        role = m.role
        if attrs.get("Justification", self._resolved_attrs(style).get("Justification")) == \
                "CenterAlign" and role not in HEAD_ROLES:
            role = "centered"      # an epigraph, a centered line: the text after starts flush
        if cp.label and cp.list_level and style.startswith("List"):
            attrs["LeftIndent"] = 18 * (cp.list_level + 1)
        if cp.page_break_before and not first:
            attrs["StartParagraph"] = "NextPage"
        # Images go in paragraphs of their own, in order with the text around them.
        out, chunk = [], []
        for r in runs:
            if r.image is not None:
                if any(x.text.strip() or x.footnote is not None for x in chunk):
                    out.append(Paragraph(style, self._runs(chunk, style, docx), dict(attrs)))
                chunk = []
                out.append(self._figure(r.image, docx))
            else:
                chunk.append(r)
        if any(x.text.strip() or x.footnote is not None for x in chunk) or not out:
            out.append(Paragraph(style, self._runs(chunk, style, docx), attrs))
        return out, role

    def _figure(self, img, docx):
        prefix = os.path.splitext(docx.name)[0]
        path = save_image(img, self.tmp, prefix)
        if path is None:
            self.report.append("Image %s in %s is not JPEG or PNG; it was left out (a line marks "
                               "its place). Save it as PNG or JPEG and place it by hand."
                               % (img.name, docx.name))
            return Paragraph("Figure", [Run("[Image not carried over: %s]" % img.name)])
        width = min(img.width or self.measure, self.measure)
        return Paragraph("Figure", [Run(image=Image(path, width=_half(width)))])

    def _table(self, ct, docx):
        self.tables_used = True
        rows = []
        for r, row in enumerate(ct.rows):
            out_row = []
            for cell in row:
                if cell is None:
                    out_row.append(None)
                    continue
                paras = []
                for cp in cell:
                    if cp.table is not None or cp.empty:
                        continue
                    m = self._mapping(docx, cp.style_id)
                    style = m.idml if m.idml and m.role not in ("body", "skip") else "Table Body"
                    if r < ct.header_rows and style == "Table Body":
                        style = "Table Head"
                    self.para_used.add(style)
                    paras.append(Paragraph(style, self._runs(cp.runs, style, docx),
                                           self._para_attrs(cp, style)))
                out_row.append(paras or [Paragraph("Table Body", [])])
            rows.append(out_row)
        n = len(rows[0]) if rows else 1
        widths = ct.widths
        if not widths or None in widths:
            widths = [self.measure / n] * n
        total = sum(widths)
        if total > self.measure:
            widths = [w * self.measure / total for w in widths]
        return Table(rows, [_half(w) for w in widths], ct.header_rows, "Book Table",
                     dict(ct.spans))

    # ---- units and stories ----

    def _stories(self):
        """[(unit, paragraphs)] in book order."""
        self.para_used = set()
        self.tables_used = False
        units_by_file = {}
        for u in self.outline.units:
            units_by_file.setdefault(u.file, []).append(u)
        stories = []
        current = None
        for docx in self.docs:
            content = read_content(docx)
            starts = {u.start: u for u in units_by_file.get(docx.name, [])}
            prev_role, first = None, True
            bib = None              # level of the bibliography heading we're under, if any
            for cp in content:
                if cp.index in starts:
                    unit = starts.pop(cp.index)
                    current = [unit, []]
                    stories.append(current)
                    prev_role, first, bib = None, True, None
                if current is None:
                    # Text before the first unit (the outline found none for it).
                    current = [None, []]
                    stories.append(current)
                if cp.index >= 0 and cp.index < len(docx.paragraphs) and \
                        docx.paragraphs[cp.index].in_toc_field and cp.table is None:
                    continue
                bib = self._bibliography_state(cp, docx, bib)
                body_seen = any(p.style in ("Body", "Body First") for p in current[1])
                paras, role = self._paragraphs(cp, docx, current[0], prev_role, first,
                                               bib is not None, body_seen)
                if paras:
                    current[1].extend(paras)
                    prev_role, first = role, False
        min_chars = self.profile["typography"].get("last_line_min_chars") or 0
        for _unit, paras in stories:
            for p in paras:
                self.para_used.add(p.style)
                self._no_runt(p, min_chars)
                for r in p.runs:
                    for n in r.footnote or ():
                        self.para_used.add(n.style)
                        self._no_runt(n, min_chars)
        n_end = sum(d.endnote_count for d in self.docs)
        if n_end:
            self.report.append("%d endnote%s converted to footnotes." %
                               (n_end, "" if n_end == 1 else "s"))
        return [(u, p) for u, p in stories if p]

    def _estimate(self, paras, sink):
        """Pages a story needs: lines of text at the styles' sizes, notes, tables, images."""
        def lines(p, measure):
            attrs, _font, leading = self.doc.resolved(p.style)
            size = attrs.get("PointSize", self.body_size)
            lead = leading if isinstance(leading, (int, float)) else size * 1.2
            text = "".join(r.text for r in p.runs)
            cpl = max(10, (measure - attrs.get("LeftIndent", 0)) / (size * self.avg_width))
            n = max(1, math.ceil(len(text) / cpl))
            return n * lead + attrs.get("SpaceBefore", 0) + attrs.get("SpaceAfter", 0)
        height = sink
        for p in paras:
            for r in p.runs:
                if r.table is not None:
                    for row in r.table.rows:
                        cells = [c for c in row if c]
                        height += max([sum(lines(q, self.measure / len(row)) for q in c)
                                       for c in cells] + [12]) + 6
                    continue
                if r.image is not None:
                    w, h, *_ = image_info(r.image.path)
                    height += r.image.width * h / w + 12
                for n in r.footnote or ():
                    height += lines(n, self.measure) + 3
            if not any(r.table is not None or r.image is not None for r in p.runs):
                height += lines(p, self.measure)
        return max(1, math.ceil(height / self.text_height))

    # ---- front matter (step 6) ----

    def _front_matter(self, stories):
        """The book's blocks in order: generated half-title, title and copyright pages, the
        manuscript's display pages, the reserved contents, then front matter, text and back
        matter. Returns [Block]."""
        front = self.settings.get("front", {})
        info, notes = frontmatter.book_info(self.outline, front)
        self.info = info
        self.report += notes
        lang = self.profile["front_matter"].get("language", "en")
        display, front_units, rest, praise = [], [], [], []
        ms_copyright, extras = [], []
        for unit, paras in stories:
            kind = unit.kind if unit else "chapter"
            if kind == "display" and unit.type in ("title page", "opening"):
                cp, ex = self._split_opening(paras)
                ms_copyright += cp
                extras += ex
            elif kind == "display" and unit.type == "copyright":
                ms_copyright += [p for p in paras if p.style != "Chapter Title"]
            elif kind == "display" and unit.type == "endorsements":
                praise.append(Block(unit, paras))
            elif kind == "display":
                display.append(Block(unit, paras))
            elif kind == "front" and unit.type == "contents":
                self.report.append('The manuscript\'s own contents ("%s") was left out: its '
                                   "page numbers would be wrong. Pages are reserved for the "
                                   "contents instead." % unit.title)
            elif kind == "front" and not rest:
                front_units.append(Block(unit, paras))
            else:
                rest.append(Block(unit, paras))
        # Endorsements come first, before the half-title (Chicago).
        blocks = list(praise)
        g = lambda kind, title, typ: Unit(kind, typ, title, "", -1, "generated")  # noqa: E731
        if info["half_title"]:
            blocks.append(Block(g("display", "Half title", "half title"),
                                frontmatter.half_title(info), sink=_half(self.text_height / 4)))
        blocks.append(Block(g("display", "Title page", "title page"), frontmatter.title_page(info),
                            sink=_half(self.text_height / 5)))
        if ms_copyright:
            paras = ms_copyright
            for p in paras:
                if p.style.startswith("Body"):
                    p.style = "Copyright"
        else:
            paras, cnotes = frontmatter.copyright_page(info, lang, self.profile.get("notices"))
            self.report += cnotes
        blocks.append(Block(g("display", "Copyright", "copyright"), paras, opens="next",
                            valign="BottomAlign"))
        if extras:
            blocks.append(Block(g("display", "(opening)", "opening"), extras))
        blocks += display
        if info["contents"]:
            depth = self.profile["front_matter"].get("contents_depth", "chapters")
            entries = frontmatter.contents_entries(self.outline, depth)
            sink = _half(self.body_lead * 6)
            pages = info["contents_pages"] or frontmatter.contents_pages(
                entries, self.geo.cpl, self.body_lead, self.text_height, sink)
            blocks.append(Block(g("front", frontmatter.texts(lang)["contents"], "contents"),
                                frontmatter.contents_page(lang), pages=pages, spare=0))
            self.report.append("Contents: %d page%s reserved for %d entries (change it in the "
                               "book settings). Place the contents from the Contents style."
                               % (pages, "" if pages == 1 else "s", len(entries)))
            self.contents_depth = depth
        else:
            self.contents_depth = None
        return blocks + front_units + rest

    def _split_opening(self, paras):
        """The manuscript's own title page: title, subtitle and author lines are replaced by
        the generated title page; from a copyright line on, the text goes on the copyright
        page; anything else is kept on a display page of its own."""
        copyright_, extras = [], []
        author = (self.outline.author or "").casefold()
        for p in paras:
            text = " ".join("".join(r.text for r in p.runs).split())
            low = text.casefold()
            if copyright_ or "\u00a9" in text or low.startswith("copyright") or \
                    "derechos reservados" in low:
                copyright_.append(p)
            elif p.style in ("Book Title", "Book Subtitle", "Author") or \
                    (author and author in low and len(text) < 80):
                continue
            else:
                extras.append(p)
        return copyright_, extras

    # ---- pagination and running heads ----

    def _short(self, title):
        return (self.settings.get("short_titles") or {}).get(title) or title

    def _head_frames(self, verso, recto):
        """Running heads above the text area: verso and recto paragraphs' runs."""
        doc, m = self.doc, self.doc.margins
        out = []
        for side, runs in (("verso", verso), ("recto", recto)):
            if runs is None:
                continue
            left = m["outside"] if side == "verso" else m["inside"]
            right = doc.width - (m["inside"] if side == "verso" else m["outside"])
            out.append(Frame(side, (m["top"] - 27, left, m["top"] - 13, right),
                             [Paragraph("Running Head", runs)], key=side[0] + "head",
                             valign="BottomAlign"))
        return out

    def _paginate(self, blocks):
        """Pages, masters, sections and running heads; returns the page count."""
        doc = self.doc
        sink = _half(self.body_lead * 6)
        items = []
        for b in blocks:
            kind = b.kind
            if b.sink is None:
                b.sink = 0 if kind in ("display", "part") else sink
            spare = b.spare if b.spare is not None else \
                (0 if kind in ("display", "part") else self._spare())
            est = b.pages or self._estimate(b.paras, b.sink)
            items.append((kind, est, spare, b.opens))
        placed, count, masters, first_body = layout.plan_pages(
            items, self.profile.get("chapters_open", "recto"))
        doc.stories, doc.sections = [], []
        optical = self.body_size if self.profile["typography"]["optical_margins"] else None
        rh = self.profile["running_heads"]
        part = None
        part_masters = []
        long_heads = []
        for n, (b, pl) in enumerate(zip(blocks, placed)):
            pages = list(range(pl.start, pl.start + pl.pages))
            doc.stories.append(Story(b.paras, pages, sink=b.sink, linked=True,
                                     optical_margins=optical, valign=b.valign))
            title = b.title if not b.title.startswith("(") and b.kind != "display" else ""
            marker = self._short(title)
            if marker and self._too_long(marker):
                long_heads.append(marker)
            body = first_body is not None and n >= first_body
            start = 1 if n == 0 or n == first_body else None
            # A blank verso before a unit belongs to the section before it.
            doc.sections.append(Section(pl.start, marker=marker,
                                        numbering="Arabic" if body else "LowerRoman",
                                        start=start))
            if b.kind == "part":
                part = self._short(b.title)
                part_masters.append(part)
            elif body and part and rh.get("verso") == "part":
                name = "P%d-Body" % len(part_masters)
                for i in pages:
                    if masters.get(i) == "A-Body":
                        masters[i] = name
        doc.page_count = max(count, 1)
        doc.page_masters = masters
        if not doc.sections:
            doc.sections = [Section(0, start=1)]
        self._masters(part_masters)
        if long_heads:
            self.report.append("Running heads too long for the page: %s. Give these a short "
                               "title in the book settings." % "; ".join(
                                   '"%s"' % h for h in long_heads))
        if self.contents_depth:
            levels = [("Chapter Title", 1, "Contents 1"), ("Part Title", 1, "Contents 1")]
            if self.contents_depth == "sections":
                levels.append(("Heading A", 2, "Contents 2"))
            lang = self.profile["front_matter"].get("language", "en")
            doc.toc_styles = [TOCStyle("Contents", frontmatter.texts(lang)["contents"],
                                       "Contents Title", levels)]
        est = sum(i[1] for i in items)
        blanks = sum(1 for v in masters.values() if v == "E-Blank")
        g, m = self.geo, doc.margins
        spare = self._spare()
        self.report.append("%d pages: about %d of text, %d blank verso%s." % (
            doc.page_count, est, blanks, "" if blanks == 1 else "s"))
        if spare == 1:
            self.report.append("Each chapter ends with a spare page. Where it stays empty, delete "
                               "it together with the blank page after it, or give it the E-Blank "
                               "master, so chapters keep their sides.")
        elif spare == 2:
            self.report.append("Each chapter ends with two spare pages. Delete unused ones two at "
                               "a time, so chapters keep their sides.")
        else:
            self.report.append("No spare pages: InDesign adds pages to a chapter whose text runs "
                               "over (then check that later chapters still open on a recto); "
                               "Affinity doesn't, so in Affinity add pages to a chapter whose "
                               "text runs over, two at a time.")
        self.report.append(self._leading_note())
        self.report.append(
            "Margins (in): top %.3g, bottom %.3g, inside %.3g, outside %.3g; text %d lines of "
            "%g pt, about %d characters per line."
            % (m["top"] / 72, m["bottom"] / 72, m["inside"] / 72, m["outside"] / 72, g.lines,
               self.body_lead, round(g.cpl)))
        return doc.page_count

    def _leading_note(self):
        sug, why = layout.leading_suggestions(self.body_size, self.x_height, self.geo.cpl,
                                              self.fonts["body"])
        lead = self.profile.get("leading") or {}
        if self.tpl and self.tpl[0].get("Body"):
            source = "from the style template"
        elif lead.get("value"):
            source = "as set in the profile"
        else:
            source = "%s, the middle of its range" % (lead.get("feel") or "standard")
        return ("Body type: %g pt on %g pt leading (%s). Suggested for %g pt: tight %g\u2013%g, "
                "standard %g\u2013%g, open %g\u2013%g%s." % (
                    self.body_size, self.body_lead, source, self.body_size,
                    sug["tight"][0], sug["tight"][1], sug["standard"][0], sug["standard"][1],
                    sug["open"][0], sug["open"][1], (" (%s)" % why) if why else ""))

    def _spare(self):
        try:
            return max(0, min(2, int(self.profile["page"].get("spare_pages") or 0)))
        except (TypeError, ValueError):
            return 0

    def _too_long(self, text):
        attrs = self._resolved_attrs("Running Head")
        size = attrs.get("PointSize", self.body_size)
        return len(text) * size * self.avg_width * 1.1 > self.measure * 0.8

    def _masters(self, parts):
        """A-Body, B-Opener and C-Front carry text (each its own primary text frames, so a
        chapter threads from B into A); D-Display and E-Blank are empty. Running heads follow
        the profile: the recto head is the section marker (the chapter's short title), the
        verso head the book title, author, chapter, part or custom text; C-Front shows the
        unit's title on both sides. Parts with part verso heads get a master each (P1-Body...),
        a copy of A-Body with the part's title."""
        doc, m = self.doc, self.doc.margins
        rh = self.profile["running_heads"]
        info = self.info
        top, bottom = m["top"], doc.height - m["bottom"]
        marker = [Run(special="section_marker")]
        verso_kind = rh.get("verso", "book_title")
        verso = {"book_title": [Run(info.get("short_title") or info["title"])],
                 "author": [Run(info["author"])], "chapter": marker,
                 "custom": [Run(rh.get("verso_custom") or "")]}.get(verso_kind)
        recto = [Run(rh.get("recto_custom") or "")] if rh.get("recto") == "custom" else marker

        def frames(heads=True, verso_runs=None, recto_runs=None):
            out = []
            for side in ("verso", "recto"):
                left = m["outside"] if side == "verso" else m["inside"]
                right = doc.width - (m["inside"] if side == "verso" else m["outside"])
                out.append(Frame(side, (top, left, bottom, right), [], primary=True))
                out.append(Frame(side, (bottom + 14, left, bottom + 28, right),
                                 [Paragraph("Folio", [Run(special="page_number")])],
                                 key="folio"))
            if heads:
                out += self._head_frames(verso_runs, recto_runs)
            return out
        doc.masters = [
            Master("A", "Body", frames=frames(True, verso or marker, recto)),
            Master("B", "Opener", frames=frames(not rh.get("suppress_on_openers", True),
                                                verso or marker, recto)),
            Master("C", "Front", frames=frames(True, marker, marker)),
            Master("D", "Display", frames=[] if rh.get("suppress_on_display", True)
                   else self._head_frames(verso or marker, recto)),
            Master("E", "Blank", frames=[] if rh.get("suppress_on_blanks", True)
                   else self._head_frames(verso or marker, recto))]
        if verso_kind == "part":
            for k, title in enumerate(parts, 1):
                doc.masters.append(Master("P%d" % k, "Body",
                                          frames=frames(True, [Run(title)], recto)))


def _label_run(text):
    from .content import CRun
    return CRun(text)


def export(paths, out_dir, profile=None, name=None, settings=None):
    """Export the manuscript to an export folder (IDML and Links). settings: the book's own
    settings. Returns (IDML path, report lines)."""
    from .idml.writer import export_book
    ex = Exporter(paths, profile, settings)
    try:
        doc = ex.build()
        path = export_book(doc, out_dir, name or _safe(doc.name))
    finally:
        ex.cleanup()
    return path, ex.report


def _safe(name):
    import re
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    return s[:80] or "Book"
