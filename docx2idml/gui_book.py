"""The Book Details tab of the window (moved out of gui.py): the book's bibliographic details
for the title and copyright pages, filled from the manuscript, and the notice library."""

from tkinter import simpledialog, ttk
import tkinter as tk

from .frontmatter import COPYRIGHT_FIELDS, ROLE_LABELS, ROLES, creators, notice_name

# Book settings (book.settings["front"]), in the tab's sections. The contributors (creators)
# are a list of their own, edited beside the title.
TITLE_FIELDS = [("title", "Title", "text"), ("subtitle", "Subtitle", "text"),
                ("short_title", "Short title (verso head)", "text")]
PUBLICATION_FIELDS = [
    ("series", "Series", "text"), ("series_number", "Number in the series", "text"),
    ("volume", "Volume", "text"), ("volumes", "Number of volumes", "text"),
    ("edition", "Edition line", "text"), ("publisher", "Publisher", "text"),
    ("publisher_address", "Place (city or address)", "text"),
    ("year", "Copyright year", "text"),
    ("holder", "Copyright holder (blank: authors)", "text"),
    ("rights", "Rights (blank: All rights reserved.)", "text"),
    ("isbn_print", "ISBN (print)", "text"), ("isbn_ebook", "ISBN (ebook)", "text"),
    ("call_number", "Call number (blank: none)", "text"),
    ("credits", "Credits", "text"), ("printed_in", "Printed in (country)", "text"),
]
PAGE_FIELDS = [("half_title", "Half-title page", "bool"), ("contents", "Contents pages", "bool"),
               ("contents_pages", "Contents pages (blank = estimated)", "text")]
FRONT_FIELDS = TITLE_FIELDS + PUBLICATION_FIELDS + PAGE_FIELDS
LABEL_ROLES = {v: k for k, v in ROLE_LABELS.items()}


class _Forms:
    """Several forms read and written as one (the tab's sections)."""

    def __init__(self, forms):
        self.forms = forms
        self.vars = {k: v for f in forms for k, v in f.vars.items()}

    def load(self, data):
        for f in self.forms:
            f.load(data)

    def save(self, data):
        for f in self.forms:
            f.save(data)


