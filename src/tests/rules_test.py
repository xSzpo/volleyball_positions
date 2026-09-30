"""Playwright test of the two rule sets: Simplified KSV (default) and Official.

Checks the default mode and the role picker of each, that a stored "drill"
reads as Simplified, that Official needs the ``rules-official`` flag, the
middle roles carried across a switch, the Simplified middle pair and SUB in
Learn, and the Rules switch wording.

Usage: python src/tests/rules_test.py
"""

import json
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
URL = (ROOT / "index.html").as_uri()
FAIL: list[str] = []
SIMPLE_ROLES = ["MB", "OH1", "OH2", "OP", "S", "L"]
OFFICIAL_ROLES = ["MB1", "MB2", "OH1", "OH2", "OP", "S", "L"]


def fail(message: str) -> None:
    FAIL.append(message)
    print("FAIL:", message, flush=True)


def open_app(page: Page, query: str, stored: dict[str, str]) -> None:
    page.goto(URL + query)
    page.evaluate(
        "(s) => { localStorage.clear();"
        " for (const [k, v] of Object.entries(s)) localStorage.setItem('ksv51:' + k, JSON.stringify(v)); }",
        stored,
    )
    page.goto(URL + query)
    page.wait_for_function("document.readyState === 'complete' && !!document.querySelector('#setchips button')")


def picker(page: Page) -> list[str]:
    roles: list[str] = page.eval_on_selector_all("#roles .role", "els => els.map(e => e.dataset.r)")
    return roles


def checked_rules(page: Page) -> str | None:
    return page.get_attribute('.rulesmode [aria-checked="true"]', "data-rm")


def open_setup(page: Page) -> None:
    if not page.is_visible("#setupPanel"):
        page.click("#roleChip")


def close_setup(page: Page) -> None:
    if page.is_visible("#setupPanel"):
        page.click("#setupDone")


def pick(page: Page, *, rules: str | None = None, role: str | None = None) -> None:
    open_setup(page)
    if rules:
        page.click(f'.rulesmode [data-rm="{rules}"]')
    if role:
        page.click(f'#roles .role[data-r="{role}"]')
    close_setup(page)


def markers(page: Page) -> list[str]:
    labels: list[str] = page.eval_on_selector_all("#courtL .mk", "els => els.map(e => e.dataset.p)")
    return labels


def learn(page: Page, rotation: int, phase: str) -> None:
    page.click("#tabLearn")
    page.click(f'.rot[data-i="{rotation}"]')
    page.click(f'.ph[data-k="{phase}"]')


def check_defaults(page: Page) -> None:
    """Built-in flags: Simplified only, even when Official or Drill was stored."""
    for stored in ("official", "drill"):
        open_app(page, "", {"role": "OH1", "rulesMode": stored})
        if checked_rules(page) != "simple":
            fail(f"defaults, stored {stored}: rules read as {checked_rules(page)}")
        if page.evaluate("!!document.getElementById('rmOfficial')"):
            fail(f"defaults, stored {stored}: the Official button is in the DOM with rules-official off")
        if picker(page) != SIMPLE_ROLES:
            fail(f"defaults: role picker is {picker(page)}")
    open_app(page, "", {"role": "MB2", "rulesMode": "official"})
    if page.inner_text("#roleChip").strip() != "MB":
        fail(f"defaults: stored MB2 shows as {page.inner_text('#roleChip')!r}, expected MB")
    if page.evaluate("JSON.parse(localStorage.getItem('ksv51:rulesMode'))") != "official":
        fail("defaults: a stored Official choice was overwritten while the flag is off")


def check_switch(page: Page) -> None:
    """With rules-official on: the picker, the middle carried across and the switch wording."""
    open_app(page, "?ff=all", {"role": "MB2", "rulesMode": "drill"})
    if checked_rules(page) != "simple":
        fail(f"stored drill reads as {checked_rules(page)}, expected simple")
    open_setup(page)
    if "training convention" not in page.inner_text("#rmSub"):
        fail(f"Simplified switch text does not say it is a training convention: {page.inner_text('#rmSub')!r}")
    if page.inner_text("#roleChip").strip() != "MB":
        fail(f"stored MB2 in Simplified shows as {page.inner_text('#roleChip')!r}")
    pick(page, rules="official")
    if picker(page) != OFFICIAL_ROLES:
        fail(f"Official role picker is {picker(page)}")
    if page.inner_text("#roleChip").strip() != "MB2":
        fail(f"back in Official the stored MB2 reads as {page.inner_text('#roleChip')!r}")
    if "Official rules" not in (page.get_attribute("#roleChip", "aria-label") or ""):
        fail("role chip label does not name Official rules")
    pick(page, rules="simple")
    if picker(page) != SIMPLE_ROLES or page.inner_text("#roleChip").strip() != "MB":
        fail(f"Simplified after Official: picker {picker(page)}, chip {page.inner_text('#roleChip')!r}")
    if "Simplified rules" not in (page.get_attribute("#roleChip", "aria-label") or ""):
        fail("role chip label does not name Simplified rules")
    page.reload()
    page.wait_for_function("!!document.querySelector('#setchips button')")
    if checked_rules(page) != "simple":
        fail("Simplified not remembered")


def check_learn(page: Page) -> None:
    """Simplified in Learn: MB always front, the pair resets into R3, SUB serves in R3 and R6."""
    open_app(page, "?ff=all", {"role": "MB", "rulesMode": "simple"})
    learn(page, 2, "start")
    if not page.inner_text("#cue").startswith("Zone 4, front row") or "resets" not in page.inner_text("#cue"):
        fail(f"MB in R3 Rotation: cue is not the zone 4 reset: {page.inner_text('#cue')!r}")
    for ri in (2, 5):
        learn(page, ri, "serve")
        shown = markers(page)
        if "SUB" not in shown or "L" in shown or any(p in shown for p in ("MB1", "MB2")):
            fail(f"Simplified R{ri + 1} Our serve markers: {shown}")
        dash = page.get_attribute('#courtL .mk[data-p="SUB"] circle:not(.hit)', "stroke-dasharray")
        if not dash:
            fail(f"Simplified R{ri + 1}: SUB marker has no dashed edge")
        learn(page, ri, "rec")
        if "SUB" in markers(page) or "L" not in markers(page):
            fail(f"Simplified R{ri + 1} Reception markers: {markers(page)}")
    learn(page, 0, "serve")
    if "SUB" in markers(page) or "L" not in markers(page):
        fail(f"Simplified R1 Our serve markers: {markers(page)}")
    pick(page, role="L")
    learn(page, 2, "serve")
    cue = page.inner_text("#cue")
    if "off court" not in cue.lower() or "SUB" not in cue:
        fail(f"L in Simplified R3 Our serve: cue {cue!r}")
    pick(page, rules="official", role="MB1")
    learn(page, 2, "serve")
    shown = markers(page)
    if "SUB" in shown or "MB1" not in shown or "L" in shown:
        fail(f"Official R3 Our serve markers: {shown}")
    if not page.inner_text("#cue").startswith("Defend zone 6") or "so you serve" not in page.inner_text("#cue"):
        fail(f"MB1 in Official R3 Our serve: cue {page.inner_text('#cue')!r}")


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        page = context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        check_defaults(page)
        check_switch(page)
        check_learn(page)
        if errors:
            fail(f"JS errors: {json.dumps(errors[:3])}")
        browser.close()
    print(f"\nTOTAL FAILURES: {len(FAIL)}")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
