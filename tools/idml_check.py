"""Structural checks on an IDML package, the part of validation that doesn't need the schema.

    python tools/idml_check.py file.idml [...]

Checks: the zip (mimetype first, stored, right content), META-INF/container.xml, every XML part
well formed, DOMVersion 21.5 in every part, designmap.xml's references and the package's files
matching both ways, the StoryList against the stories, and the links between parts (frames to
stories, threading both ways, pages to masters, master overrides, sections to pages, primary
text frames). Validation against Adobe's schema (jing) is added when the schema is in
idml-schema/. Development tool; not part of the shipped program.
"""

import posixpath
import sys
import zipfile

from lxml import etree

PKG = "http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging"
MIMETYPE = b"application/vnd.adobe.indesign-idml-package"
DOM_VERSION = "21.5"
CONTAINER = "urn:oasis:names:tc:opendocument:xmlns:container"


def check(path):
    """Return a list of problems (empty when the package is sound)."""
    problems = []
    try:
        z = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as e:
        return ["not a zip package: %s" % e]
    with z:
        infos = z.infolist()
        names = [i.filename for i in infos]
        if not infos or infos[0].filename != "mimetype":
            problems.append("mimetype is not the first entry")
        elif infos[0].compress_type != zipfile.ZIP_STORED:
            problems.append("mimetype is compressed; it must be stored")
        if "mimetype" in names and z.read("mimetype").strip() != MIMETYPE:
            problems.append("mimetype content is %r" % z.read("mimetype")[:60])
        if len(set(names)) != len(names):
            problems.append("duplicate entries in the zip")

        roots = {}
        for n in names:
            if n.endswith(".xml"):
                try:
                    roots[n] = etree.fromstring(z.read(n), etree.XMLParser(resolve_entities=False,
                                                                          huge_tree=True))
                except etree.XMLSyntaxError as e:
                    problems.append("%s is not well-formed XML: %s" % (n, e))

        c = roots.get("META-INF/container.xml")
        if c is None:
            problems.append("META-INF/container.xml is missing")
        else:
            paths = [r.get("full-path") for r in c.iter("{%s}rootfile" % CONTAINER)]
            if paths != ["designmap.xml"]:
                problems.append("container.xml points to %s, not designmap.xml" % paths)

        for n, root in roots.items():
            if n.startswith("META-INF/"):
                continue
            v = root.get("DOMVersion")
            if v != DOM_VERSION:
                problems.append("%s has DOMVersion %s (must be %s)" % (n, v, DOM_VERSION))

        dm = roots.get("designmap.xml")
        if dm is None:
            problems.append("designmap.xml is missing")
            return problems
        problems += _check_references(dm, names)
        problems += _check_links(dm, roots)
    return problems


def _check_references(dm, names):
    problems = []
    refs = [el.get("src") for el in dm.iter() if isinstance(el.tag, str)
            and el.tag.startswith("{%s}" % PKG) and el.get("src")]
    for r in refs:
        if r not in names:
            problems.append("designmap.xml refers to %s, which is not in the package" % r)
    listed = set(refs)
    for n in names:
        if n in ("mimetype", "designmap.xml") or n.startswith("META-INF/") or n.endswith("/"):
            continue
        if n not in listed:
            problems.append("%s is in the package but designmap.xml doesn't refer to it" % n)
    return problems


def _items(roots, prefix, tag):
    out = {}
    for n, root in roots.items():
        if n.startswith(prefix):
            for el in root.iter(tag):
                out[el.get("Self")] = (n, el)
    return out


