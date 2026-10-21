"""Summarize an IDML package: what a reference file contains, in a form that can be compared
with the generator's output for the same feature.

    python tools/idml_inspect.py file.idml [--json]

Reports the page setup, masters (based on, primary text frame, threading, special characters),
pages (master, master items overridden), sections, stories (styles, footnotes, special
characters, text variables, languages, local overrides), styles, TOC styles and the preferences
the converter cares about (footnotes, smart text reflow, baseline grid). Development tool; not
part of the shipped program.
"""

import json
import re
import sys
import zipfile
from collections import Counter, OrderedDict

from lxml import etree

PKG = "http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging"

# <?ACE n?> processing instructions: InDesign's special characters.
ACE = {"1": "auto page number", "3": "next page number", "4": "footnote number",
       "7": "indent to here", "8": "right indent tab", "18": "current page number",
       "19": "section marker", "21": "end nested style"}

# Character attributes that are local overrides when set on a CharacterStyleRange.
_NOT_OVERRIDES = {"AppliedCharacterStyle", "AppliedParagraphStyle", "Self",
                  "ParagraphBreakType", "AppliedConditions"}


def _parse(z, name):
    return etree.fromstring(z.read(name), etree.XMLParser(resolve_entities=False, huge_tree=True))


def _local(tag):
    return etree.QName(tag).localname if isinstance(tag, str) else ""


def _ref_name(value):
    """'ParagraphStyle/$ID/NormalParagraphStyle' -> '[Basic Paragraph]'-ish readable name."""
    if not value:
        return value
    name = value.split("/", 1)[1] if "/" in value else value
    name = name.replace("$ID/", "").replace("%3a", ":")
    return {"NormalParagraphStyle": "[Basic Paragraph]", "[No character style]": "[None]",
            "[No paragraph style]": "[No paragraph style]", "kSameStyleWithBracket": "[Same style]"}.get(name, name)


def _prop(el, name):
    """A property written as an attribute or as <Properties><name>value</name></Properties>."""
    if el.get(name) is not None:
        return el.get(name)
    p = el.find("Properties/" + name)
    if p is not None:
        return p.text if len(p) == 0 else " ".join((c.text or "") for c in p)
    return None


def _frame_info(el):
    return OrderedDict([
        ("id", el.get("Self")), ("story", el.get("ParentStory")),
        ("prev", el.get("PreviousTextFrame")), ("next", el.get("NextTextFrame")),
        ("transform", el.get("ItemTransform"))])


