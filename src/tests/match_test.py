"""Playwright test of solo match scoring and the Attack step picture in index.html.

Usage: python src/tests/match_test.py [--shard K/N] [--list]

--shard 1/4 runs one quarter of the checks; the four quarters together run each check once.
"""

import argparse
import re
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, Page, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from data import ATTACK_LINE, RULES_MODES, SETS, UNCONFIRMED_SETS, Row, RulesMode, lineup  # noqa: E402

# The app opens in Simplified KSV.
ROWS = [lineup(ri, "simple") for ri in range(6)]


def drill_ri(question: str) -> int:
    """The rotation of a Drill question titled by the setter's zone, "H5 · Reception"."""
    m = re.match(r"H([1-6]) · ", question)
    if not m:
        raise AssertionError(f"Drill question {question!r} is not named H<n>")
    return next(ri for ri in range(6) if ROWS[ri]["setter"] == int(m.group(1)))


URL = (ROOT / "index.html").as_uri() + "?anim=0"
FAIL: list[str] = []
# A stored role skips the first-visit role sheet, which covers the page.
SEED_ROLE = (
    "if (!localStorage.getItem('ksv51:role')) localStorage.setItem('ksv51:role', JSON.stringify('OH1'));"
    " localStorage.setItem('ksv51:officialReset', JSON.stringify('1'))"
)


def press_next(page: Page) -> None:
    """Presses Continue or Next and waits out the short lock that stops a double tap skipping the feedback."""
    page.click("#gNext")
    page.wait_for_selector("#gNext:not([aria-disabled])", state="attached")


def fail(message: str) -> None:
    FAIL.append(message)
    print("FAIL:", message, flush=True)


def new_page(browser: Browser, rules: str = "simple", query: str = "?anim=0") -> Page:
    page = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    page.add_init_script(SEED_ROLE)
    page.add_init_script(f"localStorage.setItem('ksv51:rulesMode', JSON.stringify('{rules}'))")
    page.on("pageerror", lambda error: FAIL.append(f"page error: {error}"))
    page.goto(URL.split("?")[0] + query)
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


def tap_at(page: Page, x: float, y: float, court: str = "courtG") -> None:
    """Taps a court at normalised court coordinates."""
    page.locator(f"#{court}").scroll_into_view_if_needed()
    cx, cy = page.evaluate(
        """([x, y, id]) => {
            const m = document.getElementById(id).getScreenCTM();
            return [m.a * x * 100 + m.e, m.d * y * 100 + m.f];
        }""",
        [x, y, court],
    )
    page.mouse.click(cx, cy)


def tap_spot(page: Page, role: str, ri: int, phase: str, check: bool = True) -> None:
    """Picks the role's correct spot for ``phase`` in rotation ``ri`` (or I'm off court), then presses Continue."""
    spots = [(s[0], s[1], s[2]) for s in (ROWS[ri]["ar"] if phase == "ar" else ROWS[ri]["rec"])]
    found = next(((x, y) for p, x, y in spots if p == role), None)
    if phase == "ar" and found is not None:
        found = pass_lands(page, ri).get(role, found)
    if found is None:
        page.click("#gOff")
    else:
        tap_at(page, *found)
    if check:
        press_next(page)


def pass_lands(page: Page, ri: int) -> dict[str, tuple[float, float]]:
    """The Attack spots: everyone as the pass reaches the setter in Learn's play, the covers on their cover spot.

    L, the deep OH and the back OP are graded on the spot they stand on at the spike.
    """
    found = page.evaluate(
        """(ri) => {
            const stages = window.ksvLearn.stages(ri, 'rec');
            const pass = stages[1];
            return {
                lands: window.ksvLearn.at(ri, 'rec', pass.start + pass.ball.ms),
                spike: stages[stages.length - 1].from,
                rules: String(localStorage.getItem('ksv51:rulesMode')).includes('official') ? 'official' : 'simple',
            };
        }""",
        ri,
    )
    row = lineup(ri, found["rules"])
    spots = {p: (at["x"], at["y"]) for p, at in found["lands"].items()}
    for p, at in found["spike"].items():
        if cover_job(row, p):
            spots[p] = (at["x"], at["y"])
    return spots


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


def check_vis_fixed(browser: Browser) -> None:
    """Solo Match offers no Show on court picker in play and scores every moment with the setting at Start."""
    page = new_page(browser)
    setup_match(page, "OH1", ("rec",), "ref")
    page.click("#gStart")
    page.wait_for_selector("#gOff:enabled")
    if page.locator("#gVisPlay").count() or page.locator('#gPlay .vis[data-vis="game"]').count():
        fail("solo Match shows a Show on court picker in play")
    page.evaluate('document.querySelector(\'.vis[data-vis="game"] [data-v="all"]\').click()')
    scored = []
    for ri in range(2):
        page.wait_for_selector("#gOff:enabled")
        tap_spot(page, "OH1", ri, "rec")
        page.wait_for_selector("#gFb .pts")
        scored.append(points(page))
        if "Setter 70%" not in page.inner_text("#gBd"):
            fail(f"moment {ri + 1} scored {page.inner_text('#gBd')!r}, expected the Setter multiplier from Start")
        press_next(page)
    print("points with Setter fixed at Start:", scored, flush=True)
    if not all(70 <= p <= 98 for p in scored):
        fail(f"moments scored {scored}, expected 70% of the full score")
    while not page.is_visible("#gEnd"):
        if page.is_enabled("#gOff") and page.is_visible("#gOff"):
            page.click("#gOff")
        press_next(page)
    shown = page.inner_text("#gShown")
    if shown != "Shown: Setter (70% points)":
        fail(f"end screen reads {shown!r}")
    best = page.evaluate("JSON.parse(localStorage.getItem('ksv51:gameBest'))")
    if list(best) != ["v9|OH1|rec|ref"]:
        fail(f"best score saved under {list(best)}, expected the starting settings only")
    page.close()


def check_best_key(browser: Browser) -> None:
    """Bests from another scoring are ignored, and the neighbour check has its own best."""
    bests = '{"v5|OH1|rec": 9999, "v6|OH1|rec": 9999, "v7|OH1|rec": 500, "v8|OH1|rec": 9999, "v9|OH1|rec": 700}'
    seed = f"localStorage.setItem('ksv51:gameBest', JSON.stringify({bests}))"
    page = new_page(browser)
    page.evaluate(seed)
    page.reload()
    page.wait_for_timeout(300)
    setup_match(page, "OH1", ("rec",))
    text = page.inner_text("#gBest")
    if "700" not in text:
        fail(f"best line reads {text!r}, expected the v9 best of 700")
    page.check("#nbGame")
    text = page.inner_text("#gBest")
    if text:
        fail(f"best with the neighbour check on reads {text!r}, expected none yet")
    page.close()
    print("best score key: old bests ignored, neighbour check separate", flush=True)


def check_our_serve(browser: Browser) -> None:
    """Our serve: no ball, a front-row player stands mid-zone before the serve; only the server gets an arrow."""
    page = new_page(browser)
    setup_match(page, "OH1", ("serve",))
    page.click("#gStart")
    page.wait_for_selector("#gOff:enabled")
    if "Our serve" not in page.inner_text("#gStepName"):
        fail(f"step name reads {page.inner_text('#gStepName')!r}, expected Our serve")
    if not page.inner_text("#gStory").endswith("We serve. Where do you stand?"):
        fail(f"R1 OH1 our serve question reads {page.inner_text('#gStory')!r}")
    if court_picture(page, "courtG")["ball"]:
        fail("our serve draws a ball before the answer, expected none")
    tap_at(page, 0.5, 0.5)
    press_next(page)
    page.wait_for_selector("#gFb .pts")
    ring = page.locator("#courtG .me-ring circle").first
    y = float(ring.get_attribute("cy") or "nan") / 100
    if not 0.15 < y < 0.3:
        fail(f"R1 OH1 our serve spot at y {y:.2f}, expected mid-zone in the front row (y 0.21)")
    arrows = page.locator("#courtG g.rt:not(.glideroute) line.route").count()
    if arrows != 1:
        fail(f"R1 our serve draws {arrows} arrows, expected 1 (the server)")
    elif not float(page.locator("#courtG g.rt:not(.glideroute) line.route").get_attribute("y1") or "nan") > 100:
        fail("the server's arrow does not start behind the end line")
    feedback = page.inner_text("#gFb")
    for want in ("middle of your zone", "not confirmed", "before the serve"):
        if want not in feedback:
            fail(f"our serve feedback reads {feedback!r}, expected {want!r}")
    if "at the net" in feedback:
        fail(f"our serve feedback reads {feedback!r}, the front row should not be at the net")
    if court_picture(page, "courtG")["ball"]:
        fail("our serve feedback draws a ball, expected none")
    page.close()
    page = new_page(browser)
    pick_role(page, "OH1")
    page.click("#tabDrill")
    page.click("#dOpts > summary")
    for _ in range(100):
        if page.inner_text("#dq").endswith("· Our serve"):
            break
        page.dblclick("#dReset")
    else:
        fail("drill: Our serve never came up")
    if court_picture(page, "courtD")["ball"]:
        fail("drill our serve draws a ball before the answer, expected none")
    tap_at(page, 0.5, 0.5, court="courtD")
    page.click("#nextBtn")
    if court_picture(page, "courtD")["ball"]:
        fail("drill our serve feedback draws a ball, expected none")
    page.close()
    page = new_page(browser)
    setup_match(page, "S", ("serve",))
    page.click("#gStart")
    page.wait_for_selector("#gOff:enabled")
    if not page.inner_text("#gStory").endswith("You serve. Where do you go after it?"):
        fail(f"R1 server question reads {page.inner_text('#gStory')!r}, expected where they go after the serve")
    page.close()
    print(
        "our serve: no ball in Drill and Match, server asked where they go, front-row spot mid-zone, one arrow",
        flush=True,
    )


def check_off_court_pill(browser: Browser) -> None:
    """A tap on the off court pill toggles I'm off court; the feedback then shows the solid pill."""
    page = new_page(browser, rules="official")
    setup_match(page, "MB2", ("rec",))
    page.click("#gStart")
    page.wait_for_selector("#gOff:enabled")
    tap_at(page, 0.12, 1.07)
    if page.get_attribute("#gOff", "aria-pressed") != "true" or page.locator("#courtG .myspot").count():
        fail("a tap on the off court pill did not pick I'm off court")
    tap_at(page, 0.12, 1.07)
    if page.get_attribute("#gOff", "aria-pressed") != "false" or page.is_enabled("#gNext"):
        fail("a second tap on the off court pill did not clear I'm off court")
    tap_at(page, 0.12, 1.07)
    press_next(page)
    page.wait_for_selector("#gFb .pts")
    if "Spot on" not in page.inner_text("#gFb"):
        fail(f"off court via the pill scored {page.inner_text('#gFb')!r}, expected Spot on")
    texts: list[str] = page.eval_on_selector_all("#courtG > text", "els => els.map(e => e.textContent)")
    if "you: off court" not in texts:
        fail(f"off court feedback court reads {texts}, expected the solid pill")
    page.close()
    print("off court pill: toggles I'm off court, feedback shows the solid pill", flush=True)


