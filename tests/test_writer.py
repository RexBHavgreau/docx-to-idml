"""The IDML writer: the generator's feature files validate and match the InDesign references."""

import os
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lxml import etree

from docx_builder import run_tests
from docx2idml.idml.model import Document, Paragraph, Run, Section, Story, Style
from docx2idml.idml.writer import Writer, roman, write_idml
from idml_check import check, schema_available
from idml_inspect import inspect
from make_generated_files import g01_footnotes

TMP = tempfile.mkdtemp()


def test_roman_and_page_names():
    assert [roman(n) for n in (1, 4, 9, 14, 40, 1999)] == ["i", "iv", "ix", "xiv", "xl", "mcmxcix"]
    doc = Document(page_count=9, sections=[Section(0, numbering="LowerRoman", start=1),
                                           Section(7, start=1)])
    assert Writer(doc)._page_names() == ["i", "ii", "iii", "iv", "v", "vi", "vii", "1", "2"]
    doc = Document(page_count=5, sections=[Section(0), Section(3, marker="Two")])
    assert Writer(doc)._page_names() == ["1", "2", "3", "4", "5"]


def test_spreads():
    assert Writer(Document(page_count=5))._spreads() == [[0], [1, 2], [3, 4]]
    assert Writer(Document(page_count=4))._spreads() == [[0], [1, 2], [3]]
    assert Writer(Document(page_count=2, facing=False))._spreads() == [[0], [1]]


def test_sections_and_spreads_as_indesign_writes_them():
    """Rules read from reference files 02, 03 and 13 (g01's first version broke them and
    InDesign wouldn't open it)."""
    doc = Document(page_count=7, sections=[Section(0, marker="One"), Section(2, marker="Two"),
                                           Section(4, marker="Three")])
    doc.stories = [Story([Paragraph("Body", [Run("x")])], [0])]
    doc.paragraph_styles = [Style("Body")]
    path = write_idml(doc, os.path.join(TMP, "sections.idml"))
    z = zipfile.ZipFile(path)
    dm = etree.fromstring(z.read("designmap.xml"))
    secs = [(s.get("Length"), s.get("AlternateLayoutLength"), s.get("AlternateLayout"))
            for s in dm.iter("Section")]
    assert secs == [("2", "7", "Custom V"), ("2", "5", ""), ("3", "3", "")], secs
    spreads = sorted((etree.fromstring(z.read(n)).find("Spread") for n in z.namelist()
                      if n.startswith("Spreads/")),
                     key=lambda sp: float(sp.get("ItemTransform").split()[5]))
    assert [(sp.get("PageCount"), sp.get("BindingLocation")) for sp in spreads] == \
        [("1", "0"), ("2", "1"), ("2", "1"), ("2", "1")]
    doc.page_count = 6
    doc.sections = [Section(0)]
    z = zipfile.ZipFile(write_idml(doc, os.path.join(TMP, "lone-verso.idml")))
    spreads = sorted((etree.fromstring(z.read(n)).find("Spread") for n in z.namelist()
                      if n.startswith("Spreads/")),
                     key=lambda sp: float(sp.get("ItemTransform").split()[5]))
    assert (spreads[-1].get("PageCount"), spreads[-1].get("BindingLocation")) == ("1", "1")


