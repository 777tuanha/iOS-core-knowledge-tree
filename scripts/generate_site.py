#!/usr/bin/env python3
"""
iOS Core Knowledge Tree — Static Site Generator
Usage: python3 scripts/generate_site.py
Requires: Python 3.6+, stdlib only (no pip installs needed)
"""

import os
import re
import shutil
import sys
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent.parent
CONTENT_DIR = ROOT / "content"
TEMPLATES_DIR = ROOT / "templates"
COMPONENTS_DIR = ROOT / "components"
ASSETS_DIR = ROOT / "assets"
SITE_DIR = ROOT / "site"

# ── Minimal Markdown → HTML converter (stdlib only) ───────────────────────

def md_to_html(text: str) -> str:
    """Convert a Markdown string to HTML using regex. Handles the subset
    used in the knowledge-tree content format."""

    lines = text.split("\n")
    html_lines = []
    in_code_block = False
    in_ul = False
    in_ol = False
    code_lang = ""
    code_lines: list[str] = []

    def close_list():
        nonlocal in_ul, in_ol
        if in_ul:
            html_lines.append("</ul>")
            in_ul = False
        if in_ol:
            html_lines.append("</ol>")
            in_ol = False

    def flush_code():
        nonlocal in_code_block, code_lines, code_lang
        escaped = "\n".join(
            line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            for line in code_lines
        )
        cls = f' class="language-{code_lang}"' if code_lang else ""
        html_lines.append(f"<pre><code{cls}>{escaped}</code></pre>")
        in_code_block = False
        code_lines = []
        code_lang = ""

    for line in lines:
        # Code fence
        if line.startswith("```"):
            if in_code_block:
                flush_code()
            else:
                close_list()
                in_code_block = True
                code_lang = line[3:].strip()
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        # Headings
        heading_match = re.match(r"^(#{1,6})\s+(.*)", line)
        if heading_match:
            close_list()
            level = len(heading_match.group(1))
            content = inline_md(heading_match.group(2))
            slug = re.sub(r"[^\w\-]", "", heading_match.group(2).lower().replace(" ", "-"))
            html_lines.append(f"<h{level} id=\"{slug}\">{content}</h{level}>")
            continue

        # Horizontal rule
        if re.match(r"^-{3,}$|^\*{3,}$|^_{3,}$", line.strip()):
            close_list()
            html_lines.append("<hr>")
            continue

        # Unordered list
        ul_match = re.match(r"^[-*+]\s+(.*)", line)
        if ul_match:
            if in_ol:
                close_list()
            if not in_ul:
                html_lines.append("<ul>")
                in_ul = True
            html_lines.append(f"<li>{inline_md(ul_match.group(1))}</li>")
            continue

        # Ordered list
        ol_match = re.match(r"^\d+\.\s+(.*)", line)
        if ol_match:
            if in_ul:
                close_list()
            if not in_ol:
                html_lines.append("<ol>")
                in_ol = True
            html_lines.append(f"<li>{inline_md(ol_match.group(1))}</li>")
            continue

        # Table row (simple — | col | col |)
        if line.strip().startswith("|") and line.strip().endswith("|"):
            cells = [c.strip() for c in line.strip()[1:-1].split("|")]
            # Separator row
            if all(re.match(r"^:?-+:?$", c) for c in cells):
                continue
            cells_html = "".join(f"<td>{inline_md(c)}</td>" for c in cells)
            html_lines.append(f"<tr>{cells_html}</tr>")
            continue

        # Close any open list before a blank or paragraph line
        close_list()

        # Blank line
        if line.strip() == "":
            html_lines.append("")
            continue

        # Paragraph
        html_lines.append(f"<p>{inline_md(line)}</p>")

    # Flush any remaining open elements
    close_list()
    if in_code_block:
        flush_code()

    # Wrap consecutive <tr> rows in a <table>
    raw = "\n".join(html_lines)
    raw = re.sub(
        r"(<tr>.*?</tr>(\n<tr>.*?</tr>)*)",
        lambda m: "<table>\n" + m.group(0) + "\n</table>",
        raw,
        flags=re.DOTALL,
    )

    return raw


