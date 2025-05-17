#!/usr/bin/env python3
"""Render Markdown file to HTML.

Tries to use the `markdown` library if available; otherwise falls back to a
minimal HTML representation.
"""

from __future__ import annotations
import html
import sys
from pathlib import Path


_DEF_PATH = 'README.md'


def simple_render(text: str) -> str:
    """Return text wrapped in <pre> as a fallback."""
    return f"<pre>{html.escape(text)}</pre>"


def render_markdown(path: Path) -> str:
    text = path.read_text(encoding='utf-8')
    try:
        import markdown  # type: ignore
    except Exception:
        return simple_render(text)
    else:
        return markdown.markdown(text)


if __name__ == '__main__':
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(_DEF_PATH)
    sys.stdout.write(render_markdown(target))
