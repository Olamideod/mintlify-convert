#!/usr/bin/env python3
"""
Scrape live URLs to MDX, including downloading images, then hand off to converter.
"""

import os
import re
import requests
from pathlib import Path
from bs4 import BeautifulSoup
import html2text
from urllib.parse import urljoin, urlparse
from typing import Tuple


def _safe_filename_from_url(url: str) -> str:
    """Generate a safe filename from URL path."""
    parts = urlparse(url).path.strip('/').split('/')
    stem = (parts[-1] or (parts[-2] if len(parts) > 1 else 'index'))
    stem = re.sub(r"[^a-zA-Z0-9_-]", "-", stem)
    return f"{stem}.mdx"


def _download_images_and_update_dom(base_url: str, soup: BeautifulSoup, output_dir: Path, images_dir: str = "images") -> BeautifulSoup:
    images_path = output_dir / images_dir
    images_path.mkdir(parents=True, exist_ok=True)

    img_tags = soup.find_all("img")
    for img in img_tags:
        src = img.get("src")
        if not src:
            continue
        absolute_url = urljoin(base_url, src)
        filename = os.path.basename(urlparse(absolute_url).path) or "image"
        local_path = images_path / filename
        try:
            resp = requests.get(absolute_url, stream=True, timeout=30)
            resp.raise_for_status()
            with open(local_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            # Update DOM to point to local relative path (kept for MDX phase then converter rewrites to /images)
            img["src"] = f"{images_dir}/{filename}"
        except Exception:
            # Leave original src if download fails
            pass
    return soup


def scrape_url_to_mdx(url: str, output_dir: Path) -> Tuple[Path, str]:
    """Scrape a live URL into an MDX file in output_dir. Returns (mdx_path, mdx_content)."""
    output_dir.mkdir(parents=True, exist_ok=True)

    headers = {
        "User-Agent": "mintlify-convert-scraper/1.0"
    }
    resp = requests.get(url, headers=headers, allow_redirects=True, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.content, "html.parser")

    # Try common main content selectors; fallback to full body
    main = (
        soup.select_one("div.theme-doc-markdown")
        or soup.select_one("article")
        or soup.select_one("main")
        or soup.body
    )

    main = _download_images_and_update_dom(url, main, output_dir)

    h2t = html2text.HTML2Text()
    h2t.body_width = 0
    h2t.ignore_images = False
    h2t.ignore_links = False
    mdx_content = h2t.handle(str(main))

    mdx_filename = _safe_filename_from_url(url)
    mdx_path = output_dir / mdx_filename
    mdx_path.write_text(mdx_content, encoding="utf-8")

    return mdx_path, mdx_content


