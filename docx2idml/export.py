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
import os
import shutil
import tempfile

from . import profile as profiles
from .content import read_content, save_image
from .docx_reader import is_greek, is_hebrew, read_docx
from .idml.images import image_info
from .idml.model import (CellStyle, Document, Frame, Image, Master, Paragraph, Run, Section,
                         Story, Style, Table, TableStyle)
from .outline import build_outline
from .stylemap import StyleMap, norm

TRIMS = {"5x8": (5, 8), "5.25x8": (5.25, 8), "5.5x8.5": (5.5, 8.5), "6x9": (6, 9),
         "7x10": (7, 10), "8.5x11": (8.5, 11), "A5": (5.83, 8.27)}
LANGUAGES = {"en": "$ID/English: USA", "es": "$ID/Spanish: Castilian"}
# Fonts Word's templates give a document by default: kept if the profile sets none, but noted.
TEMPLATE_FONTS = {"calibri", "calibri light", "cambria", "aptos", "aptos display", "aptos narrow",
                  "times new roman", "arial", "helvetica", "segoe ui"}
HEBREW_FALLBACK = "SBL Hebrew"
FONT_STYLES = {(False, False): "Regular", (False, True): "Italic", (True, False): "Bold",
               (True, True): "Bold Italic"}
# Character styles the exporter makes from Word's formatting.
CHAR_STYLES = {
    "Italic": {"FontStyle": "Italic"}, "Bold": {"FontStyle": "Bold"},
    "Bold Italic": {"FontStyle": "Bold Italic"}, "Small Caps": {"Capitalization": "SmallCaps"},
    "All Caps": {"Capitalization": "AllCaps"}, "Superscript": {"Position": "Superscript"},
    "Subscript": {"Position": "Subscript"}, "Underline": {"Underline": True},
    "Strikethrough": {"StrikeThru": True}, "Footnote Reference": {"Position": "Superscript"},
    "Hyperlink": {},
}
RESET = {"FontStyle": None, "Capitalization": "Normal", "Position": "Normal",
         "Underline": False, "StrikeThru": False}
# Roles whose paragraphs are followed by an unindented first paragraph.
HEAD_ROLES = {"chapter", "part", "heading", "book_title", "subtitle", "author", "toc_title",
              "centered"}
ROLE_BASE = {"body": "Body", "quote": "Block Quote", "verse": "Verse", "list": "List",
             "caption": "Caption", "note": "Footnote", "chapter": "Chapter Title",
             "part": "Part Title", "book_title": "Book Title", "subtitle": "Book Subtitle",
             "author": "Author"}


class ExportError(Exception):
    """Something that stops the export. The message is shown to the user."""


def _half(v):
    return round(v * 2) / 2