def inspect(path):
    z = zipfile.ZipFile(path)
    names = z.namelist()
    info = OrderedDict()
    first = z.infolist()[0]
    info["package"] = OrderedDict([
        ("parts", len(names)),
        ("mimetype_first_stored", first.filename == "mimetype" and first.compress_type == 0),
        ("dom_versions", sorted({v for v in (_dom_version(z, n) for n in names) if v}))])

    dm = _parse(z, "designmap.xml")
    prefs = _parse(z, "Resources/Preferences.xml")
    styles = _parse(z, "Resources/Styles.xml")

    docpref = prefs.find("DocumentPreference")
    info["page"] = OrderedDict([
        ("width", _f(docpref.get("PageWidth"))), ("height", _f(docpref.get("PageHeight"))),
        ("facing", docpref.get("FacingPages")),
        ("bleed", [docpref.get(k) for k in ("DocumentBleedTopOffset", "DocumentBleedBottomOffset",
                                            "DocumentBleedInsideOrLeftOffset",
                                            "DocumentBleedOutsideOrRightOffset")])])
    info["languages"] = [_ref_name(l.get("Name")) for l in dm.findall("Language")]

    # Masters.
    masters = OrderedDict()
    master_items = {}
    for n in names:
        if not n.startswith("MasterSpreads/"):
            continue
        ms = _parse(z, n).find("MasterSpread")
        frames = [_frame_info(tf) for tf in ms.iter("TextFrame")]
        for tf in ms.iter():
            if tf.get("Self") and _local(tf.tag) in ("TextFrame", "Rectangle", "GraphicLine",
                                                     "Oval", "Polygon", "Group"):
                master_items[tf.get("Self")] = (ms.get("Name"), _local(tf.tag))
        pages = ms.findall("Page")
        removed = []
        for pg in pages:
            pairs = (pg.get("OverrideList") or "").split()
            removed += [pairs[i] for i in range(0, len(pairs) - 1, 2) if pairs[i + 1] == "n"]
        masters[ms.get("Self")] = OrderedDict([
            ("name", ms.get("Name")),
            ("pages", len(pages)),
            ("based_on", [p.get("AppliedMaster") for p in pages]),
            ("parent_items_removed", removed),
            ("primary_text_frame", ms.get("PrimaryTextFrame")),
            ("text_frames", frames)])
    for m in masters.values():
        m["based_on"] = sorted({masters[b]["name"] if b in masters else b
                                for b in m["based_on"] if b and b != "n"}) or None

    # Stories (read before pages so frames can name their story's first words).
    stories = OrderedDict()
    for n in names:
        if n.startswith("Stories/"):
            st = _parse(z, n).find("Story")
            stories[st.get("Self")] = _story(st)

    # Pages, in spread order from designmap.
    pages = []
    for ref in dm.iter("{%s}Spread" % PKG):
        sp = _parse(z, ref.get("src")).find("Spread")
        for pg in sp.findall("Page"):
            pairs = (pg.get("OverrideList") or "").split()
            overrides = [OrderedDict([("master_item", pairs[i]),
                                      ("master", master_items.get(pairs[i], ("?", "?"))[0]),
                                      ("page_item", pairs[i + 1])])
                         for i in range(0, len(pairs) - 1, 2)]
            pages.append(OrderedDict([
                ("name", pg.get("Name")), ("id", pg.get("Self")),
                ("master", masters[pg.get("AppliedMaster")]["name"]
                    if pg.get("AppliedMaster") in masters else
                    None if pg.get("AppliedMaster") in (None, "n") else pg.get("AppliedMaster")),
                ("side", "verso" if (pg.get("ItemTransform") or "").split()[4:5] and
                         float(pg.get("ItemTransform").split()[4]) < 0 else "recto"),
                ("overrides", overrides)]))
        spread_pages = pages[len(pages) - len(sp.findall("Page")):]
        for tf in sp.iter("TextFrame"):
            if tf.getparent() is not None and _local(tf.getparent().tag) not in ("Spread", "Group"):
                continue   # anchored in a story
            fi = _frame_info(tf)
            fi["page"] = _page_of(tf, sp, spread_pages)
            stories.get(tf.get("ParentStory"), {}).setdefault("frames", []).append(fi)
        for gr in sp.iter("Rectangle"):
            link = gr.find(".//Link")
            if link is not None:
                wrap = gr.find("TextWrapPreference")
                info.setdefault("links", []).append(OrderedDict([
                    ("uri", link.get("LinkResourceURI")),
                    ("wrap", wrap.get("TextWrapMode") if wrap is not None else None),
                    ("page", _page_of(gr, sp, spread_pages))]))
    info["masters"] = list(masters.values())
    info["pages"] = pages

    page_names = {p["id"]: p["name"] for p in pages}
    info["sections"] = [OrderedDict([
        ("start_page", page_names.get(s.get("PageStart"), s.get("PageStart"))),
        ("marker", s.get("Marker")), ("continue_numbering", s.get("ContinueNumbering")),
        ("start", s.get("PageNumberStart")), ("style", _prop(s, "PageNumberStyle")),
        ("prefix", s.get("SectionPrefix"))]) for s in dm.findall("Section")]

    for v in stories.values():
        if v.get("frames"):
            v["frames"] = _thread_order(v["frames"])
    info["stories"] = [dict(id=k, **v) for k, v in stories.items()]
    info["styles"] = _styles(styles)
    info["preferences"] = _prefs(prefs)
    return info


