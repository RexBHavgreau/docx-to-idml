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

from docx2idml.idml.model import Document, Paragraph, Run, Section, Story, Style
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


FILES = [("g01-footnotes", g01_footnotes)]


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
