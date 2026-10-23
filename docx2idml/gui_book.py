"""The Book Details tab of the window (moved out of gui.py): the book's bibliographic details
for the title and copyright pages, filled from the manuscript, and the notice library."""

from tkinter import simpledialog, ttk
import tkinter as tk

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
        form = ttk.Frame(tab)
        form.pack(fill="x")
        fields = [((key,), label, kind, None) for key, label, kind in FRONT_FIELDS]
        from .gui import Form
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
