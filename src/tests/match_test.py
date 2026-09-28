"""Playwright test of solo match scoring in index.html.

Usage: python src/tests/match_test.py
"""

import re
import sys
from pathlib import Path

from playwright.sync_api import Browser, Page, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from data import ROWS, SETS, UNCONFIRMED_SETS  # noqa: E402

URL = (ROOT / "index.html").as_uri()
FAIL: list[str] = []


def fail(message: str) -> None:
    FAIL.append(message)
    print("FAIL:", message, flush=True)


def new_page(browser: Browser) -> Page:
    page = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    page.on("pageerror", lambda error: FAIL.append(f"page error: {error}"))
    page.goto(URL)
    page.wait_for_timeout(300)
    return page


def pick_role(page: Page, role: str) -> None:
    if page.is_hidden("#setupPanel"):
        page.click("#setupBar")
    page.click(f'.role[data-r="{role}"]')


def setup_match(
    page: Page, role: str, steps: tuple[str, ...], vis: str = "none", neighbour: bool = False, sets: bool = True
) -> None:
    """Opens Match as ``role`` with only ``steps`` switched on, in order."""
    pick_role(page, role)
    page.click("#tabGame")
    page.click(f'.vis[data-vis="game"] [data-v="{vis}"]')
    if page.get_attribute("#gOpts", "open") is None:
        page.click("#gOpts > summary")
    for step in ("start", "rec", "ar", "serve"):
        page.set_checked(f"#gs-{step}", step in steps)
    page.check('input[name="gOrder"][value="order"]')
    page.set_checked("#nbGame", neighbour)
    if "ar" in steps:
        page.set_checked("#setGame", sets)


def tap_spot(page: Page, role: str, ri: int, phase: str) -> None:
    """Taps the role's correct spot for ``phase`` in rotation ``ri``, or I'm off court if it has none."""
    spots = [(s[0], s[1], s[2]) for s in (ROWS[ri]["ar"] if phase == "ar" else ROWS[ri]["rec"])]
    found = next(((x, y) for p, x, y in spots if p == role), None)
    if found is None:
        page.click("#gOff")
        return
    x, y = found
    page.locator("#courtG").scroll_into_view_if_needed()
    cx, cy = page.evaluate(
        """([x, y]) => {
            const m = document.getElementById('courtG').getScreenCTM();
            return [m.a * x * 300 + m.e, m.d * y * 200 + m.f];
        }""",
        [x, y],
    )
    page.mouse.click(cx, cy)


def first_answer_points(browser: Browser, vis: str) -> int:
    """Plays the first reception of a match with ``vis`` and returns the points scored."""
    page = new_page(browser)
    setup_match(page, "OH1", ("rec",), vis)
    expected = {"none": "Nobody: full points · Setter: 70% · Everyone: 30%"}
    if vis == "none" and page.inner_text("#gVisPts") != expected["none"]:
        fail(f"points line under Show on court reads {page.inner_text('#gVisPts')!r}")
    page.click("#gStart")
    page.wait_for_selector("#gOff:enabled")
    tap_spot(page, "OH1", 0, "rec")
    page.wait_for_selector("#gFb .pts")
    points = int(page.inner_text("#gFb .pts").lstrip("+"))
    if "Spot on" not in page.inner_text("#gFb"):
        fail(f"vis {vis}: exact tap not scored as spot on")
    while not page.is_visible("#gEnd"):
        if page.is_enabled("#gOff") and page.is_visible("#gOff"):
            page.click("#gOff")
        page.click("#gNext")
    shown = page.inner_text("#gShown")
    want = {
        "none": "Shown: Nobody (full points)",
        "ref": "Shown: Setter (70% points)",
        "all": "Shown: Everyone (30% points)",
    }
    if shown != want[vis]:
        fail(f"end screen reads {shown!r}, expected {want[vis]!r}")
    page.close()
    return points


def check_vis_scoring(browser: Browser) -> None:
    points = {vis: first_answer_points(browser, vis) for vis in ("none", "ref", "all")}
    print("points by vis:", points, flush=True)
    if not points["none"] > points["ref"] > points["all"] > 0:
        fail(f"showing teammates does not lower the score: {points}")
    if abs(points["ref"] - round(points["none"] * 0.7)) > 1 or abs(points["all"] - round(points["none"] * 0.3)) > 1:
        fail(f"points are not 70% / 30% of the full score: {points}")