def _center_x(el):
    """Horizontal center of a page item in spread coordinates."""
    xs = []
    for pp in el.iter("PathPointType"):
        a = (pp.get("Anchor") or "").split()
        if a:
            xs.append(float(a[0]))
    t = [float(v) for v in (el.get("ItemTransform") or "1 0 0 1 0 0").split()]
    x = sum(xs) / len(xs) if xs else 0.0
    for anc in el.iterancestors():
        if _local(anc.tag) == "Spread":
            break
        if anc.get("ItemTransform"):
            at = [float(v) for v in anc.get("ItemTransform").split()]
            x = x * at[0] + at[4]
    return x * t[0] + t[4]


def _page_of(el, spread, spread_pages):
    """Name of the page a spread item sits on (by its center)."""
    x = _center_x(el)
    best = None
    for pg, info in zip(spread.findall("Page"), spread_pages):
        left = float(pg.get("ItemTransform").split()[4])
        width = float(pg.get("GeometricBounds").split()[3]) - float(pg.get("GeometricBounds").split()[1])
        if left <= x <= left + width:
            return info["name"]
        best = best or info["name"]
    return best


def _thread_order(frames):
    by_id = {f["id"]: f for f in frames}
    firsts = [f for f in frames if f["prev"] in (None, "n") or f["prev"] not in by_id]
    out = []
    for f in firsts:
        while f and f not in out:
            out.append(f)
            f = by_id.get(f["next"])
    return out + [f for f in frames if f not in out]


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return v


def _dom_version(z, name):
    if not name.endswith(".xml") or name.startswith("META-INF/"):
        return None
    head = z.read(name)[:600].decode("utf-8", "replace")
    m = re.search(r'DOMVersion="([^"]+)"', head)
    return m.group(1) if m else None


def _story(st):
    pstyles, cstyles, langs, overrides = Counter(), Counter(), Counter(), Counter()
    aces = Counter()
    footnotes = variables = tables = anchored = 0
    text = []
    for psr in st.iter("ParagraphStyleRange"):
        pstyles[_ref_name(psr.get("AppliedParagraphStyle"))] += 1
    for csr in st.iter("CharacterStyleRange"):
        cs = _ref_name(csr.get("AppliedCharacterStyle"))
        if cs and cs != "[None]":
            cstyles[cs] += 1
        lang = csr.get("AppliedLanguage") or _prop(csr, "AppliedLanguage")
        if lang:
            langs[_ref_name(lang)] += 1
        for k in csr.attrib:
            if k not in _NOT_OVERRIDES and k != "AppliedLanguage":
                overrides[k] += 1
        for p in csr.findall("Properties/*"):
            if p.tag not in ("AppliedFont", "AppliedLanguage", "Leading"):
                overrides[p.tag] += 1
            elif p.tag == "AppliedFont":
                overrides["AppliedFont"] += 1
    for el in st.iter():
        tag = _local(el.tag)
        if tag == "Footnote":
            footnotes += 1
        elif tag == "TextVariableInstance":
            variables += 1
        elif tag == "Table":
            tables += 1
        elif tag in ("Rectangle", "TextFrame") and el.getparent() is not None:
            anchored += 1
        elif el.tag is etree.ProcessingInstruction and el.target == "ACE":
            code = (el.text or "").strip()
            aces[ACE.get(code, "ACE " + code)] += 1
        if tag == "Content" and len(" ".join(text)) < 60 and not _in_footnote(el):
            text.append(el.text or "")
    out = OrderedDict([
        ("start", " ".join(" ".join(text).split())[:60]),
        ("toc_style", _ref_name(st.get("AppliedTOCStyle")) if st.get("AppliedTOCStyle") not in
            (None, "n") else None),
        ("paragraph_styles", dict(pstyles.most_common())),
        ("character_styles", dict(cstyles.most_common()))])
    if footnotes:
        out["footnotes"] = footnotes
    if aces:
        out["special_characters"] = dict(aces)
    if variables:
        out["text_variables"] = variables
    if tables:
        out["tables"] = tables
    if anchored:
        out["anchored_objects"] = anchored
    if langs:
        out["languages"] = dict(langs)
    if overrides:
        out["local_overrides"] = dict(overrides.most_common())
    return out