def check_libero_hint(browser: Browser) -> None:
    """The libero's hint at the R3 serve, off court, names the rule set in play."""
    for rules, want, unwanted in (
        ("simple", "MB serves", "official rules"),
        ("official", "official rules", "MB serves"),
    ):
        page = new_page(browser, rules=rules)
        setup_match(page, "L", ("serve",))
        page.click("#gStart")
        for _ in range(2):
            page.wait_for_selector("#gOff:enabled")
            tap_at(page, 0.5, 0.5)
            press_next(page)
            press_next(page)
        page.wait_for_selector("#gOff:enabled")
        page.click("#gHelp")
        hint = page.inner_text("#gFb")
        if want not in hint or unwanted in hint:
            fail(f"{rules} L hint at the R3 serve reads {hint!r}, expected {want!r}")
        page.close()
    print("libero hint: Simplified names MB as the server, Official the libero rule", flush=True)


def check_hint_rule_numbers(browser: Browser) -> None:
    """A Match hint that cites a rule of thumb by number points to that rule in the Learn list."""
    cases = (("OH1", 0, "outside starts left"), ("L", 0, "cover first, then base"), ("OP", 3, "opposite covers deep"))
    for rules in ("simple", "official"):
        for role, rotation, title in cases:
            page = new_page(browser, rules=rules)
            setup_match(page, role, ("ar",), sets=False)
            page.click("#gStart")
            for _ in range(rotation):
                page.wait_for_selector("#gOff:enabled")
                tap_at(page, 0.5, 0.5)
                press_next(page)
                press_next(page)
            page.wait_for_selector("#gOff:enabled")
            page.click("#gHelp")
            hint = page.inner_text("#gFb")
            cited = re.search(r"rule (\d+) of the Rules of thumb", hint)
            titles: list[str] = page.eval_on_selector_all("#thumbs li > b", "els => els.map(e => e.textContent)")
            number = int(cited[1]) if cited else 0
            if not 1 <= number <= len(titles) or title not in titles[number - 1]:
                fail(f"{rules} {role} R{rotation + 1} hint {hint!r} does not cite {title!r} in {titles}")
            page.close()
    print("hint rule numbers: each cited rule of thumb is the right one", flush=True)


ZONE_SPOTS = [(0.17, 0.21), (0.5, 0.21), (0.83, 0.21), (0.17, 0.71), (0.5, 0.71), (0.83, 0.71)]


def fill_rotate(page: Page) -> None:
    """Places the Rotate markers on distinct zones, whatever the order, until Continue is enabled."""
    for x, y in ZONE_SPOTS:
        if page.locator("#gNext").is_enabled():
            return
        tap_at(page, x, y)
    if not page.locator("#gNext").is_enabled():
        page.click("#gOff")


def rotate_lineup(page: Page, ri: int, role: str) -> tuple[list[str], dict[str, tuple[float, float]]]:
    """The markers Rotate asks for in order (setter, you, your overlap partners) and each right spot.

    In R3 and R6 the middle who serves from zone 1 is nobody's overlap partner.
    """
    spots = {
        str(o["p"]): (float(o["x"]), float(o["y"])) for o in page.evaluate(f"window.ksvLearn.players({ri}, 'start')")
    }
    order = [] if role == "S" else ["S"]
    order.append(role)
    serving = page.evaluate(f"window.ksvLearn.server({ri})") if ri in (2, 5) else None
    if role not in spots or role == serving:
        return order, spots
    grid = {(round(x * 3 - 0.5), y > 0.42): p for p, (x, y) in spots.items() if p != serving}
    col, back = round(spots[role][0] * 3 - 0.5), spots[role][1] > 0.42
    for key in [(col, not back), (col - 1, back), (col + 1, back)]:
        mate = grid.get(key)
        if mate and mate not in order:
            order.append(mate)
    return order, spots


def setter_zone(spots: dict[str, tuple[float, float]]) -> int:
    x, y = spots["S"]
    return {(0, False): 4, (1, False): 3, (2, False): 2, (0, True): 5, (1, True): 6, (2, True): 1}[
        (round(x * 3 - 0.5), y > 0.42)
    ]


def answer_match_rotate(page: Page, ctx: str, ri: int, role: str, wrong: bool = False) -> str:
    """Places every Match Rotate marker in the asked order and presses Continue; returns the asked name."""
    order, spots = rotate_lineup(page, ri, role)
    name = page.inner_text("#gTitle")
    if name != f"H{setter_zone(spots)}":
        fail(f"{ctx}: Rotate title {name!r}, expected H{setter_zone(spots)} alone")
    if page.locator("#courtG g.mk").count():
        fail(f"{ctx}: teammates shown before the answer with Show on court Everyone")
    for k, mate in enumerate(order):
        named = "the other middle" if mate == "OM" else mate
        who = "you stand" if mate == role else "the setter (S) stands" if mate == "S" else f"{named} stands"
        if page.inner_text("#gAsk") != f"Tap where {who}.":
            fail(f"{ctx}: prompt {page.inner_text('#gAsk')!r}, expected 'Tap where {who}.'")
        if page.locator("#gNext").is_enabled():
            fail(f"{ctx}: Continue enabled before every marker is placed")
        x, y = spots[mate]
        if wrong and k == 0:
            x, y = next(
                (cx, cy)
                for cx, cy in ((0.17, 0.95), (0.5, 0.95), (0.83, 0.95), (0.17, 0.45), (0.83, 0.45))
                if abs(cx - x) > 0.2 and all(abs(cx - ox) + abs(cy - oy) > 0.2 for ox, oy in spots.values())
            )
        tap_at(page, x, y)
    if not page.inner_text("#gAsk").startswith("All placed") or not page.locator("#gNext").is_enabled():
        fail(f"{ctx}: Continue not ready after placing {order}: {page.inner_text('#gAsk')!r}")
    press_next(page)
    grades = page.inner_text("#gFb .rotgrades")
    right = " · ".join(f"{'You' if m == role else 'The other middle' if m == 'OM' else m}: right" for m in order)
    if not wrong and grades != right:
        fail(f"{ctx}: grades {grades!r}, expected {right!r}")
    if wrong and not grades.startswith(f"{order[0]}: wrong"):
        fail(f"{ctx}: the setter one zone off graded {grades!r}")
    if page.inner_text("#gTitle") != name:
        fail(f"{ctx}: title after the answer {page.inner_text('#gTitle')!r}, expected {name!r}")
    if page.inner_text("#gAsk"):
        fail(f"{ctx}: the prompt stays after the answer: {page.inner_text('#gAsk')!r}")
    return name


def check_match_rotate(browser: Browser) -> None:
    """Match Rotate names the rotation H<n> alone, asks every marker, grades each one and scores at x1."""
    page = new_page(browser)
    setup_match(page, "OH1", ("start",), vis="all")
    page.click("#gStart")
    for ri in range(6):
        ctx = f"Rotate R{ri + 1}"
        page.wait_for_selector("#gOff:enabled")
        wrong = ri == 5
        answer_match_rotate(page, ctx, ri, "OH1", wrong)
        line = page.inner_text("#gBd")
        parts, total = breakdown_total(line)
        if parts != total or "%" in line:
            fail(f"{ctx}: breakdown {line!r} does not add up at x1")
        want = "Position: wrong 0" if wrong else "Position: exact 100"
        if not line.startswith(want):
            fail(f"{ctx}: breakdown {line!r}, expected {want!r}")
        press_next(page)
    page.close()
    print("match rotate: H name, every marker asked and graded, x1 scoring", flush=True)


R_NAME = re.compile(r"\bR[1-6]\b")
# The whole Match tab, closed folds and mistakes lists included, and every aria-label in it.
GAME_TEXT_JS = (
    "() => { const g = document.getElementById('game');"
    " return [g.textContent, ...[...g.querySelectorAll('[aria-label]')].map(e => e.getAttribute('aria-label'))]"
    ".join(' | '); }"
)


def r_name_in_game(page: Page, ctx: str) -> bool:
    """Fails and returns True when any Match text or aria-label names a rotation R<n>."""
    text = page.evaluate(GAME_TEXT_JS)
    found = R_NAME.search(text)
    if found:
        fail(f"{ctx}: Match names a rotation by R: ...{text[max(0, found.start() - 80) : found.end() + 40]!r}")
    return bool(found)


def check_match_h_names(browser: Browser, rules: RulesMode, role: str) -> None:
    """Every Match text names a rotation H<n> only: setup, story, title, hints, feedback, mistakes and end screen."""
    ctx = f"{rules} {role}"
    page = new_page(browser, rules)
    setup_match(page, role, ("start", "serve", "rec", "ar"))
    if r_name_in_game(page, f"{ctx} setup"):
        page.close()
        return
    page.click("#gStart")
    moments = 0
    while not page.is_visible("#gEnd") and moments < 30:
        page.wait_for_selector("#gOff:enabled")
        moments += 1
        if not re.fullmatch(r"H[1-6]", page.inner_text("#gTitle")):
            fail(f"{ctx}: title {page.inner_text('#gTitle')!r}, expected H<n>")
        if page.inner_text("#gStepName").startswith("Rotation"):
            fill_rotate(page)
        else:
            for _ in range(2):
                if page.is_enabled("#gHelp"):
                    page.click("#gHelp")
            if r_name_in_game(page, f"{ctx} moment {moments} hint"):
                break
            page.click("#gOff")
            if not page.locator("#gNext").is_enabled():
                page.click("#gOff")
        press_next(page)
        if r_name_in_game(page, f"{ctx} moment {moments} feedback"):
            break
        if page.is_visible("#gNext") and page.is_enabled("#gNext"):
            press_next(page)
    if not page.is_visible("#gEnd"):
        page.close()
        return
    if not page.locator("#gMist li").count():
        fail(f"{ctx}: no mistakes listed on the end screen")
    r_name_in_game(page, f"{ctx} end screen")
    page.close()
    print(f"match names {ctx}: H<n> only in every Match text", flush=True)


def check_learn_keeps_r_names(browser: Browser) -> None:
    """Learn keeps the full R<n> (H<n>) name that Match drops."""
    page = new_page(browser)
    page.click("#tabLearn")
    if not re.match(r"R[1-6] \(H[1-6]\) · ", page.inner_text("#learnTag")):
        fail(f"Learn lost the R<n> (H<n>) name: {page.inner_text('#learnTag')!r}")
    page.close()
    print("match names: Learn keeps R<n> (H<n>)", flush=True)