class BookTabMixin:
    """Part of gui.App: builds and reads the Book Details tab."""

    def _book_tab(self):
        tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(tab, text="Book Details")
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
        from .gui import Form

        def fields(table):
            return [((key,), label, kind, None) for key, label, kind in table]
        cols = ttk.Frame(tab)
        cols.pack(fill="both", expand=True)
        left, right = ttk.Frame(cols), ttk.Frame(cols)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        right.pack(side="left", fill="both", expand=True)
        box = ttk.LabelFrame(left, text="Title", padding=6)
        box.pack(fill="x")
        forms = [Form(box, fields(TITLE_FIELDS))]
        self._contributors_box(left)
        box = ttk.LabelFrame(right, text="Publication", padding=6)
        box.pack(fill="x")
        forms.append(Form(box, fields(PUBLICATION_FIELDS)))
        box = ttk.LabelFrame(left, text="Pages", padding=6)
        box.pack(fill="x", pady=(6, 0))
        forms.append(Form(box, fields(PAGE_FIELDS)))
        self.front_form = _Forms(forms)
        ttk.Label(tab, text="Notices on the copyright page (from the profile's library; select "
                            "any number):").pack(anchor="w", pady=(8, 2))
        self.notice_list = tk.Listbox(tab, selectmode="multiple", height=4, exportselection=False)
        self.notice_list.pack(fill="x")
        nb = ttk.Frame(tab)
        nb.pack(fill="x", pady=4)
        ttk.Button(nb, text="Add notice to library...", command=self.add_notice).pack(side="left")
        ttk.Button(nb, text="Remove from library", command=self.remove_notice).pack(side="left",
                                                                                     padx=6)

    # ---- contributors ----

    def _contributors_box(self, parent):
        """The book's contributors in order (authors, editors, translators...): the title page
        has a byline per role in this order ("Edited by...", "Translated by...")."""
        box = ttk.LabelFrame(parent, text="Contributors (in title-page order)", padding=6)
        box.pack(fill="x", pady=(6, 0))
        self.creators = []
        tree = self.creator_tree = ttk.Treeview(box, columns=("role", "name"), show="headings",
                                                height=4, selectmode="browse")
        tree.heading("role", text="Role")
        tree.heading("name", text="Name (as on the title page)")
        tree.column("role", width=110)
        tree.column("name", width=280)
        tree.grid(row=0, column=0, columnspan=4, sticky="nsew")
        tree.bind("<<TreeviewSelect>>", self._creator_picked)
        self.creator_role = tk.StringVar(value=ROLE_LABELS["author"])
        self.creator_name = tk.StringVar()
        ttk.Combobox(box, textvariable=self.creator_role, state="readonly", width=13,
                     values=[ROLE_LABELS[r] for r in ROLES]).grid(row=1, column=0, sticky="w",
                                                                   pady=(6, 0))
        ttk.Entry(box, textvariable=self.creator_name, width=30).grid(
            row=1, column=1, columnspan=3, sticky="we", padx=(6, 0), pady=(6, 0))
        btns = ttk.Frame(box)
        btns.grid(row=2, column=0, columnspan=4, sticky="w", pady=(4, 0))
        for text, cmd in (("Add", self.add_creator), ("Change", self.change_creator),
                          ("Remove", self.remove_creator), ("Move up", lambda: self.move_creator(-1)),
                          ("Move down", lambda: self.move_creator(1))):
            ttk.Button(btns, text=text, command=cmd).pack(side="left", padx=(0, 4))
        box.columnconfigure(1, weight=1)
        box.rowconfigure(0, weight=1)

    def _show_creators(self, select=None):
        tree = self.creator_tree
        tree.delete(*tree.get_children())
        for n, c in enumerate(self.creators):
            tree.insert("", "end", iid=str(n), values=(ROLE_LABELS.get(c["role"], c["role"]),
                                                       c["name"]))
        if select is not None and 0 <= select < len(self.creators):
            tree.selection_set(str(select))

    def _creator_index(self):
        sel = self.creator_tree.selection()
        return int(sel[0]) if sel else None

    def _creator_picked(self, _event=None):
        i = self._creator_index()
        if i is not None:
            c = self.creators[i]
            self.creator_role.set(ROLE_LABELS.get(c["role"], c["role"]))
            self.creator_name.set(c["name"])

    def _creator_entry(self):
        name = " ".join(self.creator_name.get().split())
        return {"role": LABEL_ROLES.get(self.creator_role.get(), "author"), "name": name} \
            if name else None

    def add_creator(self):
        c = self._creator_entry()
        if c:
            self.creators.append(c)
            self.creator_name.set("")
            self._show_creators(len(self.creators) - 1)
            self.dirty = True

    def change_creator(self):
        i, c = self._creator_index(), self._creator_entry()
        if i is not None and c:
            self.creators[i] = c
            self._show_creators(i)
            self.dirty = True

    def remove_creator(self):
        i = self._creator_index()
        if i is not None:
            del self.creators[i]
            self._show_creators(min(i, len(self.creators) - 1))
            self.dirty = True

    def move_creator(self, step):
        i = self._creator_index()
        j = None if i is None else i + step
        if j is not None and 0 <= j < len(self.creators):
            self.creators[i], self.creators[j] = self.creators[j], self.creators[i]
            self._show_creators(j)
            self.dirty = True

    # ---- notices ----

    def _take_notices(self, texts):
        """Permissions found on the manuscript's copyright page: into the profile's notice
        library (by a short name: ESV, NKJV...) unless there already, and ticked for this
        book. Returns their names."""
        library = self.profile.setdefault("notices", [])
        names = []
        for text in texts:
            same = next((n for n in library if " ".join(n.get("text", "").split()) ==
                         " ".join(text.split())), None)
            if same is None:
                name, k = notice_name(text), 2
                taken = {n.get("name") for n in library}
                base = name
                while name in taken:
                    name, k = "%s (%d)" % (base, k), k + 1
                same = {"name": name, "text": text}
                library.append(same)
                self.notice_list.insert("end", name)
            i = library.index(same)
            self.notice_list.selection_set(i)
            names.append(same["name"])
        return names

    def add_notice(self):
        from .gui import TITLE
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

    def _load_book_into_forms(self):
        front = self.book.settings.get("front") or {"half_title": True, "contents": True}
        self.front_form.load(front)
        self.creators = [dict(c) for c in creators(front)]
        self._show_creators()
        self._refresh_files()
        self._refresh_heads()

    def _forms_to_book(self):
        front = self.book.settings.setdefault("front", {})
        self.front_form.save(front)
        front["creators"] = [dict(c) for c in self.creators]
        front.pop("author", None)
        cp = front.get("contents_pages")
        try:
            front["contents_pages"] = int(cp) if cp else None
        except ValueError:
            front["contents_pages"] = None
        names = [n.get("name") for n in self.profile.get("notices") or []]
        front["notices"] = [names[i] for i in self.notice_list.curselection() if i < len(names)]
        self.book.profile = self.profile_name

    def fill_front(self):
        self._need_report(self._fill_front_now)

    def _fill_front_now(self):
        o = self.report.outline
        front = self.book.settings.setdefault("front", {})
        self.front_form.save(front)
        filled = []
        for key, value in (("title", o.title), ("subtitle", o.subtitle)):
            if value and not front.get(key):
                front[key] = value
                filled.append(key)
        details = {k: v for k, v in (getattr(o, "details", {}) or {}).items()
                   if k in COPYRIGHT_FIELDS}
        for key, value in details.items():
            if value and not front.get(key):
                front[key] = value
                filled.append(key)
        added = self._take_notices((getattr(o, "details", {}) or {}).get("notices") or [])
        found_people = creators({}, o)
        if found_people and not self.creators:
            self.creators = found_people
            self._show_creators()
            filled.append("author")
        self.front_form.load(front)
        self.dirty = True
        found = []
        for key, label, value, source in (
                ("title", "Title", o.title, o.title_source),
                ("subtitle", "Subtitle", o.subtitle, o.subtitle_source),
                ("author", "Contributors", "; ".join(
                    "%s (%s)" % (c["name"], ROLE_LABELS[c["role"]]) for c in found_people),
                 o.author_source)):
            if value:
                state = "filled in" if key in filled else "already set, kept"
                found.append("%s: \u201c%s\u201d, from %s (%s)" % (label, value, source, state))
            else:
                found.append("%s: not found in the manuscript" % label)
        labels = {key: label for key, label, _k in PUBLICATION_FIELDS}
        if details:
            found.append("from the copyright page: " + ", ".join(
                "%s %s" % (labels.get(k, k).split(" (")[0].lower(),
                           "filled in" if k in filled else "already set, kept")
                for k in details))
        if added:
            found.append("notices ticked below: %s" % ", ".join(added))
        self.front_sources.set("Found in the manuscript \u2014 " + "; ".join(found) + ".")
