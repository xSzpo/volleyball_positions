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

URL = (ROOT / "index.html").as_uri() + "?ff=all"
FAIL: list[str] = []
# A stored role skips the first-visit role sheet, which covers the page.
SEED_ROLE = "if (!localStorage.getItem('ksv51:role')) localStorage.setItem('ksv51:role', JSON.stringify('OH1'))"


def press_next(page: Page) -> None:
    """Presses Continue or Next and waits out the short lock that stops a double tap skipping the feedback."""
    page.click("#gNext")
    page.wait_for_selector("#gNext:not([aria-disabled])", state="attached")


def fail(message: str) -> None:
    FAIL.append(message)
    print("FAIL:", message, flush=True)


def new_page(browser: Browser) -> Page:
    page = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    page.add_init_script(SEED_ROLE)
    page.on("pageerror", lambda error: FAIL.append(f"page error: {error}"))
    page.goto(URL)
    page.wait_for_timeout(300)
    return page


def pick_role(page: Page, role: str) -> None:
    if page.is_hidden("#setupPanel"):
        page.click("#roleChip")
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
    for step in ("start", "serve", "rec", "ar"):
        page.set_checked(f"#gs-{step}", step in steps)
    page.check('input[name="gOrder"][value="order"]')
    page.set_checked("#nbGame", neighbour)
    if "ar" in steps:
        page.set_checked("#setGame", sets)


def tap_at(page: Page, x: float, y: float) -> None:
    """Taps the match court at normalised court coordinates."""
    page.locator("#courtG").scroll_into_view_if_needed()
    cx, cy = page.evaluate(
        """([x, y]) => {
            const m = document.getElementById('courtG').getScreenCTM();
            return [m.a * x * 100 + m.e, m.d * y * 100 + m.f];
        }""",
        [x, y],
    )
    page.mouse.click(cx, cy)


def tap_spot(page: Page, role: str, ri: int, phase: str, check: bool = True) -> None:
    """Picks the role's correct spot for ``phase`` in rotation ``ri`` (or I'm off court), then presses Continue."""
    spots = [(s[0], s[1], s[2]) for s in (ROWS[ri]["ar"] if phase == "ar" else ROWS[ri]["rec"])]
    found = next(((x, y) for p, x, y in spots if p == role), None)
    if found is None:
        page.click("#gOff")
    else:
        tap_at(page, *found)
    if check:
        press_next(page)


def breakdown_total(line: str) -> tuple[int, int]:
    """Adds up the parts of a points breakdown and returns (sum of the parts, the stated total)."""

    def part(pattern: str) -> int:
        found = re.search(pattern, line)
        return int(found.group(1)) if found else 0

    position = re.search(r"Position: \w+ (\d+)", line)
    total = re.search(r"Total (\d+)", line)
    assert position and total, f"breakdown without position or total: {line!r}"
    subtotal = int(position.group(1)) + part(r"speed \+(\d+)") + part(r"streak \+(\d+)")
    scaled = re.search(r"(\d+)% → (\d+)", line)
    if scaled:
        assert round(subtotal * int(scaled.group(1)) / 100) == int(scaled.group(2)), f"wrong scaling: {line!r}"
        subtotal = int(scaled.group(2))
    return subtotal + part(r"Set call: [^+]*\+(\d+)") + part(r"Neighbour: [^+]*\+(\d+)"), int(total.group(1))


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
        press_next(page)
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
    press_next(page)
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
        press_next(page)
    shown = page.inner_text("#gShown")
    if shown != "Shown: Nobody (full points) · Peeked: 1 moment":
        fail(f"end screen after one peek reads {shown!r}")
    best = page.evaluate("JSON.parse(localStorage.getItem('ksv51:gameBest'))")
    if list(best) != ["v4|OH1|rec"]:
        fail(f"best score saved under {list(best)}, expected the starting settings only")
    page.close()