def _in_footnote(el):
    for a in el.iterancestors():
        if _local(a.tag) == "Footnote":
            return True
    return False


_STYLE_KEYS = ("PointSize", "Leading", "FontStyle", "Justification", "FirstLineIndent",
               "Composer", "Hyphenation", "CharacterDirection", "ParagraphDirection",
               "Capitalization", "Position", "OTFFigureStyle", "Ligatures", "StartParagraph",
               "AlignToBaseline", "BalanceRaggedLines", "SpaceBefore", "SpaceAfter")


def _styles(root):
    out = OrderedDict()
    for kind, tag in (("paragraph", "ParagraphStyle"), ("character", "CharacterStyle"),
                      ("table", "TableStyle"), ("cell", "CellStyle"), ("object", "ObjectStyle")):
        items = []
        for s in root.iter(tag):
            d = OrderedDict([("name", _ref_name(s.get("Name")))])
            based = _prop(s, "BasedOn")
            if based and "No paragraph style" not in based and "No character style" not in based:
                d["based_on"] = _ref_name(based)
            for k in ("AppliedFont", "AppliedLanguage"):
                v = _prop(s, k)
                if v:
                    d[k] = _ref_name(v) if k == "AppliedLanguage" else v
            for k in _STYLE_KEYS:
                if s.get(k) is not None:
                    d[k] = s.get(k)
            if tag == "CharacterStyle":
                d["defines"] = sorted(k for k in s.attrib if not k.startswith("Epub") and
                                      k not in ("Self", "Name", "Imported",
                                                                       "KeyboardShortcut",
                                                                       "SplitDocument",
                                                                       "EmitCss",
                                                                       "StyleUniqueId",
                                                                       "IncludeClass",
                                                                       "ExtendedKeyboardShortcut"))
            items.append(d)
        out[kind] = items
    toc = []
    for t in root.iter("TOCStyle"):
        toc.append(OrderedDict([
            ("name", _ref_name(t.get("Name"))), ("title", t.get("Title")),
            ("entries", [OrderedDict([("style", _ref_name(e.get("Name"))),
                                      ("level", e.get("Level")),
                                      ("format", _ref_name(_prop(e, "FormatStyle"))),
                                      ("page_number", e.get("PageNumberPosition")),
                                      ("separator", e.get("Separator"))])
                         for e in t.findall("TOCStyleEntry")])]))
    out["toc"] = toc
    return out


def _prefs(root):
    out = OrderedDict()
    picks = {"FootnoteOption": ("SeparatorText", "RestartNumbering", "FootnoteTextStyle",
                                "FootnoteMarkerStyle", "RuleOn", "NoSplitting", "SpaceBetween",
                                "StartAt", "FootnoteNumberingStyle"),
             "TextPreference": ("SmartTextReflow", "AddPages", "LimitToMasterTextFrames",
                                "DeleteEmptyPages"),
             "GridPreference": ("BaselineStart", "BaselineDivision", "BaselineGridShown",
                                "BaselineGridRelativeOption")}
    for tag, keys in picks.items():
        el = root.find(tag)
        if el is None:
            continue
        d = OrderedDict()
        for k in keys:
            v = el.get(k)
            if v is None:
                v = _prop(el, k)
            if v is not None:
                d[k] = _ref_name(v) if "Style" in k and "/" in v else v
        out[tag] = d
    return out


