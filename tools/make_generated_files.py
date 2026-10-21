"""Write the generator's own versions of the reference files (build step 3).

    python tools/make_generated_files.py

Writes reference/generated/gNN-*.idml with docx2idml.idml.writer, each built to match the
InDesign reference file of the same number (same pages, styles and text as
reference/make_reference_files.jsx makes), and checks each with tools/idml_check.py. Compare
with the reference using tools/idml_inspect.py; then open in InDesign and Affinity.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from docx2idml.idml.model import (Document, Frame, Master, Paragraph, Run, Section, Story,
                                  Style)
from docx2idml.idml.writer import write_idml
from docx2idml.profile import default_profile

OUT = os.path.join(ROOT, "reference", "generated")

# The same sentences as the InDesign script, so the files can be compared page by page.
SENTENCES = [
    "The covenant formula recurs throughout the prophets with small but telling changes.",
    "Each change of wording marks a shift in the relationship the text describes.",
    "Readers in the early church heard these passages through the Greek translation.",
    "That translation smooths some difficulties of the Hebrew and sharpens others.",
    "A careful edition keeps both voices audible without forcing them into agreement.",
    "The apparatus at the foot of the page records where the witnesses part ways.",
    "Some of these differences are accidents of copying; others are deliberate.",
    "Distinguishing the two requires attention to the habits of each scribe.",
    "The argument of this chapter proceeds from the clearer cases to the harder ones.",
    "Office workers, affluent patrons and fifty-five official scribes all appear in the record.",
]


def filler(n_words, seed=0):
    out, count, i = [], 0, seed
    while count < n_words:
        s = SENTENCES[i % len(SENTENCES)]
        out.append(s)
        count += len(s.split())
        i += 1
    return " ".join(out)


def body_styles(font="Arno Pro"):
    """The styles the InDesign script's bodyStyles() makes."""
    return [
        Style("Body", font=font, leading=14,
              attrs={"FontStyle": "Regular", "PointSize": 11, "FirstLineIndent": 18,
                     "Justification": "LeftJustified", "Hyphenation": True,
                     "Composer": "HL Composer"}),
        Style("Body First", based_on="Body", attrs={"FirstLineIndent": 0}),
        Style("Chapter Title", based_on="Body", leading=24, next_style="Body First",
              attrs={"PointSize": 20, "FirstLineIndent": 0, "Justification": "CenterAlign",
                     "SpaceAfter": 28, "Hyphenation": False, "KeepWithNext": 2}),
        Style("Heading A", based_on="Body", leading=14, next_style="Body First",
              attrs={"PointSize": 12, "FontStyle": "Bold", "FirstLineIndent": 0,
                     "Justification": "LeftAlign", "SpaceBefore": 14, "Hyphenation": False,
                     "KeepWithNext": 2}),
        Style("Running Head", font=font, leading=11,
              attrs={"PointSize": 9, "FirstLineIndent": 0, "Hyphenation": False,
                     "Justification": "LeftAlign"}),
    ]


def note(*runs):
    return [Paragraph("Footnote", [r if isinstance(r, Run) else Run(r) for r in runs])]


