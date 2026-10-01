"""Playwright test of the feature flags in index.html.

Checks the built-in defaults, the ``?ff=`` preview override and its storage,
that a feature that is off leaves no trace in the DOM, dependency propagation,
the tab bar and the empty state, that the removed downloads leave no trace,
that a stored ``ksv51:flags`` is ignored and removed, and that a fake PostHog
SDK on the Pages host that serves flags changes no feature.

Usage: python src/tests/flags_test.py
"""

import base64
import hashlib
import json
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, BrowserContext, Page, Route, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
# A stored role skips the first-visit role sheet, which covers the page.
SEED_ROLE = "if (!localStorage.getItem('ksv51:role')) localStorage.setItem('ksv51:role', JSON.stringify('OH1'))"
URL = (ROOT / "index.html").as_uri()
PAGES_URL = "https://xszpo.github.io/volleyball_positions/"
FAIL: list[str] = []
PRIVACY = {
    "advanced_disable_flags": True,
    "api_host": "https://us.i.posthog.com",
    "ui_host": "https://us.posthog.com",
    "persistence": "memory",
    "person_profiles": "identified_only",
    "autocapture": False,
    "capture_pageview": True,
    "capture_pageleave": True,
    "disable_session_recording": True,
    "disable_surveys": True,
    "disable_web_experiments": True,
    "capture_heatmaps": False,
    "capture_dead_clicks": False,
    "capture_performance": False,
    "rageclick": False,
    "mask_all_text": True,
    "mask_all_element_attributes": True,
    "respect_dnt": True,
}
DEFAULT_OFF = {"after-dig"}
ALL_OFF = json.dumps(
    {
        key: False
        for key in (
            "learn-tab",
            "drill-tab",
            "match-solo",
            "match-online",
            "sets-tab",
            "bug-report",
            "rules-official",
            "learn-animation",
        )
    }
)
FAKE_POSTHOG = """
(() => {
  const served = { "learn-tab": false, "drill-tab": false, "match-solo": false, "sets-tab": false };
  window.posthog = {
    calls: { register: [], flagListeners: 0 },
    init(key, config) { this.config = config; return this; },
    register(props) { this.calls.register.push(props); },
    onFeatureFlags(callback) {
      this.calls.flagListeners += 1;
      callback([], served, { errorsLoading: false });
    },
    isFeatureEnabled(key) { return served[key] ?? false; },
    getFeatureFlag(key) { return served[key] ?? false; },
    capture() {},
  };
})();
"""


def fail(message: str) -> None:
    FAIL.append(message)
    print("FAIL:", message, flush=True)


def values(page: Page) -> dict[str, bool]:
    result: dict[str, bool] = page.evaluate("window.ksvFeatures.values()")
    return result


def present(page: Page, element_id: str) -> bool:
    return bool(page.evaluate("(id) => !!document.getElementById(id)", element_id))


def open_app(page: Page, query: str = "") -> None:
    page.goto(URL + query)
    page.wait_for_timeout(200)


def check_defaults(page: Page) -> None:
    open_app(page)
    got = values(page)
    for key, on in got.items():
        if on != (key not in DEFAULT_OFF):
            fail(f"default {key} = {on}")
    for element_id in ("tabLearn", "lZones", "drill", "game", "sets", "setsQuiz", "thumbsBox", "allRots"):
        if not present(page, element_id):
            fail(f"default: #{element_id} missing")
    if page.is_hidden("#tabs") or page.is_visible("#ffEmpty"):
        fail("default: tab bar hidden or empty state shown")
    if page.evaluate("localStorage.getItem('ksv51:ffOverride')") is not None:
        fail("default: override stored without ?ff=")


def check_stored_flags_ignored(page: Page) -> None:
    """A stored ``ksv51:flags`` with everything off changes nothing and is removed at start-up."""
    page.evaluate("(v) => localStorage.setItem('ksv51:flags', v)", ALL_OFF)
    open_app(page)
    got = values(page)
    if got != {key: key not in DEFAULT_OFF for key in got}:
        fail(f"stored flags all off: features changed: {got}")
    if not present(page, "drill") or not present(page, "reportBtn") or not present(page, "onBox"):
        fail("stored flags all off: a feature element missing")
    if page.evaluate("localStorage.getItem('ksv51:flags')") is not None:
        fail("stored flags all off: ksv51:flags not removed")


