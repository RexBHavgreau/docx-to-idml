"""The development tools for IDML: the structural checker and the inspector."""

import os
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from docx_builder import run_tests
from idml_check import check
from idml_inspect import inspect

TMP = tempfile.mkdtemp()
P = 'xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="21.5"'


def parts(**changes):
    """A minimal two-page package: a facing master with a primary frame, one spread, one story
    threaded through two frames that override the master frames, and two sections."""
    p = {
        "META-INF/container.xml":
            '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">'
            '<rootfiles><rootfile full-path="designmap.xml" media-type="text/xml"/></rootfiles>'
            '</container>',
        "designmap.xml":
            '<Document %s Self="d" StoryList="u20">'
            '<idPkg:Preferences src="Resources/Preferences.xml"/>'
            '<idPkg:Styles src="Resources/Styles.xml"/>'
            '<idPkg:MasterSpread src="MasterSpreads/MasterSpread_u10.xml"/>'
            '<idPkg:Spread src="Spreads/Spread_u30.xml"/>'
            '<Section Self="s1" PageStart="u31" Marker="One" ContinueNumbering="true">'
            '<Properties><PageNumberStyle type="enumeration">LowerRoman</PageNumberStyle>'
            '</Properties></Section>'
            '<Section Self="s2" PageStart="u32" Marker="Two" ContinueNumbering="false" '
            'PageNumberStart="1"/>'
            '<idPkg:Story src="Stories/Story_u20.xml"/></Document>' % P,
        "Resources/Preferences.xml":
            '<idPkg:Preferences %s><DocumentPreference PageWidth="432" PageHeight="648" '
            'FacingPages="true"/><FootnoteOption RestartNumbering="SectionRestart"/>'
            '</idPkg:Preferences>' % P,
        "Resources/Styles.xml":
            '<idPkg:Styles %s><RootParagraphStyleGroup><ParagraphStyle '
            'Self="ParagraphStyle/Body" Name="Body" PointSize="11"/></RootParagraphStyleGroup>'
            '<RootCharacterStyleGroup><CharacterStyle Self="CharacterStyle/Italic" '
            'Name="Italic" FontStyle="Italic"/></RootCharacterStyleGroup></idPkg:Styles>' % P,
        "MasterSpreads/MasterSpread_u10.xml":
            '<idPkg:MasterSpread %s><MasterSpread Self="u10" Name="A-Body" '
            'PrimaryTextFrame="u11"><Page Self="u13" ItemTransform="1 0 0 1 -432 -324"/>'
            '<Page Self="u14" ItemTransform="1 0 0 1 0 -324"/>'
            '<TextFrame Self="u11" ParentStory="u20" PreviousTextFrame="n" NextTextFrame="u12"/>'
            '<TextFrame Self="u12" ParentStory="u20" PreviousTextFrame="u11" NextTextFrame="n"/>'
            '</MasterSpread></idPkg:MasterSpread>' % P,
        "Spreads/Spread_u30.xml":
            '<idPkg:Spread %s><Spread Self="u30">'
            '<Page Self="u31" Name="i" AppliedMaster="u10" OverrideList="u11 u33" '
            'ItemTransform="1 0 0 1 -432 -324" GeometricBounds="0 0 648 432"/>'
            '<Page Self="u32" Name="1" AppliedMaster="u10" OverrideList="u12 u34" '
            'ItemTransform="1 0 0 1 0 -324" GeometricBounds="0 0 648 432"/>'
            '<TextFrame Self="u33" ParentStory="u20" PreviousTextFrame="n" NextTextFrame="u34" '
            'ItemTransform="1 0 0 1 -216 0"/>'
            '<TextFrame Self="u34" ParentStory="u20" PreviousTextFrame="u33" NextTextFrame="n" '
            'ItemTransform="1 0 0 1 216 0"/>'
            '</Spread></idPkg:Spread>' % P,
        "Stories/Story_u20.xml":
            '<idPkg:Story %s><Story Self="u20"><ParagraphStyleRange '
            'AppliedParagraphStyle="ParagraphStyle/Body"><CharacterStyleRange '
            'AppliedCharacterStyle="CharacterStyle/Italic"><Content>Hello</Content>'
            '<Footnote><ParagraphStyleRange><CharacterStyleRange><?ACE 4?><Content>. A note'
            '</Content></CharacterStyleRange></ParagraphStyleRange></Footnote>'
            '</CharacterStyleRange><CharacterStyleRange FontStyle="Bold"><Content> world'
            '</Content><?ACE 19?></CharacterStyleRange></ParagraphStyleRange></Story>'
            '</idPkg:Story>' % P,
    }
    for k, v in changes.items():
        k = k.replace("__", "/").replace("_xml", ".xml")
        if v is None:
            p.pop(k, None)
        else:
            p[k] = v
    return p