def g01_footnotes():
    """Footnotes, as reference 01: two chapters (stories) of two pages, a section each,
    numbering restarting per section, a long note running over to the next page."""
    doc = Document(page_count=4, name="g01-footnotes")
    doc.paragraph_styles = body_styles() + [
        Style("Footnote", font="Arno Pro", leading=11,
              attrs={"PointSize": 9, "FirstLineIndent": 9, "Justification": "LeftJustified"})]
    doc.character_styles = [Style("Footnote Reference", attrs={"Position": "Superscript"}),
                            Style("Italic", attrs={"FontStyle": "Italic"})]
    doc.footnotes = dict(default_profile()["footnotes"])
    ch1 = [
        Paragraph("Chapter Title", [Run("First Chapter")]),
        Paragraph("Body First", [Run(filler(60, 0)), Run(footnote=note(
            "A short note with an ", Run("italic phrase", style="Italic"), " in it."))]),
        Paragraph("Body", [Run(filler(50, 2)), Run(footnote=note("Ibid.")),
                           Run(" " + filler(40, 3))]),
        Paragraph("Body", [Run(filler(70, 5)), Run(footnote=note(
            "This note is long enough to run onto the next page. " + filler(260, 4)))]),
        Paragraph("Body", [Run(filler(120, 6)), Run(footnote=note("A note on the second page."))]),
        Paragraph("Body", [Run(filler(160, 7))]),
    ]
    ch2 = [
        Paragraph("Chapter Title", [Run("Second Chapter")]),
        Paragraph("Body First", [Run(filler(60, 1)), Run(footnote=note(
            "Numbering restarts at 1 in a new section."))]),
        Paragraph("Body", [Run(filler(80, 2)), Run(footnote=note("Second note of chapter two."))]),
        Paragraph("Body", [Run(filler(200, 3))]),
    ]
    doc.stories = [Story(ch1, [0, 1], sink=72), Story(ch2, [2, 3], sink=72)]
    doc.sections = [Section(0, marker="First Chapter"), Section(2, marker="Second Chapter")]
    return doc


def area(doc, side):
    """The text area of a page, (top, left, bottom, right), in page coordinates. In facing
    documents the inside margin is on the right of a verso and the left of a recto."""
    m = doc.margins
    left = m["outside"] if side == "verso" else m["inside"]
    right = doc.width - (m["inside"] if side == "verso" else m["outside"])
    return m["top"], left, doc.height - m["bottom"], right


def head_frame(doc, side, runs, key="head", justification=None):
    """A running head 27-13 pt above the text area, text at its foot (as the script's
    headFrame)."""
    top, left, _bottom, right = area(doc, side)
    para = Paragraph("Running Head", runs,
                     attrs={"Justification": justification} if justification else {})
    return Frame(side, (top - 27, left, top - 13, right), [para], key=key, valign="BottomAlign")


def folio_frame(doc, side, key="folio"):
    """A folio 14-28 pt below the text area (as the script's folioFrame)."""
    _top, left, bottom, right = area(doc, side)
    return Frame(side, (bottom + 14, left, bottom + 28, right),
                 [Paragraph("Folio", [Run(special="page_number")])], key=key)


def g02_section_marker_heads():
    """Running heads from section markers, as reference 02: recto head = section marker and
    page number, verso head = page number and the book title; three sections."""
    doc = Document(page_count=7, name="g02-section-marker-heads")
    doc.paragraph_styles = body_styles()
    doc.character_styles = [Style("Italic", attrs={"FontStyle": "Italic"})]
    doc.footnotes = dict(default_profile()["footnotes"])
    doc.masters = [Master("A", "Body", frames=[
        head_frame(doc, "verso", [Run("  |  Reference Book", special="page_number")]),
        head_frame(doc, "recto", [Run("  |  ", special="section_marker"),
                                  Run(special="page_number")], justification="RightAlign")])]
    chapters = [("First Chapter", [0, 1]), ("Second Chapter", [2, 3]),
                ("A Third Chapter with a Much Longer Title Than the Others", [4, 5, 6])]
    doc.stories, doc.sections = [], []
    for i, (title, pages) in enumerate(chapters):
        doc.stories.append(Story([Paragraph("Chapter Title", [Run(title)]),
                                  Paragraph("Body First", [Run(filler(200 * len(pages), i))])],
                                 pages, sink=72))
        doc.sections.append(Section(pages[0], marker=title))
    return doc


