"""
notion_sync.py — sync iOS Core Knowledge Tree content/ to Notion.

No external dependencies; uses only stdlib (urllib.request).
"""

import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Inline markdown → Notion rich_text objects
# ---------------------------------------------------------------------------

def _rt(content, *, bold=False, italic=False, code=False, link=None):
    return {
        "type": "text",
        "text": {"content": content, "link": {"url": link} if link else None},
        "annotations": {
            "bold": bold,
            "italic": italic,
            "code": code,
            "strikethrough": False,
            "underline": False,
            "color": "default",
        },
    }


_INLINE_RE = re.compile(
    r"(\*\*\*(?P<bolditalic>.+?)\*\*\*)"
    r"|(\*\*(?P<bold>.+?)\*\*)"
    r"|(\*(?P<italic>.+?)\*)"
    r"|(`(?P<code>[^`]+?)`)"
    r"|(\[(?P<ltext>[^\]]+)\]\((?P<lurl>[^)]+)\))",
    re.DOTALL,
)


def parse_inline(text: str) -> list[dict]:
    """Convert inline markdown to Notion rich_text list."""
    result = []
    pos = 0
    for m in _INLINE_RE.finditer(text):
        if m.start() > pos:
            plain = text[pos:m.start()]
            if plain:
                result.append(_rt(plain))
        if m.group("bolditalic") is not None:
            result.append(_rt(m.group("bolditalic"), bold=True, italic=True))
        elif m.group("bold") is not None:
            result.append(_rt(m.group("bold"), bold=True))
        elif m.group("italic") is not None:
            result.append(_rt(m.group("italic"), italic=True))
        elif m.group("code") is not None:
            result.append(_rt(m.group("code"), code=True))
        elif m.group("ltext") is not None:
            result.append(_rt(m.group("ltext"), link=m.group("lurl")))
        pos = m.end()
    if pos < len(text):
        tail = text[pos:]
        if tail:
            result.append(_rt(tail))
    return result or [_rt("")]


# ---------------------------------------------------------------------------
# Markdown → Notion blocks
# ---------------------------------------------------------------------------

def _heading(level, text):
    htype = {1: "heading_1", 2: "heading_2"}.get(level, "heading_3")
    return {
        "object": "block",
        "type": htype,
        htype: {"rich_text": parse_inline(text)},
    }


def _paragraph(text):
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": parse_inline(text)},
    }


def _bullet(text):
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": parse_inline(text)},
    }


def _numbered(text):
    return {
        "object": "block",
        "type": "numbered_list_item",
        "numbered_list_item": {"rich_text": parse_inline(text)},
    }


def _code(text, language="swift"):
    return {
        "object": "block",
        "type": "code",
        "code": {
            "rich_text": [_rt(text)],
            "language": language,
        },
    }


def _divider():
    return {"object": "block", "type": "divider", "divider": {}}


def _table_block(rows):
    """Convert a list of row-lists (strings) into a Notion table block."""
    if not rows:
        return None
    col_count = max(len(r) for r in rows)
    table_rows = []
    for row in rows:
        cells = []
        for i in range(col_count):
            cell_text = row[i].strip() if i < len(row) else ""
            cells.append(parse_inline(cell_text))
        table_rows.append({
            "object": "block",
            "type": "table_row",
            "table_row": {"cells": cells},
        })
    return {
        "object": "block",
        "type": "table",
        "table": {
            "table_width": col_count,
            "has_column_header": True,
            "has_row_header": False,
            "children": table_rows,
        },
    }


def _is_separator_row(cells):
    return all(re.fullmatch(r"[-: ]+", c.strip()) for c in cells if c.strip())


def _parse_table_row(line):
    line = line.strip().strip("|")
    return [c.strip() for c in line.split("|")]


