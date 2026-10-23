"""Pagination, masters and running heads for the exporter (moved out of export.py).

PaginationMixin is part of export.Exporter: it places the book's blocks on pages (layout.plan_pages),
gives each unit its story and section (recto rules, roman/arabic numbering, section markers for
the running heads) and builds the masters: A-Body, B-Opener, C-Front with their primary text
frames and folios, D-Display, E-Blank, and a copy of A-Body per part when the verso head is the
part's title. A running head from the section marker can carry only one font, so a unit whose
head has Hebrew or Greek gets a copy of its master (R1-Body, R2-Front...) with the head as
text, which takes the Hebrew and Greek styles.
"""


def _has_script(text):
    return any(is_hebrew(c) or is_greek(c) for c in text or "")

from . import frontmatter, layout
from .docx_reader import is_greek, is_hebrew
from .layout import _half
from .idml.model import Frame, Master, Paragraph, Run, Section, Story, TOCStyle


class PaginationMixin:
    # ---- pagination and running heads ----

    def _short(self, title):
        return (self.settings.get("short_titles") or {}).get(title) or title

    def _head_frames(self, verso, recto):
        """Running heads above the text area: verso and recto paragraphs' runs."""
        doc, m = self.doc, self.doc.margins
        out = []
        for side, runs in (("verso", verso), ("recto", recto)):
            if runs is None:
                continue
            left = m["outside"] if side == "verso" else m["inside"]
            right = doc.width - (m["inside"] if side == "verso" else m["outside"])
            out.append(Frame(side, (m["top"] - 27, left, m["top"] - 13, right),
                             [Paragraph("Running Head", runs)], key=side[0] + "head",
                             valign="BottomAlign"))
        return out

    def _paginate(self, blocks):
        """Pages, masters, sections and running heads; returns the page count."""
        doc = self.doc
        sink = _half(self.body_lead * 6)
        items = []
        for b in blocks:
            kind = b.kind
            if b.sink is None:
                b.sink = 0 if kind in ("display", "part") else sink
            spare = b.spare if b.spare is not None else \
                (0 if kind in ("display", "part") else self._spare())
            est = b.pages or self._estimate(b.paras, b.sink)
            items.append((kind, est, spare, b.opens))
        placed, count, masters, first_body = layout.plan_pages(
            items, self.profile.get("chapters_open", "recto"))
        doc.stories, doc.sections = [], []
        optical = self.body_size if self.profile["typography"]["optical_margins"] else None
        rh = self.profile["running_heads"]
        part = None
        part_masters = []
        script_heads = []           # (marker, part title or None, pages) for R masters
        long_heads = []
        for n, (b, pl) in enumerate(zip(blocks, placed)):
            pages = list(range(pl.start, pl.start + pl.pages))
            doc.stories.append(Story(b.paras, pages, sink=b.sink, linked=True,
                                     optical_margins=optical, valign=b.valign))
            title = b.title if not b.title.startswith("(") and b.kind != "display" else ""
            marker = self._short(title)
            if marker and self._too_long(marker):
                long_heads.append(marker)
            body = first_body is not None and n >= first_body
            start = 1 if n == 0 or n == first_body else None
            # A blank verso before a unit belongs to the section before it.
            doc.sections.append(Section(pl.start, marker=marker,
                                        numbering="Arabic" if body else "LowerRoman",
                                        start=start))
            if b.kind == "part":
                part = self._short(b.title)
                part_masters.append(part)
            elif body and part and rh.get("verso") == "part":
                name = "P%d-Body" % len(part_masters)
                for i in pages:
                    if masters.get(i) == "A-Body":
                        masters[i] = name
            if _has_script(marker) and b.kind != "part":
                script_heads.append((marker, part if body else None, pages))
        doc.page_count = max(count, 1)
        doc.page_masters = masters
        if not doc.sections:
            doc.sections = [Section(0, start=1)]
        self._masters(part_masters)
        self._script_head_masters(script_heads, masters)
        if long_heads:
            self.report.append("Running heads too long for the page: %s. Give these a short "
                               "title in the book settings." % "; ".join(
                                   '"%s"' % h for h in long_heads))
        if self.contents_depth:
            levels = [("Chapter Title", 1, "Contents 1"), ("Part Title", 1, "Contents 1")]
            if self.contents_depth == "sections":
                levels.append(("Heading A", 2, "Contents 2"))
            lang = self.profile["front_matter"].get("language", "en")
            doc.toc_styles = [TOCStyle("Contents", frontmatter.texts(lang)["contents"],
                                       "Contents Title", levels)]
        est = sum(i[1] for i in items)
        blanks = sum(1 for v in masters.values() if v == "E-Blank")
        g, m = self.geo, doc.margins
        spare = self._spare()
        self.report.append("%d pages: about %d of text, %d blank verso%s." % (
            doc.page_count, est, blanks, "" if blanks == 1 else "s"))
        if spare == 1:
            self.report.append("Each chapter ends with a spare page. Where it stays empty, delete "
                               "it together with the blank page after it, or give it the E-Blank "
                               "master, so chapters keep their sides.")
        elif spare == 2:
            self.report.append("Each chapter ends with two spare pages. Delete unused ones two at "
                               "a time, so chapters keep their sides.")
        else:
            self.report.append("No spare pages: InDesign adds pages to a chapter whose text runs "
                               "over (then check that later chapters still open on a recto); "
                               "Affinity doesn't, so in Affinity add pages to a chapter whose "
                               "text runs over, two at a time.")
        self.report.append(self._leading_note())
        self.report.append(
            "Margins (in): top %.3g, bottom %.3g, inside %.3g, outside %.3g; text %d lines of "
            "%g pt, about %d characters per line."
            % (m["top"] / 72, m["bottom"] / 72, m["inside"] / 72, m["outside"] / 72, g.lines,
               self.body_lead, round(g.cpl)))
        return doc.page_count

    def _spare(self):
        try:
            return max(0, min(2, int(self.profile["page"].get("spare_pages") or 0)))
        except (TypeError, ValueError):
            return 0

    def _too_long(self, text):
        attrs = self._resolved_attrs("Running Head")
        size = attrs.get("PointSize", self.body_size)
        return len(text) * size * self.avg_width * 1.1 > self.measure * 0.8

    def _masters(self, parts):
        """A-Body, B-Opener and C-Front carry text (each its own primary text frames, so a
        chapter threads from B into A); D-Display and E-Blank are empty. Running heads follow
        the profile: the recto head is the section marker (the chapter's short title), the
        verso head the book title, author, chapter, part or custom text; C-Front shows the
        unit's title on both sides. Parts with part verso heads get a master each (P1-Body...),
        a copy of A-Body with the part's title."""
        doc = self.doc
        rh = self.profile["running_heads"]
        info = self.info
        marker = [Run(special="section_marker")]
        verso_kind = rh.get("verso", "book_title")
        verso = {"book_title": [Run(info.get("short_title") or info["title"])],
                 "author": [Run(info["author"])], "chapter": marker,
                 "custom": [Run(rh.get("verso_custom") or "")]}.get(verso_kind)
        recto = [Run(rh.get("recto_custom") or "")] if rh.get("recto") == "custom" else marker

        frames = self._master_frames
        doc.masters = [
            Master("A", "Body", frames=frames(True, verso or marker, recto)),
            Master("B", "Opener", frames=frames(not rh.get("suppress_on_openers", True),
                                                verso or marker, recto)),
            Master("C", "Front", frames=frames(True, marker, marker)),
            Master("D", "Display", frames=[] if rh.get("suppress_on_display", True)
                   else self._head_frames(verso or marker, recto)),
            Master("E", "Blank", frames=[] if rh.get("suppress_on_blanks", True)
                   else self._head_frames(verso or marker, recto))]
        if verso_kind == "part":
            for k, title in enumerate(parts, 1):
                doc.masters.append(Master("P%d" % k, "Body",
                                          frames=frames(True, [Run(title)], recto)))

    def _master_frames(self, heads=True, verso_runs=None, recto_runs=None):
        """A text master's frames: primary text frames and folios on both sides, and the
        running heads if wanted."""
        doc, m = self.doc, self.doc.margins
        top, bottom = m["top"], doc.height - m["bottom"]
        out = []
        for side in ("verso", "recto"):
            left = m["outside"] if side == "verso" else m["inside"]
            right = doc.width - (m["inside"] if side == "verso" else m["outside"])
            out.append(Frame(side, (top, left, bottom, right), [], primary=True))
            out.append(Frame(side, (bottom + 14, left, bottom + 28, right),
                             [Paragraph("Folio", [Run(special="page_number")])],
                             key="folio"))
        if heads:
            out += self._head_frames(verso_runs, recto_runs)
        return out

    def _script_head_masters(self, units, masters):
        """Units whose running head has Hebrew or Greek: a copy of their A-Body (or part's
        P-Body) or C-Front master with the head written as text instead of the section
        marker, so _generated_scripts can give the Hebrew its style."""
        if not units:
            return
        doc, rh, info = self.doc, self.profile["running_heads"], self.info
        verso_kind = rh.get("verso", "book_title")
        custom_recto = rh.get("recto") == "custom"
        names = []
        for k, (marker, part, pages) in enumerate(units, 1):
            head = [Run(marker)]
            recto = [Run(rh.get("recto_custom") or "")] if custom_recto else head
            verso = {"book_title": [Run(info.get("short_title") or info["title"])],
                     "author": [Run(info["author"])], "chapter": head,
                     "part": [Run(part)] if part else head,
                     "custom": [Run(rh.get("verso_custom") or "")]}.get(verso_kind, head)
            made = {}
            for i in pages:
                base = masters.get(i)
                if base in ("A-Body",) or (base or "").startswith("P"):
                    kind, frames = "Body", (verso, recto)
                elif base == "C-Front":
                    kind, frames = "Front", (head, head)
                else:
                    continue                  # openers, display and blank pages: no heads
                if kind not in made:
                    made[kind] = Master("R%d" % k, kind,
                                        frames=self._master_frames(True, *frames))
                    doc.masters.append(made[kind])
                    if made[kind].name not in names:
                        names.append(made[kind].name)
                masters[i] = made[kind].name
        if names:
            self.report.append(
                "Running heads with Hebrew or Greek are written as text on masters of their "
                "own (%s), so the Hebrew and Greek get their fonts. To change such a head, "
                "edit it on that master." % ", ".join(names))