def g03_section_numbering():
    """Roman front matter, arabic from chapter 1, as reference 03: display pages (D) and blank
    pages (E) with no folio; folios on A-Body and C-Front (based on A)."""
    doc = Document(page_count=9, name="g03-section-numbering")
    doc.paragraph_styles = body_styles() + [
        Style("Folio", based_on="Running Head", attrs={"Justification": "CenterAlign"})]
    doc.character_styles = [Style("Italic", attrs={"FontStyle": "Italic"})]
    doc.footnotes = dict(default_profile()["footnotes"])
    doc.masters = [Master("A", "Body", frames=[folio_frame(doc, "verso"),
                                               folio_frame(doc, "recto")]),
                   Master("C", "Front", based_on="A-Body"),
                   Master("D", "Display"), Master("E", "Blank")]
    plan = [("D-Display", "Reference Book"), ("E-Blank", ""),
            ("D-Display", "Reference Book\rA Subtitle\rAuthor Name"),
            ("D-Display", "Copyright \u00A9 2026 Author Name. All rights reserved."),
            ("C-Front", "Contents"), ("E-Blank", ""), ("C-Front", "Preface"),
            ("A-Body", "Chapter One"), ("A-Body", "")]
    doc.stories = []
    for i, (master, text) in enumerate(plan):
        doc.page_masters[i] = master
        if text:
            lines = text.split("\r")
            paras = [Paragraph("Chapter Title", [Run(lines[0])])]
            paras += [Paragraph("Body", [Run(line)]) for line in lines[1:]]
            if i >= 4:
                paras.append(Paragraph("Body First", [Run(filler(120, i))]))
            doc.stories.append(Story(paras, [i], sink=72))
    doc.sections = [Section(0, marker="Front matter", numbering="LowerRoman", start=1),
                    Section(7, marker="Chapter One", start=1)]
    return doc


def g04_parent_child_masters():
    """B-Opener based on A-Body, as reference 04: it removes A's running heads and has its own
    folio at the foot."""
    doc = Document(page_count=6, name="g04-parent-child-masters")
    doc.paragraph_styles = body_styles() + [
        Style("Folio", based_on="Running Head", attrs={"Justification": "CenterAlign"})]
    doc.character_styles = [Style("Italic", attrs={"FontStyle": "Italic"})]
    doc.footnotes = dict(default_profile()["footnotes"])
    a = Master("A", "Body", frames=[
        head_frame(doc, "verso", [Run("  |  Reference Book", special="page_number")]),
        head_frame(doc, "recto", [Run("Chapter Title  |  "), Run(special="page_number")],
                   justification="RightAlign")])
    b = Master("B", "Opener", based_on="A-Body", removes=["head"],
               frames=[folio_frame(doc, "verso"), folio_frame(doc, "recto")])
    doc.masters = [a, b]
    for i, m in enumerate(["B-Opener", "A-Body", "A-Body", "A-Body", "B-Opener", "A-Body"]):
        doc.page_masters[i] = m
    doc.stories = [
        Story([Paragraph("Chapter Title", [Run("Chapter Opener on B")]),
               Paragraph("Body First", [Run(filler(1000, 0))])], [0, 1, 2, 3], sink=108),
        Story([Paragraph("Chapter Title", [Run("Second Opener on B")]),
               Paragraph("Body First", [Run(filler(450, 3))])], [4, 5], sink=108)]
    doc.sections = [Section(0)]
    return doc


FILES = [("g01-footnotes", g01_footnotes), ("g02-section-marker-heads", g02_section_marker_heads),
         ("g03-section-numbering", g03_section_numbering),
         ("g04-parent-child-masters", g04_parent_child_masters)]


def main():
    from idml_check import check
    os.makedirs(OUT, exist_ok=True)
    bad = 0
    for name, build in FILES:
        path = write_idml(build(), os.path.join(OUT, name + ".idml"))
        probs = check(path)
        print("%s: %s" % (name, "OK" if not probs else "%d problem(s)" % len(probs)))
        for p in probs[:20]:
            print("  - " + p[:300])
        bad += bool(probs)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
