"""Make variants of reference file 01 (footnotes), each changing one thing, to find the
footnote structure Affinity reads correctly.

    python tools/make_footnote_variants.py

Writes reference/variants/fn-*.idml from reference/idml/01-footnotes.idml and checks each with
tools/idml_check.py. In every variant the stray local italic on " in it." (left by script
version 4) is removed.

  fn-0-base             01 as InDesign wrote it (callout runs in "Footnote Reference")
  fn-a-plain-callout    callout runs set to [No character style]; the marker style is left to
                        the footnote options (as InDesign itself applies it)
  fn-b-local-superscript callout runs [No character style] with local superscript, and no
                        marker style in the footnote options (the Assumption article's pattern)
  fn-c-note-formatting  note paragraphs also carry the Footnote style's settings directly
  fn-d-note-local-italic italic inside notes as local formatting, not the Italic style
  fn-e-all              b + c + d together
"""

import os
import sys
import zipfile

from lxml import etree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "reference", "idml", "01-footnotes.idml")
OUT = os.path.join(ROOT, "reference", "variants")
NONE = "CharacterStyle/$ID/[No character style]"
sys.path.insert(0, os.path.join(ROOT, "tools"))


def footnote_style_settings(styles_xml):
    """The Footnote paragraph style's own settings, as attributes to copy onto note text."""
    root = etree.fromstring(styles_xml)
    for ps in root.iter("ParagraphStyle"):
        if ps.get("Self") == "ParagraphStyle/Footnote":
            attrs = {k: ps.get(k) for k in ("PointSize", "FirstLineIndent", "Justification",
                                            "LeftIndent", "SpaceBefore", "SpaceAfter",
                                            "FontStyle") if ps.get(k) is not None}
            props = {}
            for name in ("AppliedFont", "Leading"):
                el = ps.find("Properties/" + name)
                if el is not None:
                    props[name] = (el.get("type"), el.text)
            return attrs, props
    raise SystemExit("01-footnotes.idml has no Footnote paragraph style")


def set_props(el, props):
    """Add <Properties> children (AppliedFont, Leading) in the schema's place: first child."""
    if not props:
        return
    p = el.find("Properties")
    if p is None:
        p = etree.Element("Properties")
        el.insert(0, p)
    for name, (typ, text) in props.items():
        if p.find(name) is None:
            child = etree.SubElement(p, name, type=typ)
            child.text = text


def transform(story_xml, plain_callout=False, local_superscript=False, note_format=None,
              note_local_italic=False):
    root = etree.fromstring(story_xml)
    for csr in root.iter("CharacterStyleRange"):
        # The stray local italic after the Italic run in note 1.
        if csr.get("AppliedCharacterStyle") == NONE and csr.get("FontStyle") == "Italic":
            del csr.attrib["FontStyle"]
        if csr.find("Footnote") is not None and (plain_callout or local_superscript):
            csr.set("AppliedCharacterStyle", NONE)
            if local_superscript:
                csr.set("Position", "Superscript")
    for fn in root.iter("Footnote"):
        for psr in fn.iter("ParagraphStyleRange"):
            if note_format:
                attrs, props = note_format
                for csr in psr.iter("CharacterStyleRange"):
                    for k, v in attrs.items():
                        csr.set(k, v)
                    set_props(csr, props)
        if note_local_italic:
            for csr in fn.iter("CharacterStyleRange"):
                if csr.get("AppliedCharacterStyle") == "CharacterStyle/Italic":
                    csr.set("AppliedCharacterStyle", NONE)
                    csr.set("FontStyle", "Italic")
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def no_marker_style(prefs_xml):
    root = etree.fromstring(prefs_xml)
    fo = root.find("FootnoteOption")
    fo.set("FootnoteMarkerStyle", NONE)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


VARIANTS = [
    ("fn-0-base", {}, False),
    ("fn-a-plain-callout", {"plain_callout": True}, False),
    ("fn-b-local-superscript", {"local_superscript": True}, True),
    ("fn-c-note-formatting", {"note_format": True}, False),
    ("fn-d-note-local-italic", {"note_local_italic": True}, False),
    ("fn-e-all", {"local_superscript": True, "note_format": True, "note_local_italic": True}, True),
]


def main():
    from idml_check import check
    os.makedirs(OUT, exist_ok=True)
    src = zipfile.ZipFile(SRC)
    fmt = footnote_style_settings(src.read("Resources/Styles.xml"))
    bad = 0
    for name, opts, plain_marker in VARIANTS:
        opts = dict(opts)
        if opts.get("note_format"):
            opts["note_format"] = fmt
        path = os.path.join(OUT, name + ".idml")
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            for info in src.infolist():
                data = src.read(info.filename)
                if info.filename.startswith("Stories/"):
                    data = transform(data, **opts)
                elif info.filename == "Resources/Preferences.xml" and plain_marker:
                    data = no_marker_style(data)
                if info.filename == "mimetype":
                    z.writestr(info, data, zipfile.ZIP_STORED)
                else:
                    z.writestr(info.filename, data)
        probs = check(path)
        print("%s: %s" % (name, "OK" if not probs else "; ".join(probs[:3])))
        bad += bool(probs)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
