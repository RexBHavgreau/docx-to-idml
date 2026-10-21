"""Convert Adobe's IDML schema (RELAX NG compact, .rnc) to the XML form (.rng) that jing reads.

    python tools/prepare_schema.py

Reads idml-schema/rnc/ (as InDesign's generateIDMLSchema writes it) and writes idml-schema/rng/.
Run it again after a major InDesign update, with the new .rnc files in idml-schema/rnc/.
Needs Java and the jingtrang package (pip install jingtrang): trang converts the included
grammar correctly where rnc2rng doesn't.

Adobe's datatype.rnc has a documentation comment written without '#' marks (the "Schema for
packaged folios" table), which no parser accepts; it is commented out in a temporary copy.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RNC = os.path.join(ROOT, "idml-schema", "rnc")
RNG = os.path.join(ROOT, "idml-schema", "rng")

# The schemas for the package's parts; each includes ../datatype.rnc (or datatype.rnc).
TOP = ["designmap.rnc", "MasterSpreads/MasterSpread.rnc", "Resources/Fonts.rnc",
       "Resources/Graphic.rnc", "Resources/Preferences.rnc", "Resources/Styles.rnc",
       "Spreads/Spread.rnc", "Stories/Story.rnc", "XML/BackingStory.rnc", "XML/Mapping.rnc",
       "XML/Tags.rnc"]


def fix_datatype(text):
    """Comment out the lines of the undelimited documentation block."""
    lines = text.split("\n")
    out, inside = [], False
    for line in lines:
        if line.startswith("Schema for packaged folios"):
            inside = True
        elif inside and re.match(r"^\w+_TypeDef\s*=", line):
            inside = False
        out.append("# " + line if inside and line.strip() else line)
    return "\n".join(out)


def trang_jar():
    import jingtrang
    return os.path.join(os.path.dirname(jingtrang.__file__), "trang.jar")


def main():
    work = tempfile.mkdtemp()
    try:
        shutil.copytree(RNC, os.path.join(work, "rnc"))
        dt = os.path.join(work, "rnc", "datatype.rnc")
        with open(dt, encoding="utf-8") as f:
            text = f.read()
        with open(dt, "w", encoding="utf-8") as f:
            f.write(fix_datatype(text))
        if os.path.isdir(RNG):
            shutil.rmtree(RNG)
        for top in TOP:
            src = os.path.join(work, "rnc", top)
            dest = os.path.join(RNG, top[:-4] + ".rng")
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            # trang writes the included datatype grammar beside the output as datatype.rng.
            r = subprocess.run(["java", "-jar", trang_jar(), "-I", "rnc", "-O", "rng", src, dest],
                               capture_output=True, text=True)
            if r.returncode:
                print("trang failed on %s:\n%s" % (top, r.stderr or r.stdout))
                return 1
            print("converted " + top)
        # trang writes a copy of the shared datatype grammar beside each schema; keep the one
        # at the top and point the others at it.
        for top in TOP:
            if "/" not in top:
                continue
            d = os.path.join(RNG, os.path.dirname(top))
            copy = os.path.join(d, "datatype.rng")
            if os.path.exists(copy):
                os.remove(copy)
            rng = os.path.join(RNG, top[:-4] + ".rng")
            with open(rng, encoding="utf-8") as f:
                text = f.read()
            with open(rng, "w", encoding="utf-8") as f:
                f.write(text.replace('<include href="datatype.rng"/>',
                                     '<include href="../datatype.rng"/>'))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
