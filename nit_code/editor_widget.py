"""Code-Editor-Widget auf Basis von QScintilla mit Python/MicroPython Syntax-Highlighting."""
from PyQt6.QtCore import QEvent, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

try:
    from PyQt6.Qsci import (
        QsciScintilla,
        QsciLexerPython,
    )
    HAS_QSCI = True
except ImportError:
    HAS_QSCI = False

from .config import THEME
from .completion import JediCompleter, HAS_JEDI


def _hex(color: str) -> QColor:
    return QColor(color)


class CodeEditor(QWidget):
    """Haupt-Editor-Widget mit Zeilennummern, Syntax-Highlighting und Fehlermarkierung."""

    go_to_line_requested = pyqtSignal(int)  # für Klick auf Fehlermeldung → Zeile

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filepath: str | None = None
        # Zustand der laufenden Suche (für Weitersuchen mit findNext)
        self._search_active = False
        self._search_key = None
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI-Aufbau
    # ------------------------------------------------------------------
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Tab-Leiste (Datei-Tabs) wird von MainWindow verwaltet
        if HAS_QSCI:
            self.sci = QsciScintilla(self)
            self._configure_scintilla()
            self._setup_completion()
            layout.addWidget(self.sci)
        else:
            self.sci = _FallbackEditor(self)
            layout.addWidget(self.sci)

        # Such-/Ersetzen-Leiste (am unteren Rand, standardmäßig ausgeblendet)
        self._find_bar = _FindReplaceBar(self)
        layout.addWidget(self._find_bar)

    def _configure_scintilla(self):
        sci = self.sci
        t = THEME

        # Allgemein
        sci.setUtf8(True)
        sci.setFont(QFont("JetBrains Mono, Fira Code, Consolas, monospace", 12))

        # Farben
        sci.setPaper(_hex(t["bg_editor"]))
        sci.setColor(_hex(t["text"]))

        # Zeilennummern
        sci.setMarginType(0, QsciScintilla.MarginType.NumberMargin)
        sci.setMarginWidth(0, "0000")
        sci.setMarginsBackgroundColor(_hex(t["bg_panel"]))
        sci.setMarginsForegroundColor(_hex(t["text_dim"]))

        # Einrückungsführungslinien
        sci.setIndentationGuides(True)
        sci.setIndentationGuidesBackgroundColor(_hex(t["border"]))
        sci.setIndentationGuidesForegroundColor(_hex(t["border"]))

        # Tabs → Spaces
        sci.setTabWidth(4)
        sci.setIndentationsUseTabs(False)
        sci.setAutoIndent(True)

        # Aktuelle Zeile hervorheben
        sci.setCaretLineVisible(True)
        sci.setCaretLineBackgroundColor(_hex(t["selection"]))
        sci.setCaretForegroundColor(_hex(t["accent"]))

        # Klammernabgleich
        sci.setBraceMatching(QsciScintilla.BraceMatch.SloppyBraceMatch)

        # Zeilenumbruch
        sci.setWrapMode(QsciScintilla.WrapMode.WrapNone)

        # Scroll-Leisten
        sci.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        sci.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Fehler-Markierung (Margin 1)
        sci.setMarginType(1, QsciScintilla.MarginType.SymbolMargin)
        sci.setMarginWidth(1, 16)
        sci.setMarginSensitivity(1, True)
        self._error_marker = sci.markerDefine(QsciScintilla.MarkerSymbol.Circle)
        sci.setMarkerBackgroundColor(_hex(t["error"]), self._error_marker)
        sci.setMarkerForegroundColor(_hex(t["error"]), self._error_marker)

        # Lexer setzen
        self._set_lexer_python()

    def _set_lexer_python(self):
        if not HAS_QSCI:
            return
        t = THEME
        lexer = QsciLexerPython(self.sci)
        font = QFont("JetBrains Mono, Fira Code, Consolas, monospace", 12)

        # Basis-Farben
        lexer.setDefaultPaper(_hex(t["bg_editor"]))
        lexer.setDefaultColor(_hex(t["text"]))
        lexer.setDefaultFont(font)

        color_map = {
            QsciLexerPython.Default:          t["text"],
            QsciLexerPython.Comment:          t["text_dim"],
            QsciLexerPython.CommentBlock:     t["text_dim"],
            QsciLexerPython.Number:           t["warning"],
            QsciLexerPython.DoubleQuotedString: t["success"],
            QsciLexerPython.SingleQuotedString: t["success"],
            QsciLexerPython.TripleSingleQuotedString: t["success"],
            QsciLexerPython.TripleDoubleQuotedString: t["success"],
            QsciLexerPython.Keyword:          t["accent_hover"],
            QsciLexerPython.ClassName:        t["info"],
            QsciLexerPython.FunctionMethodName: t["info"],
            QsciLexerPython.Operator:         t["text"],
            QsciLexerPython.Identifier:       t["text"],
            QsciLexerPython.UnclosedString:   t["error"],
            QsciLexerPython.Decorator:        t["warning"],
        }
        for style, color in color_map.items():
            lexer.setColor(_hex(color), style)
            lexer.setPaper(_hex(t["bg_editor"]), style)
            lexer.setFont(font, style)

        self.sci.setLexer(lexer)
        self._lexer = lexer

    # ------------------------------------------------------------------
    # Öffentliche API
    # ------------------------------------------------------------------
    def set_text(self, text: str):
        if HAS_QSCI:
            self.sci.setText(text)
        else:
            self.sci.setPlainText(text)

    def get_text(self) -> str:
        if HAS_QSCI:
            return self.sci.text()
        return self.sci.toPlainText()

    def goto_line(self, line: int):
        """Springe zu Zeile (1-basiert)."""
        if HAS_QSCI:
            self.sci.setCursorPosition(line - 1, 0)
            self.sci.ensureLineVisible(line - 1)
        else:
            cursor = self.sci.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            for _ in range(line - 1):
                cursor.movePosition(cursor.MoveOperation.NextBlock)
            self.sci.setTextCursor(cursor)
            self.sci.ensureCursorVisible()

    def mark_error_line(self, line: int):
        """Markiert eine Fehlerzeile mit einem roten Punkt im Margin."""
        if HAS_QSCI:
            self.sci.markerAdd(line - 1, self._error_marker)

    def clear_error_markers(self):
        if HAS_QSCI:
            self.sci.markerDeleteAll(self._error_marker)

    def is_modified(self) -> bool:
        if HAS_QSCI:
            return self.sci.isModified()
        return self.sci.document().isModified()

    def set_font_size(self, size: int):
        """Schriftgröße des Editors und des Lexers ändern."""
        font = QFont("JetBrains Mono, Fira Code, Consolas, monospace", size)
        if HAS_QSCI:
            self.sci.setFont(font)
            if hasattr(self, "_lexer") and self._lexer:
                self._lexer.setDefaultFont(font)
                # Not all style IDs are valid on all QScintilla/Python builds.
                for style in range(128):
                    try:
                        self._lexer.setFont(font, style)
                    except Exception:
                        pass
        else:
            self.sci.setFont(font)

    def set_line_numbers_visible(self, visible: bool):
        """Zeilennummern ein- oder ausblenden."""
        if HAS_QSCI:
            self.sci.setMarginWidth(0, "0000" if visible else "")

    def set_word_wrap(self, enabled: bool):
        """Zeilenumbruch ein- oder ausschalten."""
        if HAS_QSCI:
            mode = QsciScintilla.WrapMode.WrapWord if enabled else QsciScintilla.WrapMode.WrapNone
            self.sci.setWrapMode(mode)

    def set_highlight_current_line(self, enabled: bool):
        """Aktuelle Zeile hervorheben ein- oder ausschalten."""
        if HAS_QSCI:
            self.sci.setCaretLineVisible(enabled)

    # ------------------------------------------------------------------
    # Suchen & Ersetzen
    # ------------------------------------------------------------------
    def show_find(self, with_replace: bool = False):
        """Such-Leiste einblenden, ggf. mit der aktuellen Auswahl vorbelegt."""
        preset = ""
        if HAS_QSCI and self.sci.hasSelectedText():
            sel = self.sci.selectedText()
            if "\n" not in sel:        # nur einzeilige Auswahl als Suchbegriff
                preset = sel
        self._find_bar.open(with_replace=with_replace, preset=preset)

    def show_replace(self):
        """Such-/Ersetzen-Leiste einblenden."""
        self.show_find(with_replace=True)

    def search_reset(self):
        """Laufende Suche verwerfen – nächster Treffer startet neu (findFirst)."""
        self._search_active = False
        self._search_key = None

    def find_next(self, query: str, *, forward: bool = True,
                  case: bool = False, whole: bool = False, regex: bool = False) -> bool:
        """Nächsten Treffer suchen und markieren. Gibt True bei Erfolg zurück."""
        if not query:
            return False
        if HAS_QSCI:
            sci = self.sci
            key = (query, case, whole, regex, forward)
            if self._search_active and key == self._search_key:
                found = sci.findNext()
            else:
                found = sci.findFirst(query, regex, case, whole, True, forward)
                self._search_key = key
            self._search_active = bool(found)
            return bool(found)
        return self._fallback_find(query, forward, case, whole)

    def replace_current(self, query: str, repl: str, *,
                        case: bool = False, whole: bool = False, regex: bool = False) -> bool:
        """Aktuellen Treffer ersetzen und zum nächsten springen."""
        if not query:
            return False
        if HAS_QSCI:
            sci = self.sci
            if self._search_active and sci.hasSelectedText():
                sci.replace(repl)
                self._search_active = False      # erzwingt findFirst ab neuer Position
            return self.find_next(query, forward=True, case=case, whole=whole, regex=regex)
        return self._fallback_replace_current(query, repl, case, whole)

    def replace_all(self, query: str, repl: str, *,
                    case: bool = False, whole: bool = False, regex: bool = False) -> int:
        """Alle Treffer ersetzen. Gibt die Anzahl der Ersetzungen zurück."""
        if not query:
            return 0
        if HAS_QSCI:
            sci = self.sci
            count = 0
            sci.beginUndoAction()
            try:
                # wrap=False, Start bei (0,0) → terminiert sicher am Dateiende
                found = sci.findFirst(query, regex, case, whole, False, True, 0, 0)
                while found:
                    sci.replace(repl)
                    count += 1
                    if count > 100000:           # Sicherung gegen Endlosschleifen
                        break
                    found = sci.findNext()
            finally:
                sci.endUndoAction()
            self.search_reset()
            return count
        return self._fallback_replace_all(query, repl, case, whole)

    # ── Fallback-Editor (ohne QScintilla) ────────────────────────────────
    def _fallback_find(self, query: str, forward: bool, case: bool, whole: bool) -> bool:
        from PyQt6.QtGui import QTextDocument
        edit = self.sci._edit
        flags = QTextDocument.FindFlag(0)
        if not forward:
            flags |= QTextDocument.FindFlag.FindBackward
        if case:
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        if whole:
            flags |= QTextDocument.FindFlag.FindWholeWords
        if edit.find(query, flags):
            return True
        # Am Dokumentende/-anfang umbrechen und erneut versuchen
        cursor = edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start if forward else cursor.MoveOperation.End)
        edit.setTextCursor(cursor)
        return edit.find(query, flags)

    def _fallback_replace_current(self, query: str, repl: str, case: bool, whole: bool) -> bool:
        edit = self.sci._edit
        cursor = edit.textCursor()
        sel = cursor.selectedText()
        if sel and (sel == query or (not case and sel.lower() == query.lower())):
            cursor.insertText(repl)
        return self._fallback_find(query, True, case, whole)

    def _fallback_replace_all(self, query: str, repl: str, case: bool, whole: bool) -> int:
        import re as _re
        text = self.get_text()
        if case:
            count = text.count(query)
            if count:
                self.set_text(text.replace(query, repl))
        else:
            new, count = _re.compile(_re.escape(query), _re.IGNORECASE).subn(repl, text)
            if count:
                self.set_text(new)
        return count

    def refresh_theme(self):
        """Farben nach Theme-Wechsel neu anwenden (ohne Margins neu zu definieren)."""
        self._find_bar.apply_theme()
        if not HAS_QSCI:
            return
        t = THEME
        self.sci.setPaper(_hex(t["bg_editor"]))
        self.sci.setColor(_hex(t["text"]))
        self.sci.setMarginsBackgroundColor(_hex(t["bg_panel"]))
        self.sci.setMarginsForegroundColor(_hex(t["text_dim"]))
        self.sci.setCaretLineBackgroundColor(_hex(t["selection"]))
        self.sci.setCaretForegroundColor(_hex(t["accent"]))
        self.sci.setIndentationGuidesBackgroundColor(_hex(t["border"]))
        self.sci.setIndentationGuidesForegroundColor(_hex(t["border"]))
        self.sci.setMarkerBackgroundColor(_hex(t["error"]), self._error_marker)
        self.sci.setMarkerForegroundColor(_hex(t["error"]), self._error_marker)
        self._set_lexer_python()

    def set_filepath(self, path: str | None):
        """Aktuellen Dateipfad setzen – verbessert jedi-Projekterkennung."""
        self._filepath = path

    def set_extra_completion_paths(self, paths: list[str]):
        """Zusätzliche Suchpfade für jedi (z. B. MicroPython-Stubs)."""
        if hasattr(self, "_completer"):
            self._completer.set_extra_paths(paths)

    # ------------------------------------------------------------------
    # Autovervollständigung (jedi)
    # ------------------------------------------------------------------
    def _setup_completion(self):
        sci = self.sci

        # QScintilla: Einzel-Auswahl sofort einfügen deaktivieren (wir steuern selbst)
        sci.setAutoCompletionUseSingle(QsciScintilla.AutoCompletionUseSingle.AcusNever)

        self._completer = JediCompleter(self)
        self._completer.completions_ready.connect(self._show_completions)

        self._completion_timer = QTimer(self)
        self._completion_timer.setSingleShot(True)
        self._completion_timer.timeout.connect(self._request_completion)

        sci.SCN_CHARADDED.connect(self._on_char_added)
        sci.SCN_USERLISTSELECTION.connect(self._on_completion_selected)

        # Ctrl+Space: Vervollständigung manuell auslösen
        shortcut = QShortcut(QKeySequence("Ctrl+Space"), sci)
        shortcut.activated.connect(self._request_completion)

    def _on_char_added(self, char: int):
        ch = chr(char) if 0 < char < 128 else ""
        if ch in (" ", "\n", "\r", "\t", ")", "]", "}", ";", ","):
            self._completion_timer.stop()
            return
        # Kürzere Wartezeit beim Punkt (Attributzugriff)
        self._completion_timer.setInterval(150 if ch == "." else 400)
        self._completion_timer.start()

    def _request_completion(self):
        sci = self.sci
        line, col = sci.getCursorPosition()
        # Mindestens 1 Zeichen des aktuellen Bezeichners getippt
        line_text = sci.text(line)
        word_start = col
        while word_start > 0 and (line_text[word_start - 1].isalnum() or line_text[word_start - 1] == "_"):
            word_start -= 1
        # Bei reinem Punkt (col direkt nach '.') auch auslösen
        at_dot = col > 0 and line_text[col - 1] == "."
        if col - word_start < 1 and not at_dot:
            return
        self._completer.request(sci.text(), line, col, self._filepath)

    def _show_completions(self, completions: list):
        if not completions or not HAS_QSCI:
            return
        names = [name for name, _ in completions]
        try:
            self.sci.showUserList(1, names)
        except Exception:
            pass

    def _on_completion_selected(self, text, list_id: int, *_args):
        if list_id != 1:
            return
        # QScintilla liefert den Text auf manchen Plattformen als bytes (char const*)
        if isinstance(text, bytes):
            text = text.decode("utf-8", errors="replace")
        # Insertion auf den nächsten Event-Loop verschieben:
        # direktes setSelection/replaceSelectedText im Signal-Handler führt auf
        # macOS zu einem reentrant QScintilla-Aufruf → abort()
        QTimer.singleShot(0, lambda t=text: self._insert_completion(t))

    def _insert_completion(self, text: str):
        try:
            sci = self.sci
            line, col = sci.getCursorPosition()
            line_text = sci.text(line)
            word_start = col
            while word_start > 0 and (line_text[word_start - 1].isalnum() or line_text[word_start - 1] == "_"):
                word_start -= 1
            sci.setSelection(line, word_start, line, col)
            sci.replaceSelectedText(text)
        except Exception:
            pass

    def comment_selection(self):
        """Markierte Zeilen mit # auskommentieren."""
        self._modify_comments("comment")

    def uncomment_selection(self):
        """Kommentarzeichen # von markierten Zeilen entfernen."""
        self._modify_comments("uncomment")

    def toggle_comment(self):
        """Kommentar in markierten Zeilen umschalten."""
        self._modify_comments("toggle")

    def _modify_comments(self, action: str):
        if HAS_QSCI:
            self._modify_comments_scintilla(action)
        else:
            self._modify_comments_fallback(action)

    def _modify_comments_scintilla(self, action: str):
        sci = self.sci
        line_from, _idx_from, line_to, idx_to = sci.getSelection()
        if line_from < 0:
            line_from, _ = sci.getCursorPosition()
            line_to = line_from
        elif idx_to == 0 and line_to > line_from:
            line_to -= 1

        if action == "toggle":
            texts = [sci.text(l).strip() for l in range(line_from, line_to + 1) if sci.text(l).strip()]
            all_commented = bool(texts) and all(t.startswith('#') for t in texts)
            action = "uncomment" if all_commented else "comment"

        sci.beginUndoAction()
        try:
            for line in range(line_from, line_to + 1):
                raw = sci.text(line)
                body = raw.rstrip('\r\n')
                indent = body[:len(body) - len(body.lstrip())]
                code = body[len(indent):]
                if action == "comment":
                    if not code.strip():
                        continue
                    new_body = f"{indent}# {code}"
                elif code.startswith('# '):
                    new_body = f"{indent}{code[2:]}"
                elif code.startswith('#'):
                    new_body = f"{indent}{code[1:]}"
                else:
                    continue
                sci.setSelection(line, 0, line, len(body))
                sci.replaceSelectedText(new_body)
        finally:
            sci.endUndoAction()

    def _modify_comments_fallback(self, action: str):
        from PyQt6.QtGui import QTextCursor
        edit = self.sci._edit
        cursor = edit.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        doc = edit.document()
        sel_start, sel_end = cursor.selectionStart(), cursor.selectionEnd()
        b_from = doc.findBlock(sel_start)
        b_to = doc.findBlock(max(sel_start, sel_end - 1))

        blocks = []
        b = b_from
        while b.isValid() and b.blockNumber() <= b_to.blockNumber():
            blocks.append(b)
            b = b.next()

        if action == "toggle":
            texts = [b.text().strip() for b in blocks if b.text().strip()]
            all_commented = bool(texts) and all(t.startswith('#') for t in texts)
            action = "uncomment" if all_commented else "comment"

        main_cursor = edit.textCursor()
        main_cursor.beginEditBlock()
        for b in reversed(blocks):
            text = b.text()
            indent = text[:len(text) - len(text.lstrip())]
            code = text[len(indent):]
            if action == "comment":
                if not code.strip():
                    continue
                new_text = f"{indent}# {code}"
            elif code.startswith('# '):
                new_text = f"{indent}{code[2:]}"
            elif code.startswith('#'):
                new_text = f"{indent}{code[1:]}"
            else:
                continue
            c = QTextCursor(b)
            c.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
            c.insertText(new_text)
        main_cursor.endEditBlock()


