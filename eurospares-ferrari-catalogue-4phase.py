#!/usr/bin/env python3
"""
Eurospares Ferrari catalogue scraper - four explicit phases with active Sucuri challenge solving.

Phases
------
--enumerate
    Uses Playwright to fetch /Components/Model/{7..15}, allowing the Sucuri
    JavaScript challenge to run. Saves the post-challenge HTML responses
    verbatim under ./data/model_groups/.

--extract
    Purely local/offline. Parses the saved model-group HTML and generates
    candidate Ferrari part-diagram catalogue URLs.

--validate
    Uses Playwright to load each candidate catalogue URL, allowing Sucuri
    JavaScript challenges to complete. Keeps only pages whose <h1> contains
    "Part Diagrams".

--run
    Reads ONLY the validated list and scrapes diagrams, parts and images.

No phase silently invokes another.

Run from the scraper directory, e.g.:

    cd /var/www/scrapers

    ./eurospares-ferrari-catalogue-4phase-playwright.py --enumerate
    ./eurospares-ferrari-catalogue-4phase-playwright.py --extract
    ./eurospares-ferrari-catalogue-4phase-playwright.py --validate
    ./eurospares-ferrari-catalogue-4phase-playwright.py --run

Intermediate/debug data is stored relative to the current working directory:

    ./data/model_groups/
    ./data/eurospares_ferrari_urls.extracted.txt
    ./data/eurospares_ferrari_urls.extracted.json
    ./data/eurospares_ferrari_urls.validated.txt
    ./data/eurospares_ferrari_validation.json
    ./data/ferrari_parts/<family>/<model>.json
    ./data/page_logs/<run-id>/

Images are stored under:

    /var/www/ferrari-nla/wp-content/uploads/images/ferrari_parts/
        <family>/<model>/<diagram-number>_<diagram-slug>.webp

The existing live Modena corpus is not touched.
"""

from __future__ import annotations

import argparse
import asyncio
import html
import json
import random
import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse

import aiohttp
from playwright.async_api import async_playwright, Page, BrowserContext
from playwright_stealth import stealth_async

BASE_URL = "https://www.eurospares.au"

MODEL_ENDPOINT_START = 7
MODEL_ENDPOINT_END = 15

MIN_DELAY = 10.0
MAX_DELAY = 15.0

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/156.0.0.0 Safari/537.36"
)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=90)

IMAGE_ROOT = (
    Path("/var/www/ferrari-nla")
    / "wp-content"
    / "uploads"
    / "images"
    / "ferrari_parts"
)


# ---------------------------------------------------------------------------
# Paths - all debug/intermediate data is relative to cwd
# ---------------------------------------------------------------------------

def paths() -> dict[str, Path]:
    data = Path.cwd() / "data"

    return {
        "data": data,
        "model_groups": data / "model_groups",
        "extracted_txt": data / "eurospares_ferrari_urls.extracted.txt",
        "extracted_json": data / "eurospares_ferrari_urls.extracted.json",
        "validated_txt": data / "eurospares_ferrari_urls.validated.txt",
        "validation_json": data / "eurospares_ferrari_validation.json",
        "corpus": data / "ferrari_parts",
        "page_logs": data / "page_logs",
    }


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------

class OptionParser(HTMLParser):
    """Extract <option value=...>visible text</option>."""

    def __init__(self) -> None:
        super().__init__()
        self.options: list[tuple[str, str]] = []
        self._inside = False
        self._value = ""
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "option":
            return

        self._inside = True
        self._value = ""
        self._text = []

        for key, value in attrs:
            if key.lower() == "value":
                self._value = value or ""

    def handle_data(self, data):
        if self._inside:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() != "option" or not self._inside:
            return

        self.options.append(
            (self._value, clean_text("".join(self._text)))
        )

        self._inside = False
        self._value = ""
        self._text = []


# ---------------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------------

def clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def slugify(value: str) -> str:
    value = clean_text(value).lower()
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def family_from_label(label: str) -> str | None:
    match = re.search(r"(?<!\d)(\d{3})(?!\d)", label)
    return match.group(1) if match else None