def check_best_key(browser: Browser) -> None:
    """Bests from before the scoring change are ignored, and the neighbour check has its own best."""
    page = new_page(browser)
    page.evaluate("""localStorage.setItem('ksv51:gameBest', JSON.stringify({"v3|OH1|rec": 9999, "v4|OH1|rec": 500}))""")
    page.reload()
    page.wait_for_timeout(300)
    setup_match(page, "OH1", ("rec",))
    text = page.inner_text("#gBest")
    if "500" not in text:
        fail(f"best line reads {text!r}, expected the v4 best of 500")
    page.check("#nbGame")
    text = page.inner_text("#gBest")
    if text:
        fail(f"best with the neighbour check on reads {text!r}, expected none yet")
    page.close()
    print("best score key: old bests ignored, neighbour check separate", flush=True)


def check_our_serve(browser: Browser) -> None:
    """Our serve: a front-row player stands mid-zone before the serve; only the server gets an arrow."""
    page = new_page(browser)
    setup_match(page, "OH1", ("serve",))
    page.click("#gStart")
    page.wait_for_selector("#gOff:enabled")
    if "Our serve" not in page.inner_text("#gStepName"):
        fail(f"step name reads {page.inner_text('#gStepName')!r}, expected Our serve")
    tap_at(page, 0.5, 0.5)
    press_next(page)
    page.wait_for_selector("#gFb .pts")
    ring = page.locator("#courtG .me-ring circle").first
    y = float(ring.get_attribute("cy") or "nan") / 100
    if not 0.15 < y < 0.3:
        fail(f"R1 OH1 our serve spot at y {y:.2f}, expected mid-zone in the front row (y 0.21)")
    arrows = page.locator("#courtG line.route").count()
    if arrows != 1:
        fail(f"R1 our serve draws {arrows} arrows, expected 1 (the server)")
    elif not float(page.locator("#courtG line.route").get_attribute("y1") or "nan") > 100:
        fail("the server's arrow does not start behind the end line")
    feedback = page.inner_text("#gFb")
    for want in ("middle of your zone", "not confirmed", "before the serve"):
        if want not in feedback:
            fail(f"our serve feedback reads {feedback!r}, expected {want!r}")
    if "at the net" in feedback:
        fail(f"our serve feedback reads {feedback!r}, the front row should not be at the net")
    page.close()
    print("our serve: front-row spot mid-zone, only the server's arrow", flush=True)


def check_match_order(browser: Browser) -> None:
    """In order, one rotation runs Rotate, Our serve, Receive, After reception, with a story for each."""
    page = new_page(browser)
    setup_match(page, "OH1", ("start", "serve", "rec", "ar"), sets=False)
    page.click("#gStart")
    page.wait_for_selector("#gOff:enabled")
    track = page.locator("#gTrack span").all_text_contents()
    if track != ["Rotate", "Our serve", "Receive", "After reception"]:
        fail(f"R1 steps run {track}, expected Rotate, Our serve, Receive, After reception")
    stories = []
    for _ in range(4):
        page.wait_for_selector("#gOff:enabled")
        stories.append(page.inner_text("#gStory"))
        tap_at(page, 0.5, 0.5)
        press_next(page)
        press_next(page)
    if "We serve in" not in stories[1]:
        fail(f"our serve story reads {stories[1]!r}, expected 'We serve in'")
    if "We lost the rally" not in stories[2]:
        fail(f"reception story reads {stories[2]!r}, expected 'We lost the rally'")
    if "We won the rally" not in page.inner_text("#gStory"):
        fail(f"R2 rotation story reads {page.inner_text('#gStory')!r}, expected 'We won the rally'")
    page.close()
    print("match order: rotate, our serve, receive, after reception", flush=True)


MATCH_SETS = [s for s in SETS if s[0] not in UNCONFIRMED_SETS]
LANES = {"left": {"1", "0", "2"}, "mid": {"Shoot", "Til"}, "right": {"7", "6"}}


def expected_sets(ri: int, role: str) -> set[str]:
    """The calls a set question may ask ``role`` after reception in rotation ``ri``."""
    spot = next((s for s in ROWS[ri]["ar"] if s[0] == role), None)
    if spot is None or spot[3] != "front":
        return {s[0] for s in MATCH_SETS}
    return LANES["left" if spot[1] < 1 / 3 else "right" if spot[1] > 2 / 3 else "mid"]


