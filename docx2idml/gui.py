"""The window (build step 7): files, book details, running heads, layout profile, preflight
and export, in themed Tkinter (ttk).

Everything the user sets lands in two places: the profile (layout, fonts, style map, running
head pattern: shared by a series) and the book settings (files in order, title and copyright
details, short running heads: this book only), saved as a book file (.json). Dropping files
from Explorer works when tkinterdnd2 is installed (it is bundled in the .exe).
"""

import copy
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
import traceback
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from . import APP_NAME, __version__, appsettings, updates
from . import profile as profiles
from .book import Book, collect
from .export import TRIMS, ExportError, export
from .outline import KIND_LABELS, KINDS, kind_key
from .stylemap import ROLES

TITLE = "docx-to-idml"     # working name
LOOKS = {"book": "the book style's", "word": "Word's, in book terms"}

# Profile fields: (path in the profile, label, kind, choices). Kinds: bool, text, number
# (blank allowed = automatic), int, choice, int_choice (a choice saved as a number), file (an
# IDML file, with Browse), font (a dropdown of installed fonts that can also
# be typed in; its choices name a script, "hebrew" or "greek", to list only fonts that have it).
PROFILE_FIELDS = {
    "Page": [
        (("page", "trim"), "Trim size", "choice", list(TRIMS) + ["custom"]),
        (("page", "custom_width"), "Custom width (in)", "number", None),
        (("page", "custom_height"), "Custom height (in)", "number", None),
        (("page", "facing"), "Facing pages", "bool", None),
        (("page", "bleed"), "Bleed (0.125 in)", "bool", None),
        (("page", "margins", "top"), "Top margin (in)", "number", None),
        (("page", "margins", "bottom"), "Bottom margin (in)", "number", None),
        (("page", "margins", "inside"), "Inside margin (in)", "number", None),
        (("page", "margins", "outside"), "Outside margin (in)", "number", None),
        (("chapters_open",), "Chapters open on", "choice", ["recto", "next_page"]),
        (("page", "spare_pages"), "Spare pages after each chapter", "int_choice", ["0", "1", "2"]),
    ],
    "Type": [
        (("styles_template",), "Styles from an IDML file (optional)", "file", None),
        (("fonts", "body"), "Body font (blank = an installed book font)", "font", None),
        (("fonts", "headings"), "Headings font", "font", None),
        (("fonts", "notes"), "Notes font", "font", None),
        (("fonts", "display"), "Display font", "font", None),
        (("fonts", "hebrew"), "Hebrew font", "font", "hebrew"),
        (("fonts", "greek"), "Greek font", "font", "greek"),
        (("body_size",), "Body size (pt)", "size", ["9", "9.5", "10", "10.5", "11", "11.5", "12",
                                                     "12.5", "13"]),
        (("leading", "feel"), "Leading", "choice", ["tight", "standard", "open"]),
        (("leading", "value"), "Exact leading (blank = from the choice above)", "number", None),
        (("leading", "unit"), "Leading unit", "choice", ["pt", "multiple", "percent"]),
        (("front_matter", "language"), "Language", "choice", ["en", "es"]),
        (("baseline_grid",), "Baseline grid (body text on the leading)", "bool", None),
        (("typography", "paragraph_composer"), "World-Ready composer (off = single-line)",
         "bool", None),
        (("typography", "optical_margins"), "Optical margin alignment", "bool", None),
        (("typography", "hyphenation"), "Hyphenation", "bool", None),
        (("typography", "ligatures"), "Ligatures", "bool", None),
        (("typography", "oldstyle_figures"), "Old-style figures", "bool", None),
        (("typography", "balance_ragged_headings"), "Balance ragged headings", "bool", None),
        (("typography", "widow_orphan_control"), "Widow and orphan control", "bool", None),
        (("typography", "last_line_min_chars"), "Shortest last line (characters, 0 = off)",
         "int", None),
    ],
    "Notes and contents": [
        (("footnotes", "numbering"), "Footnote numbering", "choice", ["per_chapter", "continuous"]),
        (("footnotes", "rule"), "Rule above the notes", "bool", None),
        (("footnotes", "continuation_rule"), "Rule above continued notes", "bool", None),
        (("footnotes", "space_above"), "Space above the notes (pt)", "number", None),
        (("footnotes", "space_below_rule"), "Space below a rule (pt)", "number", None),
        (("footnotes", "space_between"), "Space between notes (pt)", "number", None),
        (("footnotes", "rule_length"), "Rule length (pt)", "number", None),
        (("front_matter", "contents_depth"), "Contents lists", "choice", ["chapters", "sections"]),
    ],
}
HEAD_FIELDS = [
    (("running_heads", "verso"), "Verso head", "choice",
     ["book_title", "part", "chapter", "author", "custom"]),
    (("running_heads", "verso_custom"), "Verso text (custom)", "text", None),
    (("running_heads", "recto"), "Recto head", "choice", ["chapter_title", "custom"]),
    (("running_heads", "recto_custom"), "Recto text (custom)", "text", None),
    (("running_heads", "suppress_on_openers"), "No heads on chapter openers", "bool", None),
    (("running_heads", "suppress_on_display"), "No heads on display pages", "bool", None),
    (("running_heads", "suppress_on_blanks"), "No heads on blank pages", "bool", None),
]
# Book settings (book.settings["front"]).
FRONT_FIELDS = [
    ("title", "Title", "text"), ("subtitle", "Subtitle", "text"), ("author", "Author", "text"),
    ("short_title", "Short title (verso head)", "text"), ("publisher", "Publisher", "text"),
    ("publisher_address", "Publisher's address", "text"), ("year", "Copyright year", "text"),
    ("holder", "Copyright holder (blank = author)", "text"), ("edition", "Edition line", "text"),
    ("isbn_print", "ISBN (print)", "text"), ("isbn_ebook", "ISBN (ebook)", "text"),
    ("credits", "Credits", "text"), ("printed_in", "Printed in (country)", "text"),
    ("half_title", "Half-title page", "bool"), ("contents", "Contents pages", "bool"),
    ("contents_pages", "Contents pages (blank = estimated)", "text"),
]


def _get(d, path):
    for k in path:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def _set(d, path, value):
    for k in path[:-1]:
        d = d.setdefault(k, {})
    d[path[-1]] = value