def normalise_model_slug(label: str, family: str) -> str:
    return slugify(label)


def parse_catalogue_root(url: str) -> tuple[str, str]:
    parts = [p for p in urlparse(url).path.split("/") if p]

    try:
        i = parts.index("ferrari")
        family = parts[i + 1]
        model = parts[i + 2]
        marker = parts[i + 3]
    except (ValueError, IndexError) as exc:
        raise ValueError(f"Unrecognised catalogue URL: {url}") from exc

    if marker != "part-diagrams":
        raise ValueError(f"Not a part-diagrams catalogue root: {url}")

    return family, model


def diagram_identity_from_url(url: str) -> tuple[str, str]:
    parts = [p for p in urlparse(url).path.split("/") if p]

    try:
        i = parts.index("part-diagrams")
        number = parts[i + 1]
        trailing_slug = parts[i + 2]
    except (ValueError, IndexError) as exc:
        raise ValueError(f"Unrecognised diagram URL: {url}") from exc

    return number.upper(), trailing_slug.lower()


def write_url_file(path: Path, urls: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    values = list(urls)
    path.write_text(
        ("\n".join(values) + "\n") if values else "",
        encoding="utf-8",
    )


def read_url_file(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(path)

    found: list[str] = []
    seen: set[str] = set()

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()

        if not line or line.startswith("#"):
            continue

        if line not in seen:
            seen.add(line)
            found.append(line)

    return found


async def polite_pause(min_delay: float, max_delay: float) -> None:
    delay = random.uniform(min_delay, max_delay)
    print(f"Delay: {delay:.1f} seconds", flush=True)
    await asyncio.sleep(delay)


class PageLogger:
    """Persist what Playwright actually sees for every navigation."""

    def __init__(self, root: Path) -> None:
        run_id = time.strftime("%Y%m%d_%H%M%S") + f"_{int(time.time() * 1000) % 1000:03d}"
        self.dir = root / run_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.sequence = 0
        print(f"Page log: {self.dir}")

    @staticmethod
    def _safe_label(value: str) -> str:
        value = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_")
        return value[:100] or "page"

    async def capture(
        self,
        page: Page,
        *,
        label: str,
        stage: str,
        requested_url: str | None = None,
        response=None,
    ) -> None:
        self.sequence += 1
        stem = f"{self.sequence:04d}_{self._safe_label(label)}_{self._safe_label(stage)}"

        try:
            title = await page.title()
        except Exception:
            title = ""

        try:
            h1 = [clean_text(x) for x in await page.locator("h1").all_inner_texts()]
        except Exception:
            h1 = []

        try:
            body_text = await page.locator("body").inner_text()
        except Exception as exc:
            body_text = f"[Unable to read body text: {exc}]"

        try:
            page_html = await page.content()
        except Exception as exc:
            page_html = f"<!-- Unable to read page HTML: {exc} -->"

        try:
            document_referrer = await page.evaluate("document.referrer")
        except Exception:
            document_referrer = ""

        try:
            navigator_user_agent = await page.evaluate("navigator.userAgent")
        except Exception:
            navigator_user_agent = ""

        try:
            cookies = await page.context.cookies()
        except Exception:
            cookies = []

        status = response.status if response is not None else None

        metadata = {
            "sequence": self.sequence,
            "label": label,
            "stage": stage,
            "requested_url": requested_url,
            "final_url": page.url,
            "http_status": status,
            "title": title,
            "h1": h1,
            "document_referrer": document_referrer,
            "navigator_user_agent": navigator_user_agent,
            "cookies": cookies,
        }

        (self.dir / f"{stem}.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        text_header = [
            f"requested_url: {requested_url}",
            f"final_url: {page.url}",
            f"http_status: {status}",
            f"title: {title}",
            f"h1: {' | '.join(h1)}",
            f"document_referrer: {document_referrer}",
            f"user_agent: {navigator_user_agent}",
            "",
            "----- BODY TEXT -----",
            "",
        ]

        (self.dir / f"{stem}.txt").write_text(
            "\n".join(text_header) + body_text + "\n",
            encoding="utf-8",
        )

        (self.dir / f"{stem}.html").write_text(
            page_html,
            encoding="utf-8",
        )


async def solve_sucuri_challenge(page: Page) -> bool:
    """Detects and actively resolves Sucuri security block screens."""
    for attempt in range(3):
        try:
            h1_texts = [clean_text(x).lower() for x in await page.locator("h1").all_inner_texts()]
            content = (await page.content()).lower()

            if not any("are you a robot" in text for text in h1_texts) and "sucuri" not in content and "/robots" not in page.url.lower():
                return True

            print(f"  [!] Attempting Sucuri challenge bypass ({attempt + 1}/3)...")

            # 1. Check if an interactive iframe (like Cloudflare/Sucuri turnstile) exists
            frames = page.frames
            for frame in frames:
                try:
                    checkbox = frame.locator('input[type="checkbox"], .mark, #challenge-stage')
                    if await checkbox.count() > 0:
                        await checkbox.first.click(timeout=3000)
                        await page.wait_for_timeout(3000)
                        break
                except Exception:
                    pass

            # 2. Check for explicit submit or challenge buttons on the main page
            btn = page.locator('button:has-text("Continue"), input[type="submit"], #btnSubmit, .btn-primary')
            if await btn.count() > 0 and await btn.first.is_visible():
                await btn.first.click()
                await page.wait_for_timeout(3000)

            # 3. Allow JavaScript reload / cookie setting window
            await page.wait_for_timeout(5000)

        except Exception as exc:
            print(f"  [!] Error handling challenge: {exc}")

    return False


async def logged_goto(
    page: Page,
    logger: PageLogger,
    url: str,
    *,
    label: str,
    referer: str | None = None,
    timeout: int = 90000,
):
    response = await page.goto(
        url,
        wait_until="domcontentloaded",
        timeout=timeout,
        referer=referer,
    )

    await logger.capture(
        page,
        label=label,
        stage="immediate",
        requested_url=url,
        response=response,
    )

    # Active detection and execution for Sucuri challenge
    h1_texts = [clean_text(x).lower() for x in await page.locator("h1").all_inner_texts()]
    if any("are you a robot" in text for text in h1_texts) or "/robots" in page.url.lower():
        print("  [+] Block page encountered. Intercepting...")
        solved = await solve_sucuri_challenge(page)
        if solved:
            # Re-navigate back to intended target once challenge cookie is assigned
            response = await page.goto(url, wait_until="domcontentloaded", timeout=timeout, referer=referer)

    return response

async def new_browser_context(playwright) -> tuple:
    # Launch Chromium with extra evasion flags
    browser = await playwright.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
        ]
    )

    context = await browser.new_context(
        user_agent=USER_AGENT,
        viewport={"width": 1440, "height": 1200},
        locale="en-US",
        timezone_id="America/New_York"
    )

    page = await context.new_page()
    # Apply stealth overrides to mask automated webdriver attributes
    await stealth_async(page)

    return browser, context, page


