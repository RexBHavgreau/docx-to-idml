"""Command line: python -m docx2idml preflight|profile ..."""

import argparse
import sys

from . import __version__
from . import profile as profiles
from .book import Book, apply_saved_order, collect, natural_sort
from .preflight import preflight, render_text


def _out(text, path):
    if path:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        sys.stdout.write(text)


def cmd_preflight(args):
    book = None
    if args.book:
        book = Book.load(args.book)
    files, skipped = collect(args.files) if args.files else ([], [])
    if book:
        files = apply_saved_order(book.files, files) if files else book.files
    if args.sort:
        files = natural_sort(files)
    for path, reason in skipped:
        print("Skipped %s: %s" % (path, reason), file=sys.stderr)
    if not files:
        print("No .docx files to read.", file=sys.stderr)
        return 2
    prof = profiles.load(args.profile or (book.profile if book else None))
    rep = preflight(files, prof)
    _out(rep.to_json() + "\n" if args.json else render_text(rep), args.out)
    if args.save_book:
        b = book or Book()
        b.files = files
        b.profile = args.profile or b.profile
        b.save(args.save_book)
    return 1 if rep.errors else 0


def cmd_profile(args):
    if args.action == "list":
        names = profiles.list_profiles()
        print("\n".join(names) if names else "No saved profiles (the defaults are used).")
    elif args.action == "show":
        import json
        print(json.dumps(profiles.load(args.name), ensure_ascii=False, indent=2))
    elif args.action == "new":
        p = profiles.default_profile()
        p["name"] = args.name
        profiles.save(p)
        print("Saved profile %s at %s" % (args.name, profiles.profile_path(args.name)))
    elif args.action == "export":
        profiles.export_profile(args.name, args.path)
        print("Exported %s to %s" % (args.name, args.path))
    elif args.action == "import":
        print("Imported profile %s" % profiles.import_profile(args.path))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="docx2idml", description="Word manuscript to IDML book.")
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    pf = sub.add_parser("preflight", help="report what the manuscript contains and what needs "
                                          "attention")
    pf.add_argument("files", nargs="*", help=".docx files or folders, in book order")
    pf.add_argument("--profile", help="profile name or .json file")
    pf.add_argument("--book", help="book settings file (keeps the file order)")
    pf.add_argument("--save-book", metavar="PATH", help="save the file order to a book file")
    pf.add_argument("--sort", action="store_true", help="sort the files by name (natural order)")
    pf.add_argument("--json", action="store_true", help="write the report as JSON")
    pf.add_argument("--out", help="write the report to a file")
    pf.set_defaults(func=cmd_preflight)

    pr = sub.add_parser("profile", help="list, show, create, export or import profiles")
    pr.add_argument("action", choices=["list", "show", "new", "export", "import"])
    pr.add_argument("name", nargs="?", help="profile name (or file, for import)")
    pr.add_argument("path", nargs="?", help="file to export to")
    pr.set_defaults(func=cmd_profile)

    args = ap.parse_args(argv)
    if args.cmd == "profile" and args.action == "import":
        args.path = args.path or args.name
    try:
        return args.func(args)
    except profiles.ProfileError as e:
        print(str(e), file=sys.stderr)
        return 2