def _num(text, kind):
    text = (text or "").strip()
    if not text:
        return None
    try:
        v = float(text)
    except ValueError:
        return None
    return int(v) if kind == "int" else v


class Form:
    """Widgets for a list of fields, bound to a dict (read with load(), written with save())."""

    def __init__(self, parent, fields, columns=1, by_column=False):
        """by_column: fill each column top to bottom (fields listed in reading order down the
        first column, then the second), instead of row by row."""
        self.fields, self.vars, self.font_boxes, self.labels = fields, {}, [], {}
        for n, (path, label, kind, choices) in enumerate(fields):
            rows = -(-len(fields) // columns)
            if by_column:
                row, col = n % rows, (n // rows) * 2
            else:
                row, col = n // columns, (n % columns) * 2
            if kind == "bool":
                var = tk.BooleanVar()
                ttk.Checkbutton(parent, text=label, variable=var).grid(
                    row=row, column=col, columnspan=2, sticky="w", padx=6, pady=2)
            else:
                var = tk.StringVar()
                lab = ttk.Label(parent, text=label)
                lab.grid(row=row, column=col, sticky="w", padx=6, pady=2)
                self.labels[path] = (lab, label)
                if kind == "size":
                    w = ttk.Combobox(parent, textvariable=var, values=choices, width=24)
                elif kind in ("choice", "int_choice"):
                    w = ttk.Combobox(parent, textvariable=var, values=choices, state="readonly",
                                     width=24)
                elif kind == "file":
                    w = ttk.Frame(parent)
                    ttk.Entry(w, textvariable=var, width=14).pack(side="left", fill="x",
                                                                   expand=True)

                    def browse(var=var):
                        path = filedialog.askopenfilename(
                            title="IDML file whose styles the book should use",
                            filetypes=[("InDesign Markup", "*.idml")])
                        if path:
                            var.set(path)
                    ttk.Button(w, text="Browse...", command=browse).pack(side="left", padx=2)
                elif kind == "font":
                    w = ttk.Combobox(parent, textvariable=var, width=24, height=20,
                                     values=["(reading the installed fonts...)"])
                    self.font_boxes.append((w, choices))
                else:
                    w = ttk.Entry(parent, textvariable=var, width=26)
                w.grid(row=row, column=col + 1, sticky="we", padx=6, pady=2)
            self.vars[path] = (var, kind)

    def set_fonts(self, lists):
        """Fill the font dropdowns: lists = {None: all families, "hebrew": [...], ...}."""
        for box, script in self.font_boxes:
            box["values"] = lists.get(script) or lists.get(None) or []

    def load(self, data):
        for path, (var, kind) in self.vars.items():
            v = _get(data, path)
            if kind == "bool":
                var.set(bool(v))
            else:
                var.set("" if v is None else (("%g" % v) if isinstance(v, float) else str(v)))

    def save(self, data):
        for path, (var, kind) in self.vars.items():
            if kind == "bool":
                value = bool(var.get())
            elif kind == "size":
                value = _num(var.get(), "number") or 11
            elif kind == "int_choice":
                value = _num(var.get(), "int") or 0
            elif kind in ("number", "int"):
                value = _num(var.get(), kind)
                if value is None and kind == "int":
                    value = 0
            else:
                value = var.get().strip() or None
                if kind == "font" and value and value.startswith("("):
                    value = None          # the placeholder shown while fonts are read
                if kind == "choice" and value is None:
                    continue
            _set(data, path, value)


class App:
    def __init__(self, root, dnd=False):
        self.root = root
        self.settings = appsettings.load()
        self.book = Book()
        self.book_path = None
        self.dirty = False
        self.busy = False
        self.report = None           # last preflight report
        self.units = []              # (title, kind) from the last outline
        self.results = queue.Queue() # callbacks from worker threads
        self.font_lists = None       # installed fonts, once read
        self.profile_name = self.settings.get("profile")
        try:
            self.profile = profiles.load(self.profile_name)
        except profiles.ProfileError:
            self.profile_name, self.profile = None, profiles.default_profile()
        root.title("%s %s" % (TITLE, __version__))
        root.geometry("1040x720")
        root.minsize(760, 520)
        self._menus()
        self._build(dnd)
        self._load_profile_into_forms()
        self._load_book_into_forms()
        root.protocol("WM_DELETE_WINDOW", self.quit)
        self._poll()
        self._read_fonts()

    # ---- layout of the window ----

    def _menus(self):
        m = tk.Menu(self.root)
        f = tk.Menu(m, tearoff=False)
        f.add_command(label="New book", command=self.new_book)
        f.add_command(label="Open book...", command=self.open_book)
        f.add_command(label="Save book", command=self.save_book)
        f.add_command(label="Save book as...", command=lambda: self.save_book(True))
        f.add_separator()
        f.add_command(label="Quit", command=self.quit)
        m.add_cascade(label="File", menu=f)
        p = tk.Menu(m, tearoff=False)
        p.add_command(label="New profile...", command=self.new_profile)
        p.add_command(label="Save profile", command=self.save_profile)
        p.add_command(label="Save profile as...", command=lambda: self.save_profile(True))
        p.add_command(label="Import profile...", command=self.import_profile)
        p.add_command(label="Export profile...", command=self.export_profile)
        m.add_cascade(label="Profile", menu=p)
        h = tk.Menu(m, tearoff=False)
        h.add_command(label="Check for updates", command=lambda: self.check_updates(manual=True))
        self.auto_check = tk.BooleanVar(value=self.settings.get("check_updates", True))
        h.add_checkbutton(label="Check for updates at startup", variable=self.auto_check,
                          command=self._auto_check_changed)
        h.add_command(label="About", command=self.about)
        m.add_cascade(label="Help", menu=h)
        self.root.config(menu=m)

    def _build(self, dnd):
        top = ttk.Frame(self.root, padding=(8, 8, 8, 0))
        top.pack(fill="x")
        ttk.Label(top, text="Profile:").pack(side="left")
        self.profile_var = tk.StringVar()
        self.profile_box = ttk.Combobox(top, textvariable=self.profile_var, state="readonly",
                                        width=30)
        self.profile_box.pack(side="left", padx=6)
        self.profile_box.bind("<<ComboboxSelected>>", self._profile_chosen)
        self._refresh_profile_list()

        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(fill="both", expand=True, padx=8, pady=8)
        self._files_tab(dnd)
        self._book_tab()
        self._heads_tab()
        self._layout_tab()
        self._styles_tab()
        self._report_tab()

        bottom = ttk.Frame(self.root, padding=(8, 0, 8, 8))
        bottom.pack(fill="x")
        ttk.Label(bottom, text="Save the export in:").pack(side="left")
        self.out_var = tk.StringVar(value=self.settings.get("out_dir") or str(Path.home()))
        ttk.Entry(bottom, textvariable=self.out_var, width=50).pack(side="left", padx=6,
                                                                    fill="x", expand=True)
        ttk.Button(bottom, text="Browse...", command=self._choose_out).pack(side="left")
        self.export_btn = ttk.Button(bottom, text="Export IDML", command=self.export)
        self.export_btn.pack(side="left", padx=(12, 0))
        self.progress = ttk.Progressbar(bottom, mode="indeterminate", length=120)
        self.progress.pack(side="left", padx=6)
        self.status = tk.StringVar(value="Add the manuscript's .docx files to begin.")
        ttk.Label(self.root, textvariable=self.status, padding=(10, 0, 10, 6)).pack(fill="x")

    def _files_tab(self, dnd):
        tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(tab, text="Files")
        cols = ("file", "heading")
        self.tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="extended")
        self.tree.heading("file", text="File (in book order)")
        self.tree.heading("heading", text="First heading")
        self.tree.column("file", width=330)
        self.tree.column("heading", width=420)
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(tab, orient="vertical", command=self.tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)
        btns = ttk.Frame(tab)
        btns.grid(row=0, column=2, sticky="n", padx=(8, 0))
        for text, cmd in (("Add files...", self.add_files), ("Add folder...", self.add_folder),
                          ("Remove", self.remove_files), (None, None),
                          ("Move up", lambda: self.move(-1)), ("Move down", lambda: self.move(1)),
                          ("Move to top", lambda: self.move("top")),
                          ("Move to bottom", lambda: self.move("bottom")), (None, None),
                          ("Sort by filename", self.sort_files),
                          ("Run preflight", self.run_preflight)):
            if text is None:
                ttk.Separator(btns).pack(fill="x", pady=6)
            else:
                ttk.Button(btns, text=text, command=cmd, width=18).pack(pady=2)
        tab.rowconfigure(0, weight=1)
        tab.columnconfigure(0, weight=1)
        hint = "Drop .docx files or folders here, or use Add." if dnd else \
            "Use Add files or Add folder. The order here is the book's order."
        ttk.Label(tab, text=hint).grid(row=1, column=0, sticky="w", pady=(6, 0))
        if dnd:
            try:
                from tkinterdnd2 import DND_FILES
                self.tree.drop_target_register(DND_FILES)
                self.tree.dnd_bind("<<Drop>>", self._dropped)
            except Exception:
                pass

    def _book_tab(self):
        tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(tab, text="Book details")
        row = ttk.Frame(tab)
        row.pack(fill="x", pady=(0, 4))
        ttk.Button(row, text="Fill from the manuscript", command=self.fill_front).pack(side="left")
        ttk.Label(row, text="Blank fields are filled from the manuscript at export; anything "
                            "still missing appears in brackets, e.g. [ISBN].").pack(
            side="left", padx=8)
        # Where the filled values came from (which style or line), so the user sees how the
        # manuscript was read.
        self.front_sources = tk.StringVar()
        ttk.Label(tab, textvariable=self.front_sources, wraplength=900,
                  justify="left").pack(anchor="w", pady=(0, 6))
        form = ttk.Frame(tab)
        form.pack(fill="x")
        fields = [((key,), label, kind, None) for key, label, kind in FRONT_FIELDS]
        self.front_form = Form(form, fields, columns=2)
        ttk.Label(tab, text="Notices on the copyright page (from the profile's library; select "
                            "any number):").pack(anchor="w", pady=(8, 2))
        self.notice_list = tk.Listbox(tab, selectmode="multiple", height=5, exportselection=False)
        self.notice_list.pack(fill="x")
        nb = ttk.Frame(tab)
        nb.pack(fill="x", pady=4)
        ttk.Button(nb, text="Add notice to library...", command=self.add_notice).pack(side="left")
        ttk.Button(nb, text="Remove from library", command=self.remove_notice).pack(side="left",
                                                                                     padx=6)

    def _heads_tab(self):
        tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(tab, text="Running heads")
        form = ttk.Frame(tab)
        form.pack(fill="x")
        self.heads_form = Form(form, HEAD_FIELDS, columns=2)
        ttk.Label(tab, text="Units of the book (double-click a running head to give a short "
                            "title, or a kind to change what the unit is; \"too long\" means "
                            "the head won't fit the page):").pack(anchor="w", pady=(10, 2))
        self.heads = ttk.Treeview(tab, columns=("unit", "kind", "head", "note"), show="headings")
        for c, t, w in (("unit", "Title in the manuscript", 330), ("kind", "Kind (double-click)", 160),
                        ("head", "Running head", 280), ("note", "", 80)):
            self.heads.heading(c, text=t)
            self.heads.column(c, width=w)
        self.heads.pack(fill="both", expand=True)
        self.heads.bind("<Double-1>", self._edit_head)

    def _layout_tab(self):
        tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(tab, text="Layout profile")
        inner = ttk.Notebook(tab)
        inner.pack(fill="both", expand=True)
        self.profile_forms = []
        for name, fields in PROFILE_FIELDS.items():
            f = ttk.Frame(inner, padding=8)
            inner.add(f, text=name)
            # The Page tab in one column, so the four margins read together.
            self.profile_forms.append(Form(f, fields, columns=1 if name == "Page" else 2,
                                           by_column=True))
        # The suggested leading for the size and font, under the Type fields.
        typetab = inner.nametowidget(inner.tabs()[1])
        self.leading_note = tk.StringVar()
        ttk.Label(typetab, textvariable=self.leading_note, wraplength=820, justify="left").grid(
            row=-(-len(PROFILE_FIELDS["Type"]) // 2) + 1, column=0, columnspan=4, sticky="w", padx=6,
            pady=(10, 4))
        # The margins the export would calculate, shown beside the margin fields.
        page = inner.nametowidget(inner.tabs()[0])
        row = len(PROFILE_FIELDS["Page"]) + 1
        self.margin_note = tk.StringVar()
        ttk.Label(page, textvariable=self.margin_note, wraplength=820, justify="left").grid(
            row=row, column=0, columnspan=4, sticky="w", padx=6, pady=(10, 4))
        ttk.Button(page, text="Fill in the calculated margins", command=self.fill_margins).grid(
            row=row + 1, column=0, columnspan=2, sticky="w", padx=6)
        form = self.profile_forms[0]
        watched = [form.vars[p][0] for p in (("page", "trim"), ("page", "custom_width"),
                                              ("page", "custom_height"))]
        watched += [self.profile_forms[1].vars[p][0] for p in (("fonts", "body"),
                                                               ("leading", "value"),
                                                               ("leading", "unit"),
                                                               ("leading", "feel"),
                                                               ("body_size",))]
        for var in watched:
            var.trace_add("write", lambda *_: self._margins_later())
        ttk.Label(tab, text="Changes apply to the next export. Profile > Save profile keeps them "
                            "for the next book in the series.").pack(anchor="w", pady=(6, 0))

    def _styles_tab(self):
        tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(tab, text="Style map")
        ttk.Label(tab, text="Paragraph styles in the manuscript (run preflight to fill). "
                            "Double-click to map a Word style to an IDML style and role, and "
                            "to choose its look: the book style's, or (for a special paragraph "
                            "the author set up) Word's, in book terms. The map is saved in the "
                            "profile.", wraplength=900, justify="left").pack(anchor="w")
        self.styles = ttk.Treeview(tab, columns=("word", "count", "idml", "role", "look",
                                                 "source"), show="headings")
        for c, t, w in (("word", "Word style", 200), ("count", "Paragraphs", 70),
                        ("idml", "IDML style", 170), ("role", "Role", 80),
                        ("look", "Look", 150), ("source", "Found by", 220)):
            self.styles.heading(c, text=t)
            self.styles.column(c, width=w)
        self.styles.pack(fill="both", expand=True, pady=4)
        self.styles.bind("<Double-1>", self._edit_style)

    def _report_tab(self):
        tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(tab, text="Report")
        self.text = tk.Text(tab, wrap="word", height=10)
        sb = ttk.Scrollbar(tab, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        self.text.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        self.open_btn = ttk.Button(self.root, text="Open the export folder",
                                   command=self.open_export)
        self.last_export = None

    # ---- profile ----

    def _refresh_profile_list(self):
        names = profiles.list_profiles()
        self.profile_box["values"] = ["(defaults)"] + names
        self.profile_var.set(self.profile_name or "(defaults)")

    def _load_profile_into_forms(self):
        for form in self.profile_forms:
            form.load(self.profile)
        self.heads_form.load(self.profile)
        self._margins_later()
        self.notice_list.delete(0, "end")
        chosen = set((self.book.settings.get("front") or {}).get("notices") or [])
        for n, item in enumerate(self.profile.get("notices") or []):
            self.notice_list.insert("end", item.get("name", ""))
            if item.get("name") in chosen:
                self.notice_list.selection_set(n)

    def _read_fonts(self):
        """List the installed fonts in the background (a few seconds with many fonts), then
        fill the font dropdowns."""
        def work():
            from . import fonts
            return {None: fonts.families(), "hebrew": fonts.families("hebrew"),
                    "greek": fonts.families("greek")}

        def target():
            try:
                lists = work()
            except Exception:
                lists = {}
            self.results.put(lambda: self._fonts_read(lists))
        threading.Thread(target=target, daemon=True).start()

    def _fonts_read(self, lists):
        self.font_lists = lists
        for form in self.profile_forms:
            form.set_fonts(lists)

    MARGINS = ("top", "bottom", "inside", "outside")

    def _margins_later(self):
        """Recalculate the shown margins shortly after a change (not on every keystroke)."""
        if getattr(self, "_margin_job", None):
            self.root.after_cancel(self._margin_job)
        self._margin_job = self.root.after(400, self.update_margins)

    def calculated(self):
        """The margins the export would calculate now: (Geometry, pages, font found)."""
        from .export import calculated_margins
        prof = copy.deepcopy(self.profile)
        for form in self.profile_forms:
            form.save(prof)
        pages = 200
        if self.report and self.report.outline:
            # A rough count from the words, as the export starts from.
            g, _found = calculated_margins(prof)
            words = self.report.outline.words
            pages = int(words * 6.2 / (g.cpl * g.lines)) + 2 * len(self.report.outline.units) + 6
        g, found = calculated_margins(prof, pages)
        return g, pages, found

    def update_margins(self):
        self._margin_job = None
        try:
            g, pages, found = self.calculated()
        except Exception:
            return
        self._update_leading_note(g)
        form = self.profile_forms[0]
        for side in self.MARGINS:
            lab, text = form.labels[("page", "margins", side)]
            lab.configure(text="%s, calculated %.2f" % (text, g.margins[side] / 72))
        from . import fonts
        font = (self.profile_forms[1].vars[("fonts", "body")][0].get() or "").strip() or \
            fonts.book_font()
        basis = ("%s, measured" % font) if found else \
            "%s isn't installed: an average book font" % font
        self.margin_note.set(
            "Calculated margins (in): top %.2f, bottom %.2f, inside %.2f, outside %.2f, for "
            "about %d pages (%s), %d characters per line at %g pt. Blank margin fields use "
            "the calculated values, which follow the page count (KDP's inside minimum grows "
            "with it); a value typed in is used as it is."
            % (g.margins["top"] / 72, g.margins["bottom"] / 72, g.margins["inside"] / 72,
               g.margins["outside"] / 72, pages, basis, round(g.cpl),
               _num(self.profile_forms[1].vars[("body_size",)][0].get(), "number") or 11))

    def _update_leading_note(self, g):
        """The suggested leading ranges for the size and font, and the leading the export
        will use."""
        from . import fonts, layout
        from .export import body_size, leading_for
        prof = copy.deepcopy(self.profile)
        for form in self.profile_forms:
            form.save(prof)
        size = body_size(prof)
        font = (prof.get("fonts") or {}).get("body") or fonts.book_font()
        found = fonts.find_font(font)
        xh = fonts.x_height(found) if found else None
        sug, why = layout.leading_suggestions(size, xh, g.cpl, font)
        lead = leading_for(prof, size, xh, g.cpl)
        feel = (prof.get("leading") or {}).get("feel") or "standard"
        used = "as typed" if (prof.get("leading") or {}).get("value") else feel
        self.leading_note.set(
            "Suggested for %g pt%s: tight %g\u2013%g, standard %g\u2013%g, open %g\u2013%g "
            "points%s. The export will use %g on %g (%s)." % (
                size, (" " + font) if font and found else "",
                sug["tight"][0], sug["tight"][1], sug["standard"][0], sug["standard"][1],
                sug["open"][0], sug["open"][1], ("; " + why) if why else "", size, lead, used))

    def fill_margins(self):
        g, _pages, _found = self.calculated()
        form = self.profile_forms[0]
        for side in self.MARGINS:
            var = form.vars[("page", "margins", side)][0]
            if not var.get().strip():
                var.set("%.3g" % (g.margins[side] / 72))
        self.status.set("Calculated margins filled in; they are now fixed for this profile "
                        "(clear a field to let it follow the page count again).")

    def _forms_to_profile(self):
        for form in self.profile_forms:
            form.save(self.profile)
        self.heads_form.save(self.profile)

    def _profile_chosen(self, _event=None):
        name = self.profile_var.get()
        name = None if name == "(defaults)" else name
        try:
            self.profile = profiles.load(name)
        except profiles.ProfileError as e:
            messagebox.showerror(TITLE, str(e))
            return
        self.profile_name = name
        self.settings["profile"] = name
        self._load_profile_into_forms()
        self.book.profile = name

    def new_profile(self):
        name = simpledialog.askstring(TITLE, "Name of the new profile (it starts from the "
                                             "settings shown now):", parent=self.root)
        if name:
            self._forms_to_profile()
            self.profile = copy.deepcopy(self.profile)
            self.profile["name"] = name
            self.profile_name = name
            profiles.save(self.profile)
            self._refresh_profile_list()
            self.status.set('Profile "%s" saved.' % name)

    def save_profile(self, as_new=False):
        if as_new or not self.profile_name:
            return self.new_profile()
        self._forms_to_profile()
        self.profile["name"] = self.profile_name
        profiles.save(self.profile)
        self.status.set('Profile "%s" saved.' % self.profile_name)

    def import_profile(self):
        path = filedialog.askopenfilename(title="Import a profile",
                                          filetypes=[("Profile", "*.json")])
        if path:
            try:
                name = profiles.import_profile(path)
            except profiles.ProfileError as e:
                messagebox.showerror(TITLE, str(e))
                return
            self._refresh_profile_list()
            self.profile_var.set(name)
            self._profile_chosen()

    def export_profile(self):
        path = filedialog.asksaveasfilename(title="Export the profile", defaultextension=".json",
                                            initialfile=(self.profile_name or "Profile") + ".json",
                                            filetypes=[("Profile", "*.json")])
        if path:
            self._forms_to_profile()
            profiles.save_file(self.profile, path)
            self.status.set("Profile exported to %s." % path)

    def add_notice(self):
        name = simpledialog.askstring(TITLE, "Short name of the notice (e.g. ESV):",
                                      parent=self.root)
        if not name:
            return
        text = simpledialog.askstring(TITLE, "Wording of the notice, exactly as it should "
                                             "appear on the copyright page:", parent=self.root)
        if text:
            self.profile.setdefault("notices", []).append({"name": name, "text": text})
            self.notice_list.insert("end", name)
            self.status.set("Notice added. Save the profile to keep it for other books.")

    def remove_notice(self):
        for i in reversed(self.notice_list.curselection()):
            del self.profile["notices"][i]
            self.notice_list.delete(i)

    # ---- book ----

    def _load_book_into_forms(self):
        self.front_form.load(self.book.settings.get("front") or {"half_title": True,
                                                                  "contents": True})
        self._refresh_files()
        self._refresh_heads()

    def _forms_to_book(self):
        front = self.book.settings.setdefault("front", {})
        self.front_form.save(front)
        cp = front.get("contents_pages")
        try:
            front["contents_pages"] = int(cp) if cp else None
        except ValueError:
            front["contents_pages"] = None
        names = [n.get("name") for n in self.profile.get("notices") or []]
        front["notices"] = [names[i] for i in self.notice_list.curselection() if i < len(names)]
        self.book.profile = self.profile_name

    def _refresh_files(self):
        self.tree.delete(*self.tree.get_children())
        headings = (self.report.outline.first_heading if self.report and self.report.outline
                    else {})
        for f in self.book.files:
            name = os.path.basename(f)
            self.tree.insert("", "end", iid=f, values=(name, headings.get(name, "")))
        n = len(self.book.files)
        self.status.set("%d file%s." % (n, "" if n == 1 else "s") if n else
                        "Add the manuscript's .docx files to begin.")

    def _changed(self):
        self.dirty = True
        self.report = None

    def _add(self, paths, at=None):
        files, skipped = self.book.add(paths, at)
        if skipped:
            messagebox.showinfo(TITLE, "Left out:\n\n" + "\n".join(
                "%s: %s" % (os.path.basename(p), why) for p, why in skipped))
        if files:
            self._changed()
            self._refresh_files()

    def add_files(self):
        paths = filedialog.askopenfilenames(title="Add Word files",
                                            filetypes=[("Word documents", "*.docx")])
        if paths:
            self._add(list(paths))

    def add_folder(self):
        path = filedialog.askdirectory(title="Add all the .docx files in a folder")
        if path:
            self._add([path])

    def _dropped(self, event):
        paths = self.root.tk.splitlist(event.data)
        target = self.tree.identify_row(event.y) if hasattr(event, "y") else ""
        at = self.book.files.index(target) if target in self.book.files else None
        self._add(list(paths), at)

    def remove_files(self):
        for f in self.tree.selection():
            self.book.remove(f)
        self._changed()
        self._refresh_files()

    def move(self, step):
        sel = list(self.tree.selection())
        if not sel:
            return
        idx = [self.book.files.index(f) for f in sel]
        if step == "top":
            order = sel + [f for f in self.book.files if f not in sel]
        elif step == "bottom":
            order = [f for f in self.book.files if f not in sel] + sel
        else:
            order = list(self.book.files)
            for i in (sorted(idx) if step < 0 else sorted(idx, reverse=True)):
                j = i + step
                if 0 <= j < len(order) and order[j] not in sel:
                    order[i], order[j] = order[j], order[i]
        self.book.files = order
        self._changed()
        self._refresh_files()
        self.tree.selection_set(sel)

    def sort_files(self):
        self.book.sort_by_filename()
        self._changed()
        self._refresh_files()

    def new_book(self):
        if not self._maybe_save():
            return
        self.book, self.book_path, self.dirty, self.report = Book(), None, False, None
        self._load_book_into_forms()

    def open_book(self, path=None):
        if not self._maybe_save():
            return
        path = path or filedialog.askopenfilename(title="Open a book",
                                                  filetypes=[("Book", "*.json")])
        if not path:
            return
        try:
            self.book = Book.load(path)
        except (OSError, ValueError) as e:
            messagebox.showerror(TITLE, "Can't open %s: %s" % (path, e))
            return
        self.book_path, self.dirty, self.report = path, False, None
        if self.book.profile:
            self.profile_var.set(self.book.profile)
            self._profile_chosen()
        else:
            self._load_profile_into_forms()
        self._load_book_into_forms()
        self.settings["last_book"] = path

    def save_book(self, as_new=False):
        self._forms_to_book()
        path = self.book_path
        if as_new or not path:
            path = filedialog.asksaveasfilename(title="Save the book", defaultextension=".json",
                                                initialfile="Book.json",
                                                filetypes=[("Book", "*.json")])
            if not path:
                return False
        self.book.save(path)
        self.book_path, self.dirty = path, False
        self.settings["last_book"] = path
        self.status.set("Book saved: %s" % path)
        return True

    def _maybe_save(self):
        if not self.dirty or not self.book.files:
            return True
        answer = messagebox.askyesnocancel(TITLE, "Save the changes to this book first?")
        if answer is None:
            return False
        return self.save_book() if answer else True

    def fill_front(self):
        self._need_report(self._fill_front_now)

    def _fill_front_now(self):
        o = self.report.outline
        front = self.book.settings.setdefault("front", {})
        self.front_form.save(front)
        filled = []
        for key, value in (("title", o.title), ("subtitle", o.subtitle), ("author", o.author)):
            if value and not front.get(key):
                front[key] = value
                filled.append(key)
        self.front_form.load(front)
        self.dirty = True
        found = []
        for key, label, value, source in (
                ("title", "Title", o.title, o.title_source),
                ("subtitle", "Subtitle", o.subtitle, o.subtitle_source),
                ("author", "Author", o.author, o.author_source)):
            if value:
                state = "filled in" if key in filled else "already set, kept"
                found.append("%s: \u201c%s\u201d, from %s (%s)" % (label, value, source, state))
            else:
                found.append("%s: not found in the manuscript" % label)
        self.front_sources.set("Found in the manuscript \u2014 " + "; ".join(found) + ".")

    # ---- running heads ----

    def _refresh_heads(self):
        self.heads.delete(*self.heads.get_children())
        short = self.book.settings.get("short_titles") or {}
        kinds = self.book.settings.get("unit_kinds") or {}
        limit = self._head_limit()
        for title, detected in self.units:
            if self.heads.exists(title):
                continue              # two units with one title share a row
            kind = kinds.get(title, detected)
            head = short.get(title) or title
            note = "too long" if len(head) > limit and kind in ("chapter", "part", "front",
                                                                 "back") else ""
            if kind in ("display", "endorsements"):
                head, note = "(no running heads)", ""
            label = KIND_LABELS.get(kind, kind) + (" (set by you)" if title in kinds else "")
            self.heads.insert("", "end", iid=title, values=(title, label, head, note))

    def _head_limit(self):
        """Characters that fit a running head: 80% of the measure at the head's size."""
        from . import layout
        page = self.profile["page"]
        w, h = TRIMS.get(page.get("trim"), TRIMS["6x9"]) if page.get("trim") != "custom" else \
            (page.get("custom_width") or 6, page.get("custom_height") or 9)
        g = layout.geometry(w * 72, h * 72, 11, 14, 0.42, 200, page.get("margins"))
        return int(g.measure * 0.8 / (9 * 0.42 * 1.1))

    def _edit_head(self, event):
        item = self.heads.identify_row(event.y)
        if not item:
            return
        if self.heads.identify_column(event.x) == "#2":
            return self._edit_kind(item)
        current = self.heads.set(item, "head")
        new = simpledialog.askstring(TITLE, "Running head for “%s” (blank = the full "
                                            "title):" % item, initialvalue=current,
                                     parent=self.root)
        if new is None:
            return
        short = self.book.settings.setdefault("short_titles", {})
        if new.strip() and new.strip() != item:
            short[item] = new.strip()
        else:
            short.pop(item, None)
        self.dirty = True
        self._refresh_heads()

    def _edit_kind(self, title):
        """Choose what a unit is (chapter, front matter, endorsements...), over what was
        detected; saved with the book."""
        detected = dict(self.units).get(title, "chapter")
        kinds = self.book.settings.setdefault("unit_kinds", {})
        dlg = tk.Toplevel(self.root)
        dlg.title("What is \u201c%s\u201d?" % title[:40])
        dlg.transient(self.root)
        labels = [KIND_LABELS[k] for k in KINDS]
        var = tk.StringVar(value=KIND_LABELS[kinds.get(title, detected)])
        ttk.Label(dlg, text="\u201c%s\u201d is:" % title[:60]).grid(row=0, column=0, padx=8,
                                                                    pady=6, sticky="w")
        ttk.Combobox(dlg, textvariable=var, values=labels, state="readonly").grid(
            row=0, column=1, padx=8)
        ttk.Label(dlg, text="Display pages and endorsements have no folio or running heads; "
                            "endorsements go before the half-title.", wraplength=380).grid(
            row=1, column=0, columnspan=2, padx=8, sticky="w")

        def ok():
            key = [k for k in KINDS if KIND_LABELS[k] == var.get()][0]
            self.set_kind(title, key)
            dlg.destroy()
        ttk.Button(dlg, text="OK", command=ok).grid(row=2, column=1, sticky="e", padx=8, pady=8)

    def set_kind(self, title, key):
        detected = dict(self.units).get(title, "chapter")
        kinds = self.book.settings.setdefault("unit_kinds", {})
        if key == detected:
            kinds.pop(title, None)
        else:
            kinds[title] = key
        self.dirty = True
        self._refresh_heads()

    # ---- style map ----

    def _refresh_styles(self):
        self.styles.delete(*self.styles.get_children())
        if not self.report:
            return
        for s in self.report.paragraph_styles:
            self.styles.insert("", "end", iid=s.word, values=(
                s.word, s.count, s.idml or "(left out)", s.role,
                LOOKS[self._look(s.word, s.idml, s.role)], s.source))

    def _look(self, word, idml, role):
        """As the export decides: the style map's choice, else Word's look only for a style
        kept under its own name with no book counterpart."""
        from .stylemap import norm
        sm = (self.profile.get("style_map") or {}).get("paragraph") or {}
        for k, v in sm.items():
            if norm(k) == norm(word) and isinstance(v, dict) and v.get("look") in LOOKS:
                return v["look"]
        return "word" if role == "body" and idml == word else "book"

    def set_style(self, word, idml, role, look):
        """Map a Word style (the profile's style map)."""
        sm = self.profile.setdefault("style_map", {}).setdefault("paragraph", {})
        sm[word] = {"idml": idml or None, "role": role, "look": look}
        if self.styles.exists(word):
            self.styles.set(word, "idml", idml or "(left out)")
            self.styles.set(word, "role", role)
            self.styles.set(word, "look", LOOKS[look])
            self.styles.set(word, "source", "profile (save the profile to keep it)")
        self.report = None       # mappings change the outline

    def _edit_style(self, event):
        item = self.styles.identify_row(event.y)
        if not item:
            return
        dlg = tk.Toplevel(self.root)
        dlg.title("Map %s" % item)
        dlg.transient(self.root)
        idml = tk.StringVar(value=self.styles.set(item, "idml"))
        role = tk.StringVar(value=self.styles.set(item, "role"))
        ttk.Label(dlg, text="IDML style for Word's “%s”:" % item).grid(
            row=0, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(dlg, textvariable=idml, width=30).grid(row=0, column=1, padx=8)
        ttk.Label(dlg, text="Role:").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        ttk.Combobox(dlg, textvariable=role, values=ROLES, state="readonly").grid(
            row=1, column=1, padx=8, sticky="w")
        look = tk.StringVar(value=self.styles.set(item, "look"))
        ttk.Label(dlg, text="Look:").grid(row=2, column=0, sticky="w", padx=8, pady=4)
        ttk.Combobox(dlg, textvariable=look, values=list(LOOKS.values()), state="readonly",
                     width=30).grid(row=2, column=1, padx=8, sticky="w")
        ttk.Label(dlg, text="Word's look keeps the style's alignment, indents, italic or bold, "
                            "and size and spacing in proportion to the body; never Word's "
                            "fonts. It applies to a style kept under its own name.",
                  wraplength=380, justify="left").grid(row=3, column=0, columnspan=2,
                                                       padx=8, sticky="w")

        def ok():
            key = [k for k, v in LOOKS.items() if v == look.get()] or ["book"]
            idml_name = idml.get().strip()
            self.set_style(item, None if idml_name == "(left out)" else idml_name, role.get(),
                           key[0])
            dlg.destroy()
        ttk.Button(dlg, text="OK", command=ok).grid(row=4, column=1, sticky="e", padx=8, pady=8)

    # ---- preflight and export ----

    def _run(self, work, done, what):
        """Run work() in a thread; done(result) back in the window."""
        if self.busy:
            return
        self.busy = True
        self.export_btn.state(["disabled"])
        self.progress.start(12)
        self.status.set(what)

        def target():
            try:
                result = (True, work())
            except Exception as e:      # shown to the user, with details in the report tab
                result = (False, e)
            self.results.put((lambda: self._finish(result, done)))
        threading.Thread(target=target, daemon=True).start()

    def _poll(self):
        """Run what worker threads hand back (Tk may only be touched from this thread)."""
        try:
            while True:
                self.results.get_nowait()()
        except queue.Empty:
            pass
        self._poll_id = self.root.after(50, self._poll)

    def _finish(self, result, done):
        self.busy = False
        self.export_btn.state(["!disabled"])
        self.progress.stop()
        ok, value = result
        if ok:
            done(value)
        else:
            msg = str(value) if isinstance(value, (ExportError, profiles.ProfileError)) else \
                "Something went wrong: %s" % value
            self.status.set(msg)
            self._show(msg + ("" if isinstance(value, ExportError) else "\n\n" + "".join(
                traceback.format_exception(type(value), value, value.__traceback__))))
            messagebox.showerror(TITLE, msg)

    def _show(self, text):
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        self.tabs.select(len(self.tabs.tabs()) - 1)

    def run_preflight(self):
        if not self.book.files:
            messagebox.showinfo(TITLE, "Add the manuscript's .docx files first.")
            return
        self._forms_to_profile()
        files, prof = list(self.book.files), copy.deepcopy(self.profile)
        from .preflight import preflight, render_text

        def done(rep):
            self._preflighted(rep)
            self._show(render_text(rep))
            self.status.set("Preflight done: %d warning%s." % (
                len(rep.warnings), "" if len(rep.warnings) == 1 else "s"))
        self._run(lambda: preflight(files, prof), done, "Reading the manuscript...")

    def _preflighted(self, rep):
        self.report = rep
        # (title, kind as detected): the book settings' choices are applied when shown.
        self.units = [(u.title, kind_key(u)) for u in rep.outline.units] if rep.outline else []
        self._refresh_files()
        self._refresh_heads()
        self._refresh_styles()
        self._margins_later()

    def _need_report(self, then):
        """Run preflight first if there's no report for the current files."""
        if self.report is not None:
            return then()
        if not self.book.files:
            messagebox.showinfo(TITLE, "Add the manuscript's .docx files first.")
            return
        self._forms_to_profile()
        files, prof = list(self.book.files), copy.deepcopy(self.profile)
        from .preflight import preflight

        def done(rep):
            self._preflighted(rep)
            then()
        self._run(lambda: preflight(files, prof), done, "Reading the manuscript...")

    def _choose_out(self):
        path = filedialog.askdirectory(title="Where to save the export")
        if path:
            self.out_var.set(path)

    def export(self):
        if not self.book.files:
            messagebox.showinfo(TITLE, "Add the manuscript's .docx files first.")
            return
        out = self.out_var.get().strip()
        if not out or not os.path.isdir(out):
            messagebox.showinfo(TITLE, "Choose a folder to save the export in.")
            return
        self._forms_to_profile()
        self._forms_to_book()
        self.settings["out_dir"] = out
        files, prof = list(self.book.files), copy.deepcopy(self.profile)
        settings = copy.deepcopy(self.book.settings)

        def done(result):
            path, report = result
            self.last_export = os.path.dirname(path)
            self._show("Wrote %s\n\n%s" % (path, "\n".join("- " + line for line in report)))
            self.status.set("Exported: %s" % path)
            self.open_btn.pack(side="bottom", anchor="e", padx=10, pady=(0, 6))
        self._run(lambda: export(files, out, prof, None, settings), done, "Exporting...")

    def open_export(self):
        if self.last_export:
            _open_path(self.last_export)

    # ---- updates ----

    def _auto_check_changed(self):
        self.settings["check_updates"] = bool(self.auto_check.get())

    def startup(self):
        """After the window shows: offer to tidy up after an update, then check for one."""
        if updates.can_install():
            self.offer_cleanup(updates.running_exe())
        if updates.due(self.settings):
            self.check_updates(manual=False)
        if self.settings.get("last_book") and os.path.exists(self.settings["last_book"]):
            self.open_book(self.settings["last_book"])

    def offer_cleanup(self, exe):
        """At the start of a new version: offer to delete older copies in its folder and to
        point shortcuts and taskbar pins that open them at this one. A copy the user chose to
        keep isn't asked about again."""
        kept = set(self.settings.get("kept_old_versions") or [])
        olds = [p for p in updates.older_copies(exe.parent, exe) if p.name not in kept]
        if not olds:
            return
        one = len(olds) == 1
        if not messagebox.askyesno(TITLE, (
                "This is %s %s. The older version%s in this folder (%s) can be deleted now, and "
                "shortcuts and taskbar pins that open %s changed to open this version. Your "
                "settings and profiles are kept.\n\nDelete the old version%s and update the "
                "shortcuts?" % (TITLE, __version__, "" if one else "s",
                                ", ".join(p.name for p in olds), "it" if one else "them",
                                "" if one else "s"))):
            self.settings["kept_old_versions"] = sorted(kept | {p.name for p in olds})
            appsettings.save(self.settings)
            return

        def work():
            n = updates.retarget_shortcuts(olds, exe)
            deleted, left = updates.delete_old(olds)
            return n, deleted, left

        def done(r):
            n, deleted, left = r
            self.status.set("Deleted %s; shortcuts changed to open this version: %d." % (
                ", ".join(p.name for p in deleted) or "nothing", n))
            if left:
                messagebox.showwarning(TITLE, "Couldn't delete %s (it may still be open). Close "
                                              "it, then delete it by hand." % ", ".join(
                                                  p.name for p in left))
        self._run(work, done, "Tidying up after the update...")

    def check_updates(self, manual=False):
        def work():
            return updates.check()

        def show(r):
            self.settings["last_update_check"] = time.time()
            appsettings.save(self.settings)
            if updates.should_offer(r, self.settings, manual):
                self._offer_update(r)
            elif manual and r["status"] != "newer":
                msg = {"current": "This is the latest version (%s)." % __version__,
                       "norelease": "No release has been published yet.",
                       "error": "Couldn't reach GitHub to check for updates. Check the "
                                "connection and try again."}.get(r["status"], "")
                messagebox.showinfo(TITLE, msg)

        def target():
            r = work()
            self.results.put(lambda: show(r))
        threading.Thread(target=target, daemon=True).start()

    def _decline(self, version):
        self.settings["declined_version"] = version
        appsettings.save(self.settings)

    def _offer_update(self, r):
        notes = (r.get("notes") or "").strip()
        msg = "Version %s is available (this is %s).\n\n%s\n\n" % (
            r["latest"], __version__, notes[:800])
        later = ("\n\n(If you say no, the check at startup won't ask about %s again; Help > Check "
                 "for updates will.)" % r["latest"])
        if not (updates.can_install() and r.get("asset")):
            if messagebox.askyesno(TITLE, msg + "Open the download page?" + later):
                webbrowser.open(r.get("url") or "https://github.com/%s/releases" % updates.REPO)
            else:
                self._decline(r["latest"])
            return
        if not messagebox.askyesno(TITLE, msg + "Download it now? It is saved beside this "
                                                "copy; this one stays until the new version "
                                                "offers to remove it." + later):
            self._decline(r["latest"])
            return

        def work():
            return updates.install(r["asset"], r["latest"])

        def done(result):
            path, fell_back = result
            note = ("The program's folder can't be written to, so the new version was saved in "
                    "Downloads:\n%s\n\n" % path) if fell_back else ""
            if messagebox.askyesno(TITLE, note + "Open the new version now? This one will close."):
                updates.launch(path)
                self.quit(force=True)
        self._run(work, done, "Downloading version %s..." % r["latest"])

    # ---- closing ----

    def about(self):
        messagebox.showinfo(TITLE, "%s %s\n\nWord manuscripts to IDML for InDesign, Affinity "
                                   "and DesignCraft.\n\nSettings and profiles: %s" % (
                                       TITLE, __version__, profiles.settings_dir()))

    def quit(self, force=False):
        if not force and not self._maybe_save():
            return
        self.settings["profile"] = self.profile_name
        self.settings["out_dir"] = self.out_var.get().strip() or None
        appsettings.save(self.settings)
        try:
            self.root.after_cancel(self._poll_id)
        except (AttributeError, tk.TclError):
            pass
        self.root.destroy()


def _open_path(path):
    if sys.platform == "win32":
        os.startfile(path)                  # noqa: S606 (opens Explorer)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def make_root():
    """(root, drag-and-drop available)."""
    try:
        from tkinterdnd2 import TkinterDnD
        return TkinterDnD.Tk(), True
    except Exception:
        return tk.Tk(), False


def main():
    root, dnd = make_root()
    try:
        ttk.Style(root).theme_use("vista" if sys.platform == "win32" else "clam")
    except tk.TclError:
        pass
    app = App(root, dnd)
    root.after(300, app.startup)
    root.mainloop()
    return 0
