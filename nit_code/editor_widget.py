"""Code-Editor-Widget auf Basis von QScintilla mit Python/MicroPython Syntax-Highlighting."""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QKeySequence
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


def _hex(color: str) -> QColor:
    return QColor(color)


class CodeEditor(QWidget):
    """Haupt-Editor-Widget mit Zeilennummern, Syntax-Highlighting und Fehlermarkierung."""

    go_to_line_requested = pyqtSignal(int)  # für Klick auf Fehlermeldung → Zeile

    def __init__(self, parent=None):
        super().__init__(parent)
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
