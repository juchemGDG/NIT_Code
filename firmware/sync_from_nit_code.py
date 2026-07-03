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

Mit ``--check`` wird nichts geschrieben, sondern nur geprueft, ob
firmware/www/ noch synchron zu nit_code/assets/blockly/ ist (Exit-Code 1,
wenn nicht). Gedacht fuer die Release-Skripte, damit ein vergessener Sync
vor dem Build auffaellt.
"""
import filecmp
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

# Kategorien, die im iPad-Modus KEINEN Sinn ergeben und daher aus der Toolbox
# entfernt werden. Das WLAN dient hier als Accesspoint fuer das iPad – MQTT und
# ESP-NOW brauchen aber eine andere WLAN-Nutzung und funktionieren nicht.
EXCLUDE_CATEGORIES = [
    "Funk (ESP-NOW / MQTT)",
]


def check() -> None:
    """Prueft, ob firmware/www/ synchron ist – ohne etwas zu schreiben."""
    stale: list[str] = []
    pairs = [(SRC / name, DST / name) for name in FILES]
    pairs.append((SRC / "de.js", DST / "msg" / "de.js"))
    media = SRC / "media"
    if media.is_dir():
        pairs += [(f, DST / "media" / f.name) for f in media.iterdir() if f.is_file()]
    for src, dst in pairs:
        if not dst.exists() or not filecmp.cmp(src, dst, shallow=False):
            stale.append(str(dst.relative_to(ROOT)))
    if stale:
        print("NICHT synchron – bitte 'python firmware/sync_from_nit_code.py' ausfuehren:")
        for s in stale:
            print("  ", s)
        sys.exit(1)
    print("firmware/www/ ist synchron zu nit_code/assets/blockly/.")


def main() -> None:
    if not SRC.is_dir():
        sys.exit(f"Quelle nicht gefunden: {SRC}")

    if "--check" in sys.argv[1:]:
        check()
        return

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

    # Im iPad-Modus nicht nutzbare Kategorien entfernen (z. B. Funk).
    for cat in EXCLUDE_CATEGORIES:
        toolbox, removed = re.subn(
            r'\s*<category name="' + re.escape(cat) + r'".*?</category>',
            "", toolbox, flags=re.S)
        print("Kategorie entfernt:" if removed else "Kategorie nicht gefunden:", cat)

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