def test_designmap_keeps_aid_instruction():
    path = write_idml(g01_footnotes(), os.path.join(TMP, "aid.idml"))
    head = zipfile.ZipFile(path).read("designmap.xml")[:200]
    assert head.startswith(b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>')
    assert b'<?aid style="50" type="document"' in head


def test_g01_validates():
    path = write_idml(g01_footnotes(), os.path.join(TMP, "g01.idml"))
    why = schema_available()
    assert check(path, schema=why is None) == []
    if why:
        print("     (structure only: %s)" % why)


def test_g01_matches_reference():
    path = write_idml(g01_footnotes(), os.path.join(TMP, "g01b.idml"))
    info = inspect(path)
    assert [(p["name"], p["side"], p["master"]) for p in info["pages"]] == [
        ("1", "recto", "A-Body"), ("2", "verso", "A-Body"), ("3", "recto", "A-Body"),
        ("4", "verso", "A-Body")]
    assert [(s["start_page"], s["marker"], s["continue_numbering"]) for s in info["sections"]] == \
        [("1", "First Chapter", "true"), ("3", "Second Chapter", "true")]
    stories = [s for s in info["stories"] if s.get("footnotes")]
    assert sorted(s["footnotes"] for s in stories) == [2, 4]
    assert all(s["special_characters"] == {"footnote number": s["footnotes"]} for s in stories)
    first = [s for s in stories if s["footnotes"] == 4][0]
    assert [(f["page"]) for f in first["frames"]] == ["1", "2"]
    assert first["character_styles"] == {"Footnote Reference": 4, "Italic": 1}
    fo = info["preferences"]["FootnoteOption"]
    assert fo["FootnoteTextStyle"] == "Footnote" and fo["FootnoteMarkerStyle"] == "Footnote Reference"
    assert fo["RestartNumbering"] == "SectionRestart" and fo["RuleOn"] == "false"


def test_footnote_structure():
    """As decided (PLAN.md): number in its own run; Footnote settings on every note run."""
    path = write_idml(g01_footnotes(), os.path.join(TMP, "g01c.idml"))
    z = zipfile.ZipFile(path)
    notes = []
    for n in z.namelist():
        if n.startswith("Stories/"):
            notes += list(etree.fromstring(z.read(n)).iter("Footnote"))
    assert len(notes) == 6
    for fn in notes:
        psr = fn.find("ParagraphStyleRange")
        assert psr.get("AppliedParagraphStyle") == "ParagraphStyle/Footnote"
        runs = psr.findall("CharacterStyleRange")
        assert len(runs) >= 2
        first = runs[0].find("Content")
        assert isinstance(first[0], etree._ProcessingInstruction) and first[0].text == "4"
        assert first[0].tail == ". "
        for r in runs:
            assert r.get("PointSize") == "9" and r.get("FirstLineIndent") == "9"
            assert r.find("Properties/AppliedFont").text == "Arno Pro"
            assert r.find("Properties/Leading").text == "11"
    italic = [r for fn in notes for r in fn.iter("CharacterStyleRange")
              if r.get("AppliedCharacterStyle") == "CharacterStyle/Italic"]
    assert len(italic) == 1


def test_footnote_options_from_profile():
    doc = g01_footnotes()
    doc.footnotes.update(rule=True, continuation_rule=False, space_above=18, rule_length=50,
                         numbering="continuous")
    w = Writer(doc)
    w.prefs = etree.parse(os.path.join(ROOT, "docx2idml", "idml", "base", "Resources",
                                       "Preferences.xml")).getroot()
    w._write_preferences()
    fo = w.prefs.find("FootnoteOption")
    assert (fo.get("RuleOn"), fo.get("ContinuingRuleOn"), fo.get("Spacer"), fo.get("RuleWidth"),
            fo.get("FootnoteMinimumFirstBaselineOffset")) == ("true", "false", "18", "50", "17")
    assert fo.find("Properties/RestartNumbering").text == "DontRestart"


def test_text_details():
    doc = Document(page_count=1)
    doc.paragraph_styles = [Style("Body", font="Arno Pro", leading=14, attrs={"PointSize": 11})]
    doc.stories = [Story([Paragraph("Body", [Run("Line one\nline two\tand <tab> & more")]),
                          Paragraph("Body", [Run("Last", attrs={"FontStyle": "Italic"})])], [0])]
    path = write_idml(doc, os.path.join(TMP, "text.idml"))
    assert check(path, schema=schema_available() is None) == []
    z = zipfile.ZipFile(path)
    story = [etree.fromstring(z.read(n)) for n in z.namelist() if n.startswith("Stories/")][0]
    contents = [c.text for c in story.iter("Content")]
    assert contents == ["Line one line two\tand <tab> & more", "Last"]
    assert len(list(story.iter("Br"))) == 1
    assert [c.get("FontStyle") for c in story.iter("CharacterStyleRange")] == [None, "Italic"]


if __name__ == "__main__":
    run_tests(globals())
