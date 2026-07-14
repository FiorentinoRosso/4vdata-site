# -*- coding: utf-8 -*-
"""Fast, dependency-free checks for the static site."""
from __future__ import annotations

import json
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
SKIP_PARTS = {".git", ".work"}


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.in_title = False
        self.h1 = 0
        self.description = ""
        self.canonical = ""
        self.robots = ""
        self.links: list[str] = []
        self.ld: list[str] = []
        self.in_ld = False
        self.ld_buffer = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = dict(attrs)
        if tag == "title":
            self.in_title = True
        elif tag == "h1":
            self.h1 += 1
        elif tag == "meta" and data.get("name", "").lower() == "description":
            self.description = data.get("content", "") or ""
        elif tag == "meta" and data.get("name", "").lower() == "robots":
            self.robots = data.get("content", "") or ""
        elif tag == "link" and "canonical" in (data.get("rel", "") or "").lower():
            self.canonical = data.get("href", "") or ""
        elif tag == "a" and data.get("href"):
            self.links.append(data["href"] or "")
        elif tag == "script" and data.get("type") == "application/ld+json":
            self.in_ld = True
            self.ld_buffer = ""

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        elif tag == "script" and self.in_ld:
            self.in_ld = False
            self.ld.append(self.ld_buffer.strip())

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title += data
        if self.in_ld:
            self.ld_buffer += data


def internal_target(page: Path, href: str) -> Path | None:
    parsed = urlparse(href)
    if parsed.scheme in {"mailto", "tel"} or href.startswith("#"):
        return None
    if parsed.netloc and parsed.netloc != "4vdata.ru":
        return None
    path = parsed.path
    if not path:
        return None
    target = ROOT / path.lstrip("/") if path.startswith("/") else page.parent / path
    if path.endswith("/") or target.is_dir():
        target /= "index.html"
    return target.resolve()


def main() -> int:
    errors: list[str] = []
    pages = [p for p in ROOT.rglob("*.html") if not SKIP_PARTS.intersection(p.parts) and not p.name.startswith("preview-")]
    titles: dict[str, Path] = {}
    descriptions: dict[str, Path] = {}
    indexable: set[str] = set()
    for page in pages:
        text = page.read_text(encoding="utf-8")
        rel = page.relative_to(ROOT)
        if "�" in text or "Рђ" in text or "Рµ" in text:
            errors.append(f"{rel}: possible mojibake")
        parser = PageParser()
        parser.feed(text)
        if not parser.title.strip():
            errors.append(f"{rel}: missing title")
        elif parser.title.strip() in titles:
            errors.append(f"{rel}: duplicate title with {titles[parser.title.strip()].relative_to(ROOT)}")
        else:
            titles[parser.title.strip()] = page
        if not parser.description.strip():
            errors.append(f"{rel}: missing meta description")
        elif parser.description.strip() in descriptions:
            errors.append(f"{rel}: duplicate description with {descriptions[parser.description.strip()].relative_to(ROOT)}")
        else:
            descriptions[parser.description.strip()] = page
        if parser.h1 != 1:
            errors.append(f"{rel}: expected one h1, found {parser.h1}")
        if not parser.canonical.startswith("https://4vdata.ru/"):
            errors.append(f"{rel}: missing or invalid canonical")
        if not parser.ld:
            errors.append(f"{rel}: missing JSON-LD")
        for block in parser.ld:
            try:
                json.loads(block)
            except json.JSONDecodeError as exc:
                errors.append(f"{rel}: invalid JSON-LD ({exc})")
        if "noindex" not in parser.robots.lower():
            indexable.add(parser.canonical)
        for href in parser.links:
            target = internal_target(page, href)
            if target and ROOT in target.parents and not target.exists():
                errors.append(f"{rel}: broken link {href}")

    sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
    for canonical in sorted(indexable):
        if canonical not in sitemap:
            errors.append(f"sitemap.xml: missing {canonical}")
    if "https://4vdata.ru/privacy/" in sitemap:
        errors.append("sitemap.xml: noindex privacy URL must not be listed")
    budgets = {"assets/site-bg-reference.webp": 400_000, "assets/og-4vdata.jpg": 300_000}
    for name, limit in budgets.items():
        asset = ROOT / name
        if not asset.exists() or asset.stat().st_size > limit:
            errors.append(f"{name}: missing or over {limit} bytes")

    seo_css = (ROOT / "assets/seo-pages.css").read_text(encoding="utf-8")
    home_css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")
    if "site-bg-reference.png" in seo_css:
        errors.append("seo-pages.css: legacy PNG background is still referenced")
    if "min-height: 44px" not in seo_css or "min-height: 44px" not in home_css:
        errors.append("navigation: 44px touch target rule is missing")
    case_page = (ROOT / "keisy/individualnaya-analitika-sellera/index.html").read_text(encoding="utf-8")
    if "case-turnover-dashboard-synthetic.png" not in case_page or "profi.ru/profile/GayfutdinovRV" not in case_page:
        errors.append("case study: sanitized screenshot or review source is missing")

    event_script = (ROOT / "assets/site.js").read_text(encoding="utf-8")
    for goal in {"cta_contact", "contact_email", "contact_telegram", "contact_whatsapp", "contact_max", "open_demo"}:
        if goal not in event_script and not any(goal in page.read_text(encoding="utf-8") for page in pages):
            errors.append(f"analytics: missing goal {goal}")

    if errors:
        print("SEO CHECK FAILED")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print(f"SEO CHECK OK: {len(pages)} HTML pages, {len(indexable)} indexable URLs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
