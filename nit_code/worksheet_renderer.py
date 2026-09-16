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

_FENCE_RE = re.compile(
    r"^(?P<fence>```|~~~)[ \t]*(?P<lang>[\w#+.-]*)[ \t]*\n"
    r"(?P<code>.*?)\n?"
    r"^(?P=fence)[ \t]*$",
    re.MULTILINE | re.DOTALL,
)


class _NitCodeBlockPreprocessor(Preprocessor if HAS_MARKDOWN else object):
    """Ersetzt ```lang ...``` selbst (statt fenced_code/codehilite), damit wir
    volle Kontrolle über Markup + IDs für die Kopieren-/Einfügen-Toolbar behalten."""

    def __init__(self, md, blocks: dict, style_name: str):
        super().__init__(md)
        self._blocks = blocks
        self._style_name = style_name
        self._counter = 0

    def run(self, lines):
        text = "\n".join(lines)

        def repl(m):
            self._counter += 1
            block_id = f"wsblk{self._counter}"
            lang = (m.group("lang") or "").strip() or "text"
            code = m.group("code")
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
            wrapper = (
                f'<div class="nit-codeblock" data-id="{block_id}">'
                f'<div class="nit-code-toolbar">'
                f'<span class="nit-code-lang">{html.escape(lang)}</span>'
                f'<a href="#" class="nit-btn nit-btn-copy" '
                f"onclick=\"nitCopyBlock('{block_id}', this); return false;\">📋 Kopieren</a>"
                f'<a href="nitcode://insert?id={block_id}" '
                f'class="nit-btn nit-btn-insert">⬇ In Editor einfügen</a>'
                f"</div>{highlighted}</div>"
            )
            return self.md.htmlStash.store(wrapper)

        text = _FENCE_RE.sub(repl, text)
        return text.split("\n")


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
