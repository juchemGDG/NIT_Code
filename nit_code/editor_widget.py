"""Code-Editor-Widget auf Basis von QScintilla mit Python/MicroPython Syntax-Highlighting."""
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel

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
            from PyQt6.QtWidgets import QPlainTextEdit
            self.sci = _FallbackEditor(self)
            layout.addWidget(self.sci)

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

    def refresh_theme(self):
        """Farben nach Theme-Wechsel neu anwenden (ohne Margins neu zu definieren)."""
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
