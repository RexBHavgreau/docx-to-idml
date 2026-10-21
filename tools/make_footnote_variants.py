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
  fn-f-note-break       each note paragraph ends with a paragraph break (InDesign writes none)
  fn-g-renamed-styles   the note styles renamed "Note Text" and "Note Callout", in case
                        Affinity's own notes style named "Footnote" takes over
  fn-h-renamed-break    f + g
  fn-i-split-number     the footnote number (and the separator after it) in its own text run,
                        so every note has at least two runs: Affinity read only notes with
                        two or more runs as proper footnotes (October 21)
  fn-j-split-plain-callout  i + a (callout runs with no character style)
  fn-k-split-no-italic  i, with the Italic style in note 1 made plain text: no character style
                        anywhere in the notes (in fn-i, note text after the Italic run fell back
                        to InDesign's default 12 pt Minion as overrides)
  fn-l-split-local-italic  i + d (italic in notes as local formatting, not a style)
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


RENAMES = [('"ParagraphStyle/Footnote"', '"ParagraphStyle/Note Text"'),
           ('Name="Footnote"', 'Name="Note Text"'),
           ('"CharacterStyle/Footnote Reference"', '"CharacterStyle/Note Callout"'),
           ('Name="Footnote Reference"', 'Name="Note Callout"')]


def rename(xml):
    text = xml.decode("utf-8")
    for a, b in RENAMES:
        text = text.replace(a, b)
    return text.encode("utf-8")


def split_number(fn, separator):
    """Put the footnote number <?ACE 4?> and the separator after it in a run of their own."""
    for psr in fn.findall("ParagraphStyleRange"):
        for csr in psr.findall("CharacterStyleRange"):
            for content in csr.findall("Content"):
                pis = [k for k in content if isinstance(k, etree._ProcessingInstruction)
                       and (k.text or "").strip() == "4"]
                if not pis or content.text:
                    continue
                pi = pis[0]
                tail = pi.tail or ""
                head = separator if separator and tail.startswith(separator) else ""
                rest = tail[len(head):]
                if not rest and content.getnext() is None and csr.getnext() is not None:
                    return   # already on its own
                pi.tail = head
                new = etree.Element("CharacterStyleRange", csr.attrib)
                c2 = etree.SubElement(new, "Content")
                c2.text = rest
                for sib in list(content.itersiblings()):
                    new.append(sib)
                if not rest:
                    new.remove(c2)
                csr.addnext(new)
                return


def transform(story_xml, plain_callout=False, local_superscript=False, note_format=None,
              note_local_italic=False, note_break=False, split=None, note_no_italic=False):
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
        if split is not None:
            split_number(fn, split)
        if note_break:
            last = list(fn.iter("CharacterStyleRange"))[-1]
            etree.SubElement(last, "Br")
        if note_no_italic:
            for csr in fn.iter("CharacterStyleRange"):
                if csr.get("AppliedCharacterStyle") == "CharacterStyle/Italic":
                    csr.set("AppliedCharacterStyle", NONE)
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
    ("fn-f-note-break", {"note_break": True}, False),
    ("fn-g-renamed-styles", {"rename": True}, False),
    ("fn-h-renamed-break", {"rename": True, "note_break": True}, False),
    ("fn-i-split-number", {"split": True}, False),
    ("fn-j-split-plain-callout", {"split": True, "plain_callout": True}, False),
    ("fn-k-split-no-italic", {"split": True, "note_no_italic": True}, False),
    ("fn-l-split-local-italic", {"split": True, "note_local_italic": True}, False),
]


def main():
    from idml_check import check
    os.makedirs(OUT, exist_ok=True)
    src = zipfile.ZipFile(SRC)
    fmt = footnote_style_settings(src.read("Resources/Styles.xml"))
    separator = etree.fromstring(src.read("Resources/Preferences.xml")).find(
        "FootnoteOption").get("SeparatorText") or ""
    bad = 0
    for name, opts, plain_marker in VARIANTS:
        opts = dict(opts)
        renamed = opts.pop("rename", False)
        if opts.get("note_format"):
            opts["note_format"] = fmt
        if opts.get("split"):
            opts["split"] = separator
        path = os.path.join(OUT, name + ".idml")
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            for info in src.infolist():
                data = src.read(info.filename)
                if info.filename.startswith("Stories/"):
                    data = transform(data, **opts)
                elif info.filename == "Resources/Preferences.xml" and plain_marker:
                    data = no_marker_style(data)
                if renamed and info.filename.endswith(".xml"):
                    data = rename(data)
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
