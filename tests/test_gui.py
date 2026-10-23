"""The window, driven from code: files, forms, preflight, export, book file, profile.

Needs Tkinter and a display (on Linux, run under xvfb-run); skipped without them. The settings
folder is a temporary one, so real profiles are untouched."""

import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TMP = tempfile.mkdtemp()
os.environ["APPDATA"] = os.environ["XDG_CONFIG_HOME"] = os.path.join(TMP, "config")

from docx_builder import run_tests  # noqa: E402

try:
    import tkinter as tk
    _root = tk.Tk()
    _root.destroy()
    HAVE_TK = True
except Exception as e:          # no Tkinter, or no display
    HAVE_TK = False
    print("Skipped: no Tkinter or no display (%s). On Linux run: xvfb-run python "
          "tests/test_gui.py" % e)

MS = os.path.join(ROOT, "reference", "manuscript")


def _files():
    return [os.path.join(MS, f) for f in sorted(os.listdir(MS)) if f.endswith(".docx")]


def _app():
    from docx2idml import gui
    root = tk.Tk()
    root.withdraw()
    return gui.App(root, dnd=False), root


def _wait(app, root, timeout=120):
    end = time.time() + timeout
    while app.busy and time.time() < end:
        root.update()
        time.sleep(0.02)
    root.update()
    assert not app.busy, "still busy"


def test_files_and_order():
    app, root = _app()
    try:
        files = _files()
        app._add(list(reversed(files)))
        assert app.book.files == list(reversed(files))
        app.sort_files()
        assert app.book.files == files
        app.tree.selection_set(files[2])
        app.move("top")
        assert app.book.files[0] == files[2]
        app.move(1)
        assert app.book.files[1] == files[2]
        app.tree.selection_set(files[0])
        app.remove_files()
        assert files[0] not in app.book.files
    finally:
        app.quit(force=True)


def test_preflight_export_and_book_file():
    app, root = _app()
    try:
        app._add(_files())
        app.run_preflight()
        _wait(app, root)
        assert app.report is not None and app.units
        assert "PREFLIGHT" in app.text.get("1.0", "end")
        # Running heads table, with a short title.
        assert app.heads.get_children()
        # A unit's kind, changed by the user, and changed back.
        app.set_kind("Covenant and Community", "endorsements")
        assert app.book.settings["unit_kinds"] == {"Covenant and Community": "endorsements"}
        assert app.heads.set("Covenant and Community", "kind") == "endorsements (set by you)"
        assert app.heads.set("Covenant and Community", "head") == "(no running heads)"
        app.set_kind("Covenant and Community", "chapter")
        assert app.book.settings["unit_kinds"] == {}
        # The Style Map tab shows each style's look; one can be switched.
        looks = {w: lv for w, _iv, _rv, lv, _i in app.mapping.rows}
        assert looks["Epigraph"].get() == "Word's, in book terms"
        assert looks["Normal"].get() == "the book style's"
        looks["Epigraph"].set("the book style's")
        app.mapping.apply()
        _wait(app, root)
        assert app.profile["style_map"]["paragraph"]["Epigraph"]["look"] == "book"
        looks = {w: lv for w, _iv, _rv, lv, _i in app.mapping.rows}
        assert looks["Epigraph"].get() == "the book style's"
        app.book.settings["short_titles"] = {"The Formula in the Prophets": "The Formula"}
        app._refresh_heads()
        assert app.heads.set("The Formula in the Prophets", "head") == "The Formula"
        # Book details: filled from the manuscript, then edited.
        app.fill_front()
        _wait(app, root)
        var = app.front_form.vars[("isbn_print",)][0]
        var.set("978-0-000-00000-0")
        assert app.front_form.vars[("title",)][0].get() == "The Covenant Formula"
        sources = app.front_sources.get()
        assert "Title: \u201cThe Covenant Formula\u201d, from style Title in 00 Front.docx" in sources
        assert "Author: \u201cA. N. Author\u201d, from title page text" in sources
        # A profile setting from the form.
        app.pvar(("page", "trim")).set("5.5x8.5")
        out = os.path.join(TMP, "out")
        os.makedirs(out)
        app.out_var.set(out)
        app.export()
        _wait(app, root)
        assert app.last_export and os.path.exists(app.last_export)
        report = app.text.get("1.0", "end")
        assert "Wrote" in report and "[ISBN]" not in report
        assert app.profile["page"]["trim"] == "5.5x8.5"
        # The book file keeps files, details and short titles.
        path = os.path.join(TMP, "book.json")
        app.book_path = path
        assert app.save_book()
        from docx2idml.book import Book
        b = Book.load(path)
        assert b.files == app.book.files
        assert b.settings["front"]["isbn_print"] == "978-0-000-00000-0"
        assert b.settings["short_titles"]["The Formula in the Prophets"] == "The Formula"
    finally:
        app.quit(force=True)


