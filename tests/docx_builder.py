"""Builds small .docx files from raw WordprocessingML for the tests.

Writing the XML by hand (rather than with python-docx) gives full control: footnotes, endnotes,
fields, text boxes, tracked changes, sections and headers, exactly as Word writes them.
"""

import sys
import traceback
import zipfile
from xml.sax.saxutils import escape

WNS = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
       'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
       'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
       'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
       'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture" '
       'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" '
       'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
       'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" '
       'xmlns:v="urn:schemas-microsoft-com:vml"')

DEFAULT_STYLES = {
    "Normal": '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/>'
              '<w:qFormat/></w:style>',
    "Heading1": '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/>'
                '<w:basedOn w:val="Normal"/><w:link w:val="Heading1Char"/><w:pPr><w:keepNext/>'
                '<w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:rFonts w:asciiTheme="majorHAnsi" '
                'w:hAnsiTheme="majorHAnsi"/><w:sz w:val="32"/></w:rPr></w:style>',
    "Heading2": '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/>'
                '<w:basedOn w:val="Normal"/><w:pPr><w:outlineLvl w:val="1"/></w:pPr></w:style>',
    "Heading1Char": '<w:style w:type="character" w:customStyle="1" w:styleId="Heading1Char">'
                    '<w:name w:val="Heading 1 Char"/><w:link w:val="Heading1"/></w:style>',
    "Title": '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/>'
             '<w:basedOn w:val="Normal"/><w:rPr><w:sz w:val="56"/></w:rPr></w:style>',
    "Subtitle": '<w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/>'
                '<w:basedOn w:val="Normal"/></w:style>',
    "Quote": '<w:style w:type="paragraph" w:styleId="Quote"><w:name w:val="Quote"/>'
             '<w:basedOn w:val="Normal"/><w:pPr><w:ind w:left="720"/></w:pPr>'
             '<w:rPr><w:sz w:val="22"/></w:rPr></w:style>',
    "FootnoteText": '<w:style w:type="paragraph" w:styleId="FootnoteText"><w:name w:val="footnote text"/>'
                    '<w:basedOn w:val="Normal"/><w:rPr><w:sz w:val="20"/></w:rPr></w:style>',
    "FootnoteReference": '<w:style w:type="character" w:styleId="FootnoteReference">'
                         '<w:name w:val="footnote reference"/><w:rPr><w:vertAlign w:val="superscript"/>'
                         '</w:rPr></w:style>',
    "Emphasis": '<w:style w:type="character" w:styleId="Emphasis"><w:name w:val="Emphasis"/>'
                '<w:rPr><w:i/></w:rPr></w:style>',
    "TOC1": '<w:style w:type="paragraph" w:styleId="TOC1"><w:name w:val="toc 1"/>'
            '<w:basedOn w:val="Normal"/></w:style>',
    "ChapterHead": '<w:style w:type="paragraph" w:customStyle="1" w:styleId="ChapterHead">'
                   '<w:name w:val="Chapter Head"/><w:basedOn w:val="Heading1"/></w:style>',
    "Fancy": '<w:style w:type="paragraph" w:customStyle="1" w:styleId="Fancy">'
             '<w:name w:val="Fancy Para"/><w:basedOn w:val="Normal"/></w:style>',
    "PartTitle": '<w:style w:type="paragraph" w:customStyle="1" w:styleId="PartTitle">'
                 '<w:name w:val="Part Title"/><w:pPr><w:outlineLvl w:val="0"/></w:pPr></w:style>',
}