def check_off_leaves_no_trace(page: Page) -> None:
    open_app(page, "?ff=-drill-tab")
    html = page.evaluate(
        """() => {
            const body = document.body.cloneNode(true);
            body.querySelectorAll("script").forEach((s) => s.remove());
            return body.innerHTML;
        }"""
    )
    for element_id in ("tabDrill", "drill", "reviewBtn", "nbDrill", "nbGame", "dOpts", "dReset"):
        if present(page, element_id):
            fail(f"drill-tab off: #{element_id} still in the DOM")
    for text in ("quick quiz", "Drill options", "Neighbour check (who stands"):
        if text in html:
            fail(f"drill-tab off: {text!r} still in the DOM")
    got = values(page)
    if got["neighbour-check"] or got["drill-review"]:
        fail("drill-tab off: dependent features still on")
    if not got["match-solo"]:
        fail("drill-tab off: match-solo switched off too")
    page.click("#tabGame")
    page.click("#gStart")
    page.wait_for_timeout(200)
    if not page.is_visible("#gPlay"):
        fail("drill-tab off: Match does not start")


def check_zones_off(page: Page) -> None:
    """With court-zones off, a stored zones on draws no toggle and no zone numbers on any court."""
    page.goto(URL)
    page.evaluate("localStorage.setItem('ksv51:zones', 'true')")
    open_app(page, "?ff=reset,-court-zones")
    for element_id in ("lZones", "dZonesCheck", "dZones", "gZonesCheck", "gZones"):
        if present(page, element_id):
            fail(f"court-zones off: #{element_id} still in the DOM")
    if page.locator("#courtL .zones").count():
        fail("court-zones off: zone numbers on the Learn court")
    if not page.is_visible("#lNext"):
        fail("court-zones off: Next missing")
    page.click("#tabDrill")
    if page.locator("#courtD .zones").count():
        fail("court-zones off: zone numbers on the Drill court")
    page.click("#tabGame")
    page.click("#gStart")
    page.wait_for_timeout(200)
    if page.locator("#courtG .zones").count():
        fail("court-zones off: zone numbers on the Match court")
    open_app(page, "?ff=reset,-learn-tab")
    if not values(page)["court-zones"]:
        fail("learn-tab off: court-zones switched off too")
    page.evaluate("localStorage.removeItem('ksv51:zones'); localStorage.removeItem('ksv51:ffOverride')")


def check_answer_glide(page: Page) -> None:
    for query in ("?ff=reset,-answer-glide", "?ff=reset,-learn-animation"):
        open_app(page, query)
        if values(page)["answer-glide"]:
            fail(f"{query}: answer-glide still on")
        for element_id in ("dWatch", "gWatch", "rWatch"):
            if present(page, element_id):
                fail(f"{query}: #{element_id} still in the DOM")
    open_app(page, "?ff=reset")
    if not all(present(page, element_id) for element_id in ("dWatch", "gWatch", "rWatch")):
        fail("answer-glide on: a Watch the move box missing")


def check_override_storage(page: Page) -> None:
    open_app(page, "?ff=reset,-sets-quiz")
    open_app(page)
    if present(page, "setsQuiz") or not present(page, "sets"):
        fail("?ff=-sets-quiz not kept after a reload without ?ff=")
    open_app(page, "?ff=-rotations-table")
    stored = json.loads(page.evaluate("localStorage.getItem('ksv51:ffOverride')") or "null")
    if stored != {"sets-quiz": False, "rotations-table": False}:
        fail(f"?ff= does not merge into the stored override: {stored}")
    open_app(page, "?ff=all")
    if not all(values(page).values()):
        fail(f"?ff=all: not every flag on: {values(page)}")
    open_app(page, "?ff=-sets-tab")
    got = values(page)
    if got["sets-tab"] or got["sets-quiz"] or got["set-call-check"] or not got["learn-animation"]:
        fail(f"?ff=all then ?ff=-sets-tab: {got}")
    if present(page, "setGameCheck"):
        fail("sets-tab off: the set call check is still in Match options")
    open_app(page, "?ff=reset")
    if page.evaluate("localStorage.getItem('ksv51:ffOverride')") is not None:
        fail("?ff=reset left the override stored")
    if not present(page, "sets") or not values(page)["rules-official"] or values(page)["after-dig"]:
        fail("?ff=reset did not restore the defaults")
    parsed = page.evaluate("window.ksvFeatures.ffParse(' drill-tab , -nope,-learn-tab,bogus', {'sets-tab': false})")
    if parsed != {"sets-tab": False, "drill-tab": True, "learn-tab": False}:
        fail(f"ffParse: {parsed}")


def check_tabs(page: Page) -> None:
    open_app(page, "?ff=reset,-drill-tab,-match-solo,-sets-tab")
    if page.is_visible("#tabs") or not page.is_visible("#learn"):
        fail("one tab on: tab bar shown or Learn hidden")
    open_app(page, "?ff=reset,-learn-tab")
    if page.is_visible("#tabs") or not page.is_visible("#sets"):
        fail("only Sets on: tab bar shown or Sets not opened")
    open_app(page, "?ff=reset,-learn-tab,-sets-tab")
    if page.is_visible("#tabs") or not page.is_visible("#ffEmpty"):
        fail("no tab on: tab bar shown or no empty state")
    if page.locator("section").count():
        fail("no tab on: a tab section is still in the DOM")
    if not page.is_visible("#themeBtn") or not page.is_visible("#roleChip"):
        fail("no tab on: the shell is gone")
    open_app(page, "?ff=reset")