def test_profile_save_and_settings():
    from docx2idml import appsettings
    from docx2idml import profile as profiles
    app, root = _app()
    try:
        app.pvar(("fonts", "body")).set("Arno Pro")
        app.profile_name = "Series A"
        app.save_profile()
        assert profiles.load("Series A")["fonts"]["body"] == "Arno Pro"
        app._refresh_profile_list()
        assert "Series A" in app.profile_box["values"]
    finally:
        app.quit(force=True)
    assert appsettings.load()["profile"] == "Series A"


def test_font_dropdowns():
    from docx2idml import fonts
    app, root = _app()
    try:
        end = time.time() + 60
        while app.font_lists is None and time.time() < end:
            root.update()
            time.sleep(0.02)
        assert app.font_lists is not None, "fonts not read"
        installed = fonts.families()
        form = app._form_of(("fonts", "body"))
        boxes = {script: box for box, script in form.font_boxes}
        assert list(boxes[None]["values"]) == installed
        for script in ("hebrew", "greek"):
            assert set(app.font_lists[script]) <= set(installed)
        if installed:
            form.vars[("fonts", "body")][0].set(installed[0])
        form.vars[("fonts", "notes")][0].set("(reading the installed fonts...)")
        app._forms_to_profile()
        assert app.profile["fonts"]["body"] == (installed[0] if installed else None)
        assert app.profile["fonts"]["notes"] is None
    finally:
        app.quit(force=True)


def test_leading_note():
    app, root = _app()
    try:
        app.update_margins()
        note = app.leading_note.get()
        assert note.startswith("Suggested for 11 pt") and "standard 13.5" in note
        app.pvar(("body_size",)).set("10")
        app.pvar(("leading", "feel")).set("tight")
        app.update_margins()
        assert "Suggested for 10 pt" in app.leading_note.get()
        assert "(tight)" in app.leading_note.get()
        app._forms_to_profile()
        assert app.profile["body_size"] == 10 and app.profile["leading"]["feel"] == "tight"
    finally:
        app.quit(force=True)


def test_calculated_margins_shown_and_filled():
    app, root = _app()
    try:
        app.update_margins()
        form = app._form_of(("page", "margins", "inside"))
        lab, _text = form.labels[("page", "margins", "inside")]
        assert "calculated" in str(lab.cget("text"))
        note = app.margin_note.get()
        assert note.startswith("Calculated margins (in): top ") and "about 200 pages" in note
        assert "picas" in note
        mlab, _t = app._form_of(("page", "measure")).labels[("page", "measure")]
        assert "picas)" in str(mlab.cget("text"))
        g, _pages, _found = app.calculated()
        # By default the outside margin is never wider than the inside.
        assert g.margins["outside"] <= g.margins["inside"]
        app.pvar(("page", "trim")).set("5x8")
        g2, _p, _f = app.calculated()
        assert g2.measure != g.measure or g2.margins != g.margins
        form.vars[("page", "margins", "top")][0].set("1")
        app.fill_margins()
        assert form.vars[("page", "margins", "top")][0].get() == "1"       # kept as typed
        inside = float(form.vars[("page", "margins", "inside")][0].get())
        assert abs(inside - g2.margins["inside"] / 72) < 0.01
        app._forms_to_profile()
        assert app.profile["page"]["margins"]["top"] == 1
    finally:
        app.quit(force=True)


def test_update_check_at_every_start():
    """The startup check runs at every start (not once a day); a declined version isn't
    offered again at startup, but is from the Help menu."""
    from tkinter import messagebox
    from docx2idml import updates
    asked = []
    real_check, real_ask = updates.check, messagebox.askyesno
    updates.check = lambda *a, **k: {"status": "newer", "latest": "9.9.9", "url": "u",
                                     "notes": "", "asset": None}
    messagebox.askyesno = lambda *a, **k: asked.append(a[1]) or False

    def run(app, root, manual):
        n = len(asked)
        app.check_updates(manual=manual)
        end = time.time() + 10
        while len(asked) == n and time.time() < end:
            root.update()
            time.sleep(0.02)
        root.update()
        return len(asked) > n
    try:
        app, root = _app()
        app.settings["last_update_check"] = time.time()      # checked a minute ago
        assert updates.due(app.settings)
        assert run(app, root, manual=False)                   # offered; answered No
        assert app.settings["declined_version"] == "9.9.9"
        assert "9.9.9" in asked[-1]
        assert not run(app, root, manual=False)               # not asked again at startup
        assert run(app, root, manual=True)                    # but from the Help menu
        app.quit(force=True)
    finally:
        updates.check, messagebox.askyesno = real_check, real_ask


