"""Shared helpers for component HTML templates."""
import json

# Characters that could end a <script> block early or start markup, written as JSON escapes.
SCRIPT_UNSAFE = {"<": "\\u003c", ">": "\\u003e", "&": "\\u0026"}


def embed(value):
    """JSON text that is safe inside a <script> block: no < > & can appear in it."""
    text = json.dumps(value)
    for char, escaped in SCRIPT_UNSAFE.items():
        text = text.replace(char, escaped)
    return text


def fill(html_text, data=None, **placeholders):
    """Fill a component template with placeholders and optional DATA payload."""
    page = html_text
    for placeholder, text in placeholders.items():
        page = page.replace(placeholder, text)
    if data is None:
        return page
    data_text = embed(data)
    marker = "const DATA = __DATA__;"
    if marker in page:
        return page.replace(marker, f"const DATA = {data_text};", 1)
    return page.replace("__DATA__", data_text)