def set_prompt(ri: int, role: str) -> str:
    """The set question's wording for ``role`` after reception in rotation ``ri``."""
    kind = next((s[3] for s in ROWS[ri]["ar"] if s[0] == role), None)
    if kind == "set":
        return "You set this ball. What is the call?"
    if kind == "front":
        return "The setter sets this ball for you. What is the call?"
    return "The setter sets this ball. What is the call?"


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
                press_next(page)
                continue
            prompt = set_prompt(ri, role)
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
                fail(f"{tag}: Next disabled during the set question")
            if "Set call: –" not in page.inner_text("#gBd"):
                fail(f"{tag}: breakdown before the set call reads {page.inner_text('#gBd')!r}")
            before = points(page)
            if asked == 0:
                page.click(f'#gsc .setchip[data-s="{name}"]')
                if points(page) != before + 30:
                    fail(f"{tag}: right set call scored {points(page) - before}, expected 30")
                if not page.inner_text("#gsc").strip().endswith(next(s[4] for s in SETS if s[0] == name)):
                    fail(f"{tag}: right answer feedback reads {page.inner_text('#gsc')!r}")
                if f"Right: {name}" not in page.inner_text("#gsc"):
                    fail(f"{tag}: right answer not confirmed")
                if page.locator("#gsc .setok").count() != 1 or "Set call: right +30" not in page.inner_text("#gBd"):
                    fail(f"{tag}: right answer not marked right: {page.inner_text('#gBd')!r}")
            elif asked == 1:
                wrong = next(o for o in options if o != name)
                page.click(f'#gsc .setchip[data-s="{wrong}"]')
                if points(page) != before:
                    fail(f"{tag}: wrong set call scored {points(page) - before}")
                if f"Wrong: you said {wrong}, it is {name}" not in page.inner_text("#gsc"):
                    fail(f"{tag}: wrong answer feedback reads {page.inner_text('#gsc')!r}")
                if page.locator("#gsc .setbad").count() != 1 or "Set call: wrong +0" not in page.inner_text("#gBd"):
                    fail(f"{tag}: wrong answer not marked wrong: {page.inner_text('#gBd')!r}")
                page.evaluate(f"window.__missed = {name!r}")
            asked += 1
            press_next(page)
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
    page = play_set_calls(browser, "L", ("ar",))
    if "1/2 set calls right" not in page.inner_text("#gStats").replace("\n", " "):
        fail(f"libero: end screen stats read {page.inner_text('#gStats')!r}")
    page.close()
    page = play_set_calls(browser, "OH1", ("ar",), sets=False)
    if page.locator("#gSetMiss").count() or "set calls right" in page.inner_text("#gStats"):
        fail("OH1: set call stats with the option off")
    page.close()
    print("set question for the libero and the back row, none with the option off", flush=True)

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


def in_view(page: Page, selector: str) -> bool:
    """Whether the element is fully inside the phone's viewport."""
    box = page.locator(selector).bounding_box()
    return box is not None and box["y"] >= 0 and box["y"] + box["height"] <= 844


