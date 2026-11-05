#!/bin/sh

set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

cd "$ROOT"

echo
echo "Ferrari NLA Pipeline installer"
echo "=============================="
echo

command -v python3 >/dev/null 2>&1 ||
    {
        echo "ERROR: python3 not found" >&2
        exit 1
    }

[ -f requirements.txt ] ||
    {
        echo "ERROR: requirements.txt not found" >&2
        exit 1
    }

echo "Installing Python requirements..."
python3 -m pip install -r requirements.txt

echo
echo "Installing Playwright Chromium..."
python3 -m playwright install chromium

echo
echo "Checking Python dependencies..."
python3 -m pip check

echo
echo "Checking core imports..."

python3 - <<'PY'
import aiohttp
import cv2
import numpy
import paddle
import paddleocr
import PIL
import playwright
import playwright_stealth

print("aiohttp:", aiohttp.__version__)
print("OpenCV:", cv2.__version__)
print("NumPy:", numpy.__version__)
print("Paddle:", paddle.__version__)
print("PaddleOCR:", paddleocr.__version__)
print("Pillow:", PIL.__version__)
print("Playwright: OK")
print("Playwright Stealth: OK")
PY

echo
echo "Testing Playwright Chromium..."

python3 - <<'PY'
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.set_content(
            "<html><head><title>Ferrari NLA Test</title></head>"
            "<body>OK</body></html>"
        )

        title = await page.title()

        await browser.close()

        if title != "Ferrari NLA Test":
            raise RuntimeError(
                "Unexpected Chromium smoke-test result: "
                + repr(title)
            )

        print("Chromium:", title)

asyncio.run(main())
PY

echo
echo "Installation complete."
echo
