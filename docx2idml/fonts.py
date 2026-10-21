"""Installed fonts: finding a family's file, and the average width of its characters.

The measure (characters per line) is worked out from the body font itself: the average advance
width of the manuscript's own characters, read from the font file with fontTools. Fonts are
looked for in the system and per-user font folders of the machine running the tool.
"""

import os
import sys
from pathlib import Path

FONT_EXTS = {".ttf", ".otf", ".ttc", ".otc"}
# Average character width, in ems, when the font isn't installed: a typical book serif with
# English text.
FALLBACK_WIDTH = 0.42
SAMPLE = ("The covenant formula recurs throughout the prophets with small but telling changes. "
          "Each change of wording marks a shift in the relationship the text describes, and a "
          "careful reader notices when the order of its two halves is reversed.")


def font_dirs():
    dirs = []
    if sys.platform == "win32":
        windir = os.environ.get("WINDIR", r"C:\Windows")
        dirs.append(Path(windir) / "Fonts")
        local = os.environ.get("LOCALAPPDATA")
        if local:
            dirs.append(Path(local) / "Microsoft" / "Windows" / "Fonts")
    elif sys.platform == "darwin":
        dirs += [Path("/System/Library/Fonts"), Path("/Library/Fonts"),
                 Path.home() / "Library" / "Fonts"]
    else:
        dirs += [Path("/usr/share/fonts"), Path("/usr/local/share/fonts"),
                 Path.home() / ".local" / "share" / "fonts", Path.home() / ".fonts"]
    return [d for d in dirs if d.is_dir()]


_INDEX = None


def _names(font):
    """(family, style) names of a font: typographic names (16, 17) first, else 1, 2."""
    name = font["name"]

    def get(*ids):
        for i in ids:
            rec = name.getDebugName(i)
            if rec:
                return rec
        return None
    return get(16, 1), get(17, 2) or "Regular"


def font_index(dirs=None):
    """{family (lower case): {style (lower case): (path, font number)}} of installed fonts."""
    global _INDEX
    if _INDEX is not None and dirs is None:
        return _INDEX
    try:
        from fontTools.ttLib import TTCollection, TTFont
    except ImportError:
        return {}
    index = {}
    for d in dirs or font_dirs():
        for root, _subdirs, files in os.walk(d):
            for f in files:
                if os.path.splitext(f)[1].lower() not in FONT_EXTS:
                    continue
                path = os.path.join(root, f)
                try:
                    if f.lower().endswith((".ttc", ".otc")):
                        fonts = list(enumerate(TTCollection(path, lazy=True).fonts))
                    else:
                        fonts = [(0, TTFont(path, lazy=True))]
                    for n, font in fonts:
                        fam, style = _names(font)
                        if fam:
                            index.setdefault(fam.casefold(), {}).setdefault(
                                style.casefold(), (path, n))
                except Exception:
                    continue
    if dirs is None:
        _INDEX = index
    return index


def find_font(family, style="Regular", index=None):
    """(path, font number) of an installed font, or None."""
    if not family:
        return None
    styles = (index if index is not None else font_index()).get(family.casefold())
    if not styles:
        return None
    for s in (style.casefold(), "regular", "roman", "book", "normal"):
        if s in styles:
            return styles[s]
    return sorted(styles.values())[0]


def average_width(found, text=None):
    """Average advance width of the characters of text (the manuscript's, or a sample), in
    ems, from the font file. Characters the font lacks count at the average of the rest."""
    from fontTools.ttLib import TTFont
    path, number = found
    font = TTFont(path, fontNumber=number, lazy=True)
    cmap = font.getBestCmap() or {}
    hmtx = font["hmtx"]
    upem = font["head"].unitsPerEm
    text = text or SAMPLE
    total, n, missing = 0, 0, 0
    for ch in text:
        if ch in "\n\t":
            continue
        glyph = cmap.get(ord(ch))
        if glyph is None:
            missing += 1
            continue
        total += hmtx[glyph][0]
        n += 1
    if not n:
        return FALLBACK_WIDTH
    return total / n / upem