def check_tap_then_continue(browser: Browser) -> None:
    """A tap only places a marker; Continue scores the last tap, then Next; off court is undone by a tap."""
    page = new_page(browser)
    setup_match(page, "OH1", ("rec",))
    page.click("#gStart")
    page.wait_for_selector("#gOff:enabled")
    if page.inner_text("#gNext") != "CONTINUE" or page.is_enabled("#gNext"):
        fail(
            f"before a tap the primary button reads {page.inner_text('#gNext')!r}, enabled={page.is_enabled('#gNext')}"
        )
    if not in_view(page, "#gNext"):
        fail("Continue is below the fold")
    spot = next((x, y) for p, x, y in ROWS[0]["rec"] if p == "OH1")
    tap_at(page, 0.5, 0.03)
    if page.locator("#gFb .pts").count() or page.locator("#courtG .myspot").count() != 1:
        fail("the first tap scored the moment or placed no marker")
    tap_at(page, *spot)
    if page.locator("#gFb .pts").count() or page.locator("#courtG .myspot").count() != 1:
        fail("the second tap scored the moment or left two markers")
    if page.inner_text("#gNext") != "CONTINUE" or not page.is_enabled("#gNext") or not page.is_enabled("#gHelp"):
        fail(f"after a tap the primary button reads {page.inner_text('#gNext')!r}, or it or Help is disabled")
    press_next(page)
    if "Spot on" not in page.inner_text("#gFb"):
        fail(f"Continue did not score the last tap: {page.inner_text('#gFb')!r}")
    if page.inner_text("#gNext") != "NEXT":
        fail(f"after scoring the primary button reads {page.inner_text('#gNext')!r}")
    press_next(page)
    page.wait_for_selector("#gOff:enabled")
    page.click("#gOff")
    if page.get_attribute("#gOff", "aria-pressed") != "true" or not page.is_enabled("#gNext"):
        fail("I'm off court is not selected or Continue stays disabled")
    spot = next((x, y) for p, x, y in ROWS[1]["rec"] if p == "OH1")
    tap_at(page, *spot)
    if page.get_attribute("#gOff", "aria-pressed") != "false":
        fail("a court tap does not unselect I'm off court")
    press_next(page)
    if "Spot on" not in page.inner_text("#gFb"):
        fail(f"off court then a tap did not score the tap: {page.inner_text('#gFb')!r}")
    page.close()
    print("tap then Continue: marker moves, Continue scores the last pick, then Next", flush=True)


def neighbour_answer(ri: int, role: str, question: str) -> str:
    """Works out the answer to a neighbour question from the rotational lineup."""
    rows = [ROWS[ri]["front"], ROWS[ri]["back"]]
    r = next(k for k, row in enumerate(rows) if role in row)
    c = rows[r].index(role)
    if "behind" in question:
        return str(rows[1 - r][c])
    return str(rows[r][c - 1] if "on your left" in question else rows[r][c + 1])


def check_breakdown(browser: Browser) -> None:
    """The points line adds up to the points of every moment, with help, a shown setter and both bonuses."""
    page = new_page(browser)
    setup_match(page, "OH1", ("rec", "ar"), vis="ref", neighbour=True)
    page.click("#gStart")
    lines = []
    for ri in range(6):
        for phase in ("rec", "ar"):
            page.wait_for_selector("#gOff:enabled")
            if ri == 1:
                page.click("#gHelp")
            tap_spot(page, "OH1", ri, phase)
            page.wait_for_selector("#gBd")
            right = ri % 2 == 0
            if page.locator("#gnb").count():
                want = neighbour_answer(ri, "OH1", page.inner_text("#gnb"))
                page.locator(
                    f'#gnb button[data-p="{want}"]' if right else f'#gnb button:not([data-p="{want}"])'
                ).first.click()
            if page.locator("#gsc").count():
                want = asked_set(page)
                page.locator(
                    f'#gsc [data-s="{want}"]' if right else f'#gsc .setchip:not([data-s="{want}"])'
                ).first.click()
            line = page.inner_text("#gBd")
            lines.append(line)
            parts, total = breakdown_total(line)
            if not parts == total == points(page):
                fail(f"R{ri + 1} {phase}: breakdown {line!r} adds up to {parts}, total {total}, scored {points(page)}")
            if ri == 1 and "help used, 60%" not in line:
                fail(f"help not shown in the breakdown: {line!r}")
            if "Setter 70% →" not in line:
                fail(f"shown setter not in the breakdown: {line!r}")
            if not in_view(page, "#gNext"):
                fail(f"R{ri + 1} {phase}: Continue is below the fold")
            press_next(page)
    if not any("Neighbour: right" in line for line in lines) or not any("Set call: wrong" in line for line in lines):
        fail(f"breakdowns lack a right neighbour or a wrong set call: {lines}")
    page.wait_for_selector("#gEnd", state="visible")
    page.close()
    page = new_page(browser)
    setup_match(page, "OH1", ("rec",))
    page.click("#gStart")
    page.wait_for_selector("#gOff:enabled")
    tap_at(page, 0.5, 0.03)
    press_next(page)
    if not page.inner_text("#gBd").startswith("Position: wrong 0"):
        fail(f"a wrong spot reads {page.inner_text('#gBd')!r}")
    page.close()
    print("breakdown adds up to the points", flush=True)


