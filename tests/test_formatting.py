from formatting import telegram_html_from_markdown


def test_converts_markdown_bold_to_telegram_html() -> None:
    text = "**Background**\n- **Full name:** Dmytro"

    assert telegram_html_from_markdown(text) == "<b>Background</b>\n- <b>Full name:</b> Dmytro"


def test_escapes_html_like_user_content() -> None:
    text = "Use <script> safely & keep **bold**."

    assert telegram_html_from_markdown(text) == "Use &lt;script&gt; safely &amp; keep <b>bold</b>."
