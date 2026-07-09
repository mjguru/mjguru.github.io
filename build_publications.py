#!/usr/bin/env python3
"""
Generate publications.html from papers.bib and coauthors.yml.

No dependencies: this uses only the Python standard library.

Behavior:
  - Coauthor names are linked using coauthors.yml when possible.
  - Your name is bolded.
  - Paper titles are clickable.
  - Title link preference: html/arXiv page first, then pdf, then eprint-derived arXiv URL.
  - DOI and arXiv are NOT shown as separate visible links.
  - html/pdf/url/eprint/doi fields are NOT shown as separate visible links.

Usage:
  python3 build_publications_no_deps.py

Input files, in the same folder:
  papers.bib
  coauthors.yml

Output:
  publications.html
"""

from __future__ import annotations

import ast
import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BIB_FILE = ROOT / "papers.bib"
COAUTHORS_FILE = ROOT / "coauthors.yml"
OUTPUT_FILE = ROOT / "publications.html"
YOUR_NAME = "Mohit Gurumukhani"


LATEX_REPLACEMENTS = {
    r'{\"{u}}': "ü",
    r'{\"u}': "ü",
    r'\"{u}': "ü",
    r'\"u': "ü",

    r"{\'{a}}": "á",
    r"{\'a}": "á",
    r"\'{a}": "á",
    r"\'a": "á",

    r"\&": "&",
    r"\%": "%",
    r"\_": "_",
}




def clean_latex(s: str) -> str:
    """Small LaTeX-to-text cleaner tuned for this bibliography."""
    s = str(s).strip()
    for old, new in LATEX_REPLACEMENTS.items():
        s = s.replace(old, new)

    # Common math/text cleanup appearing in this .bib file.
    s = s.replace(r"\({F}_{\mbox{2}}\)", "F₂")
    s = s.replace(r"{F}_{\mbox{2}}", "F₂")
    s = s.replace(r"\mbox{2}", "2")

    # Remove remaining simple TeX commands but keep their contents.
    s = re.sub(r"\\[a-zA-Z]+\s*\{([^{}]*)\}", r"\1", s)
    s = s.replace("\\", "")

    # Remove braces used only for BibTeX capitalization/protection.
    s = s.replace("{", "").replace("}", "")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def split_bibtex_entries(text: str) -> list[str]:
    """Split a BibTeX file into raw entries."""
    entries: list[str] = []
    i = 0
    while True:
        start = text.find("@", i)
        if start == -1:
            break

        brace = text.find("{", start)
        if brace == -1:
            break

        depth = 0
        j = brace
        while j < len(text):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    entries.append(text[start : j + 1])
                    i = j + 1
                    break
            j += 1
        else:
            break

    return entries


def parse_bibtex_entry(entry: str) -> dict[str, str]:
    """Parse one BibTeX entry into a dictionary."""
    m = re.match(r"@(\w+)\s*\{\s*([^,]+),", entry, re.S)
    if not m:
        return {}

    entry_type, key = m.group(1), m.group(2).strip()
    pos = m.end()
    fields: dict[str, str] = {"entrytype": entry_type, "key": key}

    while pos < len(entry):
        while pos < len(entry) and entry[pos] in " \n\t\r,":
            pos += 1
        if pos >= len(entry) or entry[pos] == "}":
            break

        name_match = re.match(r"([A-Za-z][A-Za-z0-9_-]*)\s*=\s*", entry[pos:])
        if not name_match:
            break

        field_name = name_match.group(1).lower()
        pos += name_match.end()

        if pos < len(entry) and entry[pos] == "{":
            pos += 1
            depth = 1
            value_start = pos
            while pos < len(entry) and depth > 0:
                if entry[pos] == "{":
                    depth += 1
                elif entry[pos] == "}":
                    depth -= 1
                pos += 1
            value = entry[value_start : pos - 1]
        elif pos < len(entry) and entry[pos] == '"':
            pos += 1
            value_start = pos
            while pos < len(entry) and entry[pos] != '"':
                pos += 1
            value = entry[value_start:pos]
            pos += 1
        else:
            value_start = pos
            while pos < len(entry) and entry[pos] not in ",}\n":
                pos += 1
            value = entry[value_start:pos]

        fields[field_name] = value.strip()

    return fields


def load_coauthor_urls(path: Path) -> dict[tuple[str, str], str]:
    """
    Load the simple coauthors.yml format without PyYAML.

    Expected format:

    "Last":
      - firstname: ["First", "Other First"]
        url: https://example.com/
    """
    urls: dict[tuple[str, str], str] = {}
    current_last: str | None = None
    current_firstnames: list[str] = []

    def add_current(url: str | None) -> None:
        if not current_last or not url:
            return
        for first in current_firstnames:
            urls[(clean_latex(first), clean_latex(current_last))] = url.strip()

    if not path.exists():
        return urls

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        # Top-level key: "Last": or Last:
        if not raw_line.startswith(" ") and line.endswith(":"):
            current_last = line[:-1].strip().strip('"').strip("'")
            current_firstnames = []
            continue

        if "firstname:" in line:
            value = line.split("firstname:", 1)[1].strip()
            try:
                parsed = ast.literal_eval(value)
                if isinstance(parsed, list):
                    current_firstnames = [str(x) for x in parsed]
                else:
                    current_firstnames = [str(parsed)]
            except Exception:
                current_firstnames = [value.strip().strip('"').strip("'")]
            continue

        if line.startswith("url:"):
            url = line.split("url:", 1)[1].strip()
            add_current(url)

    return urls