def _check_links(dm, roots):
    problems = []
    stories = {}
    for n, root in roots.items():
        if n.startswith("Stories/"):
            for st in root.iter("Story"):
                stories[st.get("Self")] = n
    listed = (dm.get("StoryList") or "").split()
    for sid in stories:
        if sid not in listed:
            problems.append("story %s is not in designmap's StoryList" % sid)
    for sid in listed:
        if sid not in stories and not _backing(roots, sid):
            problems.append("StoryList names %s, but there is no such story" % sid)

    masters = _items(roots, "MasterSpreads/", "MasterSpread")
    frames = {}
    frames.update(_items(roots, "Spreads/", "TextFrame"))
    frames.update(_items(roots, "MasterSpreads/", "TextFrame"))
    frames.update(_items(roots, "Stories/", "TextFrame"))   # anchored frames
    master_items = {}
    for n, root in roots.items():
        if n.startswith("MasterSpreads/"):
            for el in root.iter():
                if isinstance(el.tag, str) and el.get("Self"):
                    master_items[el.get("Self")] = n
    page_items = set()
    for n, root in roots.items():
        if n.startswith("Spreads/"):
            for el in root.iter():
                if isinstance(el.tag, str) and el.get("Self"):
                    page_items.add(el.get("Self"))

    for fid, (n, f) in frames.items():
        ps = f.get("ParentStory")
        if ps and ps not in stories:
            problems.append("%s: frame %s belongs to story %s, which doesn't exist" % (n, fid, ps))
        nxt, prv = f.get("NextTextFrame"), f.get("PreviousTextFrame")
        if nxt and nxt != "n":
            if nxt not in frames:
                problems.append("%s: frame %s threads to %s, which doesn't exist" % (n, fid, nxt))
            elif frames[nxt][1].get("PreviousTextFrame") != fid:
                problems.append("frame %s threads to %s, but %s doesn't thread back"
                                % (fid, nxt, nxt))
            elif frames[nxt][1].get("ParentStory") != ps:
                problems.append("frames %s and %s are threaded but belong to different stories"
                                % (fid, nxt))
        if prv and prv != "n" and prv not in frames:
            problems.append("%s: frame %s follows %s, which doesn't exist" % (n, fid, prv))

    for mid, (n, ms) in masters.items():
        ptf = ms.get("PrimaryTextFrame")
        if ptf and ptf != "n" and (ptf not in frames or frames[ptf][0] != n):
            problems.append("master %s: primary text frame %s is not one of its frames"
                            % (ms.get("Name"), ptf))
        for pg in ms.iter("Page"):
            am = pg.get("AppliedMaster")
            if am and am != "n" and am not in masters:
                problems.append("master %s is based on %s, which doesn't exist"
                                % (ms.get("Name"), am))

    pages = {}
    for n, root in roots.items():
        if not n.startswith("Spreads/"):
            continue
        for pg in root.iter("Page"):
            pages[pg.get("Self")] = pg
            am = pg.get("AppliedMaster")
            if am and am != "n" and am not in masters:
                problems.append("%s: page %s uses master %s, which doesn't exist"
                                % (n, pg.get("Name"), am))
            pairs = (pg.get("OverrideList") or "").split()
            if len(pairs) % 2:
                problems.append("page %s: OverrideList has an odd number of ids" % pg.get("Name"))
            for i in range(0, len(pairs) - 1, 2):
                if pairs[i] not in master_items:
                    problems.append("page %s overrides master item %s, which doesn't exist"
                                    % (pg.get("Name"), pairs[i]))
                if pairs[i + 1] not in page_items:
                    problems.append("page %s: overriding item %s is not on any spread"
                                    % (pg.get("Name"), pairs[i + 1]))
    for s in dm.iter("Section"):
        if s.get("PageStart") not in pages:
            problems.append("section %s starts on page %s, which doesn't exist"
                            % (s.get("Self"), s.get("PageStart")))
    return problems


def _backing(roots, sid):
    bs = roots.get("XML/BackingStory.xml")
    return bs is not None and any(el.get("Self") == sid for el in bs.iter())


def main(argv=None):
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    bad = 0
    for path in args:
        problems = check(path)
        name = posixpath.basename(path.replace("\\", "/"))
        if problems:
            bad += 1
            print("%s: %d problem(s)" % (name, len(problems)))
            for p in problems:
                print("  - " + p)
        else:
            print("%s: OK (structure; schema not checked)" % name)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
