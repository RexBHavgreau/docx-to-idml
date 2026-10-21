"""Entry point for the window (and for PyInstaller)."""
import sys

from docx2idml.gui import main

if __name__ == "__main__":
    sys.exit(main())