def check_end_screen(browser: Browser) -> None:
    """The solo end screen offers Replay, Play again and Change settings without scrolling, and they work."""
    page = new_page(browser)
    setup_match(page, "OH1", ("rec",))
    page.click("#gStart")
    while not page.is_visible("#gEnd"):
        if page.is_enabled("#gOff"):
            tap_at(page, 0.5, 0.03)
        press_next(page)
    for button in ("#gReplay", "#gAgain", "#gSettings"):
        if not page.is_visible(button) or not in_view(page, button):
            fail(f"solo end screen: {button} not visible without scrolling")
    if page.is_visible("#gToLobby") or page.is_visible("#gEndWait"):
        fail("solo end screen shows online buttons")
    page.click("#gAgain")
    if not page.is_visible("#gPlay") or page.inner_text("#gStepName") != "Reception · moment 1 of 6":
        fail(f"Play again did not start a new match: {page.inner_text('#gStepName')!r}")
    page.close()
    print("solo end screen buttons ok", flush=True)


def check_court_not_covered(browser: Browser) -> None:
    """While answering, the buttons do not cover the court; after scoring they stay in view."""
    page = new_page(browser)
    setup_match(page, "OH1", ("rec",))
    page.set_viewport_size({"width": 390, "height": 640})
    page.click("#gStart")
    page.wait_for_selector("#gOff:enabled")
    page.evaluate("window.scrollTo(0, 0)")
    box = page.locator("#courtG").bounding_box()
    if box is None or box["y"] + box["height"] <= 640:
        fail("court is not cut by the fold, the test proves nothing")
    else:
        x, y = box["x"] + box["width"] / 2, 630
        inside = page.evaluate(
            "([x, y]) => document.getElementById('courtG').contains(document.elementFromPoint(x, y))", [x, y]
        )
        if not inside:
            fail("the button row covers the court while answering")
        page.mouse.click(x, y)
        if not page.is_visible("#gPlay") or page.locator("#courtG .myspot").count() != 1:
            fail("a tap on the lower court did not place a marker")
    press_next(page)
    if not in_view(page, "#gNext"):
        fail("Next is below the fold after scoring")
    page.close()
    print("court not covered while answering", flush=True)


def check_double_check(browser: Browser) -> None:
    """A double tap on Continue keeps the feedback on screen."""
    page = new_page(browser)
    setup_match(page, "OH1", ("rec",))
    page.click("#gStart")
    tap_spot(page, "OH1", 0, "rec", check=False)
    page.evaluate("() => { const b = document.getElementById('gNext'); b.click(); b.click(); }")
    if "moment 1 of" not in page.inner_text("#gStepName") or not page.locator("#gFb .pts").count():
        fail(f"a double tap on Continue skipped the feedback: {page.inner_text('#gStepName')!r}")
    press_next(page)
    if "moment 2 of" not in page.inner_text("#gStepName"):
        fail("Next does not work after the double tap lock")
    page.close()
    print("double tap on Continue keeps the feedback", flush=True)


def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        check_vis_scoring(browser)
        check_peek(browser)
        check_best_key(browser)
        check_our_serve(browser)
        check_match_order(browser)
        check_set_calls(browser)
        check_tap_then_continue(browser)
        check_breakdown(browser)
        check_end_screen(browser)
        check_court_not_covered(browser)
        check_double_check(browser)
        browser.close()
    print("MATCH TEST:", "ok" if not FAIL else f"{len(FAIL)} failures", flush=True)
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
