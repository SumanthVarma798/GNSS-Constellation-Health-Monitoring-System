"""A pull request's text as plain reading, for the administration console's Approvals page.

Text from a pull request comes from outside (the weekly job copies lines from the IGS file into its pull request), so
everything is escaped; only headings, bullet lists, bold, web links and indented lines are kept as markup.
"""
import re
from html import escape

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")


def _inline(text):
    """One line: escaped, then **bold** and [words](http link) put back."""
    text = _BOLD.sub(r"<b>\1</b>", escape(text))
    return _LINK.sub(r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>', text)


def text_html(markdown):
    """A pull request's text as reading: headings, bullet lists, bold, links and indented lines. Nothing else in it is
    read as markup."""
    out, bullets = [], []

    def end_list():
        if bullets:
            out.append("<ul>" + "".join(f"<li>{b}</li>" for b in bullets) + "</ul>")
            bullets.clear()

    for line in markdown.splitlines():
        plain = line.strip()
        if plain.startswith(("- ", "* ")):
            bullets.append(_inline(plain[2:]))
            continue
        end_list()
        if not plain:
            continue
        if plain.startswith("#"):
            out.append(f"<h4>{_inline(plain.lstrip('#').strip())}</h4>")
        elif line.startswith(("    ", "\t")):
            out.append(f"<pre>{escape(plain)}</pre>")
        else:
            out.append(f"<p>{_inline(plain)}</p>")
    end_list()
    return f'<div class="pr-text">{"".join(out)}</div>'
