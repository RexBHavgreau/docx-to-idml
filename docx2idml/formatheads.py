"""Headings set by direct formatting instead of styles.

Some manuscripts arrive without heading styles: the author made headings bigger, bold, centered
or in capitals by hand. This module finds such paragraphs and groups them by look, so they can
be mapped like styles (they show in the Style Map tab as "[14 pt bold centered]" and so on).

Only what the styles don't already provide is guessed: if the file has chapter-title styles in
use, guessed groups start at the first heading level below chapters; if it has heading styles
too, nothing is guessed. Only paragraphs whose style maps to body text are candidates.

A candidate is a short paragraph (at most 15 words, no closing period unless it is numbered like
"1." or "Chapter 3."), not in a table or note, with text under it (a paragraph of 20 words or
more, not centered like a title-page line) before the next paragraph of the same look, whose look stands out from the body text: larger, bold, capitals or small caps, centered, or (weakest) italic. Paragraphs
with the same look form a group; a group needs two members unless it is clearly prominent
(larger type or starting a page). Groups are ranked by prominence: the most prominent becomes
chapter titles (when chapters aren't styled), the next Heading A, then B, then C.
"""

import re
from collections import Counter
from dataclasses import dataclass, field

MAX_WORDS = 15
TEXT_WORDS = 20       # a paragraph of at least this many words counts as text under a heading
_NUMBERED = re.compile(r"^(chapter|part|cap[ií]tulo|parte|section|\d+(\.\d+)*|[ivxlc]+|[a-z])"
                       r"[\s.:)]", re.I)
LEVEL_STYLES = {0: "Chapter Title", 1: "Heading A", 2: "Heading B", 3: "Heading C"}


@dataclass
class Group:
    look: tuple                 # (size, bold, italic, caps, centered)
    name: str                   # "[14 pt bold centered]"
    paragraphs: list = field(default_factory=list)   # paragraph indexes
    starts_page: int = 0        # members that start a page
    role: str = "heading"
    level: int = 1

    @property
    def idml(self):
        return LEVEL_STYLES[min(self.level, 3)] if self.role == "heading" else \
            LEVEL_STYLES[0]

    @property
    def feats(self):
        """Run features that make up the look (dropped from the runs: the style gives them)."""
        size, bold, italic, caps, _c = self.look
        out = []
        if bold:
            out.append("bold")
        if italic:
            out.append("italic")
        if caps:
            out.append(caps)
        return tuple(out)


def describe(look, body_size=None):
    size, bold, italic, caps, centered = look
    parts = ["%g pt" % size] if body_size is None or size != body_size else []
    parts += [w for w, on in (("bold", bold), ("italic", italic)) if on]
    if caps:
        parts.append("capitals" if caps == "caps" else "small caps")
    if centered:
        parts.append("centered")
    return "[%s]" % " ".join(parts or ["%g pt" % size])


def _prominence(g, body):
    size, bold, italic, caps, centered = g.look
    b_size, b_bold, b_italic, b_caps, b_centered = body
    score = (size - b_size) * 10
    score += 6 if bold and not b_bold else 0
    score += 5 if caps and not b_caps else 0
    score += 4 if centered and not b_centered else 0
    score += 2 if italic and not b_italic else 0
    score += 8 * g.starts_page / max(1, len(g.paragraphs))
    return score


def _stands_out(look, body):
    size, bold, italic, caps, centered = look
    return size >= body[0] + 0.5 or (bold and not body[1]) or (caps and not body[3]) or \
        (centered and not body[4]) or (italic and not body[2])


def find_groups(doc, role_of):
    """Heading groups found by formatting in one DocxFile: (groups, {paragraph index: group}).
    role_of(p): the role a paragraph's style maps to (body, heading, chapter...)."""
    paras = [p for p in doc.paragraphs if p.where == "body" and not p.in_table and
             not p.in_toc_field and p.text.strip() and p.look]
    roles = {p.index: role_of(p) for p in paras}
    styled = set(roles.values())
    want_chapters = not ({"chapter", "part"} & styled)
    want_headings = "heading" not in styled
    if not (want_chapters or want_headings):
        return [], {}
    looks = {p.index: p.look + (p.align == "center",) for p in paras}
    # The body: the look of most of the text in long paragraphs.
    weight = Counter()
    for p in paras:
        if roles[p.index] == "body" and len(p.text.split()) >= 20:
            weight[looks[p.index]] += len(p.text)
    if not weight:
        for p in paras:
            weight[looks[p.index]] += len(p.text)
    if not weight:
        return [], {}
    body = weight.most_common(1)[0][0]
    groups, page_starts = {}, set()
    for n, p in enumerate(paras):
        text = " ".join(p.text.split())
        look = looks[p.index]
        if roles[p.index] != "body" or look == body or not _stands_out(look, body):
            continue
        if len(text.split()) > MAX_WORDS or n == len(paras) - 1:
            continue
        if text.endswith(".") and not _NUMBERED.match(text):
            continue
        g = groups.setdefault(look, Group(look, describe(look, body[0])))
        g.paragraphs.append(p.index)
        first_in_section = p.index == 0 or doc.paragraphs[p.index - 1].ends_section
        if p.page_break_before or first_in_section:
            page_starts.add(p.index)
    # A heading has text under it before the next heading of its look: a title page's lines
    # (a school, "by", a date, all centered capitals) and a typed contents' title don't.
    pos = {p.index: n for n, p in enumerate(paras)}
    texty = [roles[p.index] == "body" and len(p.text.split()) >= TEXT_WORDS and
             (p.align != "center" or body[4]) for p in paras]
    for g in groups.values():
        members = g.paragraphs
        ends = [pos[i] for i in members[1:]] + [len(paras)]
        g.paragraphs = [i for i, end in zip(members, ends) if any(texty[pos[i] + 1:end])]
        g.starts_page = sum(1 for i in g.paragraphs if i in page_starts)
    kept = [g for g in groups.values() if g.paragraphs and
            (len(g.paragraphs) >= 2 or g.look[0] >= body[0] + 2 or g.starts_page)]
    # An italic-only look is weak (titles of works, foreign words set apart): keep it only
    # as a level below a stronger group.
    if all(_only_italic(g.look, body) for g in kept):
        kept = []
    kept.sort(key=lambda g: -_prominence(g, body))
    level = 0 if want_chapters else 1
    if not want_headings:
        kept = kept[:1]
    for g in kept:
        if level == 0:
            g.role, g.level = "chapter", 0
        else:
            g.role, g.level = "heading", min(level, 3)
        level += 1
    by_para = {i: g for g in kept for i in g.paragraphs}
    return kept, by_para


def _only_italic(look, body):
    size, bold, italic, caps, centered = look
    return italic and size < body[0] + 0.5 and not (bold or caps or centered)