def split_author(author: str) -> tuple[str, str]:
    author = clean_latex(author)
    parts = author.split()
    if not parts:
        return "", ""
    return " ".join(parts[:-1]), parts[-1]


def format_author(author: str, coauthor_urls: dict[tuple[str, str], str]) -> str:
    author = clean_latex(author)
    first, last = split_author(author)
    escaped = html.escape(author)

    if author == YOUR_NAME:
        return f"{escaped}"

    url = coauthor_urls.get((first, last))
    if url:
        escaped_url = html.escape(url, quote=True)
        return f'<a href="{escaped_url}" target="_blank" rel="noopener noreferrer">{escaped}</a>'

    return escaped


def join_authors(authors: list[str], coauthor_urls: dict[tuple[str, str], str]) -> str:
    formatted = [format_author(a, coauthor_urls) for a in authors]
    if len(formatted) <= 1:
        return "".join(formatted)
    if len(formatted) == 2:
        return " and ".join(formatted)
    return ", ".join(formatted[:-1]) + ", and " + formatted[-1]


def year_of(entry: dict[str, str]) -> int:
    try:
        return int(clean_latex(entry.get("year", "0")))
    except ValueError:
        return 0


def venue_of(entry: dict[str, str]) -> str:
    for field in ["booktitle", "journal"]:
        if entry.get(field):
            return clean_latex(entry[field])

    kind = clean_latex(entry.get("kind", ""))
    if kind == "manuscript":
        return "Manuscript"
    return ""


def paper_url(entry: dict[str, str]) -> str:
    """
    URL for the clickable title.

    Prefer the arXiv/html page, then a PDF. We deliberately do not use the DOI
    URL field, because DOI/arXiv should not appear as separate fields/links.
    """
    for field in ["html", "pdf"]:
        value = entry.get(field, "").strip()
        if value:
            return clean_latex(value)

    # Optional fallback: if the entry has an arXiv eprint number but no html/pdf,
    # build the arXiv abstract URL. This is still only used as the title link.
    eprint = clean_latex(entry.get("eprint", ""))
    eprinttype = clean_latex(entry.get("eprinttype", "")).lower()
    if eprint and eprinttype == "arxiv":
        return f"https://arxiv.org/abs/{eprint}"

    return ""


def linked_title(entry: dict[str, str]) -> str:
    title = html.escape(clean_latex(entry.get("title", "Untitled")))
    url = paper_url(entry)
    if url:
        # return f'<a href="{html.escape(url)}">{title}</a>'
        escaped_url = html.escape(url, quote=True)
        return f'<a href="{escaped_url}" target="_blank" rel="noopener noreferrer">{title}</a>'
    return title


def extra_link_items(entry: dict[str, str]) -> list[str]:
    """
    Extra visible links after the venue.

    Important: the main paper link is the title, so we intentionally exclude
    DOI/arXiv/html/pdf/url/eprint fields here.
    """
    labels = {
        "poster": "poster",
        "talk": "talk",
        "slides": "slides",
        "code": "code",
    }

    items = []
    for field, label in labels.items():
        url = entry.get(field, "").strip()
        if url:
            escaped_url = html.escape(clean_latex(url), quote=True)
            items.append(
                f'<a href="{escaped_url}" target="_blank" rel="noopener noreferrer">{label}</a>'
            )

    return items


def render_entry(entry: dict[str, str], coauthor_urls: dict[tuple[str, str], str]) -> str:
    title = linked_title(entry)
    authors_raw = [a.strip() for a in re.split(r"\s+and\s+", entry.get("author", "")) if a.strip()]
    authors = join_authors(authors_raw, coauthor_urls)
    venue = html.escape(venue_of(entry))
    year = year_of(entry)
    links = " ".join(extra_link_items(entry))

    if venue and year:
        venue_line = f"{venue}, {year}"
    elif venue:
        venue_line = f"{venue}"
    elif year:
        venue_line = f"{year}"
    else:
        venue_line = ""

    # links_line = f'<span class="pub-links">{links}</span>' if links else ""

    venue_html = f'    <div class="pub-venue">{venue_line}</div>\n' if venue_line else ""
    links_html = f'    <div class="pub-links">{links}</div>\n' if links else ""

    return (
        '  <article class="publication">\n'
        f'    <div class="pub-title">{title}</div>\n'
        f'    <div class="pub-authors">{authors}</div>\n'
        f'{venue_html}'
        f'{links_html}'
        '</article>'
    )


def main() -> None:
    if not BIB_FILE.exists():
        raise FileNotFoundError(f"Could not find {BIB_FILE.name} next to this script.")

    coauthor_urls = load_coauthor_urls(COAUTHORS_FILE)
    raw_entries = split_bibtex_entries(BIB_FILE.read_text(encoding="utf-8"))
    entries = [parse_bibtex_entry(e) for e in raw_entries]
    entries = [e for e in entries if e.get("title")]

    # Reverse chronological order. For entries with no year, use .bib order.
    indexed = list(enumerate(entries))
    indexed.sort(key=lambda x: (-year_of(x[1]), x[0]))
    entries = [e for _, e in indexed]

    body = "\n\n".join(render_entry(e, coauthor_urls) for e in entries)
    OUTPUT_FILE.write_text(body + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_FILE.name} with {len(entries)} publications.")


if __name__ == "__main__":
    main()
