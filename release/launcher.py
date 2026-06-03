"""Entry point used by PyInstaller builds."""
import multiprocessing
import sys

multiprocessing.freeze_support()

# ──────────────────────────────────────────────────────────────────────────────
# Tool-Dispatcher (mpremote / esptool)
# In einem PyInstaller-Bundle ist sys.executable die App selbst (kein Python),
# und der System-Python enthält die Pakete mpremote/esptool i. d. R. NICHT
# ("No module named mpremote"). Damit die App ihre eigenen, mitgelieferten Tools
# nutzen kann, ruft sie sich selbst als Interpreter auf ("App -m mpremote ...").
# Diese Aufrufe werden hier abgefangen und das jeweilige Modul in-process
# ausgeführt – die GUI wird dabei NICHT gestartet.
# ──────────────────────────────────────────────────────────────────────────────
if getattr(sys, "frozen", False) and len(sys.argv) >= 3 and sys.argv[1] == "-m":
    _module = sys.argv[2]
    if _module == "mpremote":
        from mpremote import main as _mpremote_main
        sys.argv = ["mpremote", *sys.argv[3:]]
        sys.exit(_mpremote_main.main())
    if _module == "esptool":
        import esptool
        sys.argv = ["esptool", *sys.argv[3:]]
        sys.exit(esptool._main())

# ──────────────────────────────────────────────────────────────────────────────
# Fork-Bomb-Schutz
# Wird die App versehentlich als Interpreter gestartet ("App -i", "App -c ...",
# "App -m <unbekannt>"), darf sie NICHT die GUI öffnen – sonst startet sich die
# App rekursiv immer wieder neu (Endlosschleife, kann den Rechner zum Absturz
# bringen). In diesem Fall sofort und sauber beenden.
# ──────────────────────────────────────────────────────────────────────────────
if getattr(sys, "frozen", False) and len(sys.argv) > 1 and sys.argv[1] in ("-i", "-m", "-c"):
    sys.stderr.write(
        "NIT_Code wurde fälschlich als Python-Interpreter aufgerufen "
        f"({' '.join(sys.argv[1:])}). Beende, um eine Endlosschleife zu verhindern.\n"
    )
    sys.exit(0)

from nit_code.main import main


if __name__ == "__main__":
    main()
