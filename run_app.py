"""Entry point for PyInstaller: no arguments opens the window; with arguments the .exe runs a
command (docx2idml.cli: convert, update, export...), which is how other programs call it."""
import sys

from docx2idml.cli import main

if __name__ == "__main__":
    sys.exit(main())