def md_to_notion_blocks(text: str) -> list[dict]:
    """Convert markdown text to a list of Notion block dicts."""
    blocks = []
    lines = text.splitlines()
    in_code_block = False
    code_lang = "swift"
    code_lines = []
    in_ul = False
    in_ol = False
    table_buffer = []  # list of row-lists

    def flush_table():
        nonlocal table_buffer
        if not table_buffer:
            return
        tbl = _table_block(table_buffer)
        if tbl:
            blocks.append(tbl)
        table_buffer = []

    for line in lines:
        # ── Code block ──────────────────────────────────────────────────────
        if in_code_block:
            if line.rstrip() == "```" or line.rstrip().startswith("```") and line.rstrip().count("```") > 1:
                # closing fence
                in_code_block = False
                blocks.append(_code("\n".join(code_lines), language=code_lang))
                code_lines = []
            else:
                code_lines.append(line)
            continue

        fence_match = re.match(r"^```(\w*)$", line.rstrip())
        if fence_match:
            flush_table()
            in_ul = in_ol = False
            in_code_block = True
            code_lang = fence_match.group(1) or "plain text"
            code_lines = []
            continue

        # ── Table ───────────────────────────────────────────────────────────
        if line.lstrip().startswith("|"):
            in_ul = in_ol = False
            row = _parse_table_row(line)
            if _is_separator_row(row):
                continue  # skip separator row
            table_buffer.append(row)
            continue
        else:
            if table_buffer:
                flush_table()

        # ── Headings ────────────────────────────────────────────────────────
        h_match = re.match(r"^(#{1,6})\s+(.*)", line)
        if h_match:
            in_ul = in_ol = False
            level = len(h_match.group(1))
            blocks.append(_heading(level, h_match.group(2).strip()))
            continue

        # ── Divider ─────────────────────────────────────────────────────────
        if re.match(r"^-{3,}$", line.strip()):
            in_ul = in_ol = False
            blocks.append(_divider())
            continue

        # ── Unordered list ──────────────────────────────────────────────────
        ul_match = re.match(r"^[-*]\s+(.*)", line)
        if ul_match:
            in_ol = False
            in_ul = True
            blocks.append(_bullet(ul_match.group(1)))
            continue

        # ── Ordered list ────────────────────────────────────────────────────
        ol_match = re.match(r"^\d+\.\s+(.*)", line)
        if ol_match:
            in_ul = False
            in_ol = True
            blocks.append(_numbered(ol_match.group(1)))
            continue

        # ── Blank line ──────────────────────────────────────────────────────
        if not line.strip():
            in_ul = in_ol = False
            continue

        # ── Paragraph ───────────────────────────────────────────────────────
        in_ul = in_ol = False
        blocks.append(_paragraph(line))

    # Close any open code block
    if in_code_block and code_lines:
        blocks.append(_code("\n".join(code_lines), language=code_lang))

    flush_table()

    return blocks


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

class RateLimiter:
    """Sliding window rate limiter: max `limit` requests per `window` seconds."""

    def __init__(self, limit=3, window=1.0):
        self.limit = limit
        self.window = window
        self._times: list[float] = []

    def acquire(self):
        now = time.monotonic()
        # Drop entries outside the window
        self._times = [t for t in self._times if now - t < self.window]
        if len(self._times) >= self.limit:
            oldest = self._times[0]
            sleep_for = self.window - (now - oldest) + 0.01
            if sleep_for > 0:
                time.sleep(sleep_for)
            now = time.monotonic()
            self._times = [t for t in self._times if now - t < self.window]
        self._times.append(time.monotonic())


# ---------------------------------------------------------------------------
# Notion API client
# ---------------------------------------------------------------------------

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


class NotionClient:
    def __init__(self, token: str):
        self.token = token
        self.rl = RateLimiter(limit=3, window=1.0)

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }

    def _request(self, method, path, body=None, retry=3):
        self.rl.acquire()
        url = NOTION_API + path
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, headers=self._headers(), method=method)
        for attempt in range(retry):
            try:
                with urllib.request.urlopen(req) as resp:
                    return json.loads(resp.read().decode())
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    wait = int(e.headers.get("Retry-After", "2"))
                    time.sleep(wait)
                    self.rl.acquire()
                    continue
                raise
        raise RuntimeError(f"Request failed after {retry} attempts: {method} {path}")

    def create_page(self, parent_id: str, title: str) -> str:
        body = {
            "parent": {"type": "page_id", "page_id": parent_id},
            "properties": {
                "title": {"title": [_rt(title)]}
            },
        }
        result = self._request("POST", "/pages", body)
        return result["id"]

    def get_block_children(self, block_id: str) -> list[dict]:
        children = []
        cursor = None
        while True:
            path = f"/blocks/{block_id}/children?page_size=100"
            if cursor:
                path += f"&start_cursor={cursor}"
            result = self._request("GET", path)
            children.extend(result.get("results", []))
            if not result.get("has_more"):
                break
            cursor = result.get("next_cursor")
        return children

    def delete_block(self, block_id: str):
        self._request("DELETE", f"/blocks/{block_id}")

    def append_blocks(self, block_id: str, blocks: list[dict]):
        """Append blocks in chunks of 100 (Notion API limit)."""
        chunk_size = 100
        for i in range(0, len(blocks), chunk_size):
            chunk = blocks[i:i + chunk_size]
            self._request("PATCH", f"/blocks/{block_id}/children", {"children": chunk})

    def update_page_title(self, page_id: str, title: str):
        body = {
            "properties": {
                "title": {"title": [_rt(title)]}
            }
        }
        self._request("PATCH", f"/pages/{page_id}", body)


