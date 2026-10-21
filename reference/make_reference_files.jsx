// make_reference_files.jsx: builds the InDesign reference files for the compatibility tests.
//
// Each file shows one feature the converter needs, built the way InDesign builds it. The script
// saves each one as .indd, exports it as .idml (the reference the generator is checked against)
// and as a PDF of spreads (to compare with what Affinity and DesignCraft make of the IDML).
// It creates new documents only; nothing open is changed. A log (reference-log.txt) lists
// what was made and anything that could not be set.
//
// Run it from InDesign's Scripts panel (Window > Utilities > Scripts; right-click "User",
// Reveal in Explorer, copy this file there). ExtendScript (ES3): no let/const, no
// forEach/indexOf/map, no trim.

#target indesign

(function () {

var SCRIPT_VERSION = "3";
var log = [];
var notes = [];          // problems inside the file being built

var outFolder = Folder.selectDialog("Choose an empty folder for the reference files");
if (!outFolder) {
    return;
}

var oldInteraction = app.scriptPreferences.userInteractionLevel;
app.scriptPreferences.userInteractionLevel = UserInteractionLevels.NEVER_INTERACT;
var oldSpreads = app.pdfExportPreferences.exportReaderSpreads;
var oldRange = app.pdfExportPreferences.pageRange;

// ---- fonts: the first one installed in each list ----

function fontOK(family, style) {
    try {
        return app.fonts.itemByName(family + "\t" + (style || "Regular")).isValid;
    } catch (e) {
        return false;
    }
}

function pick(list) {
    for (var i = 0; i < list.length; i++) {
        if (fontOK(list[i], "Regular")) {
            return list[i];
        }
    }
    return list[list.length - 1];
}

var BODY = pick(["Arno Pro", "Minion Pro", "Adobe Garamond Pro", "Times New Roman"]);
var SANS = pick(["Myriad Pro", "Source Sans 3", "Segoe UI", "Arial"]);
var HEBREW = pick(["Taamey David CLM", "SBL Hebrew", "Ezra SIL", "Times New Roman"]);
var GREEK = pick(["Arno Pro", "SBL Greek", "Gentium Plus", "Times New Roman"]);

// ---- text ----

var SENTENCES = [
    "The covenant formula recurs throughout the prophets with small but telling changes.",
    "Each change of wording marks a shift in the relationship the text describes.",
    "Readers in the early church heard these passages through the Greek translation.",
    "That translation smooths some difficulties of the Hebrew and sharpens others.",
    "A careful edition keeps both voices audible without forcing them into agreement.",
    "The apparatus at the foot of the page records where the witnesses part ways.",
    "Some of these differences are accidents of copying; others are deliberate.",
    "Distinguishing the two requires attention to the habits of each scribe.",
    "The argument of this chapter proceeds from the clearer cases to the harder ones.",
    "Office workers, affluent patrons and fifty-five official scribes all appear in the record."
];

function filler(nWords, seed) {
    var out = [];
    var count = 0;
    var i = seed || 0;
    while (count < nWords) {
        var s = SENTENCES[i % SENTENCES.length];
        out.push(s);
        count += s.split(" ").length;
        i++;
    }
    return out.join(" ");
}

// ---- helpers ----

function note(msg) {
    notes.push(msg);
}

// An enumeration value by name, or undefined (and a note) if this InDesign doesn't have it,
// so one unknown setting doesn't stop the whole file.
function E(name) {
    try {
        return eval(name);
    } catch (e) {
        note("this InDesign has no " + name);
        return undefined;
    }
}

function setProps(obj, props, label) {
    for (var k in props) {
        if (props[k] === undefined) {
            continue;
        }
        try {
            obj[k] = props[k];
        } catch (e) {
            note("could not set " + k + " on " + label + ": " + e.message);
        }
    }
    return obj;
}

function pstyle(doc, name, props) {
    var s = doc.paragraphStyles.itemByName(name);
    if (!s.isValid) {
        s = doc.paragraphStyles.add({name: name});
    }
    return setProps(s, props || {}, "paragraph style " + name);
}

function cstyle(doc, name, props) {
    var s = doc.characterStyles.itemByName(name);
    if (!s.isValid) {
        s = doc.characterStyles.add({name: name});
    }
    return setProps(s, props || {}, "character style " + name);
}

function bodyStyles(doc) {
    var body = pstyle(doc, "Body", {appliedFont: BODY, fontStyle: "Regular", pointSize: 11,
        leading: 14, firstLineIndent: 18, justification: Justification.LEFT_JUSTIFIED,
        hyphenation: true, appliedLanguage: "English: USA",
        composer: "Adobe Paragraph Composer"});
    var first = pstyle(doc, "Body First", {basedOn: body, firstLineIndent: 0});
    var h1 = pstyle(doc, "Chapter Title", {basedOn: body, appliedFont: BODY, pointSize: 20,
        leading: 24, firstLineIndent: 0, justification: Justification.CENTER_ALIGN,
        spaceAfter: 28, hyphenation: false, keepWithNext: 2});
    var h2 = pstyle(doc, "Heading A", {basedOn: body, pointSize: 12, leading: 14,
        fontStyle: "Bold", firstLineIndent: 0, justification: Justification.LEFT_ALIGN,
        spaceBefore: 14, spaceAfter: 0, hyphenation: false, keepWithNext: 2});
    h1.nextStyle = first;
    h2.nextStyle = first;
    var head = pstyle(doc, "Running Head", {appliedFont: BODY, pointSize: 9, leading: 11,
        firstLineIndent: 0, hyphenation: false, justification: Justification.LEFT_ALIGN});
    cstyle(doc, "Italic", {fontStyle: "Italic"});
    return {body: body, first: first, h1: h1, h2: h2, head: head};
}

function newDoc(pages, primary) {
    var name = "docx-to-idml reference (temporary)";
    var old = app.documentPresets.itemByName(name);
    if (old.isValid) {
        old.remove();
    }
    var p = app.documentPresets.add({name: name});
    setProps(p, {pageWidth: "6in", pageHeight: "9in", facingPages: true,
        pagesPerDocument: pages || 1, createPrimaryTextFrame: !!primary, columnCount: 1,
        top: "0.75in", bottom: "0.875in", left: "0.75in", right: "0.875in",
        documentBleedTopOffset: 0, documentBleedBottomOffset: 0,
        documentBleedInsideOrLeftOffset: 0, documentBleedOutsideOrRightOffset: 0},
        "document preset");
    var doc = app.documents.add(true, p);
    p.remove();
    doc.viewPreferences.horizontalMeasurementUnits = MeasurementUnits.POINTS;
    doc.viewPreferences.verticalMeasurementUnits = MeasurementUnits.POINTS;
    doc.viewPreferences.rulerOrigin = RulerOrigin.PAGE_ORIGIN;
    doc.zeroPoint = [0, 0];
    return doc;
}

function W(doc) { return doc.documentPreferences.pageWidth; }
function H(doc) { return doc.documentPreferences.pageHeight; }

// The text area of a page, in page coordinates: [top, left, bottom, right].
// In facing documents the margin called "left" is the inside one.
function area(doc, page, sink) {
    var m = page.marginPreferences;
    var inside = m.left, outside = m.right;
    var verso = page.side == PageSideOptions.LEFT_HAND;
    return [m.top + (sink || 0), verso ? outside : inside, H(doc) - m.bottom,
            W(doc) - (verso ? inside : outside)];
}

function frame(doc, page, sink) {
    return page.textFrames.add({geometricBounds: area(doc, page, sink)});
}

// One story threaded through the given pages (indexes); sink: drop on the first page.
function flow(doc, pageIdxs, sink) {
    var first = null, prev = null;
    for (var i = 0; i < pageIdxs.length; i++) {
        var f = frame(doc, doc.pages[pageIdxs[i]], i === 0 ? sink : 0);
        if (prev) {
            prev.nextTextFrame = f;
        } else {
            first = f;
        }
        prev = f;
    }
    return first.parentStory;
}

// Add a paragraph to a story. runs: a string, or a list of strings and
// {t: text, c: characterStyle}, {fn: footnote text}, {sp: SpecialCharacters...}.
function add(story, runs, style) {
    if (typeof runs == "string") {
        runs = [runs];
    }
    var start = story.characters.length;
    for (var i = 0; i < runs.length; i++) {
        var r = runs[i];
        if (typeof r == "string") {
            story.insertionPoints[-1].contents = r;
        } else if (r.fn !== undefined) {
            var fn = story.insertionPoints[-1].footnotes.add();
            fn.insertionPoints[-1].contents = r.fn;
        } else if (r.sp !== undefined) {
            story.insertionPoints[-1].contents = r.sp;
        } else {
            var a = story.characters.length;
            story.insertionPoints[-1].contents = r.t;
            if (r.c) {
                story.characters.itemByRange(a, story.characters.length - 1)
                    .appliedCharacterStyle = r.c;
            }
        }
    }
    story.insertionPoints[-1].contents = "\r";
    if (style) {
        story.characters[start].paragraphs[0].appliedParagraphStyle = style;
    }
    return story.characters[start].paragraphs[0];
}

function headFrame(doc, page) {
    var a = area(doc, page);
    var f = page.textFrames.add({geometricBounds: [a[0] - 27, a[1], a[0] - 13, a[3]]});
    f.textFramePreferences.verticalJustification = VerticalJustification.BOTTOM_ALIGN;
    return f;
}

function folioFrame(doc, page) {
    var a = area(doc, page);
    return page.textFrames.add({geometricBounds: [a[2] + 14, a[1], a[2] + 28, a[3]]});
}

function setHead(f, parts, style, align) {
    for (var i = 0; i < parts.length; i++) {
        f.insertionPoints[-1].contents = parts[i];
    }
    f.paragraphs[0].appliedParagraphStyle = style;
    f.paragraphs[0].justification = align;
}

function master(doc, prefix, base, parent) {
    var ms = doc.masterSpreads.add(2, {namePrefix: prefix, baseName: base});
    if (parent) {
        ms.appliedMaster = parent;
    }
    return ms;
}

function ensurePages(doc, n) {
    while (doc.pages.length < n) {
        doc.pages.add();
    }
}

function sectionProps(section, props) {
    setProps(section, props, "section");
}

// ---- the reference files ----

function footnotes(doc) {
    ensurePages(doc, 4);
    var st = bodyStyles(doc);
    var fnStyle = pstyle(doc, "Footnote", {appliedFont: BODY, pointSize: 9, leading: 11,
        firstLineIndent: 9, justification: Justification.LEFT_JUSTIFIED});
    var ref = cstyle(doc, "Footnote Reference", {position: Position.SUPERSCRIPT});
    var it = doc.characterStyles.itemByName("Italic");
    setProps(doc.footnoteOptions, {footnoteMarkerStyle: ref, footnoteTextStyle: fnStyle,
        separatorText: ". ", restartNumbering: E("FootnoteRestarting.SECTION_RESTART"),
        ruleOn: true, noSplitting: false, spaceBetween: 3}, "footnote options");
    // Chapter 1: pages 1-2; chapter 2 (its own story and section): pages 3-4.
    var s1 = flow(doc, [0, 1], 72);
    add(s1, "First Chapter", st.h1);
    add(s1, [filler(60, 0), {fn: "A short note with an "}], st.first);
    add(s1, [filler(50, 2), {fn: "Ibid."}, " ", filler(40, 3)], st.body);
    var nLong = filler(260, 4);
    add(s1, [filler(70, 5), {fn: "This note is long enough to run onto the next page. " + nLong}],
        st.body);
    add(s1, [filler(120, 6), {fn: "A note on the second page."}], st.body);
    add(s1, filler(160, 7), st.body);
    var s2 = flow(doc, [2, 3], 72);
    add(s2, "Second Chapter", st.h1);
    add(s2, [filler(60, 1), {fn: "Numbering restarts at 1 in a new section."}], st.first);
    add(s2, [filler(80, 2), {fn: "Second note of chapter two."}], st.body);
    add(s2, filler(200, 3), st.body);
    // Italic inside a footnote, by character style.
    var f = s1.footnotes[0];
    var a = f.characters.length;
    f.insertionPoints[-1].contents = "italic phrase";
    f.characters.itemByRange(a, f.characters.length - 1).appliedCharacterStyle = it;
    f.insertionPoints[-1].contents = " in it.";
    sectionProps(doc.sections.add(doc.pages[2]), {continueNumbering: true, marker: "Second Chapter"});
    sectionProps(doc.sections[0], {marker: "First Chapter"});
}

function sectionMarkers(doc) {
    ensurePages(doc, 7);
    var st = bodyStyles(doc);
    var a = doc.masterSpreads[0];
    a.baseName = "Body";
    var v = headFrame(doc, a.pages[0]);
    setHead(v, [SpecialCharacters.AUTO_PAGE_NUMBER, "  |  Reference Book"], st.head,
            Justification.LEFT_ALIGN);
    var r = headFrame(doc, a.pages[1]);
    setHead(r, [SpecialCharacters.SECTION_MARKER, "  |  ", SpecialCharacters.AUTO_PAGE_NUMBER],
            st.head, Justification.RIGHT_ALIGN);
    var chapters = [["First Chapter", [0, 1]],
                    ["Second Chapter", [2, 3]],
                    ["A Third Chapter with a Much Longer Title Than the Others", [4, 5, 6]]];
    for (var i = 0; i < chapters.length; i++) {
        var s = flow(doc, chapters[i][1], 72);
        add(s, chapters[i][0], st.h1);
        add(s, filler(200 * chapters[i][1].length, i), st.first);
        var sec = i === 0 ? doc.sections[0] : doc.sections.add(doc.pages[chapters[i][1][0]]);
        sectionProps(sec, {continueNumbering: true, marker: chapters[i][0]});
    }
}

function sectionNumbering(doc) {
    ensurePages(doc, 9);
    var st = bodyStyles(doc);
    var folio = pstyle(doc, "Folio", {basedOn: st.head, justification: Justification.CENTER_ALIGN});
    var a = doc.masterSpreads[0];
    a.baseName = "Body";
    for (var i = 0; i < 2; i++) {
        setHead(folioFrame(doc, a.pages[i]), [SpecialCharacters.AUTO_PAGE_NUMBER], folio,
                Justification.CENTER_ALIGN);
    }
    var c = master(doc, "C", "Front", a);
    var d = master(doc, "D", "Display");
    var e = master(doc, "E", "Blank");
    // Pages: 1 half-title, 2 blank, 3 title, 4 copyright, 5 contents, 6 blank, 7 preface (vi..),
    // 8-9 chapter 1 (arabic 1).
    var plan = [[d, "Reference Book"], [e, ""], [d, "Reference Book\rA Subtitle\rAuthor Name"],
                [d, "Copyright © 2026 Author Name. All rights reserved."],
                [c, "Contents"], [e, ""], [c, "Preface"], [a, "Chapter One"], [a, ""]];
    for (i = 0; i < plan.length; i++) {
        doc.pages[i].appliedMaster = plan[i][0];
        if (plan[i][1]) {
            var s = frame(doc, doc.pages[i], 72).parentStory;
            add(s, plan[i][1], st.h1);
            if (i >= 4) {
                add(s, filler(120, i), st.first);
            }
        }
    }
    sectionProps(doc.sections[0], {continueNumbering: false, pageNumberStart: 1,
        pageNumberStyle: PageNumberStyle.LOWER_ROMAN, marker: "Front matter"});
    sectionProps(doc.sections.add(doc.pages[7]), {continueNumbering: false, pageNumberStart: 1,
        pageNumberStyle: PageNumberStyle.ARABIC, marker: "Chapter One"});
}

function parentChild(doc) {
    ensurePages(doc, 6);
    var st = bodyStyles(doc);
    var folio = pstyle(doc, "Folio", {basedOn: st.head, justification: Justification.CENTER_ALIGN});
    var a = doc.masterSpreads[0];
    a.baseName = "Body";
    var heads = [], i;
    for (i = 0; i < 2; i++) {
        var h = headFrame(doc, a.pages[i]);
        if (i === 0) {
            setHead(h, [SpecialCharacters.AUTO_PAGE_NUMBER, "  |  Reference Book"], st.head,
                    Justification.LEFT_ALIGN);
        } else {
            setHead(h, ["Chapter Title  |  ", SpecialCharacters.AUTO_PAGE_NUMBER], st.head,
                    Justification.RIGHT_ALIGN);
        }
        heads.push(h);
    }
    // B-Opener is based on A-Body: it removes the running heads and drops the folio to the foot.
    var b = master(doc, "B", "Opener", a);
    for (i = 0; i < 2; i++) {
        try {
            heads[i].override(b.pages[i]).remove();
        } catch (e) {
            note("could not remove the running head on B-Opener: " + e.message);
        }
        setHead(folioFrame(doc, b.pages[i]), [SpecialCharacters.AUTO_PAGE_NUMBER], folio,
                Justification.CENTER_ALIGN);
    }
    var plan = [b, a, a, a, b, a];
    for (i = 0; i < plan.length; i++) {
        doc.pages[i].appliedMaster = plan[i];
    }
    var s1 = flow(doc, [0, 1, 2, 3], 108);
    add(s1, "Chapter Opener on B", st.h1);
    add(s1, filler(1000, 0), st.first);
    var s2 = flow(doc, [4, 5], 108);
    add(s2, "Second Opener on B", st.h1);
    add(s2, filler(450, 3), st.first);
}

function primaryFrame(doc) {
    var st = bodyStyles(doc);
    setProps(doc.textPreferences, {smartTextReflow: true, addPages: E("AddPageOptions.END_OF_STORY"),
        limitToMasterTextFrames: true, deleteEmptyPages: true}, "text preferences");
    var a = doc.masterSpreads[0];
    // A preset's "primary text frame" setting is ignored when a script creates the document,
    // so the master frames are made here, threaded verso -> recto, and the verso one made
    // primary (as in the earlier test file).
    var verso = a.pages[0].textFrames.length ? a.pages[0].textFrames[0] : frame(doc, a.pages[0]);
    var recto = a.pages[1].textFrames.length ? a.pages[1].textFrames[0] : frame(doc, a.pages[1]);
    try {
        verso.nextTextFrame = recto;
    } catch (e0) {
        note("could not thread the master frames: " + e0.message);
    }
    try {
        a.primaryTextFrame = verso;
    } catch (e1) {
        note("could not make the master frame primary: " + e1.message);
    }
    var mf = null;
    try {
        mf = a.primaryTextFrame;
    } catch (e) {
        note("no primary text frame on A-Parent: " + e.message);
    }
    // One page only: the text goes into page 1's frame (the one linked to the primary frame)
    // and smart text reflow adds the pages it needs. No frames are made by the script.
    var page1 = doc.pages[0];
    var f1 = linkedFrame(page1, page1.side == PageSideOptions.LEFT_HAND ? verso : recto);
    var story = f1.parentStory;
    add(story, "Text in the Primary Frame", st.h1);
    // About six pages of text: InDesign should add the pages (smart text reflow).
    add(story, filler(2600, 0), st.first);
    try {
        doc.recompose();
    } catch (e3) {}
    note("pages after placing the text: " + doc.pages.length + " (started with 1); overset: " +
         story.overflows + "; frames in the story: " + story.textContainers.length +
         "; primary frame on A-Parent: " + primaryId(mf));
}

// The page's frame that overrides the given master frame, overriding it if InDesign hasn't.
function linkedFrame(page, masterFrame) {
    for (var i = 0; i < page.textFrames.length; i++) {
        var tf = page.textFrames[i];
        try {
            if (tf.overriddenMasterPageItem.id == masterFrame.id) {
                return tf;
            }
        } catch (e) {}
    }
    try {
        return masterFrame.override(page);
    } catch (e2) {
        note("could not override the master frame on page " + page.name + ": " + e2.message);
        return page.textFrames.length ? page.textFrames[0] : null;
    }
}

function primaryId(f) {
    try {
        return f.id;
    } catch (e) {
        return "none";
    }
}

function tableOfContents(doc) {
    ensurePages(doc, 7);
    var st = bodyStyles(doc);
    var tt = pstyle(doc, "Contents Title", {basedOn: st.h1});
    var a = area(doc, doc.pages[0]);
    var tabs = [{alignment: TabStopAlignment.RIGHT_ALIGN, position: a[3] - a[1], leader: ". "}];
    var t1 = pstyle(doc, "Contents 1", {basedOn: st.body, firstLineIndent: 0, fontStyle: "Bold",
        justification: Justification.LEFT_ALIGN, spaceBefore: 6, tabList: tabs});
    var t2 = pstyle(doc, "Contents 2", {basedOn: st.body, firstLineIndent: 0, leftIndent: 18,
        justification: Justification.LEFT_ALIGN, tabList: tabs});
    var chapters = ["Chapter One", "Chapter Two", "A Third Chapter"];
    for (var i = 0; i < chapters.length; i++) {
        var s = flow(doc, [1 + 2 * i, 2 + 2 * i], 72);
        add(s, chapters[i], st.h1);
        add(s, filler(150, i), st.first);
        add(s, "First Section of " + chapters[i], st.h2);
        add(s, filler(200, i + 1), st.first);
        add(s, "Second Section", st.h2);
        add(s, filler(150, i + 2), st.first);
    }
    var toc = doc.tocStyles.add({name: "Contents"});
    setProps(toc, {title: "Contents", titleStyle: tt}, "TOC style");
    var levels = [[st.h1, t1, 1], [st.h2, t2, 2]];
    for (i = 0; i < levels.length; i++) {
        var e = toc.tocStyleEntries.add({name: levels[i][0].name});
        setProps(e, {formatStyle: levels[i][1], level: levels[i][2],
            pageNumberPosition: PageNumberPosition.AFTER_ENTRY, separator: "^t"}, "TOC entry");
    }
    try {
        doc.layoutWindows[0].activePage = doc.pages[0];
        var stories = doc.createTOC(toc, false, undefined, [a[1], a[0]], true);
        var f = stories[0].textContainers[0];
        if (f.parentPage.documentOffset !== 0) {
            f.move(doc.pages[0]);
        }
        f.geometricBounds = a;
    } catch (e2) {
        note("could not generate the TOC: " + e2.message + " (generate it by hand: Layout > "
             + "Table of Contents, style Contents, on page 1)");
    }
}

function tables(doc) {
    ensurePages(doc, 3);
    var st = bodyStyles(doc);
    var cellText = pstyle(doc, "Table Body", {basedOn: st.body, firstLineIndent: 0,
        pointSize: 9.5, leading: 12, justification: Justification.LEFT_ALIGN, hyphenation: false});
    var headText = pstyle(doc, "Table Head", {basedOn: cellText, fontStyle: "Bold"});
    var grey = doc.colors.add({name: "Table Grey", model: ColorModel.PROCESS,
        space: ColorSpace.CMYK, colorValue: [0, 0, 0, 12]});
    var headCell = doc.cellStyles.add({name: "Head Cell"});
    setProps(headCell, {appliedParagraphStyle: headText, fillColor: grey, topInset: 3,
        bottomInset: 3, leftInset: 4, rightInset: 4}, "cell style Head Cell");
    var bodyCell = doc.cellStyles.add({name: "Body Cell"});
    setProps(bodyCell, {appliedParagraphStyle: cellText, topInset: 3, bottomInset: 3,
        leftInset: 4, rightInset: 4}, "cell style Body Cell");
    var ts = doc.tableStyles.add({name: "Book Table"});
    setProps(ts, {headerRegionCellStyle: headCell, bodyRegionCellStyle: bodyCell,
        topBorderStrokeWeight: 1, bottomBorderStrokeWeight: 1, leftBorderStrokeWeight: 0,
        rightBorderStrokeWeight: 0}, "table style");
    var s = flow(doc, [0, 1, 2], 72);
    add(s, "Tables", st.h1);
    add(s, filler(150, 0), st.first);
    var ip = s.insertionPoints[-1];
    var rows = 40, cols = 4;
    var t = ip.tables.add({headerRowCount: 1, bodyRowCount: rows, columnCount: cols});
    var cells = ["Book", "Chapters", "Verses", "Notes"];
    for (var r = 1; r <= rows; r++) {
        cells.push("Book " + r, String(r % 50 + 1), String(r * 31 % 900), r % 7 === 0 ?
                   "A longer note that wraps onto a second line in its cell." : "");
    }
    t.contents = cells;
    t.appliedTableStyle = ts;
    var aa = area(doc, doc.pages[0]);
    t.width = aa[3] - aa[1];
    try {
        t.rows[5].cells[2].merge(t.rows[5].cells[3]);
    } catch (e) {
        note("could not merge cells: " + e.message);
    }
    add(s, "", st.body);
    add(s, filler(200, 3), st.body);
}

function opentype(doc) {
    ensurePages(doc, 2);
    var st = bodyStyles(doc);
    var ot = pstyle(doc, "Body OpenType", {basedOn: st.body, ligatures: true,
        otfFigureStyle: E("OTFFigureStyle.PROPORTIONAL_OLDSTYLE"), kerningMethod: "Optical"});
    var lin = pstyle(doc, "Body Lining", {basedOn: st.body, ligatures: false,
        otfFigureStyle: E("OTFFigureStyle.TABULAR_LINING"), kerningMethod: "Metrics"});
    var single = pstyle(doc, "Body Single-line", {basedOn: st.body,
        composer: "Adobe Single-line Composer"});
    var nohy = pstyle(doc, "Body No Hyphenation", {basedOn: st.body, hyphenation: false});
    var head = pstyle(doc, "Balanced Heading", {basedOn: st.h1, balanceRaggedLines: true,
        justification: Justification.CENTER_ALIGN});
    var sc = cstyle(doc, "Small Caps", {capitalization: Capitalization.SMALL_CAPS});
    var asc = cstyle(doc, "All Small Caps", {capitalization: Capitalization.CAP_TO_SMALL_CAP});
    var dlig = cstyle(doc, "Discretionary Ligatures", {otfDiscretionaryLigature: true});
    var frac = cstyle(doc, "Fraction", {otfFraction: true});
    var ord = cstyle(doc, "Ordinal", {otfOrdinal: true});
    var s = flow(doc, [0, 1], 36);
    try {
        s.storyPreferences.opticalMarginAlignment = true;
        s.storyPreferences.opticalMarginSize = 11;
    } catch (e) {
        note("could not set optical margin alignment: " + e.message);
    }
    add(s, "A Balanced Heading That Runs Long Enough to Take Two Lines", head);
    add(s, ["Ligatures: fi fl ff ffi ffl office affluent official. Old-style figures: ",
            "1234567890, 1776, 2026. Kerning optical. “Quoted lines” hang into the margin with optical alignment. ",
            filler(80, 0)], ot);
    add(s, ["Lining figures: 1234567890, 1776, 2026. Ligatures off: fi fl ff office. Kerning metrics. ",
            filler(60, 1)], lin);
    add(s, ["Small caps style: ", {t: "Chapter and Verse", c: sc}, ". All small caps: ",
            {t: "UNESCO, NASB, LXX", c: asc}, ". Discretionary ligatures: ",
            {t: "ct st", c: dlig}, ". Fractions: ", {t: "1/2 3/4", c: frac}, ". Ordinals: ",
            {t: "1st 2nd 3rd", c: ord}, ". ", filler(60, 2)], st.body);
    add(s, ["Single-line composer: ", filler(120, 3)], single);
    add(s, ["Paragraph composer: ", filler(120, 3)], st.body);
    add(s, ["Hyphenation off: ", filler(120, 4)], nohy);
}

function baselineGrid(doc) {
    ensurePages(doc, 2);
    var st = bodyStyles(doc);
    var m = doc.pages[0].marginPreferences;
    setProps(doc.gridPreferences, {baselineStart: m.top, baselineDivision: 14,
        baselineGridShown: true,
        baselineGridRelativeOption: E("BaselineGridRelativeOption.TOP_OF_MARGIN_OF_BASELINE_GRID_RELATIVE_OPTION")},
        "grid preferences");
    var styles = [st.body, st.first, st.h1, st.h2];
    for (var i = 0; i < styles.length; i++) {
        setProps(styles[i], {alignToBaseline: true}, styles[i].name);
    }
    setProps(st.h2, {spaceBefore: 7}, "Heading A");   // half a line: snaps to the next grid line
    var quote = pstyle(doc, "Block Quote", {basedOn: st.body, pointSize: 10, leading: 12,
        leftIndent: 18, firstLineIndent: 0, alignToBaseline: false, spaceBefore: 7, spaceAfter: 7});
    var s = flow(doc, [0, 1], 72);
    add(s, "On the Grid", st.h1);
    add(s, filler(150, 0), st.first);
    add(s, "A Heading with Half a Line Before", st.h2);
    add(s, filler(120, 1), st.first);
    add(s, "A block quote set off the grid, at 10 on 12. " + filler(60, 2), quote);
    add(s, filler(250, 3), st.body);
}

var GEN = "בְּרֵאשִׁ֖ית " +
    "בָּרָ֣א אֱלֹהִ֑ים " +
    "אֵ֥ת הַשָּׁמַ֖יִם " +
    "וְאֵ֥ת הָאָֽרֶץ׃";
var GEN_PLAIN = "בראשית ברא אלהים";
var JOHN = "Ἐν ἀρχῇ ἦν ὁ λόγος, " +
    "καὶ ὁ λόγος ἦν πρὸς " +
    "τὸν θεόν, καὶ θεὸς " +
    "ἦν ὁ λόγος.";

function hebrewGreek(doc) {
    ensurePages(doc, 2);
    var st = bodyStyles(doc);
    var wr = pstyle(doc, "Body World-Ready", {basedOn: st.body,
        composer: "Adobe World-Ready Paragraph Composer"});
    // Direction and language are set in the styles this time (the earlier test had them as
    // local overrides, which Affinity ignored).
    var heb = cstyle(doc, "Hebrew", {appliedFont: HEBREW, fontStyle: "Regular",
        appliedLanguage: "Hebrew",
        characterDirection: E("CharacterDirectionOptions.RIGHT_TO_LEFT_DIRECTION")});
    var grk = cstyle(doc, "Greek", {appliedFont: GREEK, fontStyle: "Regular",
        appliedLanguage: "Greek"});
    var hebPara = pstyle(doc, "Hebrew Block", {basedOn: wr, appliedFont: HEBREW,
        fontStyle: "Regular", pointSize: 13, leading: 18, firstLineIndent: 0,
        appliedLanguage: "Hebrew", justification: Justification.RIGHT_ALIGN,
        paragraphDirection: E("ParagraphDirectionOptions.RIGHT_TO_LEFT_DIRECTION"),
        characterDirection: E("CharacterDirectionOptions.RIGHT_TO_LEFT_DIRECTION")});
    var s = flow(doc, [0, 1], 72);
    add(s, "Hebrew and Greek", st.h1);
    add(s, ["World-Ready composer. Genesis 1:1 reads ", {t: GEN, c: heb},
            " and the phrase is long enough that it should wrap across a line when set in a "
            + "paragraph of this width, which tests how the bidirectional run breaks. Unpointed: ",
            {t: GEN_PLAIN, c: heb}, ". John 1:1 reads ", {t: JOHN, c: grk}, " " + filler(40, 0)],
        wr);
    add(s, ["Paragraph composer (not World-Ready), same text: ", {t: GEN, c: heb},
            " and then John: ", {t: JOHN, c: grk}, "."], st.body);
    add(s, GEN + " " + GEN, hebPara);
    add(s, ["Greek by language only, in the body font: ", {t: JOHN, c: grk}], wr);
    note("fonts: Hebrew " + HEBREW + ", Greek " + GREEK);
}

function makeImage() {
    var dir = Folder(outFolder + "/images");
    if (!dir.exists) {
        dir.create();
    }
    var file = File(dir + "/sample.jpg");
    var d = app.documents.add(false);
    try {
        d.viewPreferences.horizontalMeasurementUnits = MeasurementUnits.POINTS;
        d.viewPreferences.verticalMeasurementUnits = MeasurementUnits.POINTS;
        d.documentPreferences.facingPages = false;
        d.documentPreferences.pageWidth = 216;
        d.documentPreferences.pageHeight = 144;
        var blue = d.colors.add({name: "Sample Blue", model: ColorModel.PROCESS,
            space: ColorSpace.RGB, colorValue: [40, 90, 160]});
        d.pages[0].rectangles.add({geometricBounds: [0, 0, 144, 216], fillColor: blue,
            strokeWeight: 0});
        var t = d.pages[0].textFrames.add({geometricBounds: [50, 10, 100, 206],
            contents: "Sample image"});
        t.paragraphs[0].pointSize = 24;
        t.paragraphs[0].justification = Justification.CENTER_ALIGN;
        t.paragraphs[0].fillColor = d.swatches.itemByName("Paper");
        app.jpegExportPreferences.exportResolution = 150;
        app.jpegExportPreferences.jpegExportRange = ExportRangeOrAllPages.EXPORT_ALL;
        d.exportFile(ExportFormat.JPG, file);
    } finally {
        d.close(SaveOptions.NO);
    }
    return file;
}

function images(doc) {
    ensurePages(doc, 2);
    var st = bodyStyles(doc);
    var cap = pstyle(doc, "Caption", {basedOn: st.body, pointSize: 9, leading: 11,
        firstLineIndent: 0, fontStyle: "Italic", justification: Justification.CENTER_ALIGN,
        spaceAfter: 7});
    var fig = pstyle(doc, "Figure", {basedOn: st.body, firstLineIndent: 0,
        justification: Justification.CENTER_ALIGN, spaceBefore: 7, spaceAfter: 4});
    var img = makeImage();
    var s = flow(doc, [0, 1], 72);
    add(s, "Images", st.h1);
    add(s, filler(80, 0), st.first);
    // An inline (anchored) image in its own paragraph, as Word's inline pictures become.
    var p = add(s, "", fig);
    var ip = p.insertionPoints[0];
    var r = ip.rectangles.add({geometricBounds: [0, 0, 108, 162]});
    r.place(img);
    r.fit(FitOptions.PROPORTIONALLY);
    r.fit(FitOptions.FRAME_TO_CONTENT);
    add(s, "Figure 1. An inline image, anchored in the text.", cap);
    add(s, filler(400, 1), st.body);
    // A free image on page 2 with a bounding-box text wrap.
    var page = doc.pages[1];
    var a = area(doc, page);
    var fr = page.rectangles.add({geometricBounds: [a[0] + 120, a[1], a[0] + 216, a[1] + 144]});
    fr.place(img);
    fr.fit(FitOptions.PROPORTIONALLY);
    setProps(fr.textWrapPreferences, {textWrapMode: TextWrapModes.BOUNDING_BOX_TEXT_WRAP,
        textWrapOffset: [6, 6, 6, 9]}, "text wrap");
    note("image linked from " + img.fsName);
}

function charStyles(doc) {
    ensurePages(doc, 1);
    var st = bodyStyles(doc);
    // Partly defined character styles: each sets one thing and should keep the paragraph's
    // font and size (Affinity gave GREP-applied text the wrong font and size in the article).
    var it = doc.characterStyles.itemByName("Italic");
    var bold = cstyle(doc, "Bold", {fontStyle: "Bold"});
    var bi = cstyle(doc, "Bold Italic", {fontStyle: "Bold Italic"});
    var sc = cstyle(doc, "Small Caps", {capitalization: Capitalization.SMALL_CAPS});
    var sup = cstyle(doc, "Superscript", {position: Position.SUPERSCRIPT});
    var und = cstyle(doc, "Underline", {underline: true});
    var nob = cstyle(doc, "No Break", {noBreak: true});
    var quote = pstyle(doc, "Block Quote", {basedOn: st.body, pointSize: 9.5, leading: 12,
        leftIndent: 18, firstLineIndent: 0, spaceBefore: 6, spaceAfter: 6});
    var head = pstyle(doc, "Sans Heading", {basedOn: st.h2, appliedFont: SANS, fontStyle: "Bold"});
    var s = flow(doc, [0], 72);
    add(s, "Character Styles", st.h1);
    var runs = ["Body text with ", {t: "italic", c: it}, ", ", {t: "bold", c: bold}, ", ",
                {t: "bold italic", c: bi}, ", ", {t: "Small Caps", c: sc}, ", a superscript",
                {t: "12", c: sup}, ", ", {t: "underline", c: und}, " and ",
                {t: "a phrase that must not break", c: nob}, ". "];
    add(s, runs.concat([filler(50, 0)]), st.first);
    add(s, ["The same in a smaller paragraph style: "].concat(runs), quote);
    add(s, ["In a sans heading: ", {t: "italic", c: it}, " and ", {t: "Small Caps", c: sc}], head);
    // Local overrides, as Word's direct formatting would become if not mapped to styles.
    var p = add(s, "Local italic override (no character style) in this sentence.", st.body);
    p.words.itemByRange(1, 1).fontStyle = "Italic";
}

function chapterStories(doc) {
    ensurePages(doc, 6);
    var st = bodyStyles(doc);
    var a = doc.masterSpreads[0];
    a.baseName = "Body";
    var b = master(doc, "B", "Opener", a);
    // Chapter one is longer than its pages: its story stays overset; chapter two still starts
    // on its own page. A blank verso (no master) sits before chapter two.
    doc.pages[0].appliedMaster = b;
    doc.pages[3].appliedMaster = NothingEnum.NOTHING;
    doc.pages[4].appliedMaster = b;
    var s1 = flow(doc, [0, 1, 2], 144);
    add(s1, "Chapter One (overset)", st.h1);
    add(s1, filler(1500, 0), st.first);
    var s2 = flow(doc, [4, 5], 144);
    add(s2, "Chapter Two", st.h1);
    add(s2, filler(500, 1), st.first);
    note("chapter one overset: " + s1.overflows);
}

var FILES = [
    ["01-footnotes", footnotes, 1, false,
     "Footnotes with a Footnote Reference character style, restart per section, a note split across pages."],
    ["02-section-marker-heads", sectionMarkers, 1, false,
     "Running heads from section markers (recto) and static text (verso); 3 sections."],
    ["03-section-numbering", sectionNumbering, 1, false,
     "Roman front matter (i), arabic from chapter 1; display pages with no folio; blank versos."],
    ["04-parent-child-masters", parentChild, 1, false,
     "B-Opener based on A-Body, removing the running heads and dropping the folio."],
    ["05-primary-text-frame", primaryFrame, 1, true,
     "Primary text frame on the master; page frames overridden from it and threaded; smart text reflow."],
    ["06-toc", tableOfContents, 1, false,
     "A TOC style (two levels, tab leader, bold level 1) and a generated contents."],
    ["07-table", tables, 1, false,
     "Table, cell and paragraph styles; header row repeating across pages; merged cells."],
    ["08-opentype", opentype, 1, false,
     "Ligatures, old-style figures, small caps, fractions, ordinals, composers, hyphenation, optical margins, balanced heading."],
    ["09-baseline-grid", baselineGrid, 1, false,
     "Baseline grid with body and headings aligned to it; a block quote off the grid."],
    ["10-hebrew-greek", hebrewGreek, 1, false,
     "Hebrew (pointed, cantillated) and polytonic Greek; direction and language in the styles."],
    ["11-images", images, 1, false,
     "An inline anchored image with caption, and a free image with text wrap (linked JPG)."],
    ["12-character-styles", charStyles, 1, false,
     "Partly defined character styles (italic, bold, small caps, superscript, no break) in different paragraph styles."],
    ["13-chapter-stories", chapterStories, 1, false,
     "One story per chapter; an overset chapter; a blank verso; openers on a B master."]
];

// Only the named files, if ONLY is not empty (e.g. ["05-primary-text-frame", "06-toc"]).
var ONLY = ["05-primary-text-frame"];

function wanted(name) {
    if (!ONLY.length) {
        return true;
    }
    for (var w = 0; w < ONLY.length; w++) {
        if (ONLY[w] == name) {
            return true;
        }
    }
    return false;
}

for (var i = 0; i < FILES.length; i++) {
    var name = FILES[i][0];
    if (!wanted(name)) {
        continue;
    }
    var doc = null;
    notes = [];
    try {
        doc = newDoc(FILES[i][2], FILES[i][3]);
        FILES[i][1](doc);
        doc.save(File(outFolder + "/" + name + ".indd"));
        doc.exportFile(ExportFormat.INDESIGN_MARKUP, File(outFolder + "/" + name + ".idml"));
        app.pdfExportPreferences.pageRange = PageRange.ALL_PAGES;
        app.pdfExportPreferences.exportReaderSpreads = true;
        doc.exportFile(ExportFormat.PDF_TYPE, File(outFolder + "/" + name + " (InDesign).pdf"),
                       false);
        var missing = [];
        for (var f = 0; f < doc.fonts.length; f++) {
            if (doc.fonts[f].status != FontStatus.INSTALLED) {
                missing.push(doc.fonts[f].name.replace("\t", " "));
            }
        }
        if (missing.length) {
            notes.push("missing fonts: " + missing.join(", "));
        }
        log.push("OK      " + name + "  (" + doc.pages.length + " pages)  " + FILES[i][4]);
    } catch (e) {
        log.push("FAILED  " + name + ": " + e.message + " (line " + e.line + ")");
    } finally {
        for (var n = 0; n < notes.length; n++) {
            log.push("          " + notes[n]);
        }
        if (doc && doc.isValid) {
            doc.close(SaveOptions.NO);
        }
    }
}

app.scriptPreferences.userInteractionLevel = oldInteraction;
app.pdfExportPreferences.exportReaderSpreads = oldSpreads;
app.pdfExportPreferences.pageRange = oldRange;

var header = ["Reference files, script version " + SCRIPT_VERSION,
              "InDesign " + app.version + " (" + app.name + ")",
              "Fonts: body " + BODY + ", sans " + SANS + ", Hebrew " + HEBREW + ", Greek " + GREEK,
              ""];
var lf = File(outFolder + "/reference-log.txt");
lf.encoding = "UTF-8";
lf.open("w");
lf.write(header.concat(log).join("\n") + "\n");
lf.close();
alert("Reference files done.\n\n" + log.join("\n").substr(0, 1500) +
      "\n\nThe full log is reference-log.txt in the chosen folder.");

}());
