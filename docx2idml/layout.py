"""Page geometry and pagination (build step 5).

Geometry: the measure is set for about 65 characters of the body font; the margins take the
rest of the width (inside smaller than outside) and a share of the height (bottom larger than
top), with floors of 0.5 in and KDP's gutter minimum for the page count. The text height is a
whole number of body lines.

Pagination: display pages (title page...) and front matter in one roman section from i, with
display pages counted but carrying no folio; the first chapter (or part) starts arabic 1.
Title page, front matter, parts and the first chapter open on a recto; later chapters on a
recto or the next page, as the profile says. Blank versos get the E-Blank master.
"""

import math
from dataclasses import dataclass, field

# KDP paperback: minimum inside margin (inches) by page count, up to the page count given.
KDP_GUTTER = [(150, 0.375), (300, 0.5), (500, 0.625), (700, 0.75), (828, 0.875)]
KDP_MAX_PAGES = 828
KDP_MIN_PAGES = 24
FLOOR = 36                  # every margin at least 0.5 in
TARGET_CPL, MIN_CPL = 65, 60
VERTICAL_SHARE = 0.19       # of the page height, for top and bottom margins together
TOP_SHARE = 0.45            # of that, for the top
INSIDE_SHARE = 0.4          # of the width left over, for the inside margin


def kdp_gutter(pages):
    """KDP's minimum inside margin in points for a page count."""
    for limit, inches in KDP_GUTTER:
        if pages <= limit:
            return inches * 72
    return KDP_GUTTER[-1][1] * 72


def kdp_band(pages):
    for n, (limit, _inches) in enumerate(KDP_GUTTER):
        if pages <= limit:
            return n
    return len(KDP_GUTTER)


def _half(v):
    return round(v * 2) / 2


@dataclass
class Geometry:
    margins: dict
    measure: float
    text_height: float
    lines: int                # body lines per page
    cpl: float                # characters per line at the body size
    notes: list = field(default_factory=list)


def geometry(width, height, size, lead, avg_width, pages, overrides=None):
    """Margins (points) for a trim, body size and leading, the body font's average character
    width (ems) and the estimated page count. overrides: the user's margins in inches."""
    overrides = {k: v for k, v in (overrides or {}).items() if v}
    notes = []
    char = size * avg_width
    gutter = max(FLOOR, kdp_gutter(pages))
    measure = TARGET_CPL * char
    left_over = width - measure
    inside = max(gutter, left_over * INSIDE_SHARE)
    outside = max(FLOOR, left_over - inside)
    if inside + outside > left_over:
        # The floors win: the measure gives way, down to 60 characters.
        measure = max(MIN_CPL * char, width - inside - outside)
        if inside + outside + measure > width:
            measure = width - inside - outside
            notes.append("The text width is under %d characters per line at %g pt on this trim. "
                         "Choose a smaller type size or a larger trim." % (MIN_CPL, size))
        outside = width - inside - measure
    if "inside" in overrides:
        inside = _half(overrides["inside"] * 72)
        if inside < kdp_gutter(pages):
            notes.append("The inside margin (%.3g in) is below KDP's minimum of %.3g in for %d "
                          "pages." % (inside / 72, kdp_gutter(pages) / 72, pages))
    if "outside" in overrides:
        outside = _half(overrides["outside"] * 72)
    measure = width - inside - outside
    if outside > 1.25 * 72 and "outside" not in overrides:
        notes.append("The margins are wide (%.2g in outside) for %g pt type on this trim. A "
                     "larger type size, or two columns, would fill the page better."
                     % (outside / 72, size))
    vertical = height * VERTICAL_SHARE
    top = max(FLOOR, _half(vertical * TOP_SHARE))
    bottom = max(FLOOR, vertical - top)
    if "top" in overrides:
        top = _half(overrides["top"] * 72)
    if "bottom" in overrides:
        bottom = _half(overrides["bottom"] * 72)
    # A whole number of body lines; what's left over goes to the bottom margin.
    lines = max(1, int((height - top - bottom) // lead))
    if "bottom" not in overrides:
        bottom = height - top - lines * lead
    m = {"top": _half(top), "bottom": _half(bottom), "inside": _half(inside),
         "outside": _half(outside)}
    measure = width - m["inside"] - m["outside"]
    return Geometry(m, measure, height - m["top"] - m["bottom"], lines,
                    measure / char, notes)


@dataclass
class Placed:
    start: int                # first page index
    pages: int                # pages the story is threaded through
    blank_before: bool = False


def plan_pages(units, chapters_open="recto"):
    """Where each unit goes. units: [(kind, estimated pages, spare pages)] or [(kind, pages,
    spare, opens)] in book order, kind as in the outline (display, front, part, chapter, back);
    opens: "recto", "next" (the next page, e.g. a copyright page after the title page), or None
    for the rule by kind.

    Returns ([Placed], page_count, masters {page index: master name}, first body unit index).
    """
    placed, masters = [], {}
    page = 0
    first_body = None
    for n, unit in enumerate(units):
        kind, est, spare = unit[:3]
        opens = unit[3] if len(unit) > 3 else None
        front = kind in ("display", "front")
        if not front and first_body is None:
            first_body = n
        if opens:
            recto = opens == "recto"
        elif front or kind == "part" or n == first_body or chapters_open == "recto":
            recto = True
        else:
            recto = False
        blank = False
        if recto and page % 2 == 1:
            masters[page] = "E-Blank"
            page += 1
            blank = True
        count = max(1, est + spare)
        placed.append(Placed(page, count, blank))
        for i in range(page, page + count):
            if kind == "display":
                masters[i] = "D-Display"
            elif i == page:
                masters[i] = "B-Opener" if kind != "part" else "D-Display"
            elif front:
                masters[i] = "C-Front"
            else:
                masters[i] = "A-Body"
        page += count
    return placed, page, masters, first_body


def page_count_notes(pages):
    notes = []
    if pages < KDP_MIN_PAGES:
        notes.append("%d pages is under KDP's minimum of %d for a paperback." % (pages, KDP_MIN_PAGES))
    if pages > KDP_MAX_PAGES:
        notes.append("%d pages is over KDP's maximum of %d for a paperback." % (pages, KDP_MAX_PAGES))
    for limit, _inches in KDP_GUTTER[:-1]:
        if abs(pages - limit) <= 8:
            notes.append("The page count (%d) is near KDP's %d-page step for the inside margin; "
                         "if the final count crosses it, check the inside margin "
                         "(%.3g in up to %d pages, %.3g in above)."
                         % (pages, limit, kdp_gutter(limit) / 72, limit,
                            kdp_gutter(limit + 1) / 72))
    return notes


def ceil_pages(height, text_height):
    return max(1, math.ceil(height / text_height))