# ------------------------------------------------------------------
# Such-/Ersetzen-Leiste
# ------------------------------------------------------------------
class _FindReplaceBar(QWidget):
    """Einklappbare Leiste am unteren Editorrand für Suchen & Ersetzen."""

    def __init__(self, editor: "CodeEditor"):
        super().__init__(editor)
        self._editor = editor
        self._build_ui()
        self.hide()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 4, 6, 4)
        outer.setSpacing(4)

        # ── Zeile 1: Suchen ──
        row1 = QHBoxLayout()
        row1.setSpacing(4)
        self._find_edit = QLineEdit()
        self._find_edit.setPlaceholderText("Suchen …")
        self._find_edit.installEventFilter(self)        # Enter / Shift+Enter abfangen
        self._find_edit.textChanged.connect(self._on_query_changed)
        row1.addWidget(self._find_edit, 1)

        self._prev_btn = QPushButton("▲")
        self._prev_btn.setToolTip("Vorheriger Treffer (Shift+Enter)")
        self._prev_btn.setFixedWidth(28)
        self._prev_btn.clicked.connect(self.find_prev)
        self._next_btn = QPushButton("▼")
        self._next_btn.setToolTip("Nächster Treffer (Enter)")
        self._next_btn.setFixedWidth(28)
        self._next_btn.clicked.connect(self.find_next)
        row1.addWidget(self._prev_btn)
        row1.addWidget(self._next_btn)

        self._cs_chk = QCheckBox("Aa")
        self._cs_chk.setToolTip("Groß-/Kleinschreibung beachten")
        self._ww_chk = QCheckBox("⊏⊐")
        self._ww_chk.setToolTip("Nur ganze Wörter")
        self._re_chk = QCheckBox(".*")
        self._re_chk.setToolTip("Regulärer Ausdruck")
        for chk in (self._cs_chk, self._ww_chk, self._re_chk):
            chk.toggled.connect(self._on_query_changed)
            row1.addWidget(chk)

        self._status_lbl = QLabel("")
        self._status_lbl.setMinimumWidth(80)
        row1.addWidget(self._status_lbl)

        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedWidth(28)
        self._close_btn.setToolTip("Schließen (Esc)")
        self._close_btn.clicked.connect(self.hide_bar)
        row1.addWidget(self._close_btn)
        outer.addLayout(row1)

        # ── Zeile 2: Ersetzen ──
        self._replace_row = QWidget()
        row2 = QHBoxLayout(self._replace_row)
        row2.setContentsMargins(0, 0, 0, 0)
        row2.setSpacing(4)
        self._replace_edit = QLineEdit()
        self._replace_edit.setPlaceholderText("Ersetzen durch …")
        self._replace_edit.returnPressed.connect(self.replace_current)
        row2.addWidget(self._replace_edit, 1)
        self._replace_btn = QPushButton("Ersetzen")
        self._replace_btn.clicked.connect(self.replace_current)
        self._replace_all_btn = QPushButton("Alle ersetzen")
        self._replace_all_btn.clicked.connect(self.replace_all)
        row2.addWidget(self._replace_btn)
        row2.addWidget(self._replace_all_btn)
        outer.addWidget(self._replace_row)

        # Esc schließt die Leiste (auch wenn der Fokus in einem Feld liegt)
        esc = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        esc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        esc.activated.connect(self.hide_bar)

        self.apply_theme()

    # ── Steuerung ─────────────────────────────────────────────────────
    def open(self, *, with_replace: bool, preset: str):
        if preset:
            self._find_edit.setText(preset)
        self._replace_row.setVisible(with_replace)
        self._editor.search_reset()
        self.show()
        self._find_edit.setFocus()
        self._find_edit.selectAll()
        self._status_lbl.setText("")

    def hide_bar(self):
        self.hide()
        if HAS_QSCI:
            self._editor.sci.setFocus()

    def eventFilter(self, obj, event):
        if obj is self._find_edit and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    self.find_prev()
                else:
                    self.find_next()
                return True
        return super().eventFilter(obj, event)

    def _opts(self) -> dict:
        return {
            "case": self._cs_chk.isChecked(),
            "whole": self._ww_chk.isChecked(),
            "regex": self._re_chk.isChecked(),
        }

    def _on_query_changed(self, *_):
        # Suchbegriff/Optionen geändert → laufende Suche zurücksetzen
        self._editor.search_reset()
        self._status_lbl.setText("")

    def find_next(self):
        self._report(self._editor.find_next(self._find_edit.text(), forward=True, **self._opts()))

    def find_prev(self):
        self._report(self._editor.find_next(self._find_edit.text(), forward=False, **self._opts()))

    def replace_current(self):
        if not self._replace_row.isVisible():
            self.find_next()
            return
        self._report(self._editor.replace_current(
            self._find_edit.text(), self._replace_edit.text(), **self._opts()))

    def replace_all(self):
        n = self._editor.replace_all(
            self._find_edit.text(), self._replace_edit.text(), **self._opts())
        self._status_lbl.setText(f"{n} ersetzt" if n else "Nicht gefunden")

    def _report(self, found: bool):
        self._status_lbl.setText("" if found else "Nicht gefunden")

    # ── Theme ─────────────────────────────────────────────────────────
    def apply_theme(self):
        t = THEME
        self.setStyleSheet(
            f"background:{t['bg_panel']}; border-top:1px solid {t['border']};"
        )
        field = (
            f"QLineEdit {{ background:{t['bg_editor']}; color:{t['text']};"
            f" border:1px solid {t['border']}; border-radius:4px; padding:3px 6px; }}"
        )
        self._find_edit.setStyleSheet(field)
        self._replace_edit.setStyleSheet(field)
        btn = (
            f"QPushButton {{ background:{t['bg_dark']}; color:{t['text']};"
            f" border:1px solid {t['border']}; border-radius:4px; padding:3px 8px; }}"
            f"QPushButton:hover {{ background:{t['accent']}; color:#fff; }}"
        )
        for b in (self._prev_btn, self._next_btn, self._close_btn,
                  self._replace_btn, self._replace_all_btn):
            b.setStyleSheet(btn)
        chk = f"color:{t['text']};"
        for c in (self._cs_chk, self._ww_chk, self._re_chk):
            c.setStyleSheet(chk)
        self._status_lbl.setStyleSheet(f"color:{t['text_dim']}; padding:0 4px;")


# ------------------------------------------------------------------
# Fallback-Editor ohne QScintilla
# ------------------------------------------------------------------
class _FallbackEditor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        from PyQt6.QtWidgets import QPlainTextEdit, QVBoxLayout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._edit = QPlainTextEdit(self)
        self._edit.setFont(QFont("Consolas, monospace", 12))
        self._edit.setStyleSheet(
            f"background:{THEME['bg_editor']}; color:{THEME['text']}; border:none;"
        )
        layout.addWidget(self._edit)

    def setPlainText(self, t):
        self._edit.setPlainText(t)

    def toPlainText(self):
        return self._edit.toPlainText()

    def textCursor(self):
        return self._edit.textCursor()

    def setTextCursor(self, c):
        self._edit.setTextCursor(c)

    def ensureCursorVisible(self):
        self._edit.ensureCursorVisible()

    def document(self):
        return self._edit.document()

    def setFont(self, font):
        self._edit.setFont(font)