# ---------------------------------------------------------------------------
# Sync orchestration
# ---------------------------------------------------------------------------

def _section_dir_to_label(slug: str) -> str:
    parts = slug.split("-", 1)
    if len(parts) == 2:
        return parts[1].replace("-", " ").title()
    return slug.replace("-", " ").title()


def sync_all(
    token: str,
    parent_page_id: str,
    content_dir: Path,
    map_file: Path,
    progress_callback,
):
    """
    Walk content/ and sync each section + its topics to Notion.

    progress_callback(event_dict) is called for each progress event.
    Event types: start, section_start, topic_done, section_done, done, error
    """
    client = NotionClient(token)

    # Load idempotency map
    notion_map: dict = {}
    if map_file.exists():
        try:
            notion_map = json.loads(map_file.read_text())
        except Exception:
            notion_map = {}

    def save_map():
        map_file.write_text(json.dumps(notion_map, indent=2))

    section_dirs = sorted(d for d in content_dir.iterdir() if d.is_dir())
    progress_callback({"type": "start", "total_sections": len(section_dirs)})

    total_topics = 0
    total_errors = 0

    for section_dir in section_dirs:
        slug = section_dir.name
        label = _section_dir_to_label(slug)
        progress_callback({"type": "section_start", "slug": slug, "label": label})

        try:
            # Create or reuse section page
            section_key = f"section:{slug}"
            if section_key in notion_map:
                section_page_id = notion_map[section_key]
            else:
                section_page_id = client.create_page(parent_page_id, label)
                notion_map[section_key] = section_page_id
                save_map()

            # Sync index.md onto the section page itself
            index_md = section_dir / "index.md"
            if index_md.exists():
                _replace_page_content(client, section_page_id, index_md.read_text())

            # Sync topic files
            topic_count = 0
            md_files = sorted(f for f in section_dir.glob("*.md") if f.name != "index.md")
            for md_file in md_files:
                topic_slug = md_file.stem
                topic_key = f"topic:{slug}/{topic_slug}"
                try:
                    if topic_key in notion_map:
                        topic_page_id = notion_map[topic_key]
                    else:
                        topic_title = topic_slug.replace("-", " ").title()
                        topic_page_id = client.create_page(section_page_id, topic_title)
                        notion_map[topic_key] = topic_page_id
                        save_map()

                    _replace_page_content(client, topic_page_id, md_file.read_text())
                    topic_count += 1
                    total_topics += 1
                    progress_callback({
                        "type": "topic_done",
                        "slug": slug,
                        "topic": topic_slug,
                        "count": topic_count,
                    })
                except Exception as exc:
                    total_errors += 1
                    progress_callback({
                        "type": "error",
                        "slug": slug,
                        "topic": topic_slug,
                        "message": str(exc),
                    })

            save_map()
            progress_callback({
                "type": "section_done",
                "slug": slug,
                "label": label,
                "topic_count": topic_count,
            })

        except Exception as exc:
            total_errors += 1
            progress_callback({
                "type": "error",
                "slug": slug,
                "message": str(exc),
            })

    progress_callback({
        "type": "done",
        "total_topics": total_topics,
        "total_errors": total_errors,
    })


def _replace_page_content(client: NotionClient, page_id: str, md_text: str):
    """Delete all existing blocks on a page, then append new blocks."""
    existing = client.get_block_children(page_id)
    for blk in existing:
        try:
            client.delete_block(blk["id"])
        except Exception:
            pass  # best-effort deletion

    blocks = md_to_notion_blocks(md_text)
    if blocks:
        client.append_blocks(page_id, blocks)