def check_match_order(browser: Browser) -> None:
    """In order, one rotation runs Rotate, Our serve, Receive, Attack, with a story for each."""
    page = new_page(browser)
    setup_match(page, "OH1", ("start", "serve", "rec", "ar"), sets=False)
    page.click("#gStart")
    page.wait_for_selector("#gOff:enabled")
    track = page.locator("#gTrack span").all_text_contents()
    if track != ["Rotate", "Our serve", "Receive", "Attack"]:
        fail(f"R1 steps run {track}, expected Rotate, Our serve, Receive, Attack")
    stories = []
    for _ in range(4):
        page.wait_for_selector("#gOff:enabled")
        stories.append(page.inner_text("#gStory"))
        if "Rotation" in page.inner_text("#gStepName"):
            fill_rotate(page)
        else:
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
    print("match order: rotate, our serve, receive, attack", flush=True)


MATCH_SETS = [s for s in SETS if s[0] not in UNCONFIRMED_SETS]
LANES = {"left": {"1", "0", "2"}, "mid": {"Shoot", "4"}, "right": {"7", "6"}}
BACK_LANES = {"left": {"C"}, "mid": {"B"}, "right": {"A"}}


def third(x: float) -> str:
    return "left" if x < 1 / 3 else "right" if x > 2 / 3 else "mid"


def expected_sets(ri: int, role: str) -> set[str]:
    """The calls a set question may ask ``role`` after reception in rotation ``ri``."""
    spot = next((s for s in ROWS[ri]["ar"] if s[0] == role), None)
    if cover_job(ROWS[ri], role):
        return {s[0] for s in MATCH_SETS}
    if spot is not None and spot[3] == "front":
        return LANES[third(spot[1])]
    if spot is not None and spot[3] == "back":
        return BACK_LANES[third(spot[1])]
    return {s[0] for s in MATCH_SETS}


def set_prompt(ri: int, role: str) -> str:
    """The set question's wording for ``role`` after reception in rotation ``ri``."""
    kind = next((s[3] for s in ROWS[ri]["ar"] if s[0] == role), None)
    if kind == "set":
        return "You set this ball. What is the call?"
    if kind in ("front", "back") and not cover_job(ROWS[ri], role):
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
    for role in ("OH1", "MB", "OP", "S"):
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
    print(
        "set call check: front row and setter asked their own sets, a covering OP any set, +30 for a right call",
        flush=True,
    )
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
        fail("set call option not disabled without the Attack step")
    if "set calls" in page.inner_text("#gOptSum"):
        fail("options summary lists set calls without the Attack step")
    page.click("#tabSets")
    if "not confirmed" in page.inner_text("#setcue"):
        fail(f"Sets tab text reads {page.inner_text('#setcue')!r}")
    for name in (s[0] for s in SETS):
        chip = f'#setchips .setchip[data-s="{name}"]'
        page.click(chip)
        want = name in UNCONFIRMED_SETS
        marked = "unconf" in (page.get_attribute(chip, "class") or "").split()
        cue = "(not confirmed)" in page.inner_text("#setcue")
        if marked != want or cue != want:
            fail(f"Sets tab marks {name}: chip {marked}, cue {cue}, expected {want}")
        page.click(chip)
    page.close()
    print("set call option and Sets tab marks ok", flush=True)


SET_NAMES = [s[0] for s in SETS]
REMOVED_SETS = ("Po", "Til")


def named_calls(text: str) -> list[str]:
    """The set calls a Sets tab text names, without zone numbers and the 3 m line."""
    text = re.sub(r"zone [0-9]|3 m", "", text)
    return re.findall(r"\b(?:Shoot|Po|Til|[0-9]|[A-C])\b", text)


def check_sets_tab(browser: Browser) -> None:
    """The Sets tab shows exactly the sets in SETS, back sets dashed; stored data naming a removed set is harmless."""
    for name in REMOVED_SETS:
        if name in SET_NAMES:
            fail(f"removed set {name} is back in SETS")
    page = new_page(browser)
    page.add_init_script(
        "localStorage.setItem('ksv51:stats2', JSON.stringify({'OH1|0|ar': {ok: 0, miss: 2}}));"
        "localStorage.setItem('ksv51:gameBest', JSON.stringify({'v5|MB|ar|0|0|none|1|1': 90, 'Po|Til': 50}));"
    )
    page.reload()
    page.click("#tabSets")
    chips = page.locator("#setchips .setchip").all_inner_texts()
    if chips != SET_NAMES:
        fail(f"Sets tab chips {chips}, expected {SET_NAMES}")
    cue = page.inner_text("#setcue")
    if sorted(named_calls(cue)) != sorted(SET_NAMES):
        fail(f"Sets tab text names {named_calls(cue)}, expected {SET_NAMES}: {cue!r}")
    labels = page.locator("#netS text").all_text_contents()
    if any(name in labels for name in REMOVED_SETS) or not all(name in labels for name in SET_NAMES):
        fail(f"Sets diagram labels {labels}")
    for s in SETS:
        chip = page.locator(f'#setchips .setchip[data-s="{s[0]}"]')
        if s[3] not in (chip.get_attribute("class") or "").split():
            fail(f"chip {s[0]} has no {s[3]} class")
        chip.click()
        text = page.inner_text("#setcue")
        if any(name in named_calls(text) for name in REMOVED_SETS):
            fail(f"{s[0]} text names a removed set: {text!r}")
        if s[3] == "back" and "behind the 3 m line" not in text:
            fail(f"{s[0]} text does not say behind the 3 m line: {text!r}")
        chip.click()
    dashed = page.locator("#netS path[stroke-dasharray]").count()
    if dashed != sum(s[3] == "back" for s in SETS):
        fail(f"{dashed} dashed paths on the Sets diagram")
    answers = page.locator("#setanswers .setchip").all_inner_texts()
    if answers != SET_NAMES:
        fail(f"quiz options {answers}, expected {SET_NAMES}")
    for _ in range(12):
        page.locator("#setanswers .setchip").first.click()
        page.click("#snext")
    page.click("#tabDrill")
    page.click("#reviewBtn")
    page.close()
    print("Sets tab lists exactly the sets in SETS; stored data naming Po or Til is harmless", flush=True)


QUIZ_LOOK = """([net, chips]) => {
  const look = (el) => getComputedStyle(el);
  const paths = [...document.querySelectorAll(`${net} path`)].map((path) => {
    const style = look(path);
    return [style.stroke, style.strokeDasharray];
  });
  const buttons = [...document.querySelectorAll(chips)].map((button) => {
    const style = look(button);
    return [style.borderTopColor, style.borderTopStyle, style.color];
  });
  return { paths, buttons };
}"""


def check_set_quiz_neutral(browser: Browser) -> None:
    """Before the answer, every Name the set path and button looks the same in both themes; after it, families show."""
    for theme in ("light", "dark"):
        page = new_page(browser)
        page.add_init_script(f"localStorage.setItem('ksv51:theme', JSON.stringify('{theme}'))")
        page.reload()
        page.click("#tabSets")
        asked: set[str] = set()
        paths: set[tuple[str, ...]] = set()
        buttons: set[tuple[str, ...]] = set()
        for _ in range(200):
            look = page.evaluate(QUIZ_LOOK, ["#netQ", "#setanswers .setchip"])
            paths.update(tuple(p) for p in look["paths"])
            buttons.update(tuple(b) for b in look["buttons"])
            asked.add(page.evaluate("() => document.querySelector('#netQ path').getAttribute('d')"))
            if len(asked) == len(SETS):
                break
            page.locator("#setanswers .setchip").first.click()
            page.click("#snext")
        if len(asked) != len(SETS):
            fail(f"{theme}: quiz asked {len(asked)} of {len(SETS)} sets")
        check_one_look(f"{theme} quiz", paths, buttons)
        page.locator("#setanswers .setchip").first.click()
        for s in SETS:
            classes = (page.get_attribute(f'#setanswers .setchip[data-s="{s[0]}"]', "class") or "").split()
            if s[3] not in classes:
                fail(f"{theme}: after the answer, button {s[0]} has no {s[3]} class")
        page.close()
    print("Name the set quiz: one neutral path and button style before the answer, families after", flush=True)


def check_one_look(tag: str, paths: set[tuple[str, ...]], buttons: set[tuple[str, ...]]) -> None:
    """Fails unless every path has one solid stroke and every button one style, in the same colour."""
    if len(paths) != 1 or len(buttons) != 1:
        fail(f"{tag}: paths {paths}, buttons {buttons} before the answer")
    elif next(iter(paths))[0] != next(iter(buttons))[0] or next(iter(paths))[1] != "none":
        fail(f"{tag}: path {paths} and buttons {buttons} differ")


def check_set_call_neutral(browser: Browser) -> None:
    """Before the answer, the Match set call check shows one neutral path and option style; after it, families."""
    for theme in ("light", "dark"):
        page = new_page(browser)
        page.add_init_script(f"localStorage.setItem('ksv51:theme', JSON.stringify('{theme}'))")
        page.reload()
        setup_match(page, "S", ("ar",))
        page.click("#gStart")
        paths: set[tuple[str, ...]] = set()
        buttons: set[tuple[str, ...]] = set()
        for ri in range(6):
            page.wait_for_selector("#gOff:enabled")
            tap_spot(page, "S", ri, "ar")
            page.wait_for_selector("#gsc .setchip")
            look = page.evaluate(QUIZ_LOOK, ["#gscNet", "#gsc .setchip"])
            paths.update(tuple(p) for p in look["paths"])
            buttons.update(tuple(b) for b in look["buttons"])
            if ri == 5:
                page.locator("#gsc .setchip").first.click()
                for chip in page.locator("#gsc .setchip").all():
                    family = next(s[3] for s in SETS if s[0] == chip.get_attribute("data-s"))
                    if family not in (chip.get_attribute("class") or "").split():
                        fail(f"{theme}: after the set call, option {chip.inner_text()} has no {family} class")
            press_next(page)
        check_one_look(f"{theme} set call check", paths, buttons)
        page.close()
    print("set call check: one neutral path and option style before the answer, families after", flush=True)


LABEL_GEOMETRY = """() => {
  const svg = document.getElementById('netS');
  const paths = [...svg.querySelectorAll('path')];
  const labels = [...svg.querySelectorAll('g')].map((g) => {
    const r = g.querySelector('rect').getBBox();
    return { name: g.querySelector('text').textContent, x: r.x, y: r.y, w: r.width, h: r.height };
  });
  const covered = paths.map((path) => {
    const n = 40, len = path.getTotalLength();
    return Array.from({ length: n + 1 }, (_, i) => path.getPointAtLength((len * i) / n));
  });
  const s = [...svg.querySelectorAll('circle')].find((c) => c.getAttribute('fill') === 'var(--role-s)').getBBox();
  const setter = { x: s.x, y: s.y, w: s.width, h: s.height };
  return { labels, points: covered.map((pts) => pts.map((q) => [q.x, q.y])), setter };
}"""