def check_peek(browser: Browser) -> None:
    """Peeking at teammates during a moment scores that moment only with the peeked setting."""
    page = new_page(browser)
    setup_match(page, "OH1", ("rec",))
    page.click("#gStart")
    page.wait_for_selector("#gOff:enabled")
    page.click('#gVisPlay [data-v="all"]')
    page.click('#gVisPlay [data-v="none"]')
    tap_spot(page, "OH1", 0, "rec")
    page.wait_for_selector("#gFb .pts")
    peeked = points(page)
    page.click("#gNext")
    page.wait_for_selector("#gOff:enabled")
    tap_spot(page, "OH1", 1, "rec")
    page.wait_for_selector("#gFb .pts")
    after = points(page)
    print("points with a peek, then without:", peeked, after, flush=True)
    if not 0 < peeked <= 36:
        fail(f"a moment with a peek at Everyone scored {peeked}, expected 30% of the full score")
    if after < 100:
        fail(f"the moment after a peek scored {after}; the peek should not carry over")
    while not page.is_visible("#gEnd"):
        if page.is_enabled("#gOff") and page.is_visible("#gOff"):
            page.click("#gOff")
        page.click("#gNext")
    shown = page.inner_text("#gShown")
    if shown != "Shown: Nobody (full points) · Peeked: 1 moment":
        fail(f"end screen after one peek reads {shown!r}")
    best = page.evaluate("JSON.parse(localStorage.getItem('ksv51:gameBest'))")
    if list(best) != ["v2|OH1|rec"]:
        fail(f"best score saved under {list(best)}, expected the starting settings only")
    page.close()


def check_best_key(browser: Browser) -> None:
    """Bests from before the scoring change are ignored, and the neighbour check has its own best."""
    page = new_page(browser)
    page.evaluate("""localStorage.setItem('ksv51:gameBest', JSON.stringify({"OH1|rec": 9999, "v2|OH1|rec": 500}))""")
    page.reload()
    page.wait_for_timeout(300)
    setup_match(page, "OH1", ("rec",))
    text = page.inner_text("#gBest")
    if "500" not in text:
        fail(f"best line reads {text!r}, expected the v2 best of 500")
    page.check("#nbGame")
    text = page.inner_text("#gBest")
    if text:
        fail(f"best with the neighbour check on reads {text!r}, expected none yet")
    page.close()
    print("best score key: old bests ignored, neighbour check separate", flush=True)


MATCH_SETS = [s for s in SETS if s[0] not in UNCONFIRMED_SETS]
LANES = {"left": {"1", "0", "2"}, "mid": {"Shoot", "Til"}, "right": {"7", "6"}}


def expected_sets(ri: int, role: str) -> set[str] | None:
    """The calls a set question may ask ``role`` after reception in rotation ``ri``, or None for no question."""
    spot = next((s for s in ROWS[ri]["ar"] if s[0] == role), None)
    if spot is None:
        return None
    if spot[3] == "set":
        return {s[0] for s in MATCH_SETS}
    if spot[3] != "front":
        return None
    return LANES["left" if spot[1] < 1 / 3 else "right" if spot[1] > 2 / 3 else "mid"]


def asked_set(page: Page) -> str:
    """Reads which set the question draws from the end point and height of its path."""
    d = page.get_attribute("#gscNet path", "d") or ""
    numbers = [float(n) for n in re.findall(r"-?[0-9.]+", d)]
    control_y, end_x = numbers[3], numbers[4]
    landing, peak = (end_x - 80) / 840, (330 - control_y) / 580
    return min(SETS, key=lambda s: abs(s[1] - landing) + abs(s[2] - peak))[0]


def points(page: Page) -> int:
    return int(page.inner_text("#gFb .pts").lstrip("+"))


