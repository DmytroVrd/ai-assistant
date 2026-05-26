from __future__ import annotations

import re
from html import escape


_BOLD_PATTERN = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)


def telegram_html_from_markdown(text: str) -> str:
    escaped = escape(text, quote=False)
    return _BOLD_PATTERN.sub(r"<b>\1</b>", escaped)
