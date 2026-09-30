"""Playwright test of the light/dark theme button in index.html.

Usage: python src/tests/theme_test.py [screenshot directory]
"""

import sys
from pathlib import Path
from typing import Literal

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
URL = (ROOT / "index.html").as_uri() + "?ff=all"
FAIL: list[str] = []
OPPOSITE = {"light": "dark", "dark": "light"}


def fail(message: str) -> None:
    FAIL.append(message)
    print("FAIL:", message, flush=True)


def shown_theme(page: Page) -> str:
    background = page.evaluate("getComputedStyle(document.body).backgroundColor")
    red = int(background.split("(")[1].split(",")[0])
    return "light" if red > 128 else "dark"


def check_button(page: Page, tag: str, expected: str) -> None:
    if shown_theme(page) != expected:
        fail(f"{tag}: body background is not {expected}")
    label = page.get_attribute("#themeBtn", "aria-label")
    if label != f"Switch to {OPPOSITE[expected]} mode":
        fail(f"{tag}: aria-label is {label!r}")


def run(scheme: Literal["light", "dark"], shots: Path | None) -> None:
    tag = f"system {scheme}"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(
            viewport={"width": 360, "height": 740},
            color_scheme=scheme,
            is_mobile=True,
            has_touch=True,
        )
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(URL)
        page.wait_for_timeout(300)
        if page.locator("#themeBtn").count() == 0:
            fail(f"{tag}: no theme button")
            browser.close()
            return
        if page.get_attribute("html", "data-theme") is not None:
            fail(f"{tag}: data-theme set without a stored choice")
        check_button(page, f"{tag} default", scheme)
        box = page.locator("#themeBtn").bounding_box()
        if box is None or box["width"] < 44 or box["height"] < 44:
            fail(f"{tag}: tap target smaller than 44px: {box}")
        if shots:
            page.set_viewport_size({"width": 390, "height": 844})
            page.locator(".top").screenshot(path=str(shots / f"header_{scheme}.png"))
            page.set_viewport_size({"width": 360, "height": 740})
        page.click("#themeBtn")
        flipped = OPPOSITE[scheme]
        if page.get_attribute("html", "data-theme") != flipped:
            fail(f"{tag}: tap did not set data-theme={flipped}")
        check_button(page, f"{tag} after tap", flipped)
        page.reload()
        page.wait_for_timeout(300)
        if page.get_attribute("html", "data-theme") != flipped:
            fail(f"{tag}: choice not remembered after reload")
        check_button(page, f"{tag} after reload", flipped)
        page.click("#tabSets")
        if not page.is_visible("#themeBtn"):
            fail(f"{tag}: button hidden on Sets")
        overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        if overflow > 1:
            fail(f"{tag}: horizontal overflow {overflow}px")
        page.click("#themeBtn")
        check_button(page, f"{tag} second tap", scheme)
        if errors:
            fail(f"{tag}: JS errors: {errors[:3]}")
        browser.close()


shot_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else None
if shot_dir:
    shot_dir.mkdir(parents=True, exist_ok=True)
run("light", shot_dir)
run("dark", shot_dir)
print("\nTOTAL FAILURES:", len(FAIL))
sys.exit(1 if FAIL else 0)
