"""Write a Document (model.py) as an IDML package.

Starts from base/ (InDesign's own preferences, colours, fonts and root styles, made by
tools/make_base.py) and adds the book: styles, masters, spreads with pages and text frames,
stories, sections and footnote options. Elements InDesign writes with many attributes (spreads,
pages, frames, stories, sections) are cloned from base/snippets.xml.

Footnotes are written as decided after the Affinity tests (PLAN.md): the Footnote paragraph
style; the number and separator in a run of their own; the Footnote style's settings also on
every run of note text.
"""

import copy
import os
import re
import uuid
import zipfile

from lxml import etree

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "base")
PKG = "http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging"
MIMETYPE = b"application/vnd.adobe.indesign-idml-package"
DOM = "21.5"
NONE_CHAR = "CharacterStyle/$ID/[No character style]"
ROOT_PARA = "$ID/[No paragraph style]"
PAGE_GAP = 180                    # vertical space between spreads, as InDesign lays them out

# Special characters: <?ACE n?> processing instructions.
SPECIAL = {"page_number": "18", "section_marker": "19"}

# Paragraph settings carried onto every run of footnote text (see the module docstring).
NOTE_ATTRS = ("PointSize", "FirstLineIndent", "LeftIndent", "RightIndent", "Justification",
              "FontStyle")


def _parse(path):
    return etree.parse(path, etree.XMLParser(remove_blank_text=True)).getroot()


HEADER = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'


def serialize(root):
    """A part as InDesign writes it: the XML declaration, then the whole document, so the
    <?aid ... type="document" ?> instruction before designmap.xml's root is kept (without it
    InDesign doesn't recognise the file at all)."""
    return HEADER + etree.tostring(root.getroottree(), encoding="UTF-8", xml_declaration=False)


