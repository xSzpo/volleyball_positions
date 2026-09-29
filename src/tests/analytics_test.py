"""Playwright test of the PostHog analytics guard in index.html.

Checks that nothing goes to PostHog from file:// or with the placeholder key, that
the load decision `analyticsOn()` only accepts the Pages host with a real key, and
that the app keeps working when the PostHog script is blocked.

Usage: python src/tests/analytics_test.py
"""

import sys
from collections.abc import Callable
from pathlib import Path

from playwright.sync_api import Browser, Page, Route, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
URL = (ROOT / "index.html").as_uri()
PAGES_URL = "https://xszpo.github.io/volleyball_positions/"
FAIL: list[str] = []
DECISIONS = [
    ("xszpo.github.io", "phc_abc123", True),
    ("xszpo.github.io", "phc_REPLACE_ME", False),
    ("xszpo.github.io", "", False),
    ("localhost", "phc_abc123", False),
    ("", "phc_abc123", False),
    ("xszpo.github.io.example.com", "phc_abc123", False),
    ("127.0.0.1", "phc_abc123", False),
]


def fail(message: str) -> None:
    FAIL.append(message)
    print("FAIL:", message, flush=True)


def is_posthog(url: str) -> bool:
    return "posthog" in url


def use_app(page: Page) -> None:
    page.click("#tabDrill")
    page.click("#courtD", position={"x": 100, "y": 100})
    page.click("#tabSets")
    page.locator("#setanswers button").first.click()
    page.click("#tabGame")
    page.click("#tabLearn")


def check_file(page: Page, errors: list[str], requests: list[str]) -> None:
    page.goto(URL)
    page.wait_for_timeout(300)
    use_app(page)
    thrown = page.evaluate(
        """() => {
            try {
                return String(window.ksvAnalytics.track("test_event", { a: 1 }));
            } catch (e) {
                return "threw " + e;
            }
        }"""
    )
    if thrown != "undefined":
        fail(f"file://: track() returned {thrown!r}")
    if page.evaluate("typeof window.posthog") != "undefined":
        fail("file://: PostHog loaded")
    for host, key, expected in DECISIONS:
        got = page.evaluate("([h, k]) => window.ksvAnalytics.analyticsOn(h, k)", [host, key])
        if got is not expected:
            fail(f"analyticsOn({host!r}, {key!r}) = {got}, expected {expected}")
    posthog = [u for u in requests if is_posthog(u)]
    if posthog:
        fail(f"file://: requests to PostHog: {posthog}")
    if errors:
        fail(f"file://: page errors: {errors}")


def serve(html: str) -> Callable[[Route], None]:
    def handler(route: Route) -> None:
        route.fulfill(status=200, content_type="text/html", body=html)

    return handler


def check_pages(page: Page, html: str, tag: str, errors: list[str], requests: list[str]) -> None:
    page.route(PAGES_URL, serve(html))
    page.route(lambda url: is_posthog(url), lambda route: route.abort())
    page.goto(PAGES_URL)
    page.wait_for_timeout(500)
    use_app(page)
    if page.evaluate("typeof window.posthog") != "undefined":
        fail(f"{tag}: PostHog loaded")
    if errors:
        fail(f"{tag}: page errors: {errors}")
    if not page.is_visible("#learn"):
        fail(f"{tag}: app not usable")


def run_case(browser: Browser, tag: str, body: str | None) -> None:
    context = browser.new_context(viewport={"width": 360, "height": 740})
    page = context.new_page()
    errors: list[str] = []
    requests: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("request", lambda request: requests.append(request.url))
    if body is None:
        check_file(page, errors, requests)
    else:
        check_pages(page, body, tag, errors, requests)
        asked = [u for u in requests if is_posthog(u)]
        if tag == "pages placeholder key" and asked:
            fail(f"{tag}: requests to PostHog: {asked}")
        if tag == "pages blocked script" and not asked:
            fail(f"{tag}: PostHog script was not requested")
    context.close()


def main() -> None:
    html = (ROOT / "index.html").read_text()
    placeholder = 'const POSTHOG_KEY = "phc_REPLACE_ME";'
    if placeholder not in html:
        fail("index.html has no placeholder POSTHOG_KEY")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        cases = [
            ("file", None),
            ("pages placeholder key", html),
            ("pages blocked script", html.replace(placeholder, 'const POSTHOG_KEY = "phc_test123";')),
        ]
        for tag, body in cases:
            run_case(browser, tag, body)
        browser.close()
    print("ANALYTICS TEST FAILURES:", len(FAIL))
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