def boxes_overlap(first: dict[str, float], second: dict[str, float]) -> bool:
    """Whether two SVG boxes with x, y, w and h intersect."""
    return (
        first["x"] < second["x"] + second["w"]
        and second["x"] < first["x"] + first["w"]
        and first["y"] < second["y"] + second["h"]
        and second["y"] < first["y"] + first["h"]
    )


def inside_box(point: list[float], box: dict[str, float]) -> bool:
    """Whether an SVG point lies inside a box with x, y, w and h."""
    return box["x"] <= point[0] <= box["x"] + box["w"] and box["y"] <= point[1] <= box["y"] + box["h"]


def check_set_labels(browser: Browser) -> None:
    """Each Sets diagram label covers at most half of its arc outside the setter and overlaps nothing."""
    page = new_page(browser)
    page.click("#tabSets")
    shape = page.evaluate(LABEL_GEOMETRY)
    setter_box = shape["setter"]
    labels = shape["labels"]
    for index, label in enumerate(labels):
        points = [point for point in shape["points"][index] if not inside_box(point, setter_box)]
        inside = sum(inside_box(point, label) for point in points)
        if inside > len(points) / 2:
            fail(f"set label {label['name']} covers {inside} of {len(points)} points of its arc")
        if boxes_overlap(label, setter_box):
            fail(f"set label {label['name']} overlaps the setter")
        for other in labels[index + 1 :]:
            if boxes_overlap(label, other):
                fail(f"set labels {label['name']} and {other['name']} overlap")
    page.close()
    print("Sets diagram labels leave their arcs visible and do not overlap", flush=True)


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
                hint = page.inner_text("#gFb")
                if phase == "rec" and ("at the whistle" not in hint or "first movement" not in hint):
                    fail(f"reception hint lacks the whistle timing: {hint!r}")
            tap_spot(page, "OH1", ri, phase)
            page.wait_for_selector("#gBd")
            right = ri % 2 == 0
            if page.locator("#gnb").count():
                question = page.inner_text("#gnb")
                if "at the whistle?" not in question or "at the serve" in question:
                    fail(f"neighbour question does not ask about the whistle: {question!r}")
                want = neighbour_answer(ri, "OH1", question)
                page.locator(
                    f'#gnb button[data-p="{want}"]' if right else f'#gnb button:not([data-p="{want}"])'
                ).first.click()
                marked = page.inner_text("#gnb")
                if "From the server's first movement you may move." not in marked or "serve is made" in marked:
                    fail(f"neighbour feedback does not give the whistle timing: {marked!r}")
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
            if phase == "rec" and "Setter 70% →" not in line:
                fail(f"shown setter not in the breakdown: {line!r}")
            if phase == "ar" and "%" in line.replace("help used, 60%", ""):
                fail(f"R{ri + 1} Attack: Show on court scales the points: {line!r}")
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


# The Learn Reception passer, one per rotation.
PASSER = ["L", "OH2", "OH1", "L", "OH1", "OH2"]
HELD = 6 + 1 + 6 * 0.65  # marker radius, its edge and the ball radius, in court units


def attack_question(ri: int, role: str, row: Row) -> str:
    if cover_job(row, role):
        hitter = zone4_hitter(row)
        return f"The setter sets {hitter} in zone 4. Where is your cover spot as {hitter} spikes?"
    if PASSER[ri] == role:
        return "You pass to the setter. Where are you as it arrives?"
    if role == "S":
        return f"{PASSER[ri]} passes to you. Where do you take it?"
    return f"{PASSER[ri]} passes to the setter. Where are you as it arrives?"


def zone4_hitter(row: Row) -> str:
    """The front-row attacker farthest left, whom the setter sets in the Reception play."""
    return min((x, p) for p, x, _, kind in row["ar"] if kind == "front")[1]


def spike_picture(page: Page, ri: int) -> tuple[dict[str, tuple[float, float]], tuple[float, float]]:
    """Everyone and the ball at the spike in Learn's Reception play, in court units."""
    found = page.evaluate(
        "(ri) => { const st = window.ksvLearn.stages(ri, 'rec').at(-1); return {at: st.from, ball: st.ball.from}; }",
        ri,
    )
    team = {p: (at["x"] * 100, at["y"] * 100) for p, at in found["at"].items()}
    return team, (found["ball"]["x"] * 100, found["ball"]["y"] * 100)


def check_ball_at_setter(
    pic: dict[str, Any], row: Row, lands: dict[str, tuple[float, float]], tag: str, page: Page, ri: int, role: str
) -> None:
    if cover_job(row, role):
        _, ball = spike_picture(page, ri)
        if not pic["ball"] or dist(pic["ball"], ball) > 0.02:
            fail(f"{tag}: ball at {pic['ball']}, not at the spike {ball}")
        return
    setter = next(p for p, _, _, kind in row["ar"] if kind == "set")
    set_spot = (lands[setter][0] * 100, lands[setter][1] * 100)
    if not pic["ball"] or abs(dist(pic["ball"], set_spot) - HELD) > 0.02:
        fail(f"{tag}: ball at {pic['ball']}, not with the setter at {set_spot}")


def court_picture(page: Page, court: str) -> dict[str, Any]:
    """Reads the markers, the ball, the pass line and the from label off a court."""
    picture: dict[str, Any] = page.evaluate(
        """(id) => {
            const svg = document.getElementById(id);
            const num = (el, a) => el ? Number(el.getAttribute(a)) : null;
            const ball = svg.querySelector('g.ball');
            const at = ball && /translate[(]([-0-9.]+) ([-0-9.]+)[)]/.exec(ball.getAttribute('transform') || '');
            const pass = svg.querySelector('g.pass line');
            const tap = svg.querySelector('line.fromtap');
            return {
                markers: [...svg.querySelectorAll('g.mk')].map((g) => {
                    const c = g.querySelector('circle[fill^="var(--role"]');
                    return {p: g.dataset.p, x: num(c, 'cx'), y: num(c, 'cy'),
                            me: !!g.querySelector('.me-ring'), faded: g.classList.contains('faded')};
                }),
                ball: at ? [Number(at[1]), Number(at[2])] : null,
                pass: pass ? [num(pass, 'x2'), num(pass, 'y2')] : null,
                from: svg.querySelectorAll('text.from').length,
                tap: tap ? [num(tap, 'x1'), num(tap, 'y1'), num(tap, 'x2'), num(tap, 'y2')] : null,
            };
        }""",
        court,
    )
    return picture


def check_from_picture(pic: dict[str, Any], row: Row, ri: int, role: str, tag: str) -> None:
    """Everyone on the reception spots, you ringed, the ball at the passer and the pass line to the set spot."""
    rec = {p: (x * 100, y * 100) for p, x, y in row["rec"]}
    got = {m["p"]: m for m in pic["markers"]}
    if sorted(got) != sorted(rec) or len(pic["markers"]) != len(rec):
        fail(f"{tag}: markers {sorted(m['p'] for m in pic['markers'])}, expected the reception six {sorted(rec)}")
        return
    for p, (x, y) in rec.items():
        m = got[p]
        if abs(m["x"] - x) > 0.01 or abs(m["y"] - y) > 0.01:
            fail(f"{tag}: {p} drawn at ({m['x']}, {m['y']}), not on its reception spot ({x:.1f}, {y:.1f})")
        if m["me"] != (p == role) or m["faded"] == (p == role):
            fail(f"{tag}: {p} ringed {m['me']}, faded {m['faded']}")
    if pic["from"] != 1:
        fail(f"{tag}: {pic['from']} from labels")
    set_spot = next((x * 100, y * 100) for _, x, y, kind in row["ar"] if kind == "set")
    passer = rec[PASSER[ri]]
    if not pic["ball"] or abs(dist(pic["ball"], passer) - HELD) > 0.02:
        fail(f"{tag}: ball at {pic['ball']}, not held by {PASSER[ri]} at {passer}")
    if not pic["pass"] or dist(pic["pass"], set_spot) > 0.01:
        fail(f"{tag}: pass line ends at {pic['pass']}, not at the set spot {set_spot}")


