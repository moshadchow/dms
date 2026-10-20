"""Convert existing memo bodies from Markdown to HTML

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-08-24 00:00:00.000000
"""

import re
import html as html_lib
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_likely_markdown(body: str) -> bool:
    """Heuristic to detect if a body string is raw Markdown (not HTML)."""
    if not body:
        return False
    # If it contains HTML block tags, it's likely already HTML
    if re.search(r"<(p|div|h[1-6]|ul|ol|li|blockquote|pre|table|br)\b", body, re.IGNORECASE):
        return False
    # If it contains markdown patterns, it's likely Markdown
    if re.search(r"^#{1,6}\s+", body, re.MULTILINE):
        return True
    if re.search(r"\*\*[^*]+\*\*", body):
        return True
    if re.search(r"^\s*[-*+]\s+", body, re.MULTILINE):
        return True
    if re.search(r"^\s*\d+[.)]\s+", body, re.MULTILINE):
        return True
    if re.search(r"^>\s?", body, re.MULTILINE):
        return True
    if "```" in body:
        return True
    return False


def _render_markdown(body: str) -> str:
    """Convert a limited markdown-style body to an HTML fragment.

    Supports: headings, bold/italic, inline code, fenced code blocks,
    unordered/ordered lists, blockquotes, and links. All text is HTML-escaped.
    """
    if not body:
        return "<p></p>"

    lines = body.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    i = 0

    def inline(text: str) -> str:
        text = re.sub(
            r"`([^`]+)`",
            lambda m: f"<code>{html_lib.escape(m.group(1))}</code>",
            text,
        )
        text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<em>\1</em>", text)
        text = re.sub(
            r"\[([^\]]+)\]\(([^)\s]+)\)",
            lambda m: f'<a href="{html_lib.escape(m.group(2), quote=True)}" target="_blank" rel="noopener noreferrer">{html_lib.escape(m.group(1))}</a>',
            text,
        )
        return text

    def para(text: str) -> str:
        return f"<p>{inline(html_lib.escape(text))}</p>"

    heading_re = re.compile(r"^(#{1,6})\s+(.*)$")
    unordered_re = re.compile(r"^\s*[-*+]\s+(.*)$")
    ordered_re = re.compile(r"^\s*\d+[.)]\s+(.*)$")
    blockquote_re = re.compile(r"^\s*>\s?(.*)$")

    while i < len(lines):
        line = lines[i]

        if line.strip().startswith("```"):
            code_lines: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1
            out.append(
                "<pre><code>" + html_lib.escape("\n".join(code_lines)) + "</code></pre>"
            )
            continue

        m = heading_re.match(line)
        if m:
            level = len(m.group(1))
            out.append(f"<h{level}>{inline(html_lib.escape(m.group(2).strip()))}</h{level}>")
            i += 1
            continue

        m = blockquote_re.match(line)
        if m:
            quote_lines: list[str] = []
            while i < len(lines):
                qm = blockquote_re.match(lines[i])
                if not qm:
                    break
                quote_lines.append(qm.group(1))
                i += 1
            inner = " ".join(html_lib.escape(x.strip()) for x in quote_lines)
            out.append(f"<blockquote>{inline(inner)}</blockquote>")
            continue

        m = unordered_re.match(line)
        if m:
            items: list[str] = []
            while i < len(lines):
                lm = unordered_re.match(lines[i])
                if not lm:
                    break
                items.append(inline(html_lib.escape(lm.group(1).strip())))
                i += 1
            out.append("<ul>" + "".join(f"<li>{item}</li>" for item in items) + "</ul>")
            continue

        m = ordered_re.match(line)
        if m:
            items: list[str] = []
            while i < len(lines):
                lm = ordered_re.match(lines[i])
                if not lm:
                    break
                items.append(inline(html_lib.escape(lm.group(1).strip())))
                i += 1
            out.append("<ol>" + "".join(f"<li>{item}</li>" for item in items) + "</ol>")
            continue

        if not line.strip():
            i += 1
            continue

        para_lines: list[str] = [line]
        i += 1
        while i < len(lines) and lines[i].strip() and not heading_re.match(lines[i]):
            para_lines.append(lines[i])
            i += 1
        out.append(para(" ".join(x.strip() for x in para_lines)))

    return "\n".join(out) or "<p></p>"


def upgrade() -> None:
    """Convert existing Markdown memo bodies to HTML."""
    conn = op.get_bind()
    result = conn.execute(sa.text("SELECT id, body FROM memos WHERE body IS NOT NULL AND body != ''"))

    converted = 0
    for row in result:
        memo_id = row[0]
        body = row[1]
        if _is_likely_markdown(body):
            html_body = _render_markdown(body)
            conn.execute(
                sa.text("UPDATE memos SET body = :body WHERE id = :id"),
                {"body": html_body, "id": memo_id},
            )
            converted += 1

    print(f"Converted {converted} memo bodies from Markdown to HTML")


def downgrade() -> None:
    """No safe downgrade - HTML cannot be reliably converted back to Markdown."""
    print("WARNING: Downgrade not supported - HTML bodies cannot be converted back to Markdown")