async def prime_sucuri(page: Page, logger: PageLogger) -> None:
    """Enter through the home page and persist the resulting session state."""
    try:
        response = await logged_goto(
            page,
            logger,
            BASE_URL + "/",
            label="home",
            referer=None,
        )

        await page.wait_for_timeout(3000)

        await logger.capture(
            page,
            label="home",
            stage="settled",
            requested_url=BASE_URL + "/",
            response=response,
        )
    except Exception as exc:
        try:
            await logger.capture(
                page,
                label="home",
                stage="error",
                requested_url=BASE_URL + "/",
                response=None,
            )
        except Exception:
            pass
        print(f"Home-page bootstrap error: {exc}", file=sys.stderr)


async def wait_for_model_payload(page: Page, timeout_ms: int = 45000) -> bool:
    try:
        await page.wait_for_selector(
            'select[name="ModelID"]',
            state="attached",
            timeout=timeout_ms,
        )
        return True
    except Exception:
        return False


async def wait_for_catalogue_h1(page: Page, timeout_ms: int = 45000) -> bool:
    try:
        await page.wait_for_selector(
            "h1",
            state="attached",
            timeout=timeout_ms,
        )
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Phase 1 - enumerate
# ---------------------------------------------------------------------------

async def enumerate_raw(
    model_start: int,
    model_end: int,
    min_delay: float,
    max_delay: float,
) -> int:
    p = paths()
    output_dir = p["model_groups"]
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest: list[dict] = []

    print(f"Delay: {min_delay:.1f}-{max_delay:.1f} seconds")
    print()
    print(f"Enumerating Eurospares model groups {model_start}..{model_end}")
    print()

    async with async_playwright() as pw:
        browser, context = await new_browser_context(pw)
        page = await context.new_page()
        logger = PageLogger(p["page_logs"])

        await prime_sucuri(page, logger)

        for group_id in range(model_start, model_end + 1):
            nonce = int(time.time() * 1000)

            url = (
                f"{BASE_URL}/Components/Model/{group_id}"
                f"?_={nonce}"
            )

            html_path = output_dir / f"model_{group_id}.html"
            meta_path = output_dir / f"model_{group_id}.meta.json"

            print(f"Fetching model group {group_id}: {url}", flush=True)

            initial_status = None
            error = None
            selector_found = False

            try:
                response = await logged_goto(
                    page,
                    logger,
                    url,
                    label=f"model_group_{group_id}",
                    referer=BASE_URL + "/",
                )

                if response is not None:
                    initial_status = response.status

                selector_found = await wait_for_model_payload(page)

                await logger.capture(
                    page,
                    label=f"model_group_{group_id}",
                    stage="settled",
                    requested_url=url,
                    response=response,
                )

                body_html = await page.locator("body").inner_html()

            except Exception as exc:
                error = str(exc)

                try:
                    body_html = await page.locator("body").inner_html()
                except Exception:
                    body_html = ""

            html_path.write_text(body_html, encoding="utf-8")

            meta = {
                "group_id": group_id,
                "requested_url": url,
                "final_url": page.url,
                "initial_navigation_status": initial_status,
                "model_selector_found": selector_found,
                "bytes_saved": len(body_html.encode("utf-8")),
                "html_file": str(html_path),
                "error": error,
            }

            meta_path.write_text(
                json.dumps(meta, indent=2),
                encoding="utf-8",
            )

            manifest.append(meta)

            result = "OK" if selector_found else "NOT RESOLVED"

            print(
                f"  {result}; initial HTTP {initial_status}; "
                f"saved {meta['bytes_saved']} bytes -> {html_path}",
                flush=True,
            )

            if error:
                print(f"  ERROR: {error}", flush=True)

            if group_id != model_end:
                print()
                await polite_pause(min_delay, max_delay)
                print()

        await browser.close()

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    print()
    print(f"Saved manifest -> {manifest_path}")
    print("No extraction has been performed.")

    return 0


