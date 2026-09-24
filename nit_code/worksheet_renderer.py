"""Markdown→HTML-Rendering für Arbeitsblätter (Obsidian-Callouts, Codeblöcke,
raw-HTML-Templates). Keine Qt-Abhängigkeit – wird von worksheet_panel.py genutzt."""
import html
import re

try:
    import markdown
    from markdown.extensions import Extension
    from markdown.preprocessors import Preprocessor
    from obsidian_callouts.extension import ObsidianCalloutsExtension
    import pygments
    from pygments.formatters import HtmlFormatter
    from pygments.lexers import get_lexer_by_name, guess_lexer
    from pygments.util import ClassNotFound
    HAS_MARKDOWN = True
except ImportError:
    HAS_MARKDOWN = False

_FENCE_OPEN_RE = re.compile(
    r"^(?P<prefix>(?:[ \t]{0,3}>[ \t]?)*)(?P<fence>```|~~~)[ \t]*(?P<lang>[\w#+.-]*)[ \t]*$"
)
_QUOTE_MARK_RE = re.compile(r"^[ \t]{0,3}>[ \t]?")


def _strip_quote_prefix(line: str, depth: int) -> str:
    """Streift bis zu `depth` Callout-/Blockquote-Marker („> ") von `line` ab.

    Eine leere Callout-Zeile darf auch nur „>" ohne folgendes Leerzeichen sein
    (siehe ObsidianCalloutProcessor.clean), deshalb ein eigener Abgleich statt
    ein simpler startswith(prefix)-Vergleich."""
    for _ in range(depth):
        new_line = _QUOTE_MARK_RE.sub("", line, count=1)
        if new_line == line:
            break
        line = new_line
    return line


class _NitCodeBlockPreprocessor(Preprocessor if HAS_MARKDOWN else object):
    """Ersetzt ```lang ...``` selbst (statt fenced_code/codehilite), damit wir
    volle Kontrolle über Markup + IDs für die Kopieren-/Einfügen-Toolbar behalten.

    Läuft zeilenweise (statt per Regex über den Gesamttext), damit Codeblöcke
    innerhalb von Obsidian-Callouts (jede Zeile mit „> " eingerückt) erkannt
    werden: das führende „> " wird vor dem Fence-Abgleich abgestreift und beim
    Platzhalter wieder vorangestellt, damit der Callout-Blockprozessor die
    Zeile weiterhin als Teil des Zitats erkennt."""

    def __init__(self, md, blocks: dict, style_name: str):
        super().__init__(md)
        self._blocks = blocks
        self._style_name = style_name
        self._counter = 0

    def run(self, lines):
        out = []
        i, n = 0, len(lines)
        while i < n:
            m = _FENCE_OPEN_RE.match(lines[i])
            if not m:
                out.append(lines[i])
                i += 1
                continue

            prefix = m.group("prefix")
            depth = prefix.count(">")
            fence = m.group("fence")
            lang = (m.group("lang") or "").strip() or "text"
            close_re = re.compile(rf"^[ \t]*{re.escape(fence)}[ \t]*$")

            code_lines = []
            i += 1
            while i < n:
                line = lines[i]
                stripped = _strip_quote_prefix(line, depth) if depth else line
                if close_re.match(stripped):
                    i += 1
                    break
                code_lines.append(stripped)
                i += 1

            code = "\n".join(code_lines)
            placeholder = self.md.htmlStash.store(self._build_wrapper(lang, code))
            out.append(f"{prefix}{placeholder}" if prefix else placeholder)
        return out

    def _build_wrapper(self, lang: str, code: str) -> str:
        self._counter += 1
        block_id = f"wsblk{self._counter}"
        self._blocks[block_id] = code
        try:
            lexer = get_lexer_by_name(lang, stripnl=False)
        except ClassNotFound:
            try:
                lexer = guess_lexer(code)
            except ClassNotFound:
                lexer = get_lexer_by_name("text", stripnl=False)
        formatter = HtmlFormatter(cssclass="codehilite", style=self._style_name, wrapcode=True)
        highlighted = pygments.highlight(code, lexer, formatter)
        return (
            f'<div class="nit-codeblock" data-id="{block_id}">'
            f'<div class="nit-code-toolbar">'
            f'<span class="nit-code-lang">{html.escape(lang)}</span>'
            f'<a href="#" class="nit-btn nit-btn-copy" '
            f"onclick=\"nitCopyBlock('{block_id}', this); return false;\">📋 Kopieren</a>"
            f'<a href="nitcode://insert?id={block_id}" '
            f'class="nit-btn nit-btn-insert">⬇ In Editor einfügen</a>'
            f"</div>{highlighted}</div>"
        )


class _NitCodeBlockExtension(Extension if HAS_MARKDOWN else object):
    def __init__(self, blocks: dict, style_name: str):
        self._blocks = blocks
        self._style_name = style_name
        super().__init__()

    def extendMarkdown(self, md):
        md.preprocessors.register(
            _NitCodeBlockPreprocessor(md, self._blocks, self._style_name), "nit_codeblocks", 25
        )


def render_worksheet(markdown_text: str, dark: bool):
    """Markdown → (HTML-Fragment, {block_id: roher Code}).

    Erfordert HAS_MARKDOWN. Ein frisches Markdown()-Objekt pro Aufruf – kein
    md.reset() nötig, passt zum bestehenden „bei jeder Änderung alles neu
    aufbauen"-Muster (vgl. MermaidPreview._reload_shell in coder_panel.py).
    """
    blocks: dict = {}
    style_name = "monokai" if dark else "default"
    md = markdown.Markdown(
        extensions=[
            "tables",
            "sane_lists",
            "nl2br",
            "md_in_html",
            ObsidianCalloutsExtension(),
            _NitCodeBlockExtension(blocks, style_name),
        ],
        output_format="html",
    )
    return md.convert(markdown_text), blocks


def pygments_css(dark: bool) -> str:
    style_name = "monokai" if dark else "default"
    return HtmlFormatter(style=style_name, cssclass="codehilite").get_style_defs(".codehilite")