def serve(html: str) -> Callable[[Route], None]:
    def handler(route: Route) -> None:
        route.fulfill(status=200, content_type="text/html", body=html)

    return handler


def pages_html() -> str:
    html = (ROOT / "index.html").read_text()
    html = html.replace('const POSTHOG_KEY = "phc_REPLACE_ME";', 'const POSTHOG_KEY = "phc_test123";')
    digest = base64.b64encode(hashlib.sha384(FAKE_POSTHOG.encode()).digest()).decode()
    return re.sub(r'integrity: "sha384-[^"]+"', f'integrity: "sha384-{digest}"', html)


def open_pages(browser: Browser, seed: dict[str, str], query: str = "") -> tuple[BrowserContext, Page, list[str]]:
    """Opens the app on the Pages host with the fake PostHog SDK and ``seed`` in localStorage on the first load."""
    context = browser.new_context(viewport={"width": 360, "height": 740})
    context.add_init_script(SEED_ROLE)
    context.add_init_script(
        f"""if (!sessionStorage.getItem('seeded')) {{
            sessionStorage.setItem('seeded', '1');
            Object.entries({json.dumps(seed)}).forEach(([k, v]) => localStorage.setItem(k, v));
        }}"""
    )
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route(PAGES_URL + "**", serve(pages_html()))
    page.route(
        re.compile("posthog-js"),
        lambda route: route.fulfill(
            body=FAKE_POSTHOG, content_type="text/javascript", headers={"Access-Control-Allow-Origin": "*"}
        ),
    )
    page.goto(PAGES_URL + query)
    page.wait_for_function("!!(window.posthog && window.posthog.config)")
    return context, page, errors


def check_bad_storage(browser: Browser, file_page: Page) -> None:
    for bad in ('"x"', "[1]", "7"):
        file_page.evaluate("(v) => localStorage.setItem('ksv51:ffOverride', v)", bad)
        open_app(file_page)
        if values(file_page) != {k: k not in DEFAULT_OFF for k in values(file_page)}:
            fail(f"file://: stored override {bad} not ignored")
        context, page, errors = open_pages(browser, {"ksv51:flags": bad, "ksv51:ffOverride": bad})
        if not present(page, "learn") or errors:
            fail(f"pages: app did not start with stored {bad}: {errors}")
        if page.evaluate("localStorage.getItem('ksv51:flags')") is not None:
            fail(f"pages: stored flags {bad} not removed")
        context.close()
    open_app(file_page, "?ff=reset")


def check_players_mode_restored(page: Page) -> None:
    """A stored Online room choice survives match-online off and is picked again when it comes back on."""
    page.evaluate("localStorage.setItem('ksv51:gPlayers', JSON.stringify('online'))")
    open_app(page, "?ff=reset,-match-online")
    if present(page, "gPlayersOnline") or page.evaluate("localStorage.getItem('ksv51:gPlayers')") != '"online"':
        fail("players mode: online shown, or the stored choice overwritten, while match-online is off")
    open_app(page, "?ff=reset")
    checked = page.evaluate("document.querySelector('input[name=\"gPlayers\"]:checked')?.value")
    if checked != "online":
        fail(f"players mode: after match-online came on, {checked!r} is checked, not the stored online")
    page.click("#tabGame")
    if not page.is_visible("#onBox") or page.is_visible("#mpBox"):
        fail("players mode: the online setup is not shown")
    page.evaluate("localStorage.removeItem('ksv51:gPlayers')")
    open_app(page)


def check_rules_restored(page: Page) -> None:
    """A stored Official choice and same-device middles survive rules-official off, and return when it comes on."""
    mp = json.dumps([{"name": "Ann", "role": "MB2"}, {"name": "Bo", "role": "OP"}])
    page.evaluate(
        "(mp) => { localStorage.setItem('ksv51:rulesMode', JSON.stringify('official'));"
        " localStorage.setItem('ksv51:role', JSON.stringify('MB2'));"
        " localStorage.setItem('ksv51:mpPlayers', mp);"
        " localStorage.setItem('ksv51:gPlayers', JSON.stringify('mp')); }",
        mp,
    )
    open_app(page, "?ff=reset,-rules-official")
    page.evaluate(
        "() => { const el = document.querySelector('#mpList input');"
        " el.value = 'Anna'; el.dispatchEvent(new Event('input')); }"
    )
    stored = page.evaluate(
        "['rulesMode', 'role', 'mpPlayers'].map((k) => JSON.parse(localStorage.getItem('ksv51:' + k)))"
    )
    if stored[0] != "official" or stored[1] != "MB2" or stored[2][0]["role"] != "MB2":
        fail(f"rules: stored choices overwritten while rules-official is off: {stored}")
    open_app(page, "?ff=reset")
    checked = page.get_attribute('.rulesmode [aria-checked="true"]', "data-rm")
    shown = page.evaluate(
        "[document.getElementById('roleChip').dataset.role, document.querySelector('#mpList select').value]"
    )
    if checked != "official" or shown != ["MB2", "MB2"]:
        fail(f"rules: after rules-official came on, rules {checked!r}, role and player 1 {shown}")
    page.evaluate(
        "() => { ['rulesMode', 'mpPlayers', 'gPlayers'].forEach((k) => localStorage.removeItem('ksv51:' + k));"
        " localStorage.setItem('ksv51:role', JSON.stringify('OH1')); }"
    )
    open_app(page)