def render(info):
    lines = []
    add = lines.append
    pk = info["package"]
    add("Package: %d parts; mimetype first and stored: %s; DOMVersion %s"
        % (pk["parts"], pk["mimetype_first_stored"], ", ".join(pk["dom_versions"])))
    pg = info["page"]
    add("Page: %s x %s pt (%.2f x %.2f in), facing %s, bleed %s"
        % (pg["width"], pg["height"], pg["width"] / 72, pg["height"] / 72, pg["facing"],
           "/".join(str(b) for b in pg["bleed"])))
    add("Languages: " + ", ".join(info["languages"]))
    add("")
    add("Masters")
    for m in info["masters"]:
        add("  %s (%d pages)%s, primary text frame: %s%s" % (
            m["name"], m["pages"], ", based on " + ", ".join(m["based_on"]) if m["based_on"] else "",
            m["primary_text_frame"],
            ", removes parent items " + " ".join(m["parent_items_removed"])
            if m["parent_items_removed"] else ""))
        for f in m["text_frames"]:
            add("    frame %s story %s prev %s next %s" % (f["id"], f["story"], f["prev"], f["next"]))
    add("")
    add("Pages")
    for p in info["pages"]:
        ov = "; ".join("%s(%s) -> %s" % (o["master_item"], o["master"],
                                         "removed" if o["page_item"] == "n" else o["page_item"])
                       for o in p["overrides"])
        add("  %-4s %-6s %-12s %s" % (p["name"], p["side"], p["master"] or "(none)",
                                     "overrides " + ov if ov else ""))
    add("")
    add("Sections")
    for s in info["sections"]:
        add("  from page %s: %s, start %s, continue %s, marker \"%s\"" % (
            s["start_page"], s["style"] or "(default)", s["start"], s["continue_numbering"],
            s["marker"]))
    add("")
    add("Stories")
    for s in info["stories"]:
        frames = s.get("frames", [])
        add("  %s: \"%s\" %s" % (s["id"], s["start"],
                                 "(TOC: %s)" % s["toc_style"] if s["toc_style"] else ""))
        if frames:
            add("    frames: " + " -> ".join("%s(p%s)" % (f["id"], f["page"]) for f in frames))
        for key in ("paragraph_styles", "character_styles", "special_characters", "languages",
                    "local_overrides"):
            if s.get(key):
                add("    %s: %s" % (key.replace("_", " "),
                                    ", ".join("%s %d" % kv for kv in s[key].items())))
        for key in ("footnotes", "text_variables", "tables", "anchored_objects"):
            if s.get(key):
                add("    %s: %d" % (key.replace("_", " "), s[key]))
    if info.get("links"):
        add("")
        add("Links")
        for l in info["links"]:
            add("  %s on page %s (wrap %s)" % (l["uri"], l["page"], l["wrap"]))
    add("")
    add("Paragraph styles")
    for s in info["styles"]["paragraph"]:
        add("  " + _style_line(s))
    add("Character styles")
    for s in info["styles"]["character"]:
        add("  %s: defines %s" % (s["name"], ", ".join(s.get("defines", [])) or "nothing"))
    for t in info["styles"]["toc"]:
        add("TOC style %s, title \"%s\"" % (t["name"], t["title"]))
        for e in t["entries"]:
            add("  level %s: %s -> %s, page number %s, separator %r" % (
                e["level"], e["style"], e["format"], e["page_number"], e["separator"]))
    add("")
    add("Preferences")
    for tag, d in info["preferences"].items():
        add("  %s: %s" % (tag, ", ".join("%s=%s" % kv for kv in d.items())))
    return "\n".join(lines) + "\n"


def _style_line(s):
    extra = ", ".join("%s=%s" % (k, v) for k, v in s.items() if k not in ("name", "defines"))
    return s["name"] + (" (" + extra + ")" if extra else "")


def main(argv=None):
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    info = inspect(args[0])
    if "--json" in args:
        print(json.dumps(info, ensure_ascii=False, indent=2))
    else:
        sys.stdout.write(render(info))
    return 0


if __name__ == "__main__":
    sys.exit(main())