def dist(a: tuple[float, float] | list[float], b: tuple[float, float] | list[float]) -> float:
    return float(((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5)


def check_tap_line(pic: dict[str, Any], row: Row, role: str, spot: tuple[float, float], tag: str) -> None:
    start = next((x * 100, y * 100) for p, x, y in row["rec"] if p == role)
    line = pic["tap"]
    if not line or dist(line[:2], start) > 0.01 or dist(line[2:], (spot[0] * 100, spot[1] * 100)) > 1:
        fail(f"{tag}: the tap line runs {line}, not from {start} to the tap")


def check_attack_match(browser: Browser, rules: RulesMode, vis: str) -> None:
    """Match Attack: the reception picture for every Show on court value, the tap line and scoring at ×1."""
    rows = [lineup(ri, rules) for ri in range(6)]
    page = new_page(browser, rules)
    setup_match(page, "OH1", ("ar",), vis, sets=False)
    page.click("#gStart")
    for ri in range(6):
        tag = f"match {rules} {vis} R{ri + 1}"
        page.wait_for_selector("#gOff:enabled")
        check_from_picture(court_picture(page, "courtG"), rows[ri], ri, "OH1", tag)
        story = page.inner_text("#gStory")
        if not story.endswith(attack_question(ri, "OH1", rows[ri])):
            fail(f"{tag}: question reads {story!r}")
        lands = pass_lands(page, ri)
        spot = lands["OH1"]
        tap_at(page, *spot)
        check_tap_line(court_picture(page, "courtG"), rows[ri], "OH1", spot, tag)
        press_next(page)
        check_tap_line(court_picture(page, "courtG"), rows[ri], "OH1", spot, f"{tag} feedback")
        picture = court_picture(page, "courtG")
        check_ball_at_setter(picture, rows[ri], lands, f"{tag} feedback", page, ri, "OH1")
        line = page.inner_text("#gBd")
        parts, total = breakdown_total(line)
        if "%" in line or not parts == total == points(page) or total < 100:
            fail(f"{tag}: Attack scored {line!r}, expected full points")
        press_next(page)
    page.wait_for_selector("#gEnd", state="visible")
    page.close()
    print("match Attack: reception picture, ball, tap line, full points", flush=True)


def check_attack_grading(browser: Browser, rules: RulesMode, role: str) -> None:
    """Attack grades everyone where Learn has them as the pass lands, the covers on cover, and rings them there."""
    checked = 0
    page = new_page(browser, rules)
    setup_match(page, role, ("ar",), sets=False)
    page.click("#gStart")
    for ri in range(6):
        tag = f"attack grading {rules} {role} R{ri + 1}"
        row = lineup(ri, rules)
        page.wait_for_selector("#gOff:enabled")
        lands = pass_lands(page, ri)
        if not any(p == role for p, _, _, _ in row["ar"]):
            page.click("#gOff")
            press_next(page)
            press_next(page)
            continue
        spot = lands[role]
        if role in row["front"] and role.startswith("MB") and spot[1] > 0.25:
            fail(f"{tag}: Learn has the middle at {spot} as the pass lands, not at the net")
        tap_at(page, *spot)
        press_next(page)
        if "Spot on" not in page.inner_text("#gFb"):
            fail(f"{tag}: a tap where Learn has you {spot} reads {page.inner_text('#gFb')!r}")
        pic = court_picture(page, "courtG")
        me = next(m for m in pic["markers"] if m["me"])
        if dist((me["x"], me["y"]), (spot[0] * 100, spot[1] * 100)) > 0.5:
            fail(f"{tag}: feedback rings you at ({me['x']}, {me['y']}), not at {spot}")
        check_ball_at_setter(pic, row, lands, tag, page, ri, role)
        checked += 1
        press_next(page)
    page.close()
    print(
        f"Attack: graded where Learn has everyone as the pass lands, the covers on cover, on {checked} courts",
        flush=True,
    )


MODE_ROLES = {"simple": ("MB", "OH1", "OH2", "OP", "S", "L"), "official": ("MB1", "MB2", "OH1", "OH2", "OP", "S", "L")}


def cover_job(row: Row, role: str) -> str | None:
    """The 3-2 cover job Learn gives `role` at Attack: close (L), deep (back-row OH) or side (back-row OP)."""
    kind = {p: k for p, _, _, k in row["ar"]}
    if role not in kind:
        return None
    if role == "L":
        return "close"
    if kind[role] == "back":
        return "side"
    return "deep" if kind[role] is None and role in row["back"] else None


# What the hint and the feedback say for each cover job, the words of Learn's cover captions.
COVER_WORDS = {
    "close": ("cover the hitter close behind", "close behind: dig a ball the block sends back"),
    "deep": ("cover deep in the middle", "Cover deep behind the close cover"),
    "side": ("come in to cover deep", "Cover deep in the middle"),
}


def check_attack_texts(browser: Browser, rules: RulesMode, role: str) -> None:
    """At Attack, the hint, the feedback and the caption of L, the deep OH and the back OP name the cover graded."""
    checked = 0
    page = new_page(browser, rules)
    setup_match(page, role, ("ar",), sets=False)
    page.click("#gStart")
    for ri in range(6):
        tag = f"attack text {rules} {role} R{ri + 1}"
        row = lineup(ri, rules)
        job = cover_job(row, role)
        page.wait_for_selector("#gOff:enabled")
        if not job:
            page.click("#gOff")
            press_next(page)
            press_next(page)
            continue
        lands = pass_lands(page, ri)
        page.click("#gHelp")
        hint = page.inner_text("#gFb")
        tap_at(page, *lands[role])
        press_next(page)
        feedback = page.inner_text("#gFb")
        caption = row["move"]["ar"][role]
        hint_words, feedback_words = COVER_WORDS[job]
        if hint_words not in hint.lower():
            fail(f"{tag}: hint {hint!r} does not say {hint_words!r}")
        if feedback_words not in feedback:
            fail(f"{tag}: feedback {feedback!r} does not say {feedback_words!r}")
        if "cover" not in caption:
            fail(f"{tag}: caption {caption!r} does not name the cover")
        for text in (hint, feedback, caption):
            if "zone 1" in text or "straight" in text.lower():
                fail(f"{tag}: graded at the {job} cover, the text reads {text!r}")
        checked += 1
        press_next(page)
    page.close()
    print(f"Attack texts: the cover graded named in hint, feedback and caption on {checked} courts", flush=True)


def check_cover_moment(browser: Browser, rules: RulesMode, role: str) -> None:
    """A cover is asked about its cover spot at the spike, and the feedback shows everyone and the ball at the spike."""
    checked = 0
    page = new_page(browser, rules)
    setup_match(page, role, ("ar",), "all", sets=False)
    page.click("#gStart")
    for ri in range(6):
        tag = f"cover moment {rules} {role} R{ri + 1}"
        row = lineup(ri, rules)
        page.wait_for_selector("#gOff:enabled")
        if not cover_job(row, role):
            page.click("#gOff")
            press_next(page)
            press_next(page)
            continue
        story = page.inner_text("#gStory")
        hitter = zone4_hitter(row)
        if "as it arrives" in story or not story.endswith(attack_question(ri, role, row)):
            fail(f"{tag}: question reads {story!r}")
        tap_at(page, *pass_lands(page, ri)[role])
        press_next(page)
        if f"cover spot as {hitter} spikes" not in page.inner_text("#gFb"):
            fail(f"{tag}: feedback {page.inner_text('#gFb')!r} does not name the cover spot at the spike")
        team, _ = spike_picture(page, ri)
        pic = court_picture(page, "courtG")
        for m in pic["markers"]:
            if m["p"] in team and dist((m["x"], m["y"]), team[m["p"]]) > 0.5:
                fail(f"{tag}: {m['p']} drawn at ({m['x']}, {m['y']}), not where it is at the spike")
        check_ball_at_setter(pic, row, {}, tag, page, ri, role)
        checked += 1
        press_next(page)
    page.close()
    print(f"Attack covers: asked and shown at the spike on {checked} courts", flush=True)


def check_cover_set_call(browser: Browser) -> None:
    """A back-row opposite who covers is asked the set call as a watcher, not a back-row set for itself."""
    checked = 0
    for rules in RULES_MODES:
        page = new_page(browser, rules)
        setup_match(page, "OP", ("ar",))
        page.click("#gStart")
        for ri in range(6):
            row = lineup(ri, rules)
            page.wait_for_selector("#gOff:enabled")
            tap_at(page, *pass_lands(page, ri)["OP"])
            press_next(page)
            ask = page.inner_text("#gsc p") if page.locator("#gsc").count() else ""
            if cover_job(row, "OP"):
                if ask != "The setter sets this ball. What is the call?":
                    fail(f"set call {rules} OP R{ri + 1}: a covering opposite is asked {ask!r}")
                checked += 1
            press_next(page)
        page.close()
    if not checked:
        fail("set call: no rotation with a covering opposite")
    print(f"set call: a covering opposite asked as a watcher on {checked} courts", flush=True)


# How far inside its start the zone 4 hitter takes off, as Learn's HIT_IN.
HIT_IN = 0.08


def check_hitter_approach(browser: Browser, rules: RulesMode, role: str) -> None:
    """The zone 4 hitter's dashed approach ends inside its start, where Learn's outside-in run hits."""
    checked = 0
    page = new_page(browser, rules)
    setup_match(page, role, ("ar",), sets=False)
    page.click("#gStart")
    for ri in range(6):
        row = lineup(ri, rules)
        page.wait_for_selector("#gOff:enabled")
        if zone4_hitter(row) != role:
            page.click("#gOff")
            press_next(page)
            press_next(page)
            continue
        tap_at(page, *pass_lands(page, ri)[role])
        press_next(page)
        ends: list[float] = page.eval_on_selector_all(
            f'#courtG g.rt[data-p="{role}"] line.route[stroke-dasharray]',
            "els => els.map(l => l.x2.baseVal.value)",
        )
        start = next(x for p, x, _, _ in row["ar"] if p == role)
        if len(ends) != 1 or abs(ends[0] - (start + HIT_IN) * 100) > 0.01:
            fail(f"hitter approach {rules} {role} R{ri + 1}: ends at x {ends}, not {(start + HIT_IN) * 100:.1f}")
        checked += 1
        press_next(page)
    page.close()
    print(f"Attack: the zone 4 hitter's approach ends outside-in on {checked} courts", flush=True)


def check_from_label(browser: Browser, rules: RulesMode, role: str) -> None:
    """The "from" label stays clear of every marker, the ball and the court edge, for every rotation and role."""
    checked = 0
    page = new_page(browser, rules)
    setup_match(page, role, ("ar",), sets=False)
    page.click("#gStart")
    for ri in range(6):
        page.wait_for_selector("#gOff:enabled")
        clash = page.evaluate(
            """() => {
                const svg = document.getElementById('courtG'), label = svg.querySelector('text.from');
                if (!label) return 'no label';
                const b = label.getBBox();
                const discs = [...svg.querySelectorAll('g.mk')].map((g) => {
                    const c = g.querySelector('circle[fill^="var(--role"]');
                    const ring = g.querySelector('.me-ring circle');
                    return {p: g.dataset.p, x: +c.getAttribute('cx'), y: +c.getAttribute('cy'),
                            r: ring ? +ring.getAttribute('r') + 0.6 : +c.getAttribute('r') + 0.5};
                });
                const ball = svg.querySelector('g.ball');
                const at = ball && /translate[(]([-0-9.]+) ([-0-9.]+)[)] scale[(]([0-9.]+)[)]/
                    .exec(ball.getAttribute('transform'));
                if (at) discs.push({p: 'ball', x: +at[1], y: +at[2], r: +at[3]});
                const hit = discs.filter((d) => {
                    const dx = Math.max(b.x - d.x, 0, d.x - b.x - b.width),
                        dy = Math.max(b.y - d.y, 0, d.y - b.y - b.height);
                    return Math.hypot(dx, dy) < d.r;
                }).map((d) => d.p);
                if (b.x < -4 || b.x + b.width > 104 || b.y < -14 || b.y + b.height > 103) hit.push('edge');
                return hit.join(', ');
            }"""
        )
        on_court = any(p == role for p, _, _ in lineup(ri, rules)["rec"])
        if clash and (clash != "no label" or on_court):
            fail(f"from label {rules} {role} R{ri + 1}: covers {clash}")
        checked += on_court
        page.click("#gOff")
        press_next(page)
        press_next(page)
    page.close()
    print(f"from label clear of markers, ball and edge on {checked} Attack courts", flush=True)


def limit_lines(page: Page, court: str) -> int:
    return int(page.locator(f"#{court} g.bnd").count())


def check_receive_limits(browser: Browser, rules: RulesMode, role: str) -> None:
    """Receive feedback draws your overlap limits as Learn does, only after the answer and the neighbour check."""
    checked = 0
    page = new_page(browser, rules)
    setup_match(page, role, ("rec",))
    page.click("#gStart")
    for ri in range(6):
        tag = f"limits match {rules} {role} R{ri + 1}"
        page.wait_for_selector("#gOff:enabled")
        tap_spot(page, role, ri, "rec", check=False)
        if limit_lines(page, "courtG"):
            fail(f"{tag}: limit lines before the answer")
        press_next(page)
        want = page.evaluate("(ri) => window.ksvLearn.bounds(ri, 'rec')", ri)
        if limit_lines(page, "courtG") != want:
            fail(f"{tag}: {limit_lines(page, 'courtG')} limit lines, Learn draws {want}")
        on_court = any(p == role for p, _, _ in lineup(ri, rules)["rec"])
        if on_court != ("Overlap: stay" in page.inner_text("#gFb")):
            fail(f"{tag}: feedback reads {page.inner_text('#gFb')!r}")
        checked += 1
        press_next(page)
    page.close()
    print(f"Receive limits {rules} {role}: after the answer as in Learn on {checked} Match courts", flush=True)


def check_receive_limits_elsewhere(browser: Browser) -> None:
    """Receive limits wait for the neighbour check in Match, and show after the answer in Drill."""
    page = new_page(browser)
    setup_match(page, "OH1", ("rec",), neighbour=True)
    page.click("#gStart")
    tap_spot(page, "OH1", 0, "rec")
    if limit_lines(page, "courtG") or "Overlap: stay" in page.inner_text("#gFb"):
        fail("limits shown while the neighbour check is open")
    page.locator("#gnb button").first.click()
    if limit_lines(page, "courtG") != page.evaluate("() => window.ksvLearn.bounds(0, 'rec')"):
        fail("limits missing after the neighbour check")
    page.close()
    for rules in RULES_MODES:
        page = new_page(browser, rules)
        pick_role(page, "OH1")
        page.click("#tabDrill")
        if page.get_attribute("#dOpts", "open") is None:
            page.click("#dOpts > summary")
        page.set_checked("#nbDrill", False)
        seen: set[int] = set()
        for _ in range(400):
            if len(seen) == 6:
                break
            question = page.inner_text("#dq")
            if not question.endswith("· Reception"):
                page.dblclick("#dReset")
                continue
            ri = drill_ri(question)
            seen.add(ri)
            tag = f"limits drill {rules} R{ri + 1}"
            if limit_lines(page, "courtD"):
                fail(f"{tag}: limit lines before the answer")
            spot = next((x, y) for p, x, y in lineup(ri, rules)["rec"] if p == "OH1")
            tap_at(page, *spot, court="courtD")
            page.click("#nextBtn")
            want = page.evaluate("(ri) => window.ksvLearn.bounds(ri, 'rec')", ri)
            if limit_lines(page, "courtD") != want or "Overlap: stay" not in page.inner_text("#fb"):
                fail(f"{tag}: {limit_lines(page, 'courtD')} limit lines, Learn draws {want}")
            page.dblclick("#dReset")
        if len(seen) < 6:
            fail(f"limits drill {rules}: Receive came up only in {sorted(seen)}")
        page.close()
    page = new_page(browser)
    pick_role(page, "OH1")
    page.click("#tabDrill")
    if page.get_attribute("#dOpts", "open") is None:
        page.click("#dOpts > summary")
    page.set_checked("#nbDrill", True)
    for _ in range(400):
        if page.inner_text("#dq").endswith("· Reception"):
            break
        page.dblclick("#dReset")
    else:
        fail("limits drill neighbour: Receive never came up")
    ri = drill_ri(page.inner_text("#dq"))
    spot = next((x, y) for p, x, y in lineup(ri, "simple")["rec"] if p == "OH1")
    tap_at(page, *spot, court="courtD")
    page.click("#nextBtn")
    page.wait_for_selector("#dnb button")
    if limit_lines(page, "courtD") or "Overlap: stay" in page.inner_text("#fb"):
        fail("limits drill: shown while the neighbour check is open")
    page.locator("#dnb button").first.click()
    want = page.evaluate("(ri) => window.ksvLearn.bounds(ri, 'rec')", ri)
    if limit_lines(page, "courtD") != want or "Overlap: stay" not in page.inner_text("#fb"):
        fail(f"limits drill: {limit_lines(page, 'courtD')} limit lines after the neighbour check, Learn draws {want}")
    page.close()
    print("Receive limits: in Drill and after the neighbour check", flush=True)


def check_middle_route(browser: Browser, rules: RulesMode, role: str) -> None:
    """Match Attack feedback: the front middle's route never reaches the 3 m line, and its dashed approach shows."""
    checked = 0
    page = new_page(browser, rules)
    setup_match(page, role, ("ar",), sets=False)
    page.click("#gStart")
    for ri in range(6):
        page.wait_for_selector("#gOff:enabled")
        if role not in lineup(ri, rules)["front"]:
            page.click("#gOff")
            press_next(page)
            press_next(page)
            continue
        tap_at(page, *pass_lands(page, ri)[role])
        press_next(page)
        ys: list[float] = page.eval_on_selector_all(
            f'#courtG g.rt[data-p="{role}"] line',
            "els => els.flatMap(l => [Number(l.getAttribute('y1')), Number(l.getAttribute('y2'))])",
        )
        if not ys or max(ys) >= (ATTACK_LINE - 0.05) * 100:
            fail(f"attack route {rules} {role} R{ri + 1}: the middle's route reaches y {max(ys, default=0):.1f}")
        dashes: list[float] = page.eval_on_selector_all(
            f'#courtG g.rt[data-p="{role}"] line.route[stroke-dasharray]',
            "els => els.map(l => Math.hypot(l.x2.baseVal.value - l.x1.baseVal.value,"
            " l.y2.baseVal.value - l.y1.baseVal.value))",
        )
        if len(dashes) != 1 or dashes[0] < 5:
            fail(f"attack route {rules} {role} R{ri + 1}: the dashed approach is {dashes} units long")
        checked += 1
        press_next(page)
    page.close()
    print(
        f"Attack: the front middle's route stays in front of the 3 m line, its approach at least 5 units,"
        f" on {checked} courts",
        flush=True,
    )


MIDDLE_ROLES = {"simple": ("MB",), "official": ("MB1", "MB2")}


def check_attack_drill(browser: Browser, rules: RulesMode) -> None:
    """Drill Attack: the reception picture in every rotation, both rule sets and every Show on court value.

    Two taps on Reset draw each next question, so the weights stay even and every rotation comes up.
    """
    rows = [lineup(ri, rules) for ri in range(6)]
    page = new_page(browser, rules)
    pick_role(page, "OH1")
    page.click("#tabDrill")
    if page.get_attribute("#dOpts", "open") is None:
        page.click("#dOpts > summary")
    page.set_checked("#nbDrill", False)
    for vis in ("none", "ref", "all"):
        page.click(f'.vis[data-vis="drill"] [data-v="{vis}"]')
        seen: set[int] = set()
        for _ in range(400):
            if len(seen) == 6:
                break
            question = page.inner_text("#dq")
            if not question.endswith("· Attack"):
                page.dblclick("#dReset")
                continue
            ri = drill_ri(question)
            tag = f"drill {rules} {vis} R{ri + 1}"
            seen.add(ri)
            check_from_picture(court_picture(page, "courtD"), rows[ri], ri, "OH1", tag)
            if page.inner_text("#dsub") != attack_question(ri, "OH1", rows[ri]):
                fail(f"{tag}: question reads {page.inner_text('#dsub')!r}")
            lands = pass_lands(page, ri)
            spot = lands["OH1"]
            tap_at(page, *spot, court="courtD")
            page.click("#nextBtn")
            check_tap_line(court_picture(page, "courtD"), rows[ri], "OH1", spot, tag)
            picture = court_picture(page, "courtD")
            check_ball_at_setter(picture, rows[ri], lands, f"{tag} feedback", page, ri, "OH1")
            page.dblclick("#dReset")
        if len(seen) < 6:
            fail(f"drill {rules} {vis}: Attack came up only in {sorted(seen)}")
    page.close()
    print("drill Attack: reception picture, ball, tap line", flush=True)


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


def drill_page(browser: Browser, steps: list[str], query: str = "", reduced: bool = False) -> Page:
    """Opens Drill as OH1 with only ``steps`` picked and the neighbour check off."""
    page = browser.new_page(
        viewport={"width": 390, "height": 844},
        is_mobile=True,
        has_touch=True,
        reduced_motion="reduce" if reduced else "no-preference",
    )
    page.add_init_script(SEED_ROLE)
    page.add_init_script(f"localStorage.setItem('ksv51:drillSteps', JSON.stringify({steps!r}))")
    page.add_init_script(ZONES_UNDER)
    page.on("pageerror", lambda error: FAIL.append(f"page error: {error}"))
    page.goto(URL.split("?")[0] + query)
    page.wait_for_timeout(300)
    page.click("#tabDrill")
    if page.get_attribute("#dOpts", "open") is None:
        page.click("#dOpts > summary")
    page.set_checked("#nbDrill", False)
    return page


def tap_far(page: Page, court: str = "courtD") -> dict[str, Any]:
    """Taps the court on the other side from your right spot, presses Continue and reads the answer in the same task."""
    result: dict[str, Any] = page.evaluate(
        """([id, ri]) => {
            const svg = document.getElementById(id);
            const ph = /Attack/.test(document.getElementById('dq').textContent) ? 'ar' : 'rec';
            const me = window.ksvLearn.players(ri, ph).find((o) => o.p === 'OH1');
            const x = me ? (me.x > 0.5 ? 0.15 : 0.85) : 0.5, y = me && me.y > 0.5 ? 0.25 : 0.8;
            const m = svg.getScreenCTM();
            svg.dispatchEvent(new PointerEvent('pointerup', {bubbles: true,
                clientX: m.a * x * 100 + m.e, clientY: m.d * y * 100 + m.f}));
            document.getElementById('nextBtn').click();
            const g = svg.querySelector('g.glide');
            const at = g && /translate[(]([-0-9.e]+) ([-0-9.e]+)[)]/.exec(g.getAttribute('transform') || '');
            const next = document.getElementById('nextBtn');
            return {
                on: !!me,
                shift: at ? Math.hypot(+at[1], +at[2]) : null,
                want: g ? Math.hypot(+g.dataset.dx, +g.dataset.dy) : null,
                target: svg.querySelectorAll('circle.target').length,
                route: svg.querySelectorAll('g.glideroute').length,
                next: !next.hidden && !next.disabled,
                zones: window.zonesUnder(id),
            };
        }""",
        [court, drill_ri(page.inner_text("#dq"))],
    )
    return result


ZONES_UNDER = """window.zonesUnder = (id) => {
    const svg = document.getElementById(id), g = svg && svg.querySelector('g.zones');
    if (!g) return 'no zone numbers';
    if (getComputedStyle(g).visibility !== 'visible') return 'zone numbers hidden';
    if (g.querySelectorAll('text').length !== 6) return 'not six zone numbers';
    const late = [...svg.querySelectorAll('.mk, .am, g.glide')].some(
        (m) => !(g.compareDocumentPosition(m) & Node.DOCUMENT_POSITION_FOLLOWING));
    return late ? 'a marker under the zone numbers' : 'ok';
};"""


def zones_under(page: Page, ctx: str, court: str = "courtD", want_markers: bool = True) -> None:
    """The court shows the six zone numbers, drawn before every marker."""
    got = page.evaluate("(id) => window.zonesUnder(id)", court)
    if got != "ok":
        fail(f"zones {ctx}: {got}")
    if want_markers and not page.locator(f"#{court} .mk").count():
        fail(f"zones {ctx}: no markers on the court")


def check_zones_courts(browser: Browser) -> None:
    """The zone numbers sit under the markers on Drill Rotate, the Attack picture and the answer glide."""
    page = drill_page(browser, ["ar"])
    for i in range(6):
        if "Attack" not in page.inner_text("#dq"):
            fail(f"zones Attack: question {page.inner_text('#dq')!r}")
        zones_under(page, f"Attack picture before the answer {i + 1}")
        got = tap_far(page)
        if got["zones"] != "ok":
            fail(f"zones Attack glide frame {i + 1}: {got['zones']}")
        zones_under(page, f"Attack picture after the answer {i + 1}")
        page.wait_for_timeout(500)
        zones_under(page, f"Attack picture after the glide {i + 1}")
        page.click("#nextBtn")
    page.close()
    page = drill_page(browser, ["start"])
    for i in range(3):
        if not page.inner_text("#dq").endswith("Rotation"):
            fail(f"zones Rotate: question {page.inner_text('#dq')!r}")
        zones_under(page, f"Rotate before the answer {i + 1}", want_markers=False)
        for x, y in ZONE_SPOTS:
            if page.locator("#nextBtn").is_enabled():
                break
            tap_at(page, x, y, "courtD")
            zones_under(page, f"Rotate placing {i + 1}")
        page.click("#nextBtn")
        zones_under(page, f"Rotate glide frame {i + 1}")
        page.wait_for_timeout(500)
        zones_under(page, f"Rotate after the answer {i + 1}")
        page.click("#nextBtn")
    page.close()


def glide_shift(page: Page, court: str) -> float | None:
    shift: float | None = page.evaluate(
        """(id) => {
            const g = document.getElementById(id).querySelector('g.glide');
            const at = g && /translate[(]([-0-9.e]+) ([-0-9.e]+)[)]/.exec(g.getAttribute('transform') || '');
            return at ? Math.hypot(+at[1], +at[2]) : null;
        }""",
        court,
    )
    return shift


def check_answer_glide(browser: Browser) -> None:
    """After the answer your marker glides 400 ms from the tap to the ring outline; Next never waits for it."""
    page = drill_page(browser, ["rec"])
    for _ in range(20):
        got = tap_far(page)
        if got["on"]:
            break
        page.click("#nextBtn")
    if not got["on"]:
        fail("glide: OH1 never on court at Receive")
    if not (got["want"] and got["shift"] and got["shift"] > 0.9 * got["want"]):
        fail(f"glide: marker does not start at the tap: {got}")
    if got["target"] != 1 or got["route"] != 1:
        fail(f"glide: {got['target']} ring outlines and {got['route']} routes")
    if not got["next"]:
        fail("glide: Next not available while the marker glides")
    page.wait_for_timeout(600)
    if glide_shift(page, "courtD") != 0:
        fail(f"glide: marker not on its spot after 600 ms ({glide_shift(page, 'courtD')})")
    page.click("#nextBtn")
    for _ in range(20):
        if tap_far(page)["on"]:
            break
        page.click("#nextBtn")
    question = page.inner_text("#dq")
    page.click("#nextBtn")
    if page.locator("#courtD g.glide").count() or page.is_visible("#dWatch"):
        fail("glide: Next mid-glide left the glide or Watch the move")
    if not page.inner_text("#dq") or "Tap the court" not in page.inner_text("#fb"):
        fail(f"glide: Next mid-glide did not open the next question ({question!r})")
    page.close()
    for query, reduced, tag in (("?anim=0", False, "anim=0"), ("", True, "reduced motion")):
        page = drill_page(browser, ["rec"], query, reduced)
        for _ in range(20):
            got = tap_far(page)
            if got["on"]:
                break
            page.click("#nextBtn")
        if got["shift"] != 0 or got["target"] != 1 or got["route"] != 1:
            fail(f"glide {tag}: the right spot and route must show at once: {got}")
        if page.is_visible("#dWatch"):
            fail(f"glide {tag}: Watch the move offered")
        page.close()
    print("answer glide: 400 ms, Next cuts it short, still with reduced motion", flush=True)


def watch_play(page: Page) -> dict[str, Any] | None:
    play: dict[str, Any] | None = page.evaluate("window.ksvWatch.play()")
    return play


def check_watch_move(browser: Browser) -> None:
    """Watch the move plays only on tap, with the Learn controls, and Next closes it at once."""
    page = drill_page(browser, ["rec", "ar"])
    for _ in range(40):
        got = tap_far(page)
        if got["on"]:
            break
        page.click("#nextBtn")
    page.wait_for_timeout(500)
    if not page.is_visible("#dWatch .wbtn") or "Watch the move" not in (page.text_content("#dWatch") or ""):
        fail("watch: no Watch the move button after a Receive or Attack answer")
    if watch_play(page) is not None:
        fail("watch: plays without a tap")
    page.click("#dWatch .wbtn")
    play = watch_play(page)
    if not play or not play["playing"]:
        fail(f"watch: tap does not play: {play}")
    markers = page.locator("#courtD g.am").count()
    if markers < 6 or page.locator("#courtD g.am .me-ring").count() != 1:
        fail(f"watch: {markers} markers in the play, or your ring missing")
    for name in ("replay", "play", "back", "step", "speed"):
        if not page.is_visible(f'#dWatch [data-w="{name}"]'):
            fail(f"watch: control {name} missing")
    if not page.is_enabled("#nextBtn"):
        fail("watch: Next disabled while it plays")
    page.wait_for_timeout(400)
    if not page.inner_text("#dWatch .wcap").strip():
        fail("watch: no caption while it plays")
    page.click('#dWatch [data-w="play"]')
    paused = watch_play(page)
    page.wait_for_timeout(300)
    if not paused or paused["playing"] or watch_play(page) != paused:
        fail(f"watch: Pause does not hold the frame: {paused} -> {watch_play(page)}")
    page.click('#dWatch [data-w="back"]')
    back = watch_play(page)
    if not back or not paused or back["t"] >= paused["t"]:
        fail(f"watch: Step back does not go back: {paused} -> {back}")
    page.click('#dWatch [data-w="play"]')
    page.wait_for_function("() => window.ksvWatch.play() === null", timeout=20000)
    if not page.locator("#courtD circle.target").count() or page.locator("#courtD g.am").count():
        fail("watch: the answer picture does not come back after the play")
    if not page.is_visible('#dWatch [data-w="replay"]'):
        fail("watch: the controls go after the play")
    page.click('#dWatch [data-w="replay"]')
    page.wait_for_timeout(200)
    page.click("#nextBtn")
    if watch_play(page) is not None or page.is_visible("#dWatch") or page.locator("#courtD g.am").count():
        fail("watch: Next does not close it at once")
    page.close()
    page = drill_page(browser, ["serve"])
    tap_at(page, 0.5, 0.5, "courtD")
    page.click("#nextBtn")
    page.wait_for_timeout(200)
    if page.is_visible("#dWatch"):
        fail("watch: offered at Our serve")
    page.close()
    page = drill_page(browser, ["start"])
    for x, y in ZONE_SPOTS:
        if page.locator("#nextBtn").is_enabled():
            break
        tap_at(page, x, y, "courtD")
    page.click("#nextBtn")
    page.wait_for_timeout(200)
    if not page.locator("#courtD g.glide").count():
        fail("glide: Rotate markers do not glide from the taps")
    if page.is_visible("#dWatch"):
        fail("watch: offered at Rotate")
    page.close()
    page = new_page(browser, query="")
    setup_match(page, "OH1", ("rec",))
    page.click("#gStart")
    if page.is_visible("#gWatch"):
        fail("watch match: offered before the answer")
    tap_spot(page, "OH1", 0, "rec")
    if not page.is_visible("#gWatch .wbtn"):
        fail("watch match: no Watch the move after the answer")
    page.click("#gWatch .wbtn")
    if not (watch_play(page) or {}).get("playing"):
        fail("watch match: tap does not play")
    press_next(page)
    if watch_play(page) is not None or page.is_visible("#gWatch"):
        fail("watch match: Next does not close it")
    page.close()
    check_watch_fit_and_boxes(browser)


def court_in_view(page: Page, court: str) -> dict[str, float]:
    box: dict[str, float] = page.evaluate(
        """(id) => {
            const r = document.getElementById(id).getBoundingClientRect();
            return {top: r.top, bottom: r.bottom, height: innerHeight};
        }""",
        court,
    )
    return box


def check_watch_fit_and_boxes(browser: Browser) -> None:
    """At 390 x 664 the court stays on screen while it plays; a Match answer keeps the Drill button."""
    page = drill_page(browser, ["rec", "ar"])
    page.set_viewport_size({"width": 390, "height": 664})
    for _ in range(40):
        if tap_far(page)["on"]:
            break
        page.click("#nextBtn")
    page.wait_for_timeout(500)
    page.click("#dWatch .wbtn")
    page.wait_for_timeout(300)
    box = court_in_view(page, "courtD")
    if not (watch_play(page) or {}).get("playing") or box["top"] < -1 or box["bottom"] > box["height"] + 1:
        fail(f"watch fit: the Drill court is not on screen while it plays: {box}")
    if not page.locator("#dWatch .wcap").is_visible():
        fail("watch fit: the Drill caption is hidden")
    if page.locator("#courtD g.zones").count() != 1 or not page.locator("#courtD g.zones").is_visible():
        fail("watch: no zone numbers on the Drill court while it plays")
    page.click("#nextBtn")
    for _ in range(40):
        if tap_far(page)["on"]:
            break
        page.click("#nextBtn")
    page.wait_for_timeout(500)
    page.click("#tabGame")
    page.click('.vis[data-vis="game"] [data-v="none"]')
    if page.get_attribute("#gOpts", "open") is None:
        page.click("#gOpts > summary")
    for step in ("start", "serve", "rec", "ar"):
        page.set_checked(f"#gs-{step}", step == "rec")
    page.check('input[name="gOrder"][value="order"]')
    page.set_checked("#nbGame", False)
    page.click("#gStart")
    tap_spot(page, "OH1", 0, "rec")
    page.click("#gWatch .wbtn")
    page.wait_for_timeout(300)
    box = court_in_view(page, "courtG")
    if not (watch_play(page) or {}).get("playing") or box["top"] < -1 or box["bottom"] > box["height"] + 1:
        fail(f"watch fit: the Match court is not on screen while it plays: {box}")
    page.click("#tabDrill")
    if not page.is_visible("#dWatch .wbtn"):
        fail("watch boxes: the Drill Watch the move is gone after a Match answer")
    page.click("#dWatch .wbtn")
    if not (watch_play(page) or {}).get("playing") or page.locator("#courtG g.am").count():
        fail("watch boxes: the Drill play does not take over from Match")
    page.click("#tabGame")
    if not page.is_visible("#gWatch") or page.locator("#courtG g.am").count():
        fail("watch boxes: the Match box lost, or its court still playing")
    page.close()
    print("Watch the move: court on screen at 390 x 664, each box kept across tabs", flush=True)
    print("Watch the move: on tap only, controls, back to the answer, Next closes it", flush=True)


def check_reveal_motion(browser: Browser) -> None:
    """Same device: no motion during a turn; the reveal glides the markers and offers Watch the move."""
    page = new_page(browser, query="")
    setup_match(page, "OH1", ("rec",))
    page.check('input[name="gPlayers"][value="mp"]')
    page.fill('#mpList input[data-k="0"]', "Anna")
    page.fill('#mpList input[data-k="1"]', "Ben")
    page.click("#gStart")
    for turn in range(2):
        page.click("#pReady")
        tap_at(page, 0.5, 0.95)
        press_next(page)
        if page.locator("#courtG g.glide, #courtG circle.target").count() or page.is_visible("#gWatch"):
            fail(f"reveal: motion or Watch the move during turn {turn + 1}")
        page.click("#gNext")
    page.wait_for_selector("#gReveal:not([hidden])")
    shift = glide_shift(page, "courtR")
    if shift is None or shift <= 0:
        fail(f"reveal: markers do not glide from the taps ({shift})")
    page.wait_for_timeout(600)
    if glide_shift(page, "courtR") != 0:
        fail("reveal: markers not on their spots after the glide")
    if not page.is_visible("#rWatch .wbtn"):
        fail("reveal: no Watch the move")
    page.click("#rWatch .wbtn")
    if not (watch_play(page) or {}).get("playing"):
        fail("reveal: Watch the move does not play")
    page.click("#rNext")
    if watch_play(page) is not None or page.is_visible("#rWatch"):
        fail("reveal: Next moment does not close Watch the move")
    page.close()
    print("same-device reveal: glide and Watch the move", flush=True)


def mistake_after(page: Page, x: float | None, y: float | None = None) -> str:
    """Taps (x, y), or I'm off court when x is None, presses Continue and returns the Common mistake line."""
    page.wait_for_selector("#gOff:enabled")
    if x is None:
        page.click("#gOff")
    else:
        tap_at(page, x, float(y or 0))
    press_next(page)
    page.wait_for_selector("#gFb .pts")
    lines = page.locator("#gFb .mistake")
    return lines.inner_text() if lines.count() else ""


def check_common_mistakes(browser: Browser) -> None:
    """Solo Match names a common mistake after a wrong or close answer, picked from the tap, and none when exact."""
    # A want of None skips the check, and "!text" means the line must not say it.
    cases: list[tuple[str, str, tuple[str, ...], str, list[tuple[float | None, float | None, str | None]]]] = [
        (
            "OH1",
            "simple",
            ("rec",),
            "?anim=0",
            [
                (0.3, 0.73, "Overlap fault: at the whistle you must stand right of MB."),
                (0.84, 0.72, ""),
                (None, None, "Only the libero goes off, while MB serves"),
            ],
        ),
        ("OH1", "official", ("rec",), "?anim=0", [(None, None, "the middle it replaces go off")]),
        ("OH1", "simple", ("serve",), "?anim=0", [(0.15, 0.8, "Wrong row: you are front row here")]),
        ("S", "simple", ("rec",), "?anim=0", [(0.75, 0.8, "!In a passing lane"), (0.58, 0.31, "")]),
        ("MB", "simple", ("rec",), "?anim=0", [(0.5, 0.65, "In a passing lane")]),
        (
            "OP",
            "simple",
            ("ar",),
            "?anim=0",
            [(0.5, 0.5, None), (0.5, 0.5, None), (0.5, 0.5, None), (0.8, 0.3, "!A back-row attacker")],
        ),
    ]
    for role, rules, steps, query, taps in cases:
        page = new_page(browser, rules=rules, query=query)
        setup_match(page, role, steps, sets=False)
        page.click("#gStart")
        for k, (x, y, want) in enumerate(taps):
            if k:
                press_next(page)
            got = mistake_after(page, x, y)
            ctx = f"{role} {rules} {steps[0]} R{k + 1} tap {x},{y}"
            if want is None:
                continue
            if want.startswith("!"):
                if want[1:] in got:
                    fail(f"{ctx}: line {got!r} should not say {want[1:]!r}")
                continue
            if not want and got:
                fail(f"{ctx}: an exact answer shows {got!r}")
            if want and not got.startswith("Common mistake:"):
                fail(f"{ctx}: no Common mistake line, expected {want!r}")
            if want and want not in got:
                fail(f"{ctx}: line {got!r}, expected {want!r}")
            if len(got) > len("Common mistake: ") + 90:
                fail(f"{ctx}: line longer than 90 characters: {got!r}")
        page.close()
    page = new_page(browser)
    setup_match(page, "OH1", ("start",))
    page.click("#gStart")
    page.wait_for_selector("#gAsk")
    order, spots = rotate_lineup(page, 0, "OH1")
    taken = {"S": spots["S"], "OH1": (0.5, 0.71)}
    free = [z for z in ZONE_SPOTS if all(abs(z[0] - t[0]) + abs(z[1] - t[1]) > 0.1 for t in taken.values())]
    for mate in order:
        tap_at(page, *(taken[mate] if mate in taken else free.pop(0)))
    press_next(page)
    got = page.locator("#gFb .mistake").inner_text() if page.locator("#gFb .mistake").count() else ""
    if "You counted along the arrows" not in got:
        fail(f"Match Rotate counted along the arrows: line {got!r}")
    page.close()
    page = drill_page(browser, ["rec"], query="?anim=0")
    for _ in range(3):
        if page.locator("#courtD .ptag").count():
            fail("a pass tag on the Drill court before the answer")
        tap_far(page)
        page.wait_for_selector("#fb b", state="attached")
        if page.locator("#courtD .ptag").count():
            fail("a pass tag on the Drill court after the answer")
        if not page.locator("#fb .mistake").count():
            fail(f"a wrong Drill answer has no Common mistake line: {page.inner_text('#fb')!r}")
        page.click("#nextBtn")
    page.close()
    print(
        "common mistakes: overlap, row, off court, lane and along the arrows lines; none when exact; "
        "no pass tag in Drill",
        flush=True,
    )


# Rough seconds per unit, from a sharded run; they only balance the shards.
COST = {
    "attack_drill": 8,
    "breakdown": 14,
    "common_mistakes": 40,
    "cover_set_call": 12,
    "hint_rule_numbers": 11,
    "match_h_names": 24,
    "set_call_neutral": 13,
    "set_calls": 61,
    "vis_scoring": 19,
    "watch_move": 16,
}
DEFAULT_COST = 6


def units() -> list[tuple[str, Callable[[Browser], None]]]:
    """Every check in run order, the heavy ones split by rule set and role or Show on court, for the shards."""
    whole: list[Callable[..., None]] = [
        check_vis_scoring,
        check_vis_fixed,
        check_best_key,
        check_our_serve,
        check_off_court_pill,
        check_match_order,
        check_match_rotate,
    ]
    found: list[tuple[str, Callable[[Browser], None]]] = []

    def add(check: Callable[..., None], *args: str) -> None:
        def unit(browser: Browser) -> None:
            check(browser, *args)

        found.append((" ".join((check.__name__.removeprefix("check_"), *args)), unit))

    for check in whole:
        add(check)
    for rules in RULES_MODES:
        for role in ("OH1", "L", "S", "MB" if rules == "simple" else "MB2"):
            add(check_match_h_names, rules, role)
    for check in (
        check_learn_keeps_r_names,
        check_libero_hint,
        check_hint_rule_numbers,
        check_set_calls,
        check_sets_tab,
        check_set_quiz_neutral,
        check_set_call_neutral,
        check_set_labels,
        check_tap_then_continue,
        check_breakdown,
        check_end_screen,
        check_court_not_covered,
        check_double_check,
    ):
        add(check)
    for rules in RULES_MODES:
        for vis in ("none", "ref", "all"):
            add(check_attack_match, rules, vis)
    for check, roles in (
        (check_attack_grading, MODE_ROLES),
        (check_attack_texts, {rules: ("L", "OH1", "OH2", "OP") for rules in RULES_MODES}),
        (check_cover_moment, MODE_ROLES),
    ):
        for rules in RULES_MODES:
            for role in roles[rules]:
                add(check, rules, role)
    add(check_cover_set_call)
    for check, roles in (
        (check_hitter_approach, MODE_ROLES),
        (check_middle_route, MIDDLE_ROLES),
        (check_from_label, MODE_ROLES),
    ):
        for rules in RULES_MODES:
            for role in roles[rules]:
                add(check, rules, role)
    for rules in RULES_MODES:
        add(check_attack_drill, rules)
    for rules in RULES_MODES:
        for role in MODE_ROLES[rules]:
            add(check_receive_limits, rules, role)
    for check in (
        check_receive_limits_elsewhere,
        check_answer_glide,
        check_zones_courts,
        check_watch_move,
        check_reveal_motion,
        check_common_mistakes,
    ):
        add(check)
    return found


def shard_of(names: list[str], count: int) -> list[int]:
    """The shard of each unit: the costliest first, each to the shard with the least work so far."""
    load = [0.0] * count
    shard = [0] * len(names)
    by_cost = sorted(range(len(names)), key=lambda i: -COST.get(names[i].split()[0], DEFAULT_COST))
    for i in by_cost:
        shard[i] = load.index(min(load))
        load[shard[i]] += COST.get(names[i].split()[0], DEFAULT_COST)
    return shard


def parse_shard(text: str) -> tuple[int, int]:
    """Reads "K/N" (1 <= K <= N) as a zero-based shard index and the shard count."""
    m = re.fullmatch(r"([1-9][0-9]*)/([1-9][0-9]*)", text)
    if not m or int(m.group(1)) > int(m.group(2)):
        raise argparse.ArgumentTypeError(f"expected K/N with 1 <= K <= N, got {text!r}")
    return int(m.group(1)) - 1, int(m.group(2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Solo match scoring and the Attack step picture.")
    parser.add_argument("--shard", type=parse_shard, default=(0, 1), help="run only shard K of N, e.g. 1/4")
    parser.add_argument("--list", action="store_true", help="print the units of the shard and stop")
    args = parser.parse_args()
    index, count = args.shard
    every = units()
    shard = shard_of([name for name, _ in every], count)
    mine = [(name, check) for (name, check), k in zip(every, shard, strict=True) if k == index]
    if args.list:
        print("\n".join(name for name, _ in mine))
        return
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for name, check in mine:
            start = time.monotonic()
            check(browser)
            print(f"unit {name}: {time.monotonic() - start:.0f} s", flush=True)
        browser.close()
    label = f"MATCH TEST (shard {index + 1}/{count}):" if count > 1 else "MATCH TEST:"
    print(label, "ok" if not FAIL else f"{len(FAIL)} failures", flush=True)
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