def _twips(props, key):
    """A value in points from a summarized Word property ("left=720 firstLine=360")."""
    for part in (props or "").split():
        k, _, v = part.partition("=")
        if k == key and v.lstrip("-").isdigit():
            return int(v) / 20
    return None


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
    def __init__(self, paths, profile=None):
        self.paths = [str(p) for p in paths]
        self.profile = profile or profiles.default_profile()
        self.sm = StyleMap.from_profile(self.profile)
        self.report = []
        self.tmp = None

    # ---- the whole export ----

    def build(self):
        if not self.paths:
            raise ExportError("No .docx files to export.")
        self.docs = [read_docx(p) for p in self.paths]
        self.outline = build_outline(self.docs, self.sm)
        self.doc = Document(name=self.outline.title or os.path.splitext(
            os.path.basename(self.paths[0]))[0])
        self.tmp = tempfile.mkdtemp(prefix="docx2idml-")
        self._geometry()
        self._fonts()
        self._book_styles()
        self.used_char = {}
        self.custom = {}
        stories = self._stories()
        self._paginate(stories)
        self._finish_styles()
        return self.doc

    def cleanup(self):
        if self.tmp:
            shutil.rmtree(self.tmp, ignore_errors=True)
            self.tmp = None

    # ---- page and fonts ----

    def _geometry(self):
        page = self.profile["page"]
        if page.get("trim") == "custom" and page.get("custom_width") and page.get("custom_height"):
            w, h = page["custom_width"], page["custom_height"]
        else:
            w, h = TRIMS.get(page.get("trim"), TRIMS["6x9"])
        doc = self.doc
        doc.width, doc.height = _half(w * 72), _half(h * 72)
        doc.facing = page.get("facing", True)
        # Provisional margins until step 5 calculates them: the profile's, else these.
        margins = {"top": 54, "bottom": 63, "inside": 63, "outside": 54}
        for k, v in (page.get("margins") or {}).items():
            if k in margins and v:
                margins[k] = _half(v * 72)
        doc.margins = margins
        doc.footnotes = dict(self.profile["footnotes"])
        self.measure = doc.width - margins["inside"] - margins["outside"]
        self.text_height = doc.height - margins["top"] - margins["bottom"]

    def _word_font(self, names):
        """The font Word gives the first of these styles found in any file."""
        for doc in self.docs:
            for sid, st in doc.styles.items():
                if norm(st.name) in names:
                    f = doc.resolve_font(sid)
                    if f:
                        return f
        for doc in self.docs:
            sid = doc.default_style.get("paragraph")
            if sid:
                f = doc.resolve_font(sid)
                if f:
                    return f
        return None

    def _fonts(self):
        pf = self.profile["fonts"]
        body = pf.get("body") or self._word_font({"normal"}) or "Minion Pro"
        if not pf.get("body"):
            note = " (a Word template default; choose a book font in the profile)" \
                if body.casefold() in TEMPLATE_FONTS else ""
            self.report.append("Body font: %s, from Word%s." % (body, note))
        heads = pf.get("headings")
        if not heads:
            word = self._word_font({"heading 1"})
            heads = word if word and word.casefold() not in TEMPLATE_FONTS else body
        notes = pf.get("notes") or body
        display = pf.get("display") or heads
        heb = pf.get("hebrew")
        if not heb:
            found = {}
            for d in self.docs:
                for f, n in d.scripts["hebrew"].fonts.items():
                    if f != "(style font)":
                        found[f] = found.get(f, 0) + n
            heb = max(found, key=found.get) if found else HEBREW_FALLBACK
            if any(d.scripts["hebrew"].chars for d in self.docs):
                self.report.append("Hebrew font: %s%s." % (
                    heb, ", from Word" if found else " (none set in Word or the profile)"))
        grk = pf.get("greek")
        if not grk:
            found = {}
            for d in self.docs:
                for f, n in d.scripts["greek"].fonts.items():
                    if f != "(style font)" and f.casefold() not in TEMPLATE_FONTS:
                        found[f] = found.get(f, 0) + n
            grk = max(found, key=found.get) if found else None
        self.fonts = {"body": body, "headings": heads, "notes": notes, "display": display,
                      "hebrew": heb, "greek": grk}

    # ---- styles ----

    def _leading(self, size):
        lead = self.profile.get("leading") or {}
        v, unit = lead.get("value"), lead.get("unit", "pt")
        if not v:
            return _half(size * 1.27)
        if unit == "multiple":
            return _half(size * v)
        if unit == "percent":
            return _half(size * v / 100)
        return v

    def _book_styles(self):
        typo = self.profile["typography"]
        f = self.fonts
        size = 11
        lead = self._leading(size)
        self.body_size, self.body_lead = size, lead
        indent = _half(size * 1.5)
        lang = LANGUAGES.get(self.profile["front_matter"].get("language"), LANGUAGES["en"])
        body = {"FontStyle": "Regular", "PointSize": size, "FirstLineIndent": indent,
                "Justification": "LeftJustified", "Hyphenation": bool(typo["hyphenation"]),
                "Composer": "HL Composer" if typo["paragraph_composer"] else "HL Single",
                "AppliedLanguage": lang, "Ligatures": bool(typo["ligatures"])}
        if typo["oldstyle_figures"]:
            body["OTFFigureStyle"] = "ProportionalOldstyle"
        if typo["widow_orphan_control"]:
            body.update({"KeepFirstLines": 2, "KeepLastLines": 2})
        else:
            body.update({"KeepFirstLines": 1, "KeepLastLines": 1})
        balance = {"BalanceRaggedLines": ("enumeration", "VeeShape")} \
            if typo["balance_ragged_headings"] else {}
        head = {"FirstLineIndent": 0, "Hyphenation": False, "KeepWithNext": 2,
                "KeepFirstLines": 2, "KeepLastLines": 2}
        note_size, note_lead = size - 2, _half((size - 2) * 1.22)
        hang = [("LeftAlign", 18, "")]
        S = Style
        self.doc.paragraph_styles = [
            S("Body", font=f["body"], leading=lead, attrs=body),
            S("Body First", "Body", {"FirstLineIndent": 0}),
            S("Chapter Title", "Body", dict(head, PointSize=_half(size * 1.8),
                                             Justification="CenterAlign", SpaceAfter=lead * 2),
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
                     "Composer": body["Composer"]}),
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
        """A Word style kept under its own name: based on its parent's IDML style (or its
        role's), with what Word sets on it."""
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
        self.custom[name] = Style(name, base)   # placeholder, against loops
        attrs, props = {}, st.props if st else {}
        jc = _prop(props.get("jc"), "val")
        just = {"center": "CenterAlign", "right": "RightAlign", "end": "RightAlign",
                "both": "LeftJustified", "left": "LeftAlign", "start": "LeftAlign"}.get(jc)
        if just:
            attrs["Justification"] = just
        ind = props.get("ind")
        if ind:
            for key, attr in (("left", "LeftIndent"), ("start", "LeftIndent"),
                              ("right", "RightIndent"), ("end", "RightIndent"),
                              ("firstLine", "FirstLineIndent")):
                v = _twips(ind, key)
                if v is not None:
                    attrs[attr] = _half(v)
            hanging = _twips(ind, "hanging")
            if hanging is not None:
                attrs["FirstLineIndent"] = -_half(hanging)
        sp = props.get("spacing")
        if sp:
            for key, attr in (("before", "SpaceBefore"), ("after", "SpaceAfter")):
                v = _twips(sp, key)
                if v is not None:
                    attrs[attr] = _half(min(v, 72))
        bold, italic = props.get("b"), props.get("i")
        if bold is not None or italic is not None:
            base_fs = self._resolved_attrs(base).get("FontStyle", "Regular")
            b = _toggle(bold) if bold is not None else "Bold" in base_fs
            i = _toggle(italic) if italic is not None else "Italic" in base_fs
            attrs["FontStyle"] = FONT_STYLES[(b, i)]
        if _toggle(props.get("caps")):
            attrs["Capitalization"] = "AllCaps"
        elif _toggle(props.get("smallCaps")):
            attrs["Capitalization"] = "SmallCaps"
        if "keepNext" in props and _toggle(props["keepNext"]):
            attrs["KeepWithNext"] = 2
        leading = None
        if "sz" in props and st and st.based_on:
            ratio = docx.resolve_size(style_id) / docx.resolve_size(st.based_on)
            if abs(ratio - 1) > 0.01:
                _a, _f, base_lead = self.doc.resolved(base)
                base_size = self._resolved_attrs(base).get("PointSize", self.body_size)
                attrs["PointSize"] = _half(base_size * ratio)
                if isinstance(base_lead, (int, float)):
                    leading = _half(base_lead * ratio)
        self.custom[name] = Style(name, base, attrs, leading=leading)
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

    def _finish_styles(self):
        self._char_style("Footnote Reference")
        order = list(CHAR_STYLES) + ["Hebrew", "Greek"]
        self.doc.character_styles = sorted(
            self.used_char.values(),
            key=lambda s: (order.index(s.name) if s.name in order else len(order), s.name))
        # Only the styles the book uses, plus the ones every book has.
        used = set(self.para_used) | {"Body", "Body First", "Footnote", "Folio"}
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

    def _paragraphs(self, cp, docx, unit, prev_role, first):
        """Model paragraphs for one content paragraph (an image splits it), with its role."""
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
        if cp.label:
            if m.role in ("chapter", "part", "heading"):
                runs.insert(0, _label_run(cp.label + " "))
            else:
                if style in ("Body", "List"):
                    style = "List Bullet" if cp.list_format == "bullet" else "List Number"
                runs.insert(0, _label_run(cp.label + (cp.label_suffix or "\t")))
        if style == "Body" and unit is not None and unit.type == "bibliography":
            style = "Bibliography"
        if style == "Body" and (first or prev_role in HEAD_ROLES):
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
            for cp in content:
                if cp.index in starts:
                    unit = starts.pop(cp.index)
                    current = [unit, []]
                    stories.append(current)
                    prev_role, first = None, True
                if current is None:
                    # Text before the first unit (the outline found none for it).
                    current = [None, []]
                    stories.append(current)
                if cp.index >= 0 and cp.index < len(docx.paragraphs) and \
                        docx.paragraphs[cp.index].in_toc_field and cp.table is None:
                    continue
                paras, role = self._paragraphs(cp, docx, current[0], prev_role, first)
                if paras:
                    current[1].extend(paras)
                    prev_role, first = role, False
        for _unit, paras in stories:
            for p in paras:
                self.para_used.add(p.style)
                for r in p.runs:
                    for n in r.footnote or ():
                        self.para_used.add(n.style)
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
            cpl = max(10, (measure - attrs.get("LeftIndent", 0)) / (size * 0.48))
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

    def _paginate(self, stories):
        doc = self.doc
        lead = self.body_lead
        sink = _half(lead * 6)
        doc.stories, doc.sections = [], []
        page = 0
        total_est = 0
        for unit, paras in stories:
            kind = unit.kind if unit else "chapter"
            s = 0 if kind in ("display", "part") else sink
            est = self._estimate(paras, s)
            total_est += est
            pages = est + (0 if kind in ("display", "part") else 1)   # one to spare
            doc.stories.append(Story(paras, list(range(page, page + pages)), sink=s, linked=True,
                                     optical_margins=self.body_size
                                     if self.profile["typography"]["optical_margins"] else None))
            title = unit.title if unit and not unit.title.startswith("(") else ""
            doc.sections.append(Section(page, marker=title[:80], start=1 if page == 0 else None))
            page += pages
        doc.page_count = max(page, 1)
        if not doc.sections:
            doc.sections = [Section(0, start=1)]
        m = doc.margins
        top, bottom = m["top"], doc.height - m["bottom"]

        def area(side):
            left = m["outside"] if side == "verso" else m["inside"]
            right = doc.width - (m["inside"] if side == "verso" else m["outside"])
            return left, right
        frames = []
        for side in ("verso", "recto"):
            left, right = area(side)
            frames.append(Frame(side, (top, left, bottom, right), [], primary=True))
            frames.append(Frame(side, (bottom + 14, left, bottom + 28, right),
                                [Paragraph("Folio", [Run(special="page_number")])], key="folio"))
        doc.masters = [Master("A", "Body", frames=frames)]
        self.report.append("%d pages: about %d of text, plus a page to spare after each chapter "
                           "(delete what isn't used)." % (doc.page_count, total_est))


def _label_run(text):
    from .content import CRun
    return CRun(text)


def export(paths, out_dir, profile=None, name=None):
    """Export the manuscript to an export folder (IDML and Links). Returns (IDML path, report
    lines)."""
    from .idml.writer import export_book
    ex = Exporter(paths, profile)
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