def inline_md(text: str) -> str:
    """Convert inline Markdown (bold, italic, code, links) to HTML."""
    # Escape HTML entities first (except in code spans — handled separately)
    parts = re.split(r"(`[^`]+`)", text)
    result = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            # inline code span
            inner = part[1:-1].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            result.append(f"<code>{inner}</code>")
        else:
            p = part.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            # Bold + italic ***text***
            p = re.sub(r"\*\*\*(.*?)\*\*\*", r"<strong><em>\1</em></strong>", p)
            # Bold **text**
            p = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", p)
            # Italic *text*
            p = re.sub(r"\*(.*?)\*", r"<em>\1</em>", p)
            # Links [text](url)
            p = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', p)
            result.append(p)
    return "".join(result)


# ── Component loader ───────────────────────────────────────────────────────

def load_component(name: str) -> str:
    path = COMPONENTS_DIR / name
    return path.read_text(encoding="utf-8")


def load_template(name: str) -> str:
    path = TEMPLATES_DIR / name
    return path.read_text(encoding="utf-8")


# ── Build helpers ──────────────────────────────────────────────────────────

def depth_root(output_path: Path) -> str:
    """Return a relative path prefix to the site root from output_path."""
    rel = output_path.relative_to(SITE_DIR)
    depth = len(rel.parts) - 1  # minus filename
    return ("../" * depth) if depth > 0 else ""


def make_breadcrumb(md_path: Path) -> str:
    """Generate breadcrumb HTML for a content file."""
    parts = md_path.relative_to(CONTENT_DIR).parts  # e.g. ('01-swift-language', 'value-vs-reference.md')
    crumbs = ['<span><a href="{root}index.html">Home</a></span>']
    if len(parts) > 1:
        section_dir = parts[0]
        section_label = section_dir_to_label(section_dir)
        crumbs.append(f'<span><a href="{{root}}{section_dir}/index.html">{section_label}</a></span>')
    if len(parts) > 1 and parts[-1] != "index.md":
        label = stem_to_label(Path(parts[-1]).stem)
        crumbs.append(f"<span>{label}</span>")
    return "\n    ".join(crumbs)


def section_dir_to_label(dirname: str) -> str:
    """'01-swift-language' → 'Swift Language'"""
    name = re.sub(r"^\d+-", "", dirname)
    return name.replace("-", " ").title()


def stem_to_label(stem: str) -> str:
    """'value-vs-reference' → 'Value vs Reference'"""
    return stem.replace("-", " ").title()


def extract_title(md_text: str) -> str:
    """Extract first H1 from Markdown or return a fallback."""
    match = re.search(r"^#\s+(.+)", md_text, re.MULTILINE)
    return match.group(1) if match else "Untitled"


def build_nav(root_prefix: str, active_section: str = "") -> str:
    nav = load_component("navigation.html")
    nav = nav.replace("{{root}}", root_prefix)
    # Mark the active section link
    if active_section:
        active_href = f'{root_prefix}{active_section}/index.html'
        nav = nav.replace(f'href="{active_href}"', f'href="{active_href}" class="active"')
    return nav


def build_header(root_prefix: str, breadcrumb_html: str) -> str:
    header = load_component("header.html")
    header = header.replace("{{root}}", root_prefix)
    header = header.replace("{{breadcrumb}}", breadcrumb_html)
    return header


def build_footer(root_prefix: str) -> str:
    footer = load_component("footer.html")
    footer = footer.replace("{{root}}", root_prefix)
    return footer


def render_topic_page(md_path: Path, output_path: Path) -> None:
    md_text = md_path.read_text(encoding="utf-8")
    title = extract_title(md_text)
    content_html = md_to_html(md_text)

    root = depth_root(output_path)
    section_dir = md_path.parent.name

    template = load_template("topic.html")
    page = template
    page = page.replace("{{title}}", title)
    page = page.replace("{{root}}", root)
    page = page.replace("{{content}}", content_html)
    page = page.replace("{{nav}}", build_nav(root, section_dir))
    page = page.replace("{{header}}", build_header(root, make_breadcrumb(md_path).replace("{root}", root)))
    page = page.replace("{{footer}}", build_footer(root))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(page, encoding="utf-8")
    print(f"  [page]    {output_path.relative_to(SITE_DIR)}")