# ---------------------------------------------------------------------------
# Phase 2 - extract
# ---------------------------------------------------------------------------

def extract_candidates() -> int:
    p = paths()
    model_dir = p["model_groups"]

    if not model_dir.exists():
        raise RuntimeError(
            f"Missing {model_dir}; run --enumerate first."
        )

    records: list[dict] = []
    candidate_urls: list[str] = []
    seen: set[str] = set()

    files = sorted(
        model_dir.glob("model_*.html"),
        key=lambda x: int(re.search(r"(\d+)", x.stem).group(1)),
    )

    if not files:
        raise RuntimeError(
            f"No model_*.html files found in {model_dir}"
        )

    for html_path in files:
        group_match = re.search(r"model_(\d+)", html_path.stem)
        group_id = int(group_match.group(1)) if group_match else None

        source = html_path.read_text(
            encoding="utf-8",
            errors="replace",
        )

        parser = OptionParser()
        parser.feed(source)

        print(
            f"{html_path.name}: "
            f"{len(parser.options)} <option> element(s)"
        )

        for option_value, label in parser.options:
            if not option_value or option_value == "0":
                continue

            if not label or label.lower() == "select model":
                continue

            family = family_from_label(label)

            if not family:
                print(f"  SKIP: no three-digit family in {label!r}")
                continue

            model_slug = normalise_model_slug(label, family)

            url = (
                f"{BASE_URL}/ferrari/{family}/"
                f"{model_slug}/part-diagrams"
            )

            record = {
                "group_id": group_id,
                "option_value": option_value,
                "label": label,
                "family": family,
                "model_slug": model_slug,
                "url": url,
            }

            records.append(record)

            if url not in seen:
                seen.add(url)
                candidate_urls.append(url)

            print(f"  {label} -> {url}")

    candidate_urls.sort()

    p["data"].mkdir(parents=True, exist_ok=True)

    write_url_file(
        p["extracted_txt"],
        candidate_urls,
    )

    p["extracted_json"].write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    print(f"Extracted {len(records)} model record(s)")
    print(f"Unique candidates: {len(candidate_urls)}")
    print(f"URLs -> {p['extracted_txt']}")
    print(f"Details -> {p['extracted_json']}")

    return 0


