"""Tiny markdown -> HTML for showing a filed note (no extra dependency). Handles headings, lists,
checkboxes, bold/italic/code, fenced code, and [[wikilinks]] (resolved ones become links)."""
from __future__ import annotations

import html
import re
from urllib.parse import quote

from c2v.vault import Vault

WIKI = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]*))?\]\]")


def _inline(s: str, vault: Vault) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![*\w])\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)

    def wl(m: re.Match) -> str:
        target, label = m.group(1).strip(), (m.group(2) or m.group(1)).strip()
        if vault.resolve(target):
            return f'<a class="wl" href="#" data-title="{quote(target)}">{label}</a>'
        return f'<span class="wl broken" title="does not resolve">{label}</span>'

    return WIKI.sub(wl, s)


def render_note(body: str, vault: Vault) -> str:
    out: list[str] = []
    in_list = in_code = False
    para: list[str] = []

    def flush():
        nonlocal in_list
        if para:
            out.append("<p>" + " ".join(para) + "</p>")
            para.clear()
        if in_list:
            out.append("</ul>")
            in_list = False

    for line in body.splitlines():
        if line.strip().startswith("```"):
            flush()
            out.append("</code></pre>" if in_code else "<pre><code>")
            in_code = not in_code
            continue
        if in_code:
            out.append(html.escape(line) + "\n")
            continue
        h = re.match(r"(#{1,6})\s+(.*)", line)
        li = re.match(r"\s*[-*+]\s+(\[[ xX]\]\s+)?(.*)", line)
        if h:
            flush()
            n = len(h.group(1))
            out.append(f"<h{n}>{_inline(h.group(2), vault)}</h{n}>")
        elif li:
            if para:
                out.append("<p>" + " ".join(para) + "</p>")
                para.clear()
            if not in_list:
                out.append("<ul>")
                in_list = True
            box = ""
            if li.group(1):
                box = '<input type="checkbox" disabled{}> '.format(
                    " checked" if "x" in li.group(1).lower() else "")
            out.append(f"<li>{box}{_inline(li.group(2), vault)}</li>")
        elif not line.strip():
            flush()
        else:
            if in_list:
                out.append("</ul>")
                in_list = False
            para.append(_inline(line, vault))
    flush()
    if in_code:
        out.append("</code></pre>")
    return "\n".join(out)