def play_set_calls(browser: Browser, role: str, steps: tuple[str, ...], sets: bool = True) -> Page:
    """Plays a whole match as ``role``: right on the first set question, wrong on the second, skips the rest."""
    page = new_page(browser)
    setup_match(page, role, steps, sets=sets)
    page.click("#gStart")
    asked = 0
    for ri in range(6):
        for phase in steps:
            page.wait_for_selector("#gOff:enabled")
            tap_spot(page, role, ri, phase)
            page.wait_for_selector("#gFb .pts")
            want = expected_sets(ri, role) if phase == "ar" and sets else None
            has_question = page.locator("#gsc").count() > 0
            tag = f"{role} R{ri + 1} {phase}"
            if has_question != (want is not None):
                fail(f"{tag}: set question shown={has_question}, expected {want is not None}")
            if not has_question or want is None:
                page.click("#gNext")
                continue
            prompt = "You set this ball" if role == "S" else "The setter sets this ball for you"
            if prompt not in page.inner_text("#gsc"):
                fail(f"{tag}: question text reads {page.inner_text('#gsc')!r}")
            name = asked_set(page)
            options = page.locator("#gsc .setchip").all_inner_texts()
            if name not in want:
                fail(f"{tag}: asked {name}, expected one of {sorted(want)}")
            if len(options) != 4 or len(set(options)) != 4 or name not in options:
                fail(f"{tag}: options {options} for {name}")
            if any(o in UNCONFIRMED_SETS for o in options):
                fail(f"{tag}: unconfirmed set among the options {options}")
            if not page.is_enabled("#gNext"):
                fail(f"{tag}: Continue disabled during the set question")
            before = points(page)
            if asked == 0:
                page.click(f'#gsc .setchip[data-s="{name}"]')
                if points(page) != before + 30:
                    fail(f"{tag}: right set call scored {points(page) - before}, expected 30")
                if not page.inner_text("#gsc").strip().endswith(next(s[4] for s in SETS if s[0] == name)):
                    fail(f"{tag}: right answer feedback reads {page.inner_text('#gsc')!r}")
                if "Correct." not in page.inner_text("#gsc"):
                    fail(f"{tag}: right answer not confirmed")
            elif asked == 1:
                wrong = next(o for o in options if o != name)
                page.click(f'#gsc .setchip[data-s="{wrong}"]')
                if points(page) != before:
                    fail(f"{tag}: wrong set call scored {points(page) - before}")
                if f"It is {name}." not in page.inner_text("#gsc"):
                    fail(f"{tag}: wrong answer feedback reads {page.inner_text('#gsc')!r}")
                page.evaluate(f"window.__missed = {name!r}")
            asked += 1
            page.click("#gNext")
    page.wait_for_selector("#gEnd", state="visible")
    return page


def check_set_calls(browser: Browser) -> None:
    for role in ("OH1", "MB1", "S"):
        page = play_set_calls(browser, role, ("rec", "ar"))
        stats = page.inner_text("#gStats")
        if "1/2 set calls right" not in stats.replace("\n", " "):
            fail(f"{role}: end screen stats read {stats!r}")
        missed = page.evaluate("window.__missed")
        if page.inner_text("#gSetMiss") != f"Set calls to practise: {missed}":
            fail(f"{role}: practise line reads {page.inner_text('#gSetMiss')!r}")
        page.click("#gSetPractise")
        if page.get_attribute("#tabSets", "aria-selected") != "true":
            fail(f"{role}: Practise in Sets does not open the Sets tab")
        page.close()
    print("set call check: front row and setter asked their own sets, +30 for a right call", flush=True)
    for role in ("L", "OH1"):
        page = play_set_calls(browser, role, ("ar",), sets=role != "OH1")
        if page.locator("#gSetMiss").count() or "set calls right" in page.inner_text("#gStats"):
            fail(f"{role}: set call stats without any question")
        page.close()
    print("no set question for the libero, the back row or with the option off", flush=True)

    page = new_page(browser)
    setup_match(page, "OH1", ("rec", "ar"))
    if "set calls" not in page.inner_text("#gOptSum"):
        fail(f"options summary does not list set calls: {page.inner_text('#gOptSum')!r}")
    page.uncheck("#gs-ar")
    if page.is_enabled("#setGame") or not page.is_visible("#setGameHint"):
        fail("set call option not disabled without the After reception step")
    if "set calls" in page.inner_text("#gOptSum"):
        fail("options summary lists set calls without the After reception step")
    page.click("#tabSets")
    for name in UNCONFIRMED_SETS:
        page.click(f'#setchips .setchip[data-s="{name}"]')
        if "(not confirmed)" not in page.inner_text("#setcue"):
            fail(f"Sets tab does not mark {name} as not confirmed")
        page.click(f'#setchips .setchip[data-s="{name}"]')
    page.close()
    print("set call option and unconfirmed marks ok", flush=True)


def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        check_vis_scoring(browser)
        check_peek(browser)
        check_best_key(browser)
        check_set_calls(browser)
        browser.close()
    print("MATCH TEST:", "ok" if not FAIL else f"{len(FAIL)} failures", flush=True)
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
