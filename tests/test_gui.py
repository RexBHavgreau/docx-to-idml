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
        app.profile_forms[0].vars[("page", "trim")][0].set("5.5x8.5")
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
        app.profile_forms[1].vars[("fonts", "body")][0].set("Arno Pro")
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
        form = app.profile_forms[1]
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


if __name__ == "__main__":
    if not HAVE_TK:
        sys.exit(0)
    run_tests(globals())