def check_posthog(browser: Browser) -> None:
    """PostHog analytics still load on the Pages host, and the flags it serves change no feature."""
    context, page, errors = open_pages(browser, {"ksv51:flags": ALL_OFF})
    config: dict[str, Any] = page.evaluate("window.posthog.config")
    if config != PRIVACY:
        fail(f"posthog: init options {config}, expected {PRIVACY}")
    if page.evaluate("window.posthog.calls.register") != [{"app_version": "2"}]:
        fail("posthog: app_version not registered")
    if page.evaluate("window.posthog.calls.flagListeners"):
        fail("posthog: the app still listens for PostHog flags")
    page.wait_for_timeout(200)
    got = values(page)
    if got != {key: key not in DEFAULT_OFF for key in got}:
        fail(f"posthog: features do not follow FEATURES: {got}")
    if not all(present(page, element_id) for element_id in ("drill", "game", "sets", "onBox", "reportBtn")):
        fail("posthog: a feature element missing")
    if page.evaluate("localStorage.getItem('ksv51:flags')") is not None:
        fail("posthog: stored ksv51:flags not removed")
    page.goto(PAGES_URL + "?ff=reset,-sets-tab")
    page.wait_for_function("!!(window.posthog && window.posthog.config)")
    if values(page)["sets-tab"] or present(page, "sets"):
        fail("posthog: ?ff= does not apply on the Pages host")
    if errors:
        fail(f"posthog: page errors: {errors}")
    context.close()


def check_downloads_removed(browser: Browser, file_page: Page) -> None:
    """The removed downloads leave nothing in index.html, and a stored or served ``downloads`` flag is ignored."""
    html = (ROOT / "index.html").read_text()
    for text in ("data:application/pdf", "application/pdf", "data-dl", 'id="downloads"', "Printable", "__PDF_"):
        if text in html:
            fail(f"downloads: {text!r} still in index.html")
    errors: list[str] = []
    file_page.on("pageerror", lambda error: errors.append(str(error)))
    file_page.evaluate(
        "localStorage.setItem('ksv51:ffOverride', JSON.stringify({downloads: true, 'sets-quiz': false}))"
    )
    open_app(file_page, "?ff=downloads,-downloads")
    got = values(file_page)
    if "downloads" in got or got["sets-quiz"] or not got["sets-tab"]:
        fail(f"downloads: stored override with downloads not handled: {got}")
    if present(file_page, "downloads") or errors:
        fail(f"downloads: section in the DOM or page errors: {errors}")
    open_app(file_page, "?ff=reset")
    context, page, page_errors = open_pages(browser, {"ksv51:flags": '{"downloads": true, "sets-tab": true}'})
    if "downloads" in values(page) or not present(page, "sets"):
        fail("downloads: stored downloads flag not ignored")
    if page_errors:
        fail(f"downloads: page errors on the Pages host: {page_errors}")
    context.close()


def check_first_visit_sheet(browser: Browser) -> None:
    """The first-visit role sheet opens over a tab, but not over the empty state."""
    for query, want in (("?ff=reset", True), ("?ff=reset,-learn-tab,-sets-tab", False)):
        page = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        open_app(page, query)
        if page.is_visible("#setupPanel") != want:
            fail(f"first visit with {query}: role sheet {'hidden' if want else 'open over the empty state'}")
        page.close()


def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        page.add_init_script(SEED_ROLE)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        for check in (
            check_defaults,
            check_stored_flags_ignored,
            check_off_leaves_no_trace,
            check_zones_off,
            check_answer_glide,
            check_override_storage,
            check_tabs,
            check_players_mode_restored,
            check_rules_restored,
        ):
            check(page)
        if errors:
            fail(f"page errors: {errors}")
        check_bad_storage(browser, page)
        check_posthog(browser)
        check_downloads_removed(browser, page)
        check_first_visit_sheet(browser)
        browser.close()
    print("FLAGS TEST FAILURES:", len(FAIL))
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