def test_style_mapping_panel():
    """All styles in the Style Map tab after the automatic mapping (shown after the first
    preflight); the user's choices are saved in the profile and used by the export. The
    manuscript's own contents styles aren't listed."""
    from docx2idml import gui
    app, root = _app()
    try:
        assert not app.mapping.rows                   # nothing read yet
        app._add(_files())
        app.run_preflight()
        _wait(app, root)
        end = time.time() + 5
        while app.tabs.select() != str(app.styles_tab) and time.time() < end:
            root.update()
            time.sleep(0.02)
        assert app.tabs.select() == str(app.styles_tab), "the mapping is shown after preflight"
        panel = app.mapping
        rows = {w: (iv, rv, lv) for w, iv, rv, lv, _i in panel.rows}
        assert not [w for w in rows if w.lower().startswith("toc")]
        assert rows["Epigraph"][0].get() == gui.OWN
        assert rows["Heading 1"][0].get() == "Chapter Title"
        iv, rv, lv = rows["Epigraph"]
        iv.set("Block Quote")
        panel._role_for(iv, rv)                       # a book style sets its role
        assert rv.get() == "quote"
        chars = {w: cv for w, cv, _i in panel.char_rows}
        chars["Scripture Ref"].set("Small Caps")
        panel.apply()
        _wait(app, root)
        sm = app.profile["style_map"]
        assert sm["paragraph"]["Epigraph"]["idml"] == "Block Quote"
        assert sm["paragraph"]["Epigraph"]["role"] == "quote"
        assert "Normal" not in sm["paragraph"]         # unchanged rows aren't saved
        assert sm["character"]["Scripture Ref"] == "Small Caps"
        assert app.report is not None                 # read again with the new map
        rows = {w: iv for w, iv, _rv, _lv, _i in app.mapping.rows}
        assert rows["Epigraph"].get() == "Block Quote"
        from docx2idml.export import Exporter
        ex = Exporter(app.book.files, app.profile)
        try:
            doc = ex.build()
            styles = {p.style for st in doc.stories for p in st.paragraphs}
            assert "Block Quote" in styles and "Epigraph" not in styles
            runs = [r for st in doc.stories for p in st.paragraphs for r in p.runs
                    if "Lev 26:12" in r.text]
            assert runs and runs[0].style == "Small Caps"
        finally:
            ex.cleanup()
        # A change not yet applied is kept when the profile is read from the window.
        rows = {w: iv for w, iv, _rv, _lv, _i in app.mapping.rows}
        rows["Normal"].set("Block Quote")
        app._forms_to_profile()
        assert app.profile["style_map"]["paragraph"]["Normal"]["idml"] == "Block Quote"
        # Back to the automatic mapping.
        app.mapping.reset()
        _wait(app, root)
        assert "Epigraph" not in app.profile["style_map"]["paragraph"]
        assert "Normal" not in app.profile["style_map"]["paragraph"]
        assert "Scripture Ref" not in app.profile["style_map"]["character"]
    finally:
        app.quit(force=True)


def test_tabs_in_title_case_and_head_style():
    app, root = _app()
    try:
        names = [app.tabs.tab(t, "text") for t in app.tabs.tabs()]
        assert names == ["Files", "Book Details", "Running Heads", "Layout Profile", "Style Map",
                         "Report"]
        app.head_style_form.vars[("running_heads", "style", "case")][0].set("as_typed")
        app.head_style_form.vars[("running_heads", "style", "italic")][0].set(True)
        app._forms_to_profile()
        rs = app.profile["running_heads"]["style"]
        assert rs["case"] == "as_typed" and rs["italic"] is True
    finally:
        app.quit(force=True)


def test_cleanup_after_update():
    """The new version offers to delete older copies and retarget shortcuts; declined copies
    aren't asked about again."""
    from pathlib import Path
    from tkinter import messagebox
    from docx2idml import __version__, updates
    folder = Path(tempfile.mkdtemp())
    me = folder / updates.exe_name(__version__)
    old = folder / updates.exe_name("0.2.0")
    for p in (me, old):
        p.write_bytes(b"x")
    answers, asked, retargeted = [], [], []
    real_ask, real_retarget = messagebox.askyesno, updates.retarget_shortcuts
    messagebox.askyesno = lambda *a, **k: asked.append(a[1]) or answers.pop(0)
    updates.retarget_shortcuts = lambda olds, new, **k: retargeted.append((olds, new)) or 1
    try:
        app, root = _app()
        answers.append(False)
        app.offer_cleanup(me)                              # No: kept, not asked again
        assert old.exists() and app.settings["kept_old_versions"] == [old.name]
        assert "shortcuts" in asked[-1] and old.name in asked[-1]
        n = len(asked)
        app.offer_cleanup(me)
        assert len(asked) == n
        app.settings["kept_old_versions"] = []
        answers.append(True)
        app.offer_cleanup(me)                              # Yes: retargeted and deleted
        end = time.time() + 20
        while app.busy and time.time() < end:
            root.update()
            time.sleep(0.02)
        root.update()
        assert not old.exists() and me.exists()
        assert retargeted == [([old], me)]
        assert "shortcuts changed to open this version: 1" in app.status.get()
        app.quit(force=True)
    finally:
        messagebox.askyesno, updates.retarget_shortcuts = real_ask, real_retarget


if __name__ == "__main__":
    if not HAVE_TK:
        sys.exit(0)
    run_tests(globals())
