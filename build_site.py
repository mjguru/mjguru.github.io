#!/usr/bin/env python3

from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "_site"

PLACEHOLDER = "<!-- PUBLICATIONS_PLACEHOLDER -->"

# Start fresh.
if SITE.exists():
    shutil.rmtree(SITE)

SITE.mkdir()

# Read homepage template and generated publications.
index_html = (ROOT / "index.html").read_text(encoding="utf-8")
publications_html = (ROOT / "publications.html").read_text(encoding="utf-8")

if PLACEHOLDER not in index_html:
    raise RuntimeError(f"Could not find {PLACEHOLDER} in index.html")

# Inject generated publications into homepage.
index_html = index_html.replace(PLACEHOLDER, publications_html)

# Write final homepage to deployed site folder.
(SITE / "index.html").write_text(index_html, encoding="utf-8")

# Copy static files.
for filename in [
    "style.css",
    "publications.html",
    "photo-large.jpg",
    "headshot.jpeg",
]:
    src = ROOT / filename
    if src.exists():
        shutil.copy2(src, SITE / filename)

# Copy PDFs.
for pdf in ROOT.glob("*.pdf"):
    shutil.copy2(pdf, SITE / pdf.name)