def render_section_index(md_path: Path, output_path: Path, topic_files: list[Path]) -> None:
    md_text = md_path.read_text(encoding="utf-8")
    title = extract_title(md_text)

    # Build the description from the overview paragraph (first non-heading paragraph)
    desc_match = re.search(r"^## Overview\n+(.*?)(?=\n## |\Z)", md_text, re.DOTALL | re.MULTILINE)
    description = inline_md(desc_match.group(1).strip()) if desc_match else ""

    root = depth_root(output_path)
    section_dir = md_path.parent.name

    # Build topic links
    links_html = ""
    for tf in sorted(topic_files):
        if tf.name == "index.md":
            continue
        tf_text = tf.read_text(encoding="utf-8")
        tf_title = extract_title(tf_text)
        href = tf.stem + ".html"
        links_html += f'<li><a href="{href}">{tf_title}</a></li>\n        '

    template = load_template("section.html")
    page = template
    page = page.replace("{{title}}", title)
    page = page.replace("{{description}}", description)
    page = page.replace("{{root}}", root)
    page = page.replace("{{topic_links}}", links_html)
    page = page.replace("{{nav}}", build_nav(root, section_dir))
    page = page.replace("{{header}}", build_header(root, make_breadcrumb(md_path).replace("{root}", root)))
    page = page.replace("{{footer}}", build_footer(root))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(page, encoding="utf-8")
    print(f"  [section] {output_path.relative_to(SITE_DIR)}")


def render_site_index(sections: list[tuple[str, str]]) -> None:
    """Generate site/index.html listing all sections."""
    root = ""
    nav = build_nav(root)
    header = build_header(root, '<span><a href="index.html">Home</a></span>')
    footer = build_footer(root)

    section_items = "\n".join(
        f'<li><a href="{slug}/index.html">{label}</a></li>'
        for slug, label in sections
    )

    notion_sync_ui = """\
<div class="notion-sync-container">
  <button id="notion-sync-btn" class="btn-notion-sync" type="button">Sync to Notion</button>
  <div id="notion-sync-panel" hidden></div>
</div>"""

    content = f"""<h1>iOS Core Knowledge Tree</h1>
<p>A structured reference for senior iOS engineers covering Swift, architecture, performance, and more.</p>
{notion_sync_ui}
<h2>All Sections</h2>
<ul class="topic-list">
{section_items}
</ul>"""

    template = load_template("topic.html")
    page = template
    page = page.replace("{{title}}", "iOS Core Knowledge Tree")
    page = page.replace("{{root}}", root)
    page = page.replace("{{content}}", content)
    page = page.replace("{{nav}}", nav)
    page = page.replace("{{header}}", header)
    page = page.replace("{{footer}}", footer)
    page = page.replace("</body>", '<script src="assets/notion-sync.js"></script>\n</body>')

    (SITE_DIR / "index.html").write_text(page, encoding="utf-8")
    print(f"  [index]   index.html")


# ── Main build ─────────────────────────────────────────────────────────────

def build():
    print("=== iOS Knowledge Tree — Site Generator ===\n")

    # Clean and recreate site/
    if SITE_DIR.exists():
        shutil.rmtree(SITE_DIR)
    SITE_DIR.mkdir()
    print(f"Cleaned: {SITE_DIR}\n")

    # Copy assets
    dest_assets = SITE_DIR / "assets"
    shutil.copytree(ASSETS_DIR, dest_assets)
    print(f"Copied assets → site/assets/\n")

    # Walk content/ and collect section info
    sections: list[tuple[str, str]] = []  # (slug, label)

    if not CONTENT_DIR.exists():
        print("ERROR: content/ directory not found. Aborting.")
        sys.exit(1)

    for section_dir in sorted(CONTENT_DIR.iterdir()):
        if not section_dir.is_dir():
            continue

        slug = section_dir.name
        label = section_dir_to_label(slug)
        sections.append((slug, label))
        print(f"Building section: {label} ({slug})")

        md_files = sorted(section_dir.glob("*.md"))
        index_md = section_dir / "index.md"

        for md_file in md_files:
            out_html = SITE_DIR / slug / (md_file.stem + ".html")
            if md_file.name == "index.md":
                render_section_index(md_file, out_html, md_files)
            else:
                render_topic_page(md_file, out_html)

        print()

    # Site root index
    print("Building site index...")
    render_site_index(sections)

    print(f"\n=== Build complete → {SITE_DIR} ===")


if __name__ == "__main__":
    build()
