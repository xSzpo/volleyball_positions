"""Playwright test of the two rule sets: Official (default) and Simplified KSV.

Checks the default mode and the role picker of each, that a stored "simple"
or "drill" reads as Simplified, that Official needs the ``rules-official`` flag, the
middle roles carried across a switch, the Simplified middle pair and SUB in
Learn, the Rules switch wording, and the one-time reset of stored rules and role
to a first visit in Official.

Usage: python src/tests/rules_test.py
"""

import json
import sys
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
URL = (ROOT / "index.html").as_uri()
FAIL: list[str] = []
SIMPLE_ROLES = ["MB", "OH1", "OH2", "OP", "S", "L"]
OFFICIAL_ROLES = ["MB1", "MB2", "OH1", "OH2", "OP", "S", "L"]


def fail(message: str) -> None:
    FAIL.append(message)
    print("FAIL:", message, flush=True)


def open_app(page: Page, query: str, stored: dict[str, Any]) -> None:
    page.goto(URL + query)
    page.evaluate(
        "(s) => { localStorage.clear(); localStorage.setItem('ksv51:officialReset', JSON.stringify('1'));"
        " for (const [k, v] of Object.entries(s))"
        " if (v === null) localStorage.removeItem('ksv51:' + k);"
        " else localStorage.setItem('ksv51:' + k, JSON.stringify(v)); }",
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
        page.click("#roleChip")


def pick(page: Page, *, rules: str | None = None, role: str | None = None) -> None:
    open_setup(page)
    if rules:
        page.click(f'.rulesmode [data-rm="{rules}"]')
    if role:
        open_setup(page)
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
    """Built-in flags: Official by default, a stored Simplified kept; rules-official off keeps a stored Official."""
    for stored, want in ((None, "official"), ("simple", "simple"), ("drill", "simple"), ("official", "official")):
        open_app(page, "", {"role": "OH1"} | ({"rulesMode": stored} if stored else {}))
        if checked_rules(page) != want:
            fail(f"defaults, stored {stored}: rules read as {checked_rules(page)}, expected {want}")
        if picker(page) != (OFFICIAL_ROLES if want == "official" else SIMPLE_ROLES):
            fail(f"defaults, stored {stored}: role picker is {picker(page)}")
        if want == "official" and "two middles" not in page.inner_text("#rmSub"):
            fail(f"defaults, stored {stored}: the Rules note is {page.inner_text('#rmSub')!r}")
        if not page.evaluate("!!document.getElementById('rmOfficial')"):
            fail(f"defaults, stored {stored}: the Official button is missing with rules-official on")
        if page.evaluate("localStorage.getItem('ksv51:rulesMode')") != (json.dumps(stored) if stored else None):
            fail(f"defaults, stored {stored}: the stored rules changed on load")
    open_app(page, "", {})
    if checked_rules(page) != "official" or picker(page) != OFFICIAL_ROLES:
        fail(f"first visit: rules {checked_rules(page)}, role picker {picker(page)}")
    if page.get_attribute("#roleChip", "data-role") != "MB1":
        fail(f"first visit: role chip shows {page.get_attribute('#roleChip', 'data-role')!r}, expected MB1")
    open_app(page, "", {"role": "MB"})
    if page.get_attribute("#roleChip", "data-role") != "MB1":
        fail(f"stored MB with no rules shows as {page.get_attribute('#roleChip', 'data-role')!r}, expected MB1")
    for stored in ("official", "drill"):
        open_app(page, "?ff=-rules-official", {"role": "OH1", "rulesMode": stored})
        if checked_rules(page) != "simple":
            fail(f"rules-official off, stored {stored}: rules read as {checked_rules(page)}")
        if page.evaluate("!!document.getElementById('rmOfficial')"):
            fail(f"rules-official off, stored {stored}: the Official button is in the DOM")
        if picker(page) != SIMPLE_ROLES:
            fail(f"rules-official off: role picker is {picker(page)}")
    open_app(page, "?ff=-rules-official", {"role": "MB2", "rulesMode": "official"})
    if page.get_attribute("#roleChip", "data-role") != "MB":
        fail(f"rules-official off: stored MB2 shows as {page.get_attribute('#roleChip', 'data-role')!r}, expected MB")
    if page.evaluate("JSON.parse(localStorage.getItem('ksv51:rulesMode'))") != "official":
        fail("rules-official off: a stored Official choice was overwritten")


def stored_keys(page: Page, keys: list[str]) -> list[Any]:
    values: list[Any] = page.evaluate("(keys) => keys.map((k) => JSON.parse(localStorage.getItem('ksv51:' + k)))", keys)
    return values


def check_official_reset(page: Page) -> None:
    """One reset of the stored rules and role to a first visit in Official, progress kept, then a choice kept."""
    stats = {"OH1|0|start": [1, 0]}
    open_app(page, "", {"rulesMode": "simple", "role": "MB", "stats2": stats, "officialReset": None})
    if checked_rules(page) != "official" or picker(page) != OFFICIAL_ROLES:
        fail(f"reset: rules {checked_rules(page)}, role picker {picker(page)}")
    if not page.is_visible("#setupNudge"):
        fail("reset: the role list did not open with Pick your role")
    after = stored_keys(page, ["rulesMode", "role", "stats2", "officialReset"])
    if after != [None, None, stats, "1"]:
        fail(f"reset: rules, role, stats and mark stored as {after}")
    pick(page, role="OH2")
    pick(page, rules="simple")
    page.reload()
    page.wait_for_function("document.readyState === 'complete' && !!document.querySelector('#setchips button')")
    if checked_rules(page) != "simple" or page.get_attribute("#roleChip", "data-role") != "OH2":
        fail(f"reset: after a reload rules {checked_rules(page)}, role {page.get_attribute('#roleChip', 'data-role')}")
    if page.is_visible("#setupPanel"):
        fail("reset: the role list opened again after a reload")
    open_app(page, "?ff=all,-rules-official", {"rulesMode": "simple", "role": "OH1", "officialReset": None})
    after = stored_keys(page, ["rulesMode", "role", "officialReset"])
    if after != ["simple", "OH1", None] or page.is_visible("#setupPanel"):
        fail(f"reset with rules-official off: stored {after}, role list open {page.is_visible('#setupPanel')}")


def check_switch(page: Page) -> None:
    """With rules-official on: the picker, the middle carried across and the switch wording."""
    open_app(page, "?ff=all&anim=0", {"role": "MB2", "rulesMode": "drill"})
    if checked_rules(page) != "simple":
        fail(f"stored drill reads as {checked_rules(page)}, expected simple")
    open_setup(page)
    order = page.eval_on_selector_all(".rulesmode [data-rm]", "els => els.map(e => e.dataset.rm)")
    if order != ["official", "simple"]:
        fail(f"the Rules switch reads {order}, expected Official then Simplified")
    if "training convention" not in page.inner_text("#rmSub"):
        fail(f"Simplified switch text does not say it is a training convention: {page.inner_text('#rmSub')!r}")
    if page.get_attribute("#roleChip", "data-role") != "MB":
        fail(f"stored MB2 in Simplified shows as {page.get_attribute('#roleChip', 'data-role')!r}")
    pick(page, rules="official")
    if picker(page) != OFFICIAL_ROLES:
        fail(f"Official role picker is {picker(page)}")
    if page.get_attribute("#roleChip", "data-role") != "MB2":
        fail(f"back in Official the stored MB2 reads as {page.get_attribute('#roleChip', 'data-role')!r}")
    if "Official rules" not in (page.get_attribute("#roleChip", "aria-label") or ""):
        fail("role chip label does not name Official rules")
    if " ".join(page.inner_text("#roleChip").split()) != "MB2 · O":
        fail(f"role chip does not show the role and rules: {page.inner_text('#roleChip')!r}")
    pick(page, rules="simple")
    if picker(page) != SIMPLE_ROLES or page.get_attribute("#roleChip", "data-role") != "MB":
        fail(f"Simplified after Official: picker {picker(page)}, chip {page.get_attribute('#roleChip', 'data-role')!r}")
    if "Simplified rules" not in (page.get_attribute("#roleChip", "aria-label") or ""):
        fail("role chip label does not name Simplified rules")
    page.reload()
    page.wait_for_function("!!document.querySelector('#setchips button')")
    if checked_rules(page) != "simple":
        fail("Simplified not remembered")


def check_learn(page: Page) -> None:
    """Simplified in Learn: MB always front, the pair resets into R3, SUB serves in R3 and R6."""
    open_app(page, "?ff=all&anim=0", {"role": "MB", "rulesMode": "simple"})
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


def check_short_phone(page: Page) -> None:
    """At 390 x 664 the Official role list fits on screen under the header button, with no sideways scroll."""
    page.set_viewport_size({"width": 390, "height": 664})
    open_app(page, "?ff=all&anim=0", {"role": "MB2", "rulesMode": "official"})
    open_setup(page)
    fits = page.evaluate(
        "(() => { const r = document.getElementById('setup').getBoundingClientRect();"
        " return r.bottom <= innerHeight && r.right <= innerWidth && r.left >= 0"
        " && document.documentElement.scrollWidth <= innerWidth; })()"
    )
    if not fits or picker(page) != OFFICIAL_ROLES:
        fail(f"390 x 664: the Official role list does not fit on screen: {page.locator('#setup').bounding_box()}")
    close_setup(page)
    page.set_viewport_size({"width": 390, "height": 844})


def court_point(page: Page, court: str) -> tuple[float, float]:
    """A point on the court, above the off court pill and below the open role list."""
    box = page.locator(court).bounding_box()
    menu = page.locator("#setup").bounding_box()
    assert box is not None and menu is not None
    top = max(box["y"], menu["y"] + menu["height"] + 10)
    return box["x"] + box["width"] * 0.5, (top + box["y"] + box["height"] * 0.85) / 2


def tap_court_with_list_open(page: Page, court: str) -> None:
    page.locator(court).scroll_into_view_if_needed()
    open_setup(page)
    x, y = court_point(page, court)
    page.mouse.click(x, y)


def check_outside_tap(page: Page) -> None:
    """A tap on the Drill or Match court that closes the role list does not answer."""
    open_app(page, "?ff=all&anim=0", {"role": "OH1"})
    page.click("#tabDrill")
    stats = page.evaluate("localStorage.getItem('ksv51:stats2')")
    court = page.inner_html("#courtD")
    tap_court_with_list_open(page, "#courtD")
    if page.is_visible("#setupPanel"):
        fail("Drill: a tap on the court did not close the role list")
    answered = page.inner_html("#courtD") != court
    if answered or page.evaluate("localStorage.getItem('ksv51:stats2')") != stats:
        fail("Drill: the tap that closed the role list also answered")
    page.click("#tabGame")
    page.click("#gStart")
    court = page.inner_html("#courtG")
    tap_court_with_list_open(page, "#courtG")
    if page.is_visible("#setupPanel"):
        fail("Match: a tap on the court did not close the role list")
    if page.inner_html("#courtG") != court:
        fail("Match: the tap that closed the role list also placed your spot")
    open_setup(page)
    x, y = court_point(page, "#courtG")
    close_setup(page)
    page.mouse.click(x, y)
    if page.inner_html("#courtG") == court:
        fail("Match: the next court tap after closing the role list did not place your spot")


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        page = context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        check_defaults(page)
        check_official_reset(page)
        check_switch(page)
        check_learn(page)
        check_short_phone(page)
        check_outside_tap(page)
        if errors:
            fail(f"JS errors: {json.dumps(errors[:3])}")
        browser.close()
    print(f"\nTOTAL FAILURES: {len(FAIL)}")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
