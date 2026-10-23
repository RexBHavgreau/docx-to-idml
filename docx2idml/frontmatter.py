"""Front matter (build step 6): half-title, title page, copyright page and reserved contents.

The book's details (title, subtitle, author, copyright holder, ISBNs...) come from the book
settings, prefilled from what the outline detected. Anything still missing is written as a
bracketed placeholder ("[ISBN]") and reported, so nothing is left out silently. The tool ships
no notice wording of its own: notices come from the user's library in the profile, ticked per
book.

Book settings (Book.settings["front"]):
    half_title (True), title, subtitle, author, short_title (verso running head),
    publisher, publisher_address, year, holder, edition, isbn_print, isbn_ebook, credits,
    printed_in, notices (names from the profile's library), contents (True),
    contents_pages (None = estimated)
"""

import datetime
import math

from .idml.model import Paragraph, Run

TEXT = {
    "en": {"contents": "Contents", "rights": "All rights reserved.",
           "copyright": "Copyright © {year} by {holder}", "printed": "Printed in {country}",
           "isbn_print": "ISBN {isbn} (paperback)", "isbn_ebook": "ISBN {isbn} (ebook)"},
    "es": {"contents": "Contenido", "rights": "Todos los derechos reservados.",
           "copyright": "© {year} {holder}", "printed": "Impreso en {country}",
           "isbn_print": "ISBN: {isbn} (rústica)", "isbn_ebook": "ISBN: {isbn} (libro electrónico)"},
}

def texts(lang):
    return TEXT.get(lang, TEXT["en"])


def book_info(outline, front=None):
    """The book's details: the settings first, then what was detected. Returns (info, notes);
    notes name what had to be left as a placeholder."""
    front = dict(front or {})
    info = {
        "half_title": front.get("half_title", True),
        "title": front.get("title") or outline.title,
        "subtitle": front.get("subtitle") or outline.subtitle,
        "author": front.get("author") or outline.author,
        "short_title": front.get("short_title"),
        "publisher": front.get("publisher") or "",
        "publisher_address": front.get("publisher_address") or "",
        "year": front.get("year") or datetime.date.today().year,
        "holder": front.get("holder"),
        "edition": front.get("edition") or "",
        "isbn_print": front.get("isbn_print") or "",
        "isbn_ebook": front.get("isbn_ebook") or "",
        "credits": front.get("credits") or "",
        "printed_in": front.get("printed_in") or "",
        "notices": list(front.get("notices") or []),
        "contents": front.get("contents", True),
        "contents_pages": front.get("contents_pages"),
    }
    notes = []
    if not info["title"]:
        info["title"] = "[Book title]"
        notes.append("No book title was found: the title pages say [Book title]. Enter the title "
                     "in the book settings.")
    if not info["author"]:
        info["author"] = "[Author]"
        notes.append("No author was found: the title page says [Author]. Enter the author in "
                     "the book settings.")
    if not info["holder"]:
        info["holder"] = info["author"]
    return info, notes


def half_title(info):
    return [Paragraph("Half Title", [Run(info["title"])])]


def title_page(info):
    paras = [Paragraph("Book Title", [Run(info["title"])])]
    if info["subtitle"]:
        paras.append(Paragraph("Book Subtitle", [Run(info["subtitle"])]))
    paras.append(Paragraph("Author", [Run(info["author"])]))
    if info["publisher"]:
        paras.append(Paragraph("Publisher", [Run(info["publisher"])]))
    return paras


def copyright_page(info, lang, library=()):
    """The generated copyright page. Returns (paragraphs, notes)."""
    t = texts(lang)
    notes = []
    lines = [t["copyright"].format(year=info["year"], holder=info["holder"]), t["rights"]]
    paras = [Paragraph("Copyright", [Run(line)]) for line in lines]
    by_name = {n.get("name"): n.get("text", "") for n in library or ()}
    for name in info["notices"]:
        if name in by_name:
            paras.append(Paragraph("Copyright", [Run(by_name[name])]))
        else:
            notes.append('The notice "%s" is not in the profile\'s notice library; it was left '
                         "out." % name)
    if info["credits"]:
        paras.append(Paragraph("Copyright", [Run(info["credits"])]))
    pub = [x for x in (info["publisher"], info["publisher_address"]) if x]
    if pub:
        paras.append(Paragraph("Copyright", [Run("\n".join(pub))]))
    isbns = []
    if info["isbn_print"]:
        isbns.append(t["isbn_print"].format(isbn=info["isbn_print"]))
    if info["isbn_ebook"]:
        isbns.append(t["isbn_ebook"].format(isbn=info["isbn_ebook"]))
    if not isbns:
        isbns.append(t["isbn_print"].format(isbn="[ISBN]"))
        notes.append("The copyright page has [ISBN] where the ISBN goes. Enter it in the book "
                     "settings (or delete the line if the book has none).")
    paras.append(Paragraph("Copyright", [Run("\n".join(isbns))]))
    last = [x for x in (t["printed"].format(country=info["printed_in"])
                        if info["printed_in"] else "", info["edition"]) if x]
    if last:
        paras.append(Paragraph("Copyright", [Run("\n".join(last))]))
    return paras, notes


def contents_page(lang):
    return [Paragraph("Contents Title", [Run(texts(lang)["contents"])])]


def contents_entries(outline, depth="chapters"):
    """(level, title) of each contents entry: the units after the contents (front matter that
    follows it, parts, chapters, back matter), and first-level sections if depth is
    "sections"."""
    out = []
    for u in outline.units:
        if u.kind == "display" or u.type == "contents":
            continue
        out.append((1, u.title))
        if depth == "sections":
            out += [(2, s) for s in u.subheads]
    return out


def contents_pages(entries, cpl, lead, text_height, sink):
    """Pages to reserve for the contents: the title block, then each entry's lines (long titles
    wrap short of the page number), with a little space above level-1 entries."""
    height = sink + 4 * lead
    for level, title in entries:
        room = max(20, cpl - 8 - (4 if level > 1 else 0))
        height += math.ceil(max(1, len(title)) / room) * lead + (6 if level == 1 else 0)
    return max(1, math.ceil(height / text_height))