def package(name, files, mimetype_first=True, stored=True):
    path = os.path.join(TMP, name)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        if mimetype_first:
            z.writestr(zipfile.ZipInfo("mimetype"), "application/vnd.adobe.indesign-idml-package",
                       zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED)
        for n, data in files.items():
            z.writestr(n, '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + data)
        if not mimetype_first:
            z.writestr("mimetype", "application/vnd.adobe.indesign-idml-package")
    return path


def test_sound_package():
    assert check(package("ok.idml", parts())) == []


def test_zip_problems():
    assert check(package("m1.idml", parts(), mimetype_first=False))[0] == \
        "mimetype is not the first entry"
    assert check(package("m2.idml", parts(), stored=False)) == \
        ["mimetype is compressed; it must be stored"]
    junk = os.path.join(TMP, "junk.idml")
    with open(junk, "w") as f:
        f.write("x")
    assert check(junk)[0].startswith("not a zip package")


def test_reference_problems():
    p = parts()
    p["designmap.xml"] = p["designmap.xml"].replace('DOMVersion="21.5"', 'DOMVersion="13.0"')
    p["Resources/Extra.xml"] = '<x %s/>' % P
    p["designmap.xml"] = p["designmap.xml"].replace(
        '<idPkg:Story src="Stories/Story_u20.xml"/>',
        '<idPkg:Story src="Stories/Story_u20.xml"/><idPkg:Story src="Stories/Story_u99.xml"/>')
    probs = check(package("refs.idml", p))
    assert "designmap.xml has DOMVersion 13.0 (must be 21.5)" in probs
    assert "Resources/Extra.xml is in the package but designmap.xml doesn't refer to it" in probs
    assert "designmap.xml refers to Stories/Story_u99.xml, which is not in the package" in probs


def test_link_problems():
    p = parts()
    sp = p["Spreads/Spread_u30.xml"]
    sp = sp.replace('NextTextFrame="u34" ItemTransform', 'NextTextFrame="u35" ItemTransform')
    sp = sp.replace('AppliedMaster="u10" OverrideList="u12 u34"',
                    'AppliedMaster="u77" OverrideList="u12 u34 u88"')
    p["Spreads/Spread_u30.xml"] = sp
    p["MasterSpreads/MasterSpread_u10.xml"] = p["MasterSpreads/MasterSpread_u10.xml"].replace(
        'PrimaryTextFrame="u11"', 'PrimaryTextFrame="u44"')
    p["designmap.xml"] = p["designmap.xml"].replace('PageStart="u32"', 'PageStart="u39"')
    probs = check(package("links.idml", p))
    expected = [
        "Spreads/Spread_u30.xml: frame u33 threads to u35, which doesn't exist",
        "Spreads/Spread_u30.xml: page 1 uses master u77, which doesn't exist",
        "page 1: OverrideList has an odd number of ids",
        "master A-Body: primary text frame u44 is not one of its frames",
        "section s2 starts on page u39, which doesn't exist",
    ]
    for e in expected:
        assert e in probs, (e, probs)
    p2 = parts()
    p2["Stories/Story_u20.xml"] = p2["Stories/Story_u20.xml"].replace("<Content>", "<Content")
    assert any("not well-formed" in x for x in check(package("bad.idml", p2)))


def test_inspect():
    info = inspect(package("ok2.idml", parts()))
    assert info["page"]["width"] == 432 and info["page"]["facing"] == "true"
    m = info["masters"][0]
    assert m["name"] == "A-Body" and m["primary_text_frame"] == "u11"
    assert [(pg["name"], pg["side"], pg["master"], pg["overrides"][0]["master_item"])
            for pg in info["pages"]] == [("i", "verso", "A-Body", "u11"), ("1", "recto", "A-Body", "u12")]
    assert [(s["start_page"], s["style"], s["marker"]) for s in info["sections"]] == \
        [("i", "LowerRoman", "One"), ("1", None, "Two")]
    st = info["stories"][0]
    assert [f["id"] for f in st["frames"]] == ["u33", "u34"]
    assert [f["page"] for f in st["frames"]] == ["i", "1"]
    assert st["footnotes"] == 1
    assert st["special_characters"] == {"footnote number": 1, "section marker": 1}
    assert st["character_styles"] == {"Italic": 1}
    assert st["local_overrides"] == {"FontStyle": 1}
    assert st["start"] == "Hello world"
    assert info["styles"]["character"][0]["defines"] == ["FontStyle"]
    assert info["preferences"]["FootnoteOption"] == {"RestartNumbering": "SectionRestart"}


if __name__ == "__main__":
    run_tests(globals())