# LibreOffice refuses a theme without a color scheme, so the theme carries one.
THEME = ('<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Office">'
         '<a:themeElements><a:clrScheme name="Office"><a:dk1><a:sysClr val="windowText" '
         'lastClr="000000"/></a:dk1><a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1>'
         '<a:dk2><a:srgbClr val="44546A"/></a:dk2><a:lt2><a:srgbClr val="E7E6E6"/></a:lt2>'
         + "".join('<a:accent%d><a:srgbClr val="4472C4"/></a:accent%d>' % (i, i) for i in range(1, 7))
         + '<a:hlink><a:srgbClr val="0563C1"/></a:hlink><a:folHlink><a:srgbClr val="954F72"/>'
         '</a:folHlink></a:clrScheme><a:fontScheme name="Office"><a:majorFont><a:latin '
         'typeface="Calibri Light"/><a:ea typeface=""/><a:cs typeface=""/></a:majorFont><a:minorFont>'
         '<a:latin typeface="Calibri"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont>'
         '</a:fontScheme></a:themeElements></a:theme>')

SECT = ('<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" '
        'w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/></w:sectPr>')


def run(text, rpr=""):
    rpr = "<w:rPr>%s</w:rPr>" % rpr if rpr else ""
    return '<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>' % (rpr, escape(text))


def para(content="", style=None, ppr=""):
    """content: plain text, or raw XML when it starts with '<'."""
    if content and not content.startswith("<"):
        content = run(content)
    pstyle = '<w:pStyle w:val="%s"/>' % style if style else ""
    p = "<w:pPr>%s%s</w:pPr>" % (pstyle, ppr) if (pstyle or ppr) else ""
    return "<w:p>%s%s</w:p>" % (p, content)


def footnote_ref(n):
    return ('<w:r><w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr>'
            '<w:footnoteReference w:id="%d"/></w:r>' % n)


def endnote_ref(n):
    return '<w:r><w:endnoteReference w:id="%d"/></w:r>' % n


def field(instr, result=""):
    return ('<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> %s '
            '</w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r>%s'
            '<w:r><w:fldChar w:fldCharType="end"/></w:r>' % (escape(instr), run(result) if result else ""))


def section_break(break_type="nextPage", style=None, text=""):
    return para(text, style, '<w:sectPr><w:type w:val="%s"/><w:pgSz w:w="8640" w:h="12960"/>'
                             '</w:sectPr>' % break_type)


def textbox(text):
    return ('<w:r><w:drawing><wp:anchor><wp:docPr id="1" name="Text Box 1"/><a:graphic><a:graphicData '
            'uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"><wps:wsp><wps:txbx>'
            '<w:txbxContent>%s</w:txbxContent></wps:txbx></wps:wsp></a:graphicData></a:graphic>'
            '</wp:anchor></w:drawing></w:r>' % para(text))


def image(floating=False):
    tag = "wp:anchor" if floating else "wp:inline"
    return ('<w:r><w:drawing><%s><wp:docPr id="2" name="Picture 1"/><a:graphic><a:graphicData '
            'uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic><pic:nvPicPr/>'
            '</pic:pic></a:graphicData></a:graphic></%s></w:drawing></w:r>' % (tag, tag))