# ---------------------------------------------------------------------------
# Phase 3 - validate
# ---------------------------------------------------------------------------

async def validate_candidates(
    min_delay: float,
    max_delay: float,
) -> int:
    p = paths()
    candidates = read_url_file(p["extracted_txt"])

    valid: list[str] = []
    validation: list[dict] = []

    print(f"Validating {len(candidates)} candidate catalogue(s)")
    print()

    async with async_playwright() as pw:
        browser, context = await new_browser_context(pw)
        page = await context.new_page()
        logger = PageLogger(p["page_logs"])

        await prime_sucuri(page, logger)

        for index, url in enumerate(candidates, start=1):
            print(f"[{index}/{len(candidates)}] {url}", flush=True)

            initial_status = None
            error = None
            h1_texts: list[str] = []
            valid_page = False

            try:
                response = await logged_goto(
                    page,
                    logger,
                    url,
                    label=f"validate_{index:03d}",
                    referer=BASE_URL + "/",
                )

                if response is not None:
                    initial_status = response.status

                await wait_for_catalogue_h1(page)

                await logger.capture(
                    page,
                    label=f"validate_{index:03d}",
                    stage="settled",
                    requested_url=url,
                    response=response,
                )

                h1_texts = [
                    clean_text(x)
                    for x in await page.locator("h1").all_inner_texts()
                ]

                valid_page = any(
                    "part diagrams" in text.lower()
                    for text in h1_texts
                )

            except Exception as exc:
                error = str(exc)

            blocked = any(
                "are you a robot" in text.lower()
                for text in h1_texts
            )

            record = {
                "url": url,
                "final_url": page.url,
                "initial_navigation_status": initial_status,
                "h1": h1_texts,
                "valid": valid_page,
                "blocked": blocked,
                "error": error,
            }

            validation.append(record)

            print(f"  initial HTTP: {initial_status}")
            print(
                "  h1: "
                + (" | ".join(h1_texts) if h1_texts else "(none)")
            )
            if blocked:
                print("  BLOCKED")
            else:
                print("  " + ("VALID" if valid_page else "INVALID"))

            if error:
                print(f"  ERROR: {error}")

            if valid_page:
                valid.append(url)

            if blocked:
                print()
                print("Challenge page detected; stopping validation immediately.")
                print(f"Inspect page log: {logger.dir}")
                break

            if index != len(candidates):
                print()
                await polite_pause(min_delay, max_delay)
                print()

        await browser.close()

    write_url_file(
        p["validated_txt"],
        valid,
    )

    p["validation_json"].write_text(
        json.dumps(validation, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    print(f"Validated {len(valid)} / {len(candidates)} catalogue(s)")
    print(f"URLs -> {p['validated_txt']}")
    print(f"Report -> {p['validation_json']}")

    return 0


# ---------------------------------------------------------------------------
# Phase 4 - run
# ---------------------------------------------------------------------------

async def discover_diagram_links(
    page: Page,
    logger: PageLogger,
    catalogue_root: str,
) -> list[str]:
    response = await logged_goto(
        page,
        logger,
        catalogue_root,
        label="catalogue_" + urlparse(catalogue_root).path.strip("/").replace("/", "_"),
        referer=BASE_URL + "/",
    )

    await wait_for_catalogue_h1(page)

    await logger.capture(
        page,
        label="catalogue_" + urlparse(catalogue_root).path.strip("/").replace("/", "_"),
        stage="settled",
        requested_url=catalogue_root,
        response=response,
    )

    h1_texts = [
        clean_text(x)
        for x in await page.locator("h1").all_inner_texts()
    ]

    if not any(
        "part diagrams" in text.lower()
        for text in h1_texts
    ):
        raise RuntimeError(
            f"Validated catalogue no longer has Part Diagrams H1: "
            f"{catalogue_root}"
        )

    root_path = urlparse(catalogue_root).path.rstrip("/")
    selector = f'a[href*="{root_path}/"]'

    links = page.locator(selector)

    found: list[str] = []
    seen: set[str] = set()

    for index in range(await links.count()):
        href = await links.nth(index).get_attribute("href")

        if not href:
            continue

        full = urljoin(BASE_URL, href)

        try:
            diagram_identity_from_url(full)
        except ValueError:
            continue

        if full not in seen:
            seen.add(full)
            found.append(full)

    def sort_key(url: str):
        number, trailing_slug = diagram_identity_from_url(url)
        match = re.match(r"^(\d+)([A-Z]*)$", number)

        if match:
            return (
                int(match.group(1)),
                match.group(2),
                trailing_slug,
            )

        return (999999, number, trailing_slug)

    found.sort(key=sort_key)
    return found


async def extract_diagram(
    page: Page,
    logger: PageLogger,
    diagram_url: str,
    catalogue_root: str,
) -> dict:
    response = await logged_goto(
        page,
        logger,
        diagram_url,
        label="diagram_" + urlparse(diagram_url).path.strip("/").replace("/", "_"),
        referer=catalogue_root,
    )

    await logger.capture(
        page,
        label="diagram_" + urlparse(diagram_url).path.strip("/").replace("/", "_"),
        stage="settled",
        requested_url=diagram_url,
        response=response,
    )

    number, trailing_slug = diagram_identity_from_url(diagram_url)

    h1_text = ""
    if await page.locator("h1").count():
        h1_text = clean_text(
            await page.locator("h1").first.inner_text()
        )

    image_url = None
    image_alt = ""

    image = page.locator("img.diagram-image").first

    if await image.count():
        image_url = (
            await image.get_attribute("src")
            or await image.get_attribute("data-src")
        )

        image_alt = clean_text(
            await image.get_attribute("alt")
        )

        if image_url:
            image_url = urljoin(BASE_URL, image_url)

    parts: list[dict] = []
    rows = page.locator(".js-master-row")

    for row_index in range(await rows.count()):
        row = rows.nth(row_index)
        cells = row.locator("td")
        count = await cells.count()

        key_number = (
            clean_text(await cells.nth(0).inner_text())
            if count >= 1 else ""
        )

        part_number = (
            clean_text(await cells.nth(1).inner_text())
            if count >= 2 else ""
        )

        description = (
            clean_text(await cells.nth(2).inner_text())
            if count >= 3 else ""
        )

        availability = ""
        availability_button = row.locator(
            ".availability-section button"
        ).first

        if await availability_button.count():
            availability = clean_text(
                await availability_button.inner_text()
            )

        price = ""
        price_block = row.locator(
            ".d-none.d-xl-block.col-xl-2.text-right"
        ).first

        if await price_block.count():
            price = clean_text(
                await price_block.inner_text()
            )

        if not any(
            (
                key_number,
                part_number,
                description,
                availability,
                price,
            )
        ):
            continue

        parts.append(
            {
                "key_number": key_number,
                "part_number": part_number,
                "description": description,
                "availability": availability,
                "price": price,
            }
        )

    return {
        "diagram_number": number,
        "diagram_slug": trailing_slug,
        "diagram_title": trailing_slug.replace("-", " ").upper(),
        "diagram_url": diagram_url,
        "page_h1": h1_text,
        "diagram_image_url": image_url,
        "diagram_image_alt": image_alt,
        "parts": parts,
    }


async def download_image(
    session: aiohttp.ClientSession,
    image_url: str,
    destination: Path,
) -> None:
    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    async with session.get(image_url) as response:
        response.raise_for_status()
        data = await response.read()

    destination.write_bytes(data)


def load_checkpoint(path: Path) -> list[dict]:
    if not path.exists():
        return []

    try:
        payload = json.loads(
            path.read_text(encoding="utf-8")
        )
    except Exception:
        return []

    diagrams = payload.get("diagrams", [])
    return diagrams if isinstance(diagrams, list) else []


def checkpoint_json(
    path: Path,
    catalogue_root: str,
    family: str,
    model: str,
    diagrams: list[dict],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = {
        "catalogue_url": catalogue_root,
        "family": family,
        "model": model,
        "diagram_count": len(diagrams),
        "diagrams": diagrams,
    }

    temp_path = path.with_suffix(
        path.suffix + ".tmp"
    )

    temp_path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    temp_path.replace(path)


async def scrape_catalogue(
    page: Page,
    logger: PageLogger,
    image_session: aiohttp.ClientSession,
    catalogue_root: str,
    min_delay: float,
    max_delay: float,
) -> None:
    p = paths()

    family, model = parse_catalogue_root(
        catalogue_root
    )

    json_path = (
        p["corpus"]
        / family
        / f"{model}.json"
    )

    image_dir = (
        IMAGE_ROOT
        / family
        / model
    )

    image_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    existing = load_checkpoint(json_path)

    results = list(existing)

    result_index_by_url = {
        item.get("diagram_url"): index
        for index, item in enumerate(results)
        if item.get("diagram_url")
    }

    print()
    print("=" * 78)
    print(f"CATALOGUE: {family} / {model}")
    print(f"URL:       {catalogue_root}")
    print(f"JSON:      {json_path}")
    print(f"IMAGES:    {image_dir}")
    print("=" * 78)

    diagram_urls = await discover_diagram_links(
        page,
        logger,
        catalogue_root,
    )

    print(f"Found {len(diagram_urls)} diagram(s)")

    for index, diagram_url in enumerate(
        diagram_urls,
        start=1,
    ):
        number, trailing_slug = (
            diagram_identity_from_url(
                diagram_url
            )
        )

        filename = (
            f"{number.lower()}_"
            f"{trailing_slug}.webp"
        )

        local_path = image_dir / filename

        existing_record = None

        if diagram_url in result_index_by_url:
            existing_record = results[
                result_index_by_url[diagram_url]
            ]

        if (
            existing_record
            and existing_record.get("scrape_complete")
        ):
            print(
                f"[{index:03}/{len(diagram_urls):03}] "
                f"{number} {trailing_slug} - already complete"
            )
            continue

        print(
            f"[{index:03}/{len(diagram_urls):03}] "
            f"{number} {trailing_slug}"
        )

        record = await extract_diagram(
            page,
            logger,
            diagram_url,
            catalogue_root,
        )

        record["local_image_path"] = str(
            local_path
        )

        record["image_downloaded"] = False
        record["scrape_complete"] = False

        image_url = record.get(
            "diagram_image_url"
        )

        if image_url:
            try:
                if not local_path.exists():
                    await download_image(
                        image_session,
                        image_url,
                        local_path,
                    )

                record["image_downloaded"] = (
                    local_path.exists()
                )

            except Exception as exc:
                record["image_download_error"] = (
                    str(exc)
                )

        record["scrape_complete"] = True

        if diagram_url in result_index_by_url:
            results[
                result_index_by_url[diagram_url]
            ] = record
        else:
            result_index_by_url[diagram_url] = len(
                results
            )
            results.append(record)

        checkpoint_json(
            json_path,
            catalogue_root,
            family,
            model,
            results,
        )

        print(
            f"  {len(record['parts'])} parts"
            f" | image="
            f"{'yes' if record['image_downloaded'] else 'no'}"
        )

        if index != len(diagram_urls):
            await polite_pause(
                min_delay,
                max_delay,
            )

    checkpoint_json(
        json_path,
        catalogue_root,
        family,
        model,
        results,
    )

    print(f"Complete: {family}/{model}")


async def run_scraper(
    min_delay: float,
    max_delay: float,
) -> int:
    p = paths()
    catalogues = read_url_file(
        p["validated_txt"]
    )

    if not catalogues:
        raise RuntimeError(
            f"No validated catalogue URLs in "
            f"{p['validated_txt']}"
        )

    image_headers = {
        "User-Agent": USER_AGENT,
        "Referer": BASE_URL + "/",
    }

    async with async_playwright() as pw:
        browser, context = await new_browser_context(pw)
        page = await context.new_page()
        logger = PageLogger(p["page_logs"])

        await prime_sucuri(page, logger)

        async with aiohttp.ClientSession(
            timeout=REQUEST_TIMEOUT,
            headers=image_headers,
        ) as image_session:

            for index, catalogue_root in enumerate(
                catalogues,
                start=1,
            ):
                print()
                print(
                    f"Catalogue {index}/{len(catalogues)}: "
                    f"{catalogue_root}"
                )

                try:
                    await scrape_catalogue(
                        page,
                        logger,
                        image_session,
                        catalogue_root,
                        min_delay,
                        max_delay,
                    )
                except Exception as exc:
                    print(
                        f"CATALOGUE ERROR: {exc}",
                        file=sys.stderr,
                    )

                if index != len(catalogues):
                    print()
                    await polite_pause(
                        min_delay,
                        max_delay,
                    )

        await browser.close()

    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Four-phase Eurospares Ferrari catalogue "
            "enumerator/scraper."
        )
    )

    phase = parser.add_mutually_exclusive_group(
        required=True
    )

    phase.add_argument(
        "--enumerate",
        action="store_true",
        help=(
            "Use Playwright to fetch/save raw "
            "Components/Model responses."
        ),
    )

    phase.add_argument(
        "--extract",
        action="store_true",
        help=(
            "Parse saved raw responses and generate "
            "candidate catalogue URLs."
        ),
    )

    phase.add_argument(
        "--validate",
        action="store_true",
        help=(
            "Use Playwright to validate extracted "
            "catalogue URLs."
        ),
    )

    phase.add_argument(
        "--run",
        action="store_true",
        help=(
            "Scrape ONLY the validated catalogue URLs."
        ),
    )

    parser.add_argument(
        "--model-start",
        type=int,
        default=MODEL_ENDPOINT_START,
        help=(
            f"First Components/Model group "
            f"(default {MODEL_ENDPOINT_START})."
        ),
    )

    parser.add_argument(
        "--model-end",
        type=int,
        default=MODEL_ENDPOINT_END,
        help=(
            f"Last Components/Model group "
            f"(default {MODEL_ENDPOINT_END})."
        ),
    )

    parser.add_argument(
        "--min-delay",
        type=float,
        default=MIN_DELAY,
        help=(
            f"Minimum inter-request delay "
            f"(default {MIN_DELAY:g}s)."
        ),
    )

    parser.add_argument(
        "--max-delay",
        type=float,
        default=MAX_DELAY,
        help=(
            f"Maximum inter-request delay "
            f"(default {MAX_DELAY:g}s)."
        ),
    )

    return parser


async def async_main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.min_delay < 0:
        parser.error("--min-delay cannot be negative")

    if args.max_delay < args.min_delay:
        parser.error(
            "--max-delay must be >= --min-delay"
        )

    if args.model_end < args.model_start:
        parser.error(
            "--model-end must be >= --model-start"
        )

    if args.enumerate:
        return await enumerate_raw(
            args.model_start,
            args.model_end,
            args.min_delay,
            args.max_delay,
        )

    if args.extract:
        return extract_candidates()

    if args.validate:
        return await validate_candidates(
            args.min_delay,
            args.max_delay,
        )

    if args.run:
        return await run_scraper(
            args.min_delay,
            args.max_delay,
        )

    parser.error("No phase selected")
    return 2


def main() -> int:
    try:
        return asyncio.run(async_main())
    except KeyboardInterrupt:
        print()
        print("Interrupted.")
        return 130
    except Exception as exc:
        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