def _num(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return ("%.4f" % v).rstrip("0").rstrip(".")
    return str(v)


def roman(n, upper=False):
    vals = [(1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"), (50, "l"),
            (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")]
    out = ""
    for v, s in vals:
        while n >= v:
            out += s
            n -= v
    return out.upper() if upper else out


class Ids:
    """Self ids that don't clash with those already in the base."""

    def __init__(self):
        top = 0
        for dirpath, _dirs, files in os.walk(BASE):
            for f in files:
                with open(os.path.join(dirpath, f), encoding="utf-8") as fh:
                    for m in re.finditer(r'Self="u([0-9a-f]+)"', fh.read()):
                        top = max(top, int(m.group(1), 16))
        self.n = max(top + 0x100, 0x1000)

    def __call__(self):
        self.n += 1
        return "u%x" % self.n


class Writer:
    def __init__(self, doc):
        self.doc = doc
        self.ids = Ids()
        self.snip = {el.tag: el for el in _parse(os.path.join(BASE, "snippets.xml"))}
        self.parts = {}           # package path -> root element
        self.layer = None

    # ---- package ----

    def write(self, path):
        doc = self.doc
        dm = _parse(os.path.join(BASE, "designmap.xml"))
        self.layer = dm.find("Layer").get("Self")
        self.styles = _parse(os.path.join(BASE, "Resources", "Styles.xml"))
        self.prefs = _parse(os.path.join(BASE, "Resources", "Preferences.xml"))
        self._write_styles()
        self._write_preferences()
        self.section_ids = [self.ids() for _ in doc.sections]
        masters = self._write_masters()
        spreads, page_ids, frames = self._write_spreads(masters)
        stories = self._write_stories(frames)
        self._write_designmap(dm, masters, spreads, stories, page_ids)

        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(zipfile.ZipInfo("mimetype"), MIMETYPE, zipfile.ZIP_STORED)
            files = {"designmap.xml": dm, "Resources/Styles.xml": self.styles,
                     "Resources/Preferences.xml": self.prefs}
            files.update(self.parts)
            for name in ("META-INF/container.xml", "Resources/Graphic.xml", "Resources/Fonts.xml",
                         "XML/Tags.xml", "XML/BackingStory.xml"):
                files.setdefault(name, _parse(os.path.join(BASE, *name.split("/"))))
            for name, root in files.items():
                z.writestr(name, serialize(root))
        return path

    def _wrap(self, kind, el):
        """<idPkg:Kind> wrapper around a part's main element."""
        w = etree.Element("{%s}%s" % (PKG, kind), nsmap={"idPkg": PKG})
        w.set("DOMVersion", DOM)
        w.append(el)
        return w

    # ---- styles and preferences ----

    def _style_el(self, s, kind):
        tag = "ParagraphStyle" if kind == "paragraph" else "CharacterStyle"
        el = etree.Element(tag, Self="%s/%s" % (tag, s.name), Name=s.name, Imported="false")
        if kind == "paragraph":
            el.set("NextStyle", "ParagraphStyle/%s" % (s.next_style or s.name))
        # The housekeeping attributes InDesign writes on every style.
        for k, v in (("SplitDocument", "false"), ("EmitCss", "true"),
                     ("StyleUniqueId", str(uuid.uuid5(uuid.NAMESPACE_URL, tag + "/" + s.name))),
                     ("IncludeClass", "true"), ("ExtendedKeyboardShortcut", "0 0 0"),
                     ("EpubAriaRole", "")):
            el.set(k, v)
        if kind == "paragraph":
            for k in ("EmptyNestedStyles", "EmptyLineStyles", "EmptyGrepStyles"):
                el.set(k, "true")
        el.set("KeyboardShortcut", "0 0")
        for k, v in s.attrs.items():
            el.set(k, _num(v))
        props = etree.SubElement(el, "Properties")
        based = etree.SubElement(props, "BasedOn")
        if s.based_on:
            based.set("type", "object")
            based.text = "%s/%s" % (tag, s.based_on)
        else:
            based.set("type", "string")
            based.text = ROOT_PARA if kind == "paragraph" else "$ID/[No character style]"
        self._font_leading(props, s.font, s.leading)
        return el

    @staticmethod
    def _font_leading(props, font, leading):
        if font:
            etree.SubElement(props, "AppliedFont", type="string").text = font
        if leading is not None:
            if leading == "Auto":
                etree.SubElement(props, "Leading", type="enumeration").text = "Auto"
            else:
                etree.SubElement(props, "Leading", type="unit").text = _num(leading)

    def _write_styles(self):
        pg = self.styles.find("RootParagraphStyleGroup")
        for s in self.doc.paragraph_styles:
            pg.append(self._style_el(s, "paragraph"))
        cg = self.styles.find("RootCharacterStyleGroup")
        for s in self.doc.character_styles:
            cg.append(self._style_el(s, "character"))

    def _write_preferences(self):
        doc, p = self.doc, self.prefs
        dp = p.find("DocumentPreference")
        dp.set("PageWidth", _num(doc.width))
        dp.set("PageHeight", _num(doc.height))
        dp.set("FacingPages", _num(doc.facing))
        # PagesPerDocument stays as InDesign writes it (1): it is the page count for a new
        # document, not this one's. Set to the real count, InDesign adds that many pages before
        # the file's own when opening it.
        mp = p.find("MarginPreference")
        m = doc.margins
        for k, v in (("Top", m["top"]), ("Bottom", m["bottom"]), ("Left", m["inside"]),
                     ("Right", m["outside"])):
            mp.set(k, _num(v))
        mp.set("ColumnsPositions", "0 %s" % _num(self.measure))
        fo = p.find("FootnoteOption")
        fn = doc.footnotes
        _attrs, _font, leading = doc.resolved(doc.footnote_style)
        lead = leading if isinstance(leading, (int, float)) else 11
        any_rule = fn.get("rule", False) or fn.get("continuation_rule", True)
        fo.set("FootnoteTextStyle", "ParagraphStyle/%s" % doc.footnote_style)
        fo.set("FootnoteMarkerStyle", "CharacterStyle/%s" % doc.footnote_marker_style
               if doc.style(doc.footnote_marker_style, "character") else NONE_CHAR)
        fo.set("SeparatorText", doc.footnote_separator)
        fo.set("Spacer", _num(fn.get("space_above", 12)))
        fo.set("SpaceBetween", _num(fn.get("space_between", 3)))
        fo.set("FootnoteFirstBaselineOffset", "LeadingOffset")
        fo.set("FootnoteMinimumFirstBaselineOffset",
               _num(lead + (fn.get("space_below_rule", 6) if any_rule else 0)))
        fo.set("NoSplitting", "false")
        fo.set("RuleOn", _num(fn.get("rule", False)))
        fo.set("ContinuingRuleOn", _num(fn.get("continuation_rule", True)))
        for prefix in ("Rule", "ContinuingRule"):
            fo.set(prefix + "Width", _num(fn.get("rule_length", 72)))
            fo.set(prefix + "LineWeight", "0.5")
            fo.set(prefix + "Offset", "0")
            fo.set(prefix + "LeftIndent", "0")
        restart = fo.find("Properties/RestartNumbering")
        if restart is not None:
            restart.text = ("DontRestart" if fn.get("numbering") == "continuous"
                            else "SectionRestart")

    # ---- geometry ----

    @property
    def measure(self):
        m = self.doc.margins
        return self.doc.width - m["inside"] - m["outside"]

    def _is_recto(self, i):
        """In facing documents a page's side follows its number, as in InDesign: odd numbers
        are rectos, so a section restarting at 1 after an odd page puts two rectos together."""
        if not self.doc.facing:
            return True
        if not hasattr(self, "_numbers"):
            self._numbers = [n for n, _sec in self._page_numbers()]
        return self._numbers[i] % 2 == 1

    def _page_left(self, i):
        """x of the page's left edge in spread coordinates."""
        if not self.doc.facing:
            return -self.doc.width / 2
        return 0 if self._is_recto(i) else -self.doc.width

    def _spreads(self):
        """Pages grouped into spreads: a verso starts a spread, a recto ends one."""
        n = self.doc.page_count
        if not self.doc.facing:
            return [[i] for i in range(n)]
        groups = []
        for i in range(n):
            if not groups or not self._is_recto(i) or self._is_recto(groups[-1][-1]):
                groups.append([i])
            else:
                groups[-1].append(i)
        return groups

    def _page_numbers(self):
        """[(page number, its section)] for every page."""
        doc = self.doc
        out = []
        sections = sorted(doc.sections, key=lambda s: s.page)
        number = 0
        for i in range(doc.page_count):
            sec = [s for s in sections if s.page <= i][-1]
            if sec.page == i:
                number = sec.start if sec.start is not None else number + 1
            else:
                number += 1
            out.append((number, sec))
        return out

    def _page_names(self):
        names = []
        for number, sec in self._page_numbers():
            if sec.numbering == "LowerRoman":
                names.append(roman(number))
            elif sec.numbering == "UpperRoman":
                names.append(roman(number, True))
            else:
                names.append(str(number))
        return names

    def _descriptor(self, page, number, sec):
        """Page number information, as InDesign records it on each page: prefix, numbering
        style, continue numbering, include prefix, the number (twice), section marker."""
        props = page.find("Properties")
        desc = etree.Element("Descriptor", type="list")
        for typ, text in (("string", ""), ("enumeration", sec.numbering),
                          ("boolean", _num(sec.start is None)), ("boolean", "false"),
                          ("long", str(number)), ("long", str(number)), ("string", sec.marker)):
            etree.SubElement(desc, "ListItem", type=typ).text = text
        props.insert(0, desc)

    def _page_el(self, self_id, x, name, master_id, alt_layout, master_page=False):
        page = copy.deepcopy(self.snip["Page"] if not master_page else
                             self.snip["MasterSpread"].find("Page"))
        page.set("Self", self_id)
        page.set("ItemTransform", "1 0 0 1 %s %s" % (_num(x), _num(-self.doc.height / 2)))
        page.set("GeometricBounds", "0 0 %s %s" % (_num(self.doc.height), _num(self.doc.width)))
        page.set("Name", name)
        page.set("AppliedMaster", master_id or "n")
        page.set("OverrideList", "")
        page.set("AppliedAlternateLayout", alt_layout)
        desc = page.find("Properties/Descriptor")
        if desc is not None:
            desc.getparent().remove(desc)
        m = self.doc.margins
        mp = page.find("MarginPreference")
        for k, v in (("Top", m["top"]), ("Bottom", m["bottom"]), ("Left", m["inside"]),
                     ("Right", m["outside"])):
            mp.set(k, _num(v))
        mp.set("ColumnsPositions", "0 %s" % _num(self.measure))
        return page

    def _frame_el(self, story_id, left, top, width, height, master=False, valign=None):
        f = copy.deepcopy(self.snip["TextFrame"])
        if master:
            f.set("AllowOverrides", "true")
        if valign:
            f.find("TextFramePreference").set("VerticalJustification", valign)
        fid = self.ids()
        f.set("Self", fid)
        f.set("ParentStory", story_id)
        f.set("PreviousTextFrame", "n")
        f.set("NextTextFrame", "n")
        f.set("ItemLayer", self.layer)
        f.set("ItemTransform", "1 0 0 1 %s %s" % (_num(left + width / 2), _num(top + height / 2)))
        hw, hh = _num(width / 2), _num(height / 2)
        pts = f.findall("Properties/PathGeometry/GeometryPathType/PathPointArray/PathPointType")
        for pt, (x, y) in zip(pts, (("-" + hw, "-" + hh), ("-" + hw, hh), (hw, hh), (hw, "-" + hh))):
            xy = "%s %s" % (x, y)
            pt.set("Anchor", xy)
            pt.set("LeftDirection", xy)
            pt.set("RightDirection", xy)
        f.find("TextFramePreference").set("TextColumnFixedWidth", _num(width))
        return f

    # ---- masters, spreads ----

    def _write_masters(self):
        out = {}
        for m in self.doc.masters:
            out[m.name] = self.ids()
        frame_ids = {}            # (master name, frame key, side) -> frame id
        self.master_stories = []  # (story id, paragraphs)
        for m in self._parents_first():
            ms = etree.Element("MasterSpread", self.snip["MasterSpread"].attrib)
            mid = out[m.name]
            ms.set("Self", mid)
            ms.set("Name", m.name)
            ms.set("NamePrefix", m.prefix)
            ms.set("BaseName", m.base)
            ms.set("PageCount", "2" if self.doc.facing else "1")
            ms.set("PrimaryTextFrame", "n")
            parent = out.get(m.based_on) if m.based_on else None
            if self.doc.facing:
                sides = [("verso", -self.doc.width), ("recto", 0)]
            else:
                sides = [("recto", -self.doc.width / 2)]
            pages = {}
            for side, x in sides:
                page = self._page_el(self.ids(), x, m.prefix, parent, "n", master_page=True)
                pairs = []
                for key in m.removes:
                    pid = frame_ids.get((m.based_on, key, side))
                    if pid:
                        pairs += [pid, "n"]
                page.set("OverrideList", " ".join(pairs))
                ms.append(page)
                pages[side] = x
            for fr in m.frames:
                x = pages.get(fr.side, pages.get("recto"))
                top, left, bottom, right = fr.bounds
                sid = self.ids()
                f = self._frame_el(sid, x + left, -self.doc.height / 2 + top, right - left,
                                   bottom - top, master=True, valign=fr.valign)
                ms.append(f)
                self.master_stories.append((sid, fr.paragraphs))
                if fr.key:
                    frame_ids[(m.name, fr.key, fr.side)] = f.get("Self")
            self.parts["MasterSpreads/MasterSpread_%s.xml" % mid] = self._wrap("MasterSpread", ms)
        return out

    def _parents_first(self):
        done, out = set(), []
        masters = {m.name: m for m in self.doc.masters}

        def visit(m):
            if m.name in done:
                return
            done.add(m.name)
            if m.based_on in masters:
                visit(masters[m.based_on])
            out.append(m)
        for m in self.doc.masters:
            visit(m)
        return out

    def _write_spreads(self, masters):
        doc = self.doc
        default_master = masters[doc.masters[0].name] if doc.masters else None
        names = self._page_names()
        numbers = self._page_numbers()
        page_ids = [self.ids() for _ in range(doc.page_count)]
        story_ids = [self.ids() for _ in doc.stories]
        frames = {k: [] for k in range(len(doc.stories))}
        spreads = []
        for k, group in enumerate(self._spreads()):
            sp = etree.Element("Spread", self.snip["Spread"].attrib)
            for child in self.snip["Spread"]:
                sp.append(copy.deepcopy(child))
            sid = self.ids()
            sp.set("Self", sid)
            sp.set("ItemTransform", "1 0 0 1 0 %s" % _num(k * (doc.height + PAGE_GAP)))
            sp.set("PageCount", str(len(group)))
            # The spine's position among the spread's pages: after the verso, if there is one.
            sp.set("BindingLocation", "0" if self._is_recto(group[0]) else "1")
            for i in group:
                mname = doc.page_masters.get(i)
                mid = masters.get(mname, default_master) if mname != "" else None
                page = self._page_el(page_ids[i], self._page_left(i), names[i], mid,
                                     self.section_ids[0])
                self._descriptor(page, *numbers[i])
                sp.append(page)
            for i in group:
                for k2, story in enumerate(doc.stories):
                    if i in story.pages:
                        m = doc.margins
                        recto = self._is_recto(i)
                        left = self._page_left(i) + (m["inside"] if recto else m["outside"])
                        sink = story.sink if i == story.pages[0] else 0
                        top = -doc.height / 2 + m["top"] + sink
                        height = doc.height - m["top"] - m["bottom"] - sink
                        f = self._frame_el(story_ids[k2], left, top, self.measure, height)
                        sp.append(f)
                        frames[k2].append(f)
            self.parts["Spreads/Spread_%s.xml" % sid] = self._wrap("Spread", sp)
            spreads.append(sid)
        for k2, fl in frames.items():
            for a, b in zip(fl, fl[1:]):
                a.set("NextTextFrame", b.get("Self"))
                b.set("PreviousTextFrame", a.get("Self"))
        self.story_ids = story_ids
        return spreads, page_ids, frames

    # ---- stories ----

    def _write_stories(self, frames):
        out = []
        todo = [(self.story_ids[k], story.paragraphs) for k, story in enumerate(self.doc.stories)]
        for sid, paragraphs in self.master_stories + todo:
            st = etree.Element("Story", self.snip["Story"].attrib)
            for child in self.snip["Story"]:
                st.append(copy.deepcopy(child))
            st.set("Self", sid)
            for n, para in enumerate(paragraphs):
                st.append(self._paragraph(para, last=(n == len(paragraphs) - 1)))
            self.parts["Stories/Story_%s.xml" % sid] = self._wrap("Story", st)
            out.append(sid)
        return out

    def _csr(self, style, attrs=None, font=None, leading=None):
        el = etree.Element("CharacterStyleRange",
                           AppliedCharacterStyle="CharacterStyle/%s" % style if style else NONE_CHAR)
        for k, v in (attrs or {}).items():
            el.set(k, _num(v))
        if font or leading is not None:
            self._font_leading(etree.SubElement(el, "Properties"), font, leading)
        return el

    @staticmethod
    def _content(parent, text):
        """Text as Content elements; a line break inside a paragraph is U+2028."""
        if text:
            etree.SubElement(parent, "Content").text = text.replace("\n", " ")

    def _paragraph(self, para, last, note=None, number=False):
        """note: (attrs, font, leading) of the Footnote style, for text inside a footnote;
        number: write the footnote number first (a note's first paragraph)."""
        psr = etree.Element("ParagraphStyleRange",
                            AppliedParagraphStyle="ParagraphStyle/%s" % para.style)
        for k, v in para.attrs.items():
            psr.set(k, _num(v))
        if number:
            # The footnote number and separator in a run of their own.
            attrs, font, leading = note
            num = self._csr(None, attrs, font, leading)
            c = etree.SubElement(num, "Content")
            pi = etree.ProcessingInstruction("ACE", "4")
            pi.tail = self.doc.footnote_separator
            c.append(pi)
            psr.append(num)
        for run in para.runs:
            if run.footnote is not None:
                csr = self._csr(self.doc.footnote_marker_style
                                if self.doc.style(self.doc.footnote_marker_style, "character")
                                else None)
                csr.append(self._footnote(run.footnote))
                psr.append(csr)
                continue
            if note is not None:
                attrs, font, leading = note
                merged = dict(attrs)
                merged.update(run.attrs)
                csr = self._csr(run.style, merged, font, leading)
            else:
                csr = self._csr(run.style, run.attrs)
            if run.special:
                c = etree.SubElement(csr, "Content")
                pi = etree.ProcessingInstruction("ACE", SPECIAL[run.special])
                pi.tail = run.text.replace("\n", "\u2028") if run.text else None
                c.append(pi)
            else:
                self._content(csr, run.text)
            psr.append(csr)
        if not last:
            if not len(psr) or psr[-1].find("Footnote") is not None:
                psr.append(self._csr(None))
            etree.SubElement(psr[-1], "Br")
        return psr

    def _footnote(self, paragraphs):
        fn = etree.Element("Footnote")
        attrs, font, leading = self.doc.resolved(self.doc.footnote_style)
        note = ({k: v for k, v in attrs.items() if k in NOTE_ATTRS}, font, leading)
        for n, para in enumerate(paragraphs):
            fn.append(self._paragraph(para, last=(n == len(paragraphs) - 1), note=note,
                                      number=(n == 0)))
        return fn

    # ---- designmap ----

    def _write_designmap(self, dm, masters, spreads, stories, page_ids):
        doc = self.doc
        dm.set("Name", doc.name + ".indd")
        backing = dm.find("{%s}BackingStory" % PKG)
        story_list = (dm.get("StoryList") or "").split() + stories
        dm.set("StoryList", " ".join(story_list))
        layers = dm.findall("Layer")
        anchor = layers[-1] if layers else dm.find("{%s}Tags" % PKG)
        pos = list(dm).index(anchor) + 1
        new = []
        for mid in masters.values():
            new.append(etree.Element("{%s}MasterSpread" % PKG,
                                     src="MasterSpreads/MasterSpread_%s.xml" % mid))
        for sid in spreads:
            new.append(etree.Element("{%s}Spread" % PKG, src="Spreads/Spread_%s.xml" % sid))
        sections = sorted(doc.sections, key=lambda s: s.page)
        for n, sec in enumerate(sections):
            el = copy.deepcopy(self.snip["Section"])
            el.set("Self", self.section_ids[n])
            end = sections[n + 1].page if n + 1 < len(sections) else doc.page_count
            el.set("Length", str(end - sec.page))
            # As InDesign writes them: the layout's name on the first section only, and each
            # section's AlternateLayoutLength the pages from its start to the end.
            el.set("AlternateLayoutLength", str(doc.page_count - sec.page))
            if n:
                el.set("AlternateLayout", "")
            el.set("PageStart", page_ids[sec.page])
            el.set("Marker", sec.marker)
            el.set("ContinueNumbering", _num(sec.start is None))
            if sec.start is not None:
                el.set("PageNumberStart", str(sec.start))
            elif "PageNumberStart" in el.attrib:
                del el.attrib["PageNumberStart"]
            el.set("IncludeSectionPrefix", "false")
            style = el.find("Properties/PageNumberStyle")
            if style is not None:
                style.text = sec.numbering
            new.append(el)
        for el in new:
            dm.insert(pos, el)
            pos += 1
        pos = list(dm).index(backing) + 1
        for sid in stories:
            dm.insert(pos, etree.Element("{%s}Story" % PKG, src="Stories/Story_%s.xml" % sid))
            pos += 1


def write_idml(doc, path):
    return Writer(doc).write(path)