def make_docx(path, body, styles=None, extra_styles=(), footnotes=(), endnotes=(), header=None,
              core=None, app=None, sect=SECT, doc_defaults_size="24"):
    """Write a .docx. body: list of paragraph XML strings. footnotes/endnotes: note texts
    (ids from 1). header: XML of a header's paragraphs. styles: {id: xml} replacing defaults."""
    st = dict(DEFAULT_STYLES)
    if styles:
        st.update(styles)
    style_xml = ('<w:styles %s><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:asciiTheme="minorHAnsi" '
                 'w:hAnsiTheme="minorHAnsi"/><w:sz w:val="%s"/></w:rPr></w:rPrDefault></w:docDefaults>%s%s'
                 '</w:styles>' % (WNS, doc_defaults_size, "".join(st.values()), "".join(extra_styles)))
    if header is not None:
        sect = sect.replace("<w:sectPr>", '<w:sectPr><w:headerReference w:type="default" r:id="rIdH1"/>')
    document = '<w:document %s><w:body>%s%s</w:body></w:document>' % (WNS, "".join(body), sect)
    rels = ['<Relationship Id="rIdS" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
            'relationships/styles" Target="styles.xml"/>',
            '<Relationship Id="rIdT" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
            'relationships/theme" Target="theme/theme1.xml"/>']
    files = {"word/styles.xml": style_xml, "word/theme/theme1.xml": THEME,
             "word/document.xml": document}

    def notes(kind, texts):
        items = ['<w:%s w:type="separator" w:id="-1"><w:p><w:r><w:separator/></w:r></w:p></w:%s>'
                 % (kind, kind)]
        for i, t in enumerate(texts, 1):
            items.append('<w:%s w:id="%d">%s</w:%s>' % (kind, i, para(t, "FootnoteText"), kind))
        return '<w:%ss %s>%s</w:%ss>' % (kind, WNS, "".join(items), kind)
    if footnotes:
        files["word/footnotes.xml"] = notes("footnote", footnotes)
        rels.append('<Relationship Id="rIdF" Type="http://schemas.openxmlformats.org/officeDocument/'
                    '2006/relationships/footnotes" Target="footnotes.xml"/>')
    if endnotes:
        files["word/endnotes.xml"] = notes("endnote", endnotes)
        rels.append('<Relationship Id="rIdE" Type="http://schemas.openxmlformats.org/officeDocument/'
                    '2006/relationships/endnotes" Target="endnotes.xml"/>')
    if header is not None:
        files["word/header1.xml"] = '<w:hdr %s>%s</w:hdr>' % (WNS, header)
        rels.append('<Relationship Id="rIdH1" Type="http://schemas.openxmlformats.org/officeDocument/'
                    '2006/relationships/header" Target="header1.xml"/>')
    files["word/_rels/document.xml.rels"] = (
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">%s'
        '</Relationships>' % "".join(rels))
    files["_rels/.rels"] = (
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
        'relationships/officeDocument" Target="word/document.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/'
        'metadata/core-properties" Target="docProps/core.xml"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
        'relationships/extended-properties" Target="docProps/app.xml"/></Relationships>')
    core = core or {}
    files["docProps/core.xml"] = (
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/'
        'core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/">%s%s</cp:coreProperties>'
        % ("<dc:title>%s</dc:title>" % escape(core["title"]) if "title" in core else "",
           "<dc:creator>%s</dc:creator>" % escape(core["creator"]) if "creator" in core else ""))
    app = app or {}
    files["docProps/app.xml"] = (
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
        '%s</Properties>' % "".join("<%s>%s</%s>" % (k, v, k) for k, v in app.items()))
    ct = ('<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-'
          'officedocument.wordprocessingml.document.main+xml"/>'
          '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-'
          'officedocument.wordprocessingml.styles+xml"/>'
          '<Override PartName="/word/theme/theme1.xml" ContentType="application/vnd.openxmlformats-'
          'officedocument.theme+xml"/>'
          '%s%s%s'
          '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-'
          'package.core-properties+xml"/>'
          '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-'
          'officedocument.extended-properties+xml"/></Types>'
          % ('<Override PartName="/word/footnotes.xml" ContentType="application/vnd.openxmlformats-'
             'officedocument.wordprocessingml.footnotes+xml"/>' if footnotes else "",
             '<Override PartName="/word/endnotes.xml" ContentType="application/vnd.openxmlformats-'
             'officedocument.wordprocessingml.endnotes+xml"/>' if endnotes else "",
             '<Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-'
             'officedocument.wordprocessingml.header+xml"/>' if header is not None else ""))
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        for name, data in files.items():
            z.writestr(name, data)
    return path


def run_tests(namespace):
    """Run every test_* function in a module; print a summary; exit 1 on failure."""
    tests = [(n, f) for n, f in namespace.items() if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print("ok   " + name)
        except Exception:
            failed += 1
            print("FAIL " + name)
            traceback.print_exc()
    print("%d passed, %d failed" % (len(tests) - failed, failed))
    sys.exit(1 if failed else 0)
