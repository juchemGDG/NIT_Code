"""Jedi-basierte Code-Vervollständigung in einem einzelnen Hintergrund-Worker."""
import threading

from PyQt6.QtCore import QObject, pyqtSignal

try:
    import jedi
    HAS_JEDI = True
except ImportError:
    HAS_JEDI = False


class JediCompleter(QObject):
    """Berechnet Vervollständigungen in EINEM Daemon-Worker.

    Frühere Version: pro Tastendruck wurde ein neuer Thread gestartet. Bei
    schnellem Tippen liefen dadurch viele teure ``jedi.complete()``-Aufrufe
    gleichzeitig (CPU-Spitzen). Jetzt gibt es genau einen Worker mit einem
    "latest wins"-Slot: Nur die jeweils neueste Anfrage wird berechnet,
    veraltete werden verworfen, bevor (und nachdem) gerechnet wird.
    """

    completions_ready = pyqtSignal(list)  # list of (name: str, type: str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cond = threading.Condition()
        self._pending: tuple | None = None       # neueste Anfrage
        self._seq = 0
        self._extra_paths: list[str] = []
        self._worker_started = False
        self._worker = threading.Thread(target=self._loop, daemon=True)

    def set_extra_paths(self, paths: list[str]):
        """Zusätzliche sys.path-Einträge für jedi (z. B. MicroPython-Stubs)."""
        self._extra_paths = list(paths)

    def request(self, source: str, line: int, col: int, path: str | None = None):
        """Stellt eine Completion-Anfrage. line/col sind 0-basiert (wie QScintilla)."""
        if not HAS_JEDI:
            return
        with self._cond:
            self._seq += 1
            self._pending = (source, line + 1, col, path,
                             list(self._extra_paths), self._seq)
            if not self._worker_started:
                self._worker_started = True
                self._worker.start()
            self._cond.notify()

    def _loop(self):
        while True:
            with self._cond:
                while self._pending is None:
                    self._cond.wait()
                source, line, col, path, extra_paths, seq = self._pending
                self._pending = None

            try:
                project_kwargs: dict = {}
                if extra_paths:
                    project_kwargs["added_sys_path"] = extra_paths
                project = jedi.Project(".", **project_kwargs)
                script_kwargs: dict = {"project": project}
                if path:
                    script_kwargs["path"] = path
                script = jedi.Script(source, **script_kwargs)
                completions = script.complete(line, col)
                results = [(c.name, c.type) for c in completions[:80]]
            except Exception:
                results = []

            # Während der Berechnung kam evtl. eine neuere Anfrage → verwerfen
            with self._cond:
                if seq != self._seq:
                    continue
            self.completions_ready.emit(results)
