"""Playwright test of the light/dark theme button and the court and role colour contrast in index.html.

The app opens light whatever the system scheme; only a stored choice or a tap makes it dark.

Usage: python src/tests/theme_test.py [screenshot directory]
"""

import sys
from pathlib import Path
from typing import Literal

from playwright.sync_api import Error, Page, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
URL = (ROOT / "index.html").as_uri() + "?ff=all&anim=0"
FAIL: list[str] = []
OPPOSITE = {"light": "dark", "dark": "light"}
COURT = ("--court-g0", "--court-g1", "--court-g2")
ROLE_FILLS = ("--role-s", "--role-op", "--role-mb", "--role-oh")
ROUTES = ("--route-s", "--route-op", "--route-mb", "--route-oh", "--route-l")
SET_FAMILIES = ("--set-left", "--set-mid", "--set-right", "--set-back")
RGB = tuple[float, float, float]


def fail(message: str) -> None:
    FAIL.append(message)
    print("FAIL:", message, flush=True)


def shown_theme(page: Page) -> str:
    background = page.evaluate("getComputedStyle(document.body).backgroundColor")
    red = int(background.split("(")[1].split(",")[0])
    return "light" if red > 128 else "dark"


def parse_colour(value: str) -> tuple[RGB, float]:
    """Parses ``#rrggbb`` or ``rgba(r, g, b, a)`` into an RGB triple and an alpha."""
    value = value.strip()
    if value.startswith("#") and len(value) == 7:
        return (int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16)), 1.0
    parts = [float(x) for x in value[value.index("(") + 1 : value.index(")")].split(",")]
    return (parts[0], parts[1], parts[2]), parts[3] if len(parts) > 3 else 1.0


def over(top: str, bottom: RGB) -> RGB:
    """Composites a possibly translucent colour over an opaque one."""
    rgb, alpha = parse_colour(top)
    red, green, blue = (alpha * rgb[i] + (1 - alpha) * bottom[i] for i in range(3))
    return red, green, blue


def luminance(rgb: RGB) -> float:
    channels = [c / 255 for c in rgb]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def ratio(first: RGB, second: RGB) -> float:
    """WCAG 2.x contrast ratio."""
    light, dark = sorted((luminance(first), luminance(second)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def check_contrast(page: Page, tag: str) -> None:
    """Court, role and set tokens meet the ratios in docs/v2.md section 2.2: text 4.5, shapes and lines 3."""
    names = ["--court-line", "--net-label", "--marker-edge", "--ring", "--halo", "--tag", "--tag-ink"]
    names += ["--role-ink", "--role-l", "--role-l-ink", *COURT, *ROLE_FILLS, *ROUTES]
    names += ["--panel", *SET_FAMILIES]
    raw: dict[str, str] = page.evaluate(
        "names => { const style = getComputedStyle(document.documentElement);"
        " return Object.fromEntries(names.map(n => [n, style.getPropertyValue(n)])); }",
        names,
    )
    missing = [name for name, value in raw.items() if not value.strip()]
    if missing:
        fail(f"{tag}: tokens not defined: {missing}")
        return
    colour = {name: parse_colour(value)[0] for name, value in raw.items()}

    def need(label: str, first: RGB, second: RGB, minimum: float) -> None:
        found = ratio(first, second)
        if found < minimum:
            fail(f"{tag}: {label} contrast {found:.2f} < {minimum}")

    for band in COURT:
        need(f"--court-line on {band}", colour["--court-line"], colour[band], 3)
        need(f"--net-label on {band}", colour["--net-label"], colour[band], 4.5)
        need(f"--marker-edge on {band}", colour["--marker-edge"], colour[band], 3)
        need(f"--ring on {band}", colour["--ring"], colour[band], 3)
        for route in ROUTES:
            need(f"{route} over --halo on {band}", colour[route], over(raw["--halo"], colour[band]), 3)
    for fill in ROLE_FILLS:
        need(f"--role-ink on {fill}", colour["--role-ink"], colour[fill], 4.5)
    need("--role-l-ink on --role-l", colour["--role-l-ink"], colour["--role-l"], 4.5)
    need("--tag-ink on --tag", colour["--tag-ink"], colour["--tag"], 4.5)
    for family in SET_FAMILIES:
        need(f"{family} on --panel", colour[family], colour["--panel"], 4.5)


def wait_stored(page: Page, keys: list[str]) -> None:
    """Waits until a fresh page of the same context reads the stored keys as this page does.

    A reload can land in a new renderer, which reads the browser's copy of localStorage, not this page's.
    """
    values = page.evaluate("keys => keys.map(k => localStorage.getItem(k))", keys)
    probe = page.context.new_page()
    probe.goto((ROOT / "requirements.txt").as_uri())
    probe.wait_for_function(
        "([keys, values]) => keys.every((k, i) => localStorage.getItem(k) === values[i])", arg=[keys, values]
    )
    probe.close()


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
        page = browser.new_context(
            viewport={"width": 360, "height": 740},
            color_scheme=scheme,
            is_mobile=True,
            has_touch=True,
        ).new_page()
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.add_init_script("localStorage.setItem('ksv51:role', JSON.stringify('OH1'))")
        page.goto(URL)
        page.wait_for_timeout(300)
        if page.locator("#themeBtn").count() == 0:
            fail(f"{tag}: no theme button")
            browser.close()
            return
        if page.get_attribute("html", "data-theme") is not None:
            fail(f"{tag}: data-theme set without a stored choice")
        check_button(page, f"{tag} default", "light")
        check_contrast(page, f"{tag} tokens")
        box = page.locator("#themeBtn").bounding_box()
        if box is None or box["width"] < 44 or box["height"] < 44:
            fail(f"{tag}: tap target smaller than 44px: {box}")
        if shots:
            page.set_viewport_size({"width": 390, "height": 844})
            page.locator(".top").screenshot(path=str(shots / f"header_{scheme}.png"))
            page.set_viewport_size({"width": 360, "height": 740})
        page.click("#themeBtn")
        flipped = "dark"
        if page.get_attribute("html", "data-theme") != flipped:
            fail(f"{tag}: tap did not set data-theme={flipped}")
        check_button(page, f"{tag} after tap", flipped)
        check_contrast(page, f"{tag} tokens after tap")
        if page.evaluate("localStorage.getItem('ksv51:theme')") != f'"{flipped}"':
            fail(f"{tag}: tap did not store ksv51:theme={flipped}")
        wait_stored(page, ["ksv51:theme"])
        page.reload()
        try:
            page.wait_for_function(
                "([shown, next]) => document.documentElement.dataset.theme === shown"
                " && document.getElementById('themeBtn').getAttribute('aria-label') === `Switch to ${next} mode`",
                arg=[flipped, OPPOSITE[flipped]],
                timeout=5000,
            )
        except Error:
            fail(f"{tag}: choice not remembered after reload")
        check_button(page, f"{tag} after reload", flipped)
        page.click("#tabSets")
        if not page.is_visible("#themeBtn"):
            fail(f"{tag}: button hidden on Sets")
        overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        if overflow > 1:
            fail(f"{tag}: horizontal overflow {overflow}px")
        page.click("#themeBtn")
        check_button(page, f"{tag} second tap", "light")
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
