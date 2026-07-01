#!/usr/bin/env python3
"""Synchronisiert die iPad-Firmware-Oberflaeche mit NIT_Code.

Einzige Quelle der Wahrheit ist ``nit_code/assets/blockly/`` (derselbe
Block-Editor, den auch das Desktop-Programm nutzt). Dieses Skript

  * kopiert die Blockly-Binaries, die Blockdefinitionen (nit_blocks.js,
    nitbw_blocks.js), die deutsche Uebersetzung und die media-Dateien nach
    ``firmware/www/blockly/`` und
  * uebernimmt die Toolbox aus ``editor.html`` in ``firmware/www/index.html``
    (zwischen den TOOLBOX-Markern).

Nach jeder Aenderung an Bloecken oder Toolbox in NIT_Code einmal ausfuehren:

    python firmware/sync_from_nit_code.py

Dadurch ist jeder neue/geaenderte Block automatisch auch im iPad-Modus
verfuegbar – ohne Doppelpflege.
"""
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "nit_code" / "assets" / "blockly"
DST = ROOT / "firmware" / "www" / "blockly"
INDEX = ROOT / "firmware" / "www" / "index.html"

# 1:1 uebernommene Dateien (Blockly-Kern + geteilte Blockdefinitionen)
FILES = [
    "blockly_compressed.js",
    "blocks_compressed.js",
    "python_compressed.js",
    "nit_blocks.js",
    "nitbw_blocks.js",
]

TOOLBOX_START = ("<!-- TOOLBOX:START (auto-generiert aus editor.html via "
                 "sync_from_nit_code.py – nicht von Hand aendern) -->")
TOOLBOX_END = "<!-- TOOLBOX:END -->"


def main() -> None:
    if not SRC.is_dir():
        sys.exit(f"Quelle nicht gefunden: {SRC}")

    (DST / "msg").mkdir(parents=True, exist_ok=True)
    (DST / "media").mkdir(parents=True, exist_ok=True)

    for name in FILES:
        shutil.copy2(SRC / name, DST / name)
        print("kopiert:", name)

    shutil.copy2(SRC / "de.js", DST / "msg" / "de.js")
    print("kopiert: de.js -> msg/de.js")

    for f in (SRC / "media").iterdir():
        if f.is_file():
            shutil.copy2(f, DST / "media" / f.name)
    print("kopiert: media/*")

    # Toolbox aus editor.html extrahieren und in index.html einsetzen
    editor = (SRC / "editor.html").read_text(encoding="utf-8")
    m = re.search(r'<xml id="toolbox".*?</xml>', editor, re.S)
    if not m:
        sys.exit("Toolbox (<xml id=\"toolbox\">) in editor.html nicht gefunden")
    toolbox = m.group(0)

    index = INDEX.read_text(encoding="utf-8")
    pattern = re.escape(TOOLBOX_START) + r".*?" + re.escape(TOOLBOX_END)
    replacement = f"{TOOLBOX_START}\n{toolbox}\n{TOOLBOX_END}"
    new_index, n = re.subn(pattern, lambda _: replacement, index, flags=re.S)
    if n == 0:
        sys.exit("TOOLBOX-Marker in index.html nicht gefunden")
    INDEX.write_text(new_index, encoding="utf-8")
    print("Toolbox in index.html aktualisiert")
    print("\nFertig. firmware/www/ ist mit nit_code/assets/blockly/ synchron.")


if __name__ == "__main__":
    main()
