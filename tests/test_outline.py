"""The outline across several files, and the style map."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from docx_builder import field, footnote_ref, make_docx, para, run, run_tests, section_break
from docx2idml.docx_reader import read_docx
from docx2idml.outline import build_outline, classify
from docx2idml.stylemap import StyleMap, display_name

TMP = tempfile.mkdtemp()


def doc(name, body, **kw):
    return read_docx(make_docx(os.path.join(TMP, name), body, **kw))


def book():
    front = doc("00 Front.docx", [
        para("The Covenant", "Title"), para("A Study", "Subtitle"), para("by Jane Smith"),
        para("© 2026 Jane Smith. All rights reserved."),
        para("Preface", "Heading1"), para("Why this book. " * 10)])
    ch1 = doc("Chapter 1.docx", [
        para("Part One", "Heading1"),
        para("Beginnings", "ChapterHead"), para("Some text" + "", None),
        para(run("Noted") + footnote_ref(1)), para("First section", "Heading2"),
        para("More text."), para("Second section", "Heading2")], footnotes=["A note."])
    ch2 = doc("Chapter 2.docx", [
        para("A stray opening line."),
        para("Endings", "Heading1"), para("Text.")])
    back = doc("Back.docx", [para("Bibliography", "Heading1"), para("Smith, J. 2020.")])
    return [front, ch1, ch2, back]


def test_outline_across_files():
    out = build_outline(book())
    got = [(u.kind, u.type, u.title, u.file) for u in out.units]
    assert got == [
        ("display", "title page", "(title page)", "00 Front.docx"),
        ("front", "preface", "Preface", "00 Front.docx"),
        ("part", "part", "Part One", "Chapter 1.docx"),
        ("chapter", "chapter", "Beginnings", "Chapter 1.docx"),
        ("chapter", "chapter", "Endings", "Chapter 2.docx"),
        ("back", "bibliography", "Bibliography", "Back.docx"),
    ], got
    ch = out.units[3]
    assert ch.subheads == ["First section", "Second section"]
    assert ch.note_refs == 1
    assert "style Chapter Head (based on Heading 1)" == ch.detected_by
    assert out.title == "The Covenant" and out.subtitle == "A Study"
    assert out.author == "Jane Smith" and out.author_source == "title page text"
    assert out.copyright_found
    assert out.first_heading == {"00 Front.docx": "Preface", "Chapter 1.docx": "Part One",
                                 "Chapter 2.docx": "Endings", "Back.docx": "Bibliography"}
    # Text before the first heading of a later file stays with the previous unit, with a note.
    assert any("Chapter 2.docx starts with 1 paragraph of" in n for n in out.notes), out.notes
    assert out.present() >= {"title page", "copyright", "preface"}


def test_classify():
    assert classify("PREFACE", False) == ("front", "preface")
    assert classify("Preface", True) == ("chapter", "chapter")      # front names only up front
    assert classify("Notes:", True) == ("back", "notes")
    assert classify("Appendix B: Tables", True) == ("back", "appendix")
    assert classify("Part II", False) == ("part", "part")
    assert classify("Parte primera", False) == ("part", "part")
    assert classify("Party Politics", False) == ("chapter", "chapter")
    assert classify("Índice", False) == ("front", "contents")
    assert classify("Índice", True) == ("back", "index")
    assert classify("Agradecimientos", False) == ("front", "acknowledgments")


def test_profile_map_overrides():
    # A manuscript using Heading 1 for parts and Heading 2 for chapters.
    d = doc("h.docx", [para("Part One", "Heading1"), para("Chapter A", "Heading2"),
                       para("Text"), para("Chapter B", "Heading2")])
    sm = StyleMap({"Heading 1": {"idml": "Part Title", "role": "part"},
                   "heading 2": {"idml": "Chapter Title", "role": "chapter"}})
    out = build_outline([d], sm)
    assert [(u.kind, u.title) for u in out.units] == [
        ("part", "Part One"), ("chapter", "Chapter A"), ("chapter", "Chapter B")]


def test_fallback_styleref():
    hdr = para(field('STYLEREF "Fancy Para"', "x"))
    d = doc("r.docx", [para("Opening", "Fancy"), para("Text"), para("Second", "Fancy")], header=hdr)
    out = build_outline([d])
    assert [u.title for u in out.units] == ["Opening", "Second"]
    assert out.units[0].detected_by == 'Word running head (STYLEREF "Fancy Para")'


def test_fallback_outline_level():
    d = doc("o.docx", [para("Intro text"), para("Real Chapter", ppr='<w:outlineLvl w:val="0"/>'),
                       para("Text")])
    out = build_outline([d])
    assert [(u.kind, u.title) for u in out.units] == [
        ("display", "(text before the first heading)"), ("chapter", "Real Chapter")]
    assert out.units[1].detected_by == "outline level 1"


def test_fallback_section_breaks_and_whole_file():
    # A section's w:type says how that section starts: the second section starts on a new
    # page, the third runs on (its type is on the body's final sectPr).
    d = doc("s.docx", [para("First Title"), para("text"), section_break("nextPage"),
                       para(""), para("Second Title"), para("text"),
                       section_break("nextPage"), para("Not a title")],
            sect='<w:sectPr><w:type w:val="continuous"/></w:sectPr>')
    w = doc("w.docx", [para(""), para("Lonely Chapter"), para("text")])
    out = build_outline([d, w])
    assert [(u.title, u.detected_by) for u in out.units] == [
        ("First Title", "section break (start of file)"), ("Second Title", "section break"),
        ("Lonely Chapter", "whole file")], [(u.title, u.detected_by) for u in out.units]
    assert any("no recognized headings" in n for n in out.notes)


def test_toc_paragraphs_ignored():
    d = doc("t.docx", [para("Contents", "Heading1"), para(field("TOC \\o", "Chapter One\t1"), "TOC1"),
                       para("Chapter One", "Heading1"), para("Text")])
    out = build_outline([d])
    assert [(u.kind, u.type, u.title) for u in out.units] == [
        ("front", "contents", "Contents"), ("chapter", "chapter", "Chapter One")]
    assert out.toc_field and out.units[0].words == 1


def test_stylemap_mappings():
    d = doc("m.docx", [para("x")])
    sm = StyleMap()
    m = sm.paragraph_style(d, "Fancy")
    assert (m.idml, m.role, m.source, m.warning) == ("Fancy Para", "body", "based on Normal", True)
    m = sm.paragraph_style(d, "PartTitle")
    assert (m.role, m.source) == ("chapter", "outline level 1")
    m = sm.paragraph_style(d, "Heading2")
    assert (m.idml, m.role, m.level) == ("Heading A", "heading", 1)
    m = sm.paragraph_style(d, "TOC1")
    assert m.role == "toc" and m.word == "TOC 1"
    assert sm.character_style(d, "Heading1Char").role == "skip"
    assert sm.character_style(d, "Emphasis").idml == "Italic"
    assert sm.character_style(d, "FootnoteReference").idml == "Footnote Reference"
    assert display_name("footnote text") == "Footnote Text"
    assert display_name("My Style") == "My Style"


def test_endorsements_and_kinds_set_by_user():
    from docx2idml.outline import KINDS, apply_kinds, classify, kind_key
    for title in ("Endorsements", "Praise for The Covenant Formula", "Advance Praise",
                  "What Others Are Saying", "Elogios"):
        assert classify(title, False) == ("display", "endorsements"), title
    assert classify("Praise for The Covenant Formula", True) == ("chapter", "chapter")
    doc = read_docx(make_docx(os.path.join(TMP, "e.docx"), [para("Praise for This Book", "Heading1"), para("A fine book. -- A."),
                           para("Kind Words", "Heading1"), para("Also fine."),
                           para("Chapter One", "Heading1"), para("Text.")]))
    out = build_outline([doc])
    assert [(u.title, kind_key(u)) for u in out.units] == [
        ("Praise for This Book", "endorsements"), ("Kind Words", "chapter"),
        ("Chapter One", "chapter")]
    apply_kinds(out, {"Kind Words": "endorsements", "Chapter One": "chapter", "x": "bogus"})
    assert (out.units[1].kind, out.units[1].type) == KINDS["endorsements"]
    assert "set in the book settings" in out.units[1].detected_by
    assert "set in the book settings" not in out.units[2].detected_by


def test_text_before_the_title_page_is_endorsements():
    from docx2idml.outline import kind_key
    # One file: endorsements with no heading, then the title page, then chapters.
    one = read_docx(make_docx(os.path.join(TMP, "pre.docx"), [
        para("\u201cA wonderful book.\u201d \u2014 A. Reader"),
        para("\u201cRead it twice.\u201d \u2014 B. Critic"),
        para("The Covenant Formula", "Title"), para("Studies", "Subtitle"),
        para("by A. N. Author"),
        para("Preface", "Heading1"), para("Text."),
        para("Chapter One", "Heading1"), para("Text.")]))
    out = build_outline([one])
    assert [(u.title, kind_key(u), u.type) for u in out.units] == [
        ("(endorsements)", "endorsements", "endorsements"),
        ("(title page)", "display", "title page"), ("Preface", "front", "preface"),
        ("Chapter One", "chapter", "chapter")]
    assert out.title == "The Covenant Formula" and out.author == "A. N. Author"
    # Two files: a file of endorsements with no headings, then the title page and chapters.
    praise = read_docx(make_docx(os.path.join(TMP, "00 Praise.docx"), [
        para("\u201cA wonderful book.\u201d \u2014 A. Reader"), para("\u201cRead it.\u201d")]))
    book = read_docx(make_docx(os.path.join(TMP, "01 Book.docx"), [
        para("The Covenant Formula", "Title"), para("Preface", "Heading1"), para("Text."),
        para("Chapter One", "Heading1"), para("Text.")]))
    out = build_outline([praise, book])
    assert [(kind_key(u), u.type) for u in out.units] == [
        ("endorsements", "endorsements"), ("display", "title page"), ("front", "preface"),
        ("chapter", "chapter")], [(u.title, u.kind, u.type) for u in out.units]


if __name__ == "__main__":
    run_tests(globals())
