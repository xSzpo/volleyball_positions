"""Playwright end-to-end sweep of index.html.

Usage: python src/tests/qa.py [m|d] [--quick] [--all-combos] [--seed N], where m is
phone size in light theme and d is desktop size in dark theme. --quick runs a reduced
sweep for the edit-and-test loop; the default is the full sweep. The match section
plays each single step, all steps and two combos picked with the seed; --all-combos
plays all 15.
"""

import argparse
import itertools
import random
import re
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from playwright.sync_api import Browser, Error, Page, ViewportSize, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

FAIL: list[str] = []
START = time.monotonic()


def section(name: str) -> None:
    print(f"# {name} ({time.monotonic() - START:.0f} s)", flush=True)


def fail(m: str) -> None:
    FAIL.append(m)
    print("FAIL:", m, flush=True)


URL = (ROOT / "index.html").as_uri() + "?ff=all&anim=0"
MODE_ROLES = {
    "simple": ["MB", "OH1", "OH2", "OP", "S", "L"],
    "official": ["MB1", "MB2", "OH1", "OH2", "OP", "S", "L"],
}
RULES = list(MODE_ROLES)
PHASES = ["start", "rec", "ar", "serve"]
STEPS = ["start", "serve", "rec", "ar"]
QUICK_COMBOS = [("start", "rec"), ("serve", "ar")]

# The next forward control in a match or drill, read in one call so a timer
# (the 400 ms lock on #gNext after scoring) cannot change the state between checks.
# Only that lock is worth waiting for; with no control and no lock the page is stuck.
NEXT_ACTION_JS = """([nb, next, off, end]) => {
  const shown = (e) => !!e && e.getClientRects().length > 0 && getComputedStyle(e).visibility !== "hidden";
  const usable = (e) => shown(e) && !e.disabled && !e.closest('[aria-disabled="true"]');
  if (end && shown(document.querySelector(end))) return "end";
  if ([...document.querySelectorAll(nb + " button")].some(usable)) return "nb";
  const n = document.querySelector(next);
  if (usable(n)) return "next";
  const o = document.querySelector(off);
  if (o && !o.disabled) return "answer";
  return shown(n) && n.getAttribute("aria-disabled") === "true" ? null : "stuck";
}"""


def collect_errors(errs: list[str]) -> Callable[[Error], None]:
    return lambda e: errs.append(str(e))


def vis_en(pg: Page, sel: str) -> bool:
    loc = pg.locator(sel)
    return loc.count() > 0 and loc.first.is_visible() and loc.first.is_enabled()


def next_action(pg: Page, nb: str, next_: str, off: str, end: str | None = None) -> str | None:
    """Wait out the lock after scoring, then name the usable forward control; None if there is none."""
    try:
        handle = pg.wait_for_function(NEXT_ACTION_JS, arg=[nb, next_, off, end], timeout=30000)
    except Error:
        return None
    action = str(handle.json_value())
    return None if action == "stuck" else action


def wait_ready(pg: Page) -> None:
    pg.wait_for_function("document.readyState === 'complete' && !!document.querySelector('#setchips button')")


def tap(pg: Page, svg: str, x: float | None = None, y: float | None = None) -> None:
    box = pg.locator(svg).bounding_box()
    assert box is not None
    x = random.random() if x is None else x
    y = 0.9 * random.random() if y is None else y  # the bottom tenth is the off court pill
    pg.mouse.click(box["x"] + box["width"] * x, box["y"] + box["height"] * y)


def open_setup(pg: Page) -> None:
    if pg.locator("#setupPanel").is_hidden():
        pg.click("#roleChip")


def close_setup(pg: Page) -> None:
    if pg.locator("#setupPanel").is_visible():
        pg.click("#roleChip")


def pick_role(pg: Page, role: str) -> None:
    open_setup(pg)
    pg.click(f'.role[data-r="{role}"]')


def pick_rules(pg: Page, mode: str) -> None:
    open_setup(pg)
    pg.click(f'.rulesmode [data-rm="{mode}"]')
    close_setup(pg)


def open_fold(pg: Page, sel: str) -> None:
    if pg.get_attribute(sel, "open") is None:
        pg.click(f"{sel} > summary")


def menu_open(pg: Page) -> bool:
    return pg.is_visible("#setupPanel") and pg.get_attribute("#roleChip", "aria-expanded") == "true"


def check_header(pg: Page, tag: str) -> None:
    """The role and rules list unrolls under the header button.

    Covers the first visit, anchoring, no backdrop, the open and close paths and the keyboard.
    """
    if not menu_open(pg) or not pg.is_visible("#setupNudge"):
        fail(f"{tag} first visit: role list not open with nudge")
    if pg.is_visible(".rulesmode"):
        fail(f"{tag} first visit: the role list has more than one job")
    if not pg.is_visible("#subtitle"):
        fail(f"{tag} first visit: subtitle hidden")
    pg.click('.role[data-r="OH1"]')
    if pg.is_visible("#setupPanel"):
        fail(f"{tag} role pick did not close the list")
    if pg.get_attribute("#roleChip", "data-role") != "OH1" or "Outside 1" not in (
        pg.get_attribute("#roleChip", "aria-label") or ""
    ):
        fail(f"{tag} role button does not show the role")
    if " ".join(pg.inner_text("#roleChip").split()) != "Outside 1 · Simplified":
        fail(f"{tag} role button text is {pg.inner_text('#roleChip')!r}")
    chip = pg.locator("#roleChip").bounding_box()
    assert chip is not None
    if chip["height"] < 44 or chip["height"] > 48:
        fail(f"{tag} role button is not one 44 px line: {chip}")
    if pg.evaluate("document.documentElement.scrollWidth > innerWidth"):
        fail(f"{tag} the header scrolls sideways")
    pg.click("#roleChip")
    if not menu_open(pg):
        fail(f"{tag} role button did not open the list")
    if pg.evaluate("document.activeElement.dataset.r") != "OH1":
        fail(f"{tag} opening the list does not focus the current role")
    menu = pg.locator("#setup").bounding_box()
    assert menu is not None
    width = pg.evaluate("innerWidth")
    if not (chip["y"] + chip["height"] <= menu["y"] <= chip["y"] + chip["height"] + 16):
        fail(f"{tag} the list is not anchored under the button: button {chip}, list {menu}")
    if menu["x"] > chip["x"] + chip["width"] or menu["x"] < 0 or menu["x"] + menu["width"] > width:
        fail(f"{tag} the list is not under the button or leaves the screen: button {chip}, list {menu}")
    small = pg.eval_on_selector_all(
        "#setup button", "els => els.filter(e => e.getBoundingClientRect().height < 44).map(e => e.textContent.trim())"
    )
    if small:
        fail(f"{tag} list tap targets under 44 px: {small}")
    covered = pg.evaluate(
        "(() => { const el = document.elementFromPoint(2, innerHeight - 2);"
        " return !el || document.getElementById('setup').contains(el)"
        " || getComputedStyle(el).position === 'fixed'; })()"
    )
    if covered or pg.evaluate("document.querySelector('.wrap').inert"):
        fail(f"{tag} the open list has a backdrop or blocks the page")
    pg.click('.rulesmode [data-rm="official"]')
    if pg.is_visible("#setupPanel") or pg.evaluate("document.activeElement.id") != "roleChip":
        fail(f"{tag} a rules pick did not close the list and focus the button")
    if "Official rules" not in (pg.get_attribute("#roleChip", "aria-label") or ""):
        fail(f"{tag} role button label does not name the rules")
    pg.click("#roleChip")
    pg.click('.rulesmode [data-rm="simple"]')
    pg.click("#roleChip")
    pg.click("#roleChip")
    if pg.is_visible("#setupPanel") or pg.get_attribute("#roleChip", "aria-expanded") != "false":
        fail(f"{tag} a second tap on the button did not close the list")
    pg.focus("#roleChip")
    pg.keyboard.press("Enter")
    if not menu_open(pg):
        fail(f"{tag} Enter on the button did not open the list")
    pg.keyboard.press("Tab")
    if not pg.evaluate("document.getElementById('setup').contains(document.activeElement)") or not menu_open(pg):
        fail(f"{tag} Tab inside the open list left it")
    learn_tag = pg.inner_text("#learnTag")
    pg.evaluate("document.body.dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowRight', bubbles: true}))")
    if pg.inner_text("#learnTag") != learn_tag:
        fail(f"{tag} an arrow key with the list open changed the rotation")
    pg.keyboard.press("Escape")
    if pg.is_visible("#setupPanel") or pg.evaluate("document.activeElement.id") != "roleChip":
        fail(f"{tag} Escape did not close the list and focus the button")
    pg.click("#roleChip")
    pg.focus('.rulesmode [data-rm="official"]')
    pg.keyboard.press("Tab")
    if pg.is_visible("#setupPanel") or pg.evaluate("document.activeElement.id") != "themeBtn":
        fail(f"{tag} Tab past the list did not close it and move on")
    pg.click("#roleChip")
    pg.mouse.click(5, 5)
    if pg.is_visible("#setupPanel"):
        fail(f"{tag} a tap outside did not close the list")
    pg.reload()
    wait_ready(pg)
    if pg.is_visible("#setupPanel") or pg.is_visible("#setupNudge") or pg.is_visible("#subtitle"):
        fail(f"{tag} returning visit: role sheet or subtitle shown")
    pg.click("#tabSets")
    if not pg.is_visible("#roleChip"):
        fail(f"{tag} role chip hidden on Sets")
    pg.click("#tabLearn")
    for sel in ["#thumbsBox", "#allRots"]:
        if pg.get_attribute(sel, "open") is not None:
            fail(f"{tag} {sel} open by default")
    open_fold(pg, "#allRots")
    if pg.locator("#rotTable tbody tr").count() != 6:
        fail(f"{tag} all-rotations table does not have 6 rows")
    pg.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    pg.click("#tabDrill")
    top = pg.evaluate("document.getElementById('drill').getBoundingClientRect().top")
    if not 0 <= top < pg.evaluate("innerHeight") / 2:
        fail(f"{tag} tab switch left the tab content at {top}px")
    pg.click("#tabLearn")


def check_court_look(pg: Page, tag: str, phone: bool) -> None:
    """Learn court: title tag, square viewBox, your player ringed, labelled markers, haloed routes, fits the phone."""
    pick_role(pg, "OH1")
    pg.click('.rot[data-i="0"]')
    pg.click('.ph[data-k="rec"]')
    if pg.inner_text("#learnTag").strip() != "R1 (H1) · Reception":
        fail(f"{tag} title tag reads {pg.inner_text('#learnTag')!r}")
    if pg.get_attribute("#courtL", "viewBox") != "-4 -14 108 127":
        fail(f"{tag} court viewBox is {pg.get_attribute('#courtL', 'viewBox')!r}")
    if pg.locator("#courtL .me-ring").count() != 1 or pg.locator('#courtL .mk[data-p="OH1"] .me-ring').count() != 1:
        fail(f"{tag} your player is not the one ringed")
    labels: list[str] = pg.eval_on_selector_all("#courtL .mk text", "els => els.map(e => e.textContent)")
    if sorted(labels) != sorted(["S", "OH1", "MB", "OP", "OH2", "L"]):
        fail(f"{tag} marker labels read {labels}")
    if pg.locator("#courtL .rt").count():
        fail(f"{tag} routes drawn in Reception")
    pg.click('.ph[data-k="serve"]')
    if (
        not pg.locator("#courtL .rt").count()
        or pg.locator("#courtL .rt").count() != pg.locator("#courtL .rt .halo").count()
    ):
        fail(f"{tag} Our serve route missing or without a halo")
    pg.click('.ph[data-k="ar"]')
    if pg.locator("#courtL .rt").count() or pg.get_attribute("#courtL .ball", "opacity") != "1":
        fail(f"{tag} Base draws routes or no ball")
    if phone:
        pg.evaluate("window.scrollTo(0, 0)")
        view = pg.evaluate("[innerWidth, innerHeight]")
        box = pg.locator("#courtL").bounding_box()
        marker = pg.locator('#courtL .mk[data-p="OH1"] circle:not(.hit)').last.bounding_box()
        if box is None or box["x"] < 0 or box["x"] + box["width"] > view[0] or box["y"] + box["height"] > view[1]:
            fail(f"{tag} court {box} does not fit the {view} screen")
        if marker is None or marker["width"] < 36:
            fail(f"{tag} marker {marker} is under 36 px")
        if pg.locator(".tab small").first.is_visible():
            fail(f"{tag} tab captions shown on a phone")
    pg.click('.ph[data-k="rec"]')
    check_drill_pill(pg, tag)


def check_drill_pill(pg: Page, tag: str) -> None:
    """In Drill a tap on the off court pill answers "I'm off court"; the feedback shows the solid pill when off."""
    pg.click("#tabDrill")
    wait_ready(pg)
    pg.locator("#courtD").scroll_into_view_if_needed()
    x, y = pg.evaluate(
        "() => { const m = document.getElementById('courtD').getScreenCTM();"
        " return [m.a * 12 + m.e, m.d * 107 + m.f]; }"
    )
    pg.mouse.click(x, y)
    texts: list[str] = pg.eval_on_selector_all("#courtD > text", "els => els.map(e => e.textContent)")
    if pg.inner_text("#dq").endswith("Rotation"):
        if "you: off court" not in texts or pg.locator("#fb .rotgrades").count():
            fail(f"{tag} a tap on the Drill off court pill at Rotate did not mark you off: {texts}")
        pg.click("#tabLearn")
        return
    feedback = pg.inner_text("#fb")
    if "you are off" not in feedback and "you are on court" not in feedback:
        fail(f"{tag} a tap on the Drill off court pill scored as a spot: {feedback!r}")
    if ("you are off" in feedback) != ("you: off court" in texts):
        fail(f"{tag} Drill feedback pill {texts} does not match {feedback!r}")
    pg.click("#tabLearn")


def check_page(pg: Page, ctx: str) -> None:
    t = pg.inner_text("body")
    if re.search(r"\bundefined\b|\bNaN\b|\[object|\bnull\b", t):
        fail(f"{ctx}: bad text in page")
    if re.search(r"\(S\d\)", t):
        fail(f"{ctx}: a rotation label still uses S")
    w = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    if w > 1:
        fail(f"{ctx}: horizontal overflow {w}px")


def play_match(pg: Page, ctx: str, maxsteps: int = 200) -> bool:
    """Play until end. At every state some forward control must exist."""
    n = 0
    while n < maxsteps:
        n += 1
        action = next_action(pg, "#gnb", "#gNext", "#gOff", "#gEnd")
        if action == "end":
            return True
        if action == "nb":
            btns = pg.locator("#gnb button:enabled")
            btns.nth(random.randrange(btns.count())).click()
            continue
        if action == "next":
            pg.click("#gNext")
            continue
        if action == "answer":
            r = random.random()
            if r < 0.15 and pg.locator("#gHelp").is_enabled():
                pg.click("#gHelp")
                continue
            if r < 0.35:
                pg.click("#gOff")
                continue
            tap(pg, "#courtG")
            continue
        fail(f"{ctx}: STUCK in match at {pg.inner_text('#gTitle')} / {pg.inner_text('#gStepName')}")
        return False
    fail(f"{ctx}: match did not finish in {maxsteps} actions")
    return False


def drill_steps(pg: Page, ctx: str, k: int = 30) -> None:
    for _ in range(k):
        action = next_action(pg, "#dnb", "#nextBtn", "#offBtn")
        if action == "nb":
            b = pg.locator("#dnb button:enabled")
            b.nth(random.randrange(b.count())).click()
            continue
        if action == "next":
            pg.click("#nextBtn")
            continue
        if action == "answer":
            (pg.click("#offBtn") if random.random() < 0.3 else tap(pg, "#courtD"))
            continue
        fail(f"{ctx}: STUCK in drill at {pg.inner_text('#dq')}")
        return


def sweep_learn(pg: Page, tag: str, quick: bool) -> None:
    """Every role, rotation and phase under both rules; quick: one rules mode and one phase per rotation."""
    combos = [(rm, role) for rm in RULES for role in MODE_ROLES[rm]]
    for ri, (rm, role) in enumerate(combos):
        if quick and rm != RULES[MODE_ROLES[rm].index(role) % 2]:
            continue
        pick_rules(pg, rm)
        pick_role(pg, role)
        for i in range(6):
            pg.click(f'.rot[data-i="{i}"]')
            for ph in [PHASES[(i + ri) % 4]] if quick else PHASES:
                pg.click(f'.ph[data-k="{ph}"]')
                cue = pg.inner_text("#cue")
                if not cue.strip():
                    fail(f"{tag} empty cue {role} R{i + 1} {ph}")
        check_page(pg, f"{tag} learn {rm} {role}")
    # keyboard nav
    pg.click('.rot[data-i="0"]')
    pg.keyboard.press("ArrowLeft")
    if pg.get_attribute('.rot[data-i="5"]', "aria-pressed") != "true":
        fail(f"{tag} ArrowLeft wrap failed")
    pg.keyboard.press("ArrowRight")


def sweep_drill(pg: Page, tag: str, quick: bool) -> None:
    """All roles, visibility modes, neighbour on/off and rules modes; quick: each role once."""
    section("DRILL all roles")
    pg.click("#tabDrill")
    for rm in RULES:
        pick_rules(pg, rm)
        for ri, role in enumerate(MODE_ROLES[rm]):
            if quick and rm != RULES[ri % 2]:
                continue
            pick_role(pg, role)
            for v in [["none", "ref", "all"][ri % 3]] if quick else ["none", "ref", "all"]:
                pg.click(f'.vis[data-vis="drill"] button[data-v="{v}"]')
                if random.random() < 0.5:
                    open_fold(pg, "#dOpts")
                    pg.click("#nbDrill")
                drill_steps(pg, f"{tag} drill {rm} {role} {v}", 6 if quick else 12)
            check_page(pg, f"{tag} drill {role}")
    # switch role mid neighbour-check
    pick_role(pg, "OH1")
    for _ in range(40):
        if "Reception" in pg.inner_text("#dq") and pg.locator("#offBtn").is_enabled():
            break
        drill_steps(pg, tag + " seek", 1)
    if not pg.is_checked("#nbDrill"):
        open_fold(pg, "#dOpts")
        pg.click("#nbDrill")
    tap(pg, "#courtD", 0.5, 0.7)
    pick_role(pg, "L")
    drill_steps(pg, f"{tag} drill after role switch mid-check", 5)
    # tab switch mid-check and back
    pick_role(pg, "OH2")
    for _ in range(40):
        if "Reception" in pg.inner_text("#dq") and pg.locator("#offBtn").is_enabled():
            break
        drill_steps(pg, tag + " seek", 1)
    tap(pg, "#courtD", 0.5, 0.7)
    pg.click("#tabLearn")
    pg.click("#tabDrill")
    drill_steps(pg, f"{tag} drill after tab switch mid-check", 5)
    # review flow
    for _ in range(15 if quick else 40):
        drill_steps(pg, tag + " build misses", 1)
    if pg.is_visible("#reviewBtn"):
        if vis_en(pg, "#nextBtn") is False and vis_en(pg, "#dnb button:enabled"):
            pg.locator("#dnb button").last.click()
        pg.click("#reviewBtn")
        for _ in range(40):
            if pg.inner_text("#dq") == "Review done":
                break
            drill_steps(pg, tag + " review", 1)
        if pg.inner_text("#dq") != "Review done":
            fail(f"{tag} review did not finish")
        else:
            pg.click("#nextBtn")
            drill_steps(pg, tag + " after review", 4)
    else:
        fail(f"{tag} review button never appeared")
    open_fold(pg, "#dOpts")
    pg.click("#resetBtn")
    drill_steps(pg, tag + " after reset", 3)


DRILL_STEP_NAME = {"start": "Rotation", "serve": "Our serve", "rec": "Reception", "ar": "Attack"}


def drill_picked(pg: Page) -> list[str]:
    return [
        str(s) for s in pg.eval_on_selector_all('#dSteps [aria-pressed="true"]', "els => els.map(e => e.dataset.s)")
    ]


def check_drill_steps(browser: Browser, tag: str) -> None:
    """The Drill steps picker: asks only the picked steps, is stored, keeps one step on and fits a 390 x 664 phone."""
    section("DRILL steps picker")
    ctx = browser.new_context(viewport={"width": 390, "height": 664}, is_mobile=True, has_touch=True)
    ctx.add_init_script("if (!localStorage.getItem('ksv51:role')) localStorage.setItem('ksv51:role', '\"OH1\"')")
    pg = ctx.new_page()
    errs: list[str] = []
    pg.on("pageerror", collect_errors(errs))
    pg.goto(URL)
    wait_ready(pg)
    pg.click("#tabDrill")
    if drill_picked(pg) != STEPS:
        fail(f"{tag} drill steps default to {drill_picked(pg)}, not all")
    labels = pg.eval_on_selector_all("#dSteps button", "els => els.map(e => e.textContent.trim())")
    if labels != ["Rotate", "Our serve", "Receive", "Attack"]:
        fail(f"{tag} drill step chips read {labels}")
    pg.evaluate("window.scrollTo(0, 0)")
    view = pg.evaluate("[innerWidth, innerHeight]")
    boxes = pg.eval_on_selector_all(
        "#dSteps button",
        "els => els.map(e => { const r = e.getBoundingClientRect(); return [r.x, r.y, r.width, r.height]; })",
    )
    if len({round(b[1]) for b in boxes}) != 1:
        fail(f"{tag} drill step chips wrap onto more than one row: {boxes}")
    for x, y, w, h in boxes:
        if w < 44 or h < 44 or x < 0 or x + w > view[0] or y + h > view[1]:
            fail(f"{tag} drill step chip {x, y, w, h} under 44 px or off the {view} screen")
    if pg.evaluate(
        "[...document.querySelectorAll('#dSteps, #dSteps button')].some(e => e.scrollWidth > e.clientWidth)"
    ):
        fail(f"{tag} drill step chip text overflows its chip")
    picker = pg.locator("#dSteps").bounding_box()
    court = pg.locator("#courtD").bounding_box()
    off = pg.locator("#offBtn").bounding_box()
    assert picker and court and off
    if picker["y"] + picker["height"] > court["y"] or picker["y"] + picker["height"] > off["y"]:
        fail(f"{tag} drill steps picker {picker} covers the court {court} or the buttons {off}")
    check_page(pg, f"{tag} drill steps")
    for step in ["serve", "rec", "ar"]:
        pg.tap(f'#dSteps [data-s="{step}"]')
    if drill_picked(pg) != ["start"] or pg.get_attribute('#dSteps [data-s="start"]', "aria-disabled") != "true":
        fail(f"{tag} drill steps after switching three off: {drill_picked(pg)}")
    look = (
        "e => { const c = getComputedStyle(e);"
        " return [c.outlineStyle, c.outlineWidth, c.outlineColor, c.boxShadow, c.borderColor, c.backgroundColor]; }"
    )
    tapped, other = (pg.eval_on_selector(f'#dSteps [data-s="{s}"]', look) for s in ("ar", "serve"))
    if tapped != other or pg.evaluate("document.activeElement.matches('#dSteps button')"):
        fail(f"{tag} a tapped off step chip looks {tapped}, other off chips {other}")
    if "Rotation" not in pg.inner_text("#dq"):
        fail(f"{tag} the open question {pg.inner_text('#dq')!r} was not replaced by a Rotation one")
    pg.click('#dSteps [data-s="start"]', force=True)
    if drill_picked(pg) != ["start"]:
        fail(f"{tag} the last drill step could be switched off: {drill_picked(pg)}")
    for picked in (["start"], ["serve", "ar"]):
        if picked != ["start"]:
            for step in ["serve", "ar", "start"]:
                pg.click(f'#dSteps [data-s="{step}"]')
            if drill_picked(pg) != picked:
                fail(f"{tag} could not pick drill steps {picked}: {drill_picked(pg)}")
            weak = pg.inner_text("#weak")
            if "No weak spots in the steps you picked." not in weak or pg.is_visible("#reviewBtn"):
                fail(f"{tag} Rotation misses shown as weak spots for {picked}: {weak!r}")
        asked = set()
        for _ in range(20):
            asked.add(pg.inner_text("#dq").split(" · ")[-1])
            drill_miss(pg)
        if asked - {DRILL_STEP_NAME[s] for s in picked}:
            fail(f"{tag} drill with {picked} asked {sorted(asked)}")
        if picked == ["start"] and not pg.is_visible("#reviewBtn"):
            fail(f"{tag} 20 Rotation misses gave no Review weak spots")
    pg.click("#reviewBtn")
    if not re.search(r"Review 1/\d · .* · (Our serve|Attack)$", pg.inner_text("#dq")):
        fail(f"{tag} Review weak spots opened {pg.inner_text('#dq')!r}, not a picked step")
    pg.reload()
    wait_ready(pg)
    pg.click("#tabDrill")
    if drill_picked(pg) != ["serve", "ar"]:
        fail(f"{tag} drill steps not restored from storage: {drill_picked(pg)}")
    pg.evaluate("localStorage.setItem('ksv51:drillSteps', '[\"nope\", 3]')")
    pg.reload()
    wait_ready(pg)
    if drill_picked(pg) != STEPS:
        fail(f"{tag} a bad stored drill steps value gave {drill_picked(pg)}, not all")
    if errs:
        fail(f"{tag} drill steps JS errors: {errs[:3]}")
    ctx.close()


BOX_JS = "els => els.map(e => { const r = e.getBoundingClientRect(); return [r.width, r.height]; })"
# Selector of each tap target, and whether its width must be 44 px too.
TARGETS = {
    "drill": [('.vis[data-vis="drill"] button', False), ("#dName button", True), ("#nbDrillCheck", False)],
    "game": [
        ('.visbox .vis[data-vis="game"] button', False),
        ("#gOpts .steps label", False),
        ("#nbGameCheck", False),
        ("#setGameCheck", False),
        (".scoring > summary", False),
    ],
    "sets": [("#setchips button", False)],
}
TAB_BUTTON = {"drill": "#tabDrill", "game": "#tabGame", "sets": "#tabSets"}


def check_targets(pg: Page, tag: str) -> None:
    """The Drill, Match and Sets controls are tap targets at least 44 px high."""
    for tab, targets in TARGETS.items():
        pg.click(TAB_BUTTON[tab])
        for fold in ("#dOpts", "#gOpts"):
            if pg.is_visible(fold):
                open_fold(pg, fold)
        for sel, wide in targets:
            boxes = pg.eval_on_selector_all(sel, BOX_JS)
            if not boxes:
                fail(f"{tag} no {sel} to measure")
            for w, h in boxes:
                if h < 44 or (wide and w < 44):
                    fail(f"{tag} tap target {sel} is {w:.0f} x {h:.0f} px")
    pg.click("#tabLearn")


def check_learn_fit(browser: Browser, tag: str, quick: bool) -> None:
    """At 390 x 664 every Learn screen opens with all markers above the sticky Next row, which is in view.

    The quick sweep checks one role; your ring is the only marker that changes with the role.
    """
    section("LEARN fit 390 x 664 and tap targets")
    ctx = browser.new_context(viewport={"width": 390, "height": 664}, is_mobile=True, has_touch=True)
    ctx.add_init_script("if (!localStorage.getItem('ksv51:role')) localStorage.setItem('ksv51:role', '\"OH1\"')")
    pg = ctx.new_page()
    pg.goto(URL)
    wait_ready(pg)
    fit = """() => { const row = document.querySelector('.lctl').getBoundingClientRect();
      const marks = [...document.querySelectorAll('#courtL .mk circle:not(.hit)')]
        .map(e => [e.closest('.mk').dataset.p, e.getBoundingClientRect().bottom]);
      return [row.top, row.bottom, marks]; }"""
    for mode in RULES:
        pick_rules(pg, mode)
        for role in ["OH1"] if quick else MODE_ROLES[mode]:
            pick_role(pg, role)
            for ri in range(6):
                for phase in STEPS:
                    pg.click(f'.rot[data-i="{ri}"]')
                    pg.click(f'.ph[data-k="{phase}"]')
                    pg.evaluate("window.scrollTo(0, 0)")
                    top, bottom, marks = pg.evaluate(fit)
                    low = [p for p, b in marks if b > top]
                    if low or not marks or bottom > 664:
                        fail(f"{tag} {mode} {role} R{ri + 1} {phase}: {low} under the Next row at {top:.0f} px")
    check_targets(pg, tag + " 390 x 664")
    ctx.close()
    ctx = browser.new_context(viewport={"width": 1280, "height": 800})
    ctx.add_init_script("if (!localStorage.getItem('ksv51:role')) localStorage.setItem('ksv51:role', '\"OH1\"')")
    pg = ctx.new_page()
    pg.goto(URL)
    wait_ready(pg)
    check_targets(pg, tag + " 1280 x 800")
    ctx.close()


ZONES_JS = """() => {
  const g = document.querySelector('#courtL .zones');
  if (!g) return null;
  const first = document.querySelector('#courtL .mk, #courtL .am');
  const front = [], back = [];
  [...g.querySelectorAll('text')]
    .sort((a, b) => a.getAttribute('x') - b.getAttribute('x'))
    .forEach((t) => (t.getAttribute('y') < 42 ? front : back).push(t.textContent));
  return { shown: getComputedStyle(g).visibility === 'visible',
    under: !first || !!(g.compareDocumentPosition(first) & Node.DOCUMENT_POSITION_FOLLOWING),
    rows: front.join('') + '/' + back.join(''),
    pressed: document.querySelector('#lZones').getAttribute('aria-pressed') };
}"""


def zones_shown(pg: Page, ctx: str, on: bool) -> None:
    """The zone numbers layer: front 4 3 2, back 5 6 1, under the markers, shown and pressed as `on`."""
    state = pg.evaluate(ZONES_JS)
    if state is None:
        fail(f"{ctx}: no zone numbers layer on the Learn court")
    elif state["rows"] != "432/561" or not state["under"]:
        fail(f"{ctx}: zone numbers {state['rows']}, under the markers {state['under']}")
    elif state["shown"] != on or state["pressed"] != str(on).lower():
        fail(f"{ctx}: zones shown {state['shown']}, pressed {state['pressed']}, want {on}")


def check_zones(browser: Browser, tag: str) -> None:
    """The Zones toggle beside Next: off by default, stored, kept across screens, reloads and a Reception play."""
    section("LEARN zones toggle")
    ctx = browser.new_context(viewport={"width": 390, "height": 664}, is_mobile=True, has_touch=True)
    ctx.add_init_script("if (!localStorage.getItem('ksv51:role')) localStorage.setItem('ksv51:role', '\"OH1\"')")
    pg = ctx.new_page()
    pg.goto(URL)
    wait_ready(pg)
    zones_shown(pg, f"{tag} zones default", False)
    box, row = pg.locator("#lZones").bounding_box(), pg.locator("#lCtl").bounding_box()
    assert box is not None and row is not None
    if box["width"] < 44 or box["height"] < 44:
        fail(f"{tag} Zones tap target {box['width']:.0f} x {box['height']:.0f} px")
    if box["y"] < row["y"] - 0.5 or box["y"] + box["height"] > row["y"] + row["height"] + 0.5:
        fail(f"{tag} Zones is not in the sticky Next row")
    if pg.evaluate("(() => { const n = document.querySelector('#lNext'); return n.scrollWidth > n.clientWidth; })()"):
        fail(f"{tag} the Next label is cut off beside Zones")
    pg.click("#lZones")
    if pg.evaluate("localStorage.getItem('ksv51:zones')") != "true":
        fail(f"{tag} zones on is not stored")
    for ri in (0, 3):
        for phase in STEPS:
            pg.click(f'.rot[data-i="{ri}"]')
            pg.click(f'.ph[data-k="{phase}"]')
            zones_shown(pg, f"{tag} zones R{ri + 1} {phase}", True)
    pg.click("#lNext")
    zones_shown(pg, f"{tag} zones after Next", True)
    pg.goto(URL.replace("&anim=0", ""))
    wait_ready(pg)
    pg.click('.rot[data-i="0"]')
    pg.click('.ph[data-k="rec"]')
    zones_shown(pg, f"{tag} zones after a reload", True)
    pg.click("#lPlay")
    pg.wait_for_function("window.ksvLearn.anim()?.playing && window.ksvLearn.anim().t > 0")
    zones_shown(pg, f"{tag} zones while Reception plays", True)
    pg.click("#lZones")
    zones_shown(pg, f"{tag} zones off while Reception plays", False)
    if not pg.evaluate("window.ksvLearn.anim()?.playing"):
        fail(f"{tag} Zones stopped the Reception play")
    pg.reload()
    wait_ready(pg)
    zones_shown(pg, f"{tag} zones off after a reload", False)
    if pg.evaluate("localStorage.getItem('ksv51:zones')") != "false":
        fail(f"{tag} zones off is not stored")
    ctx.close()


def court_xy(pg: Page, x: float, y: float) -> tuple[float, float]:
    """The screen point of court spot (x, y) on the Drill court."""
    point = pg.evaluate(
        "([x, y]) => { const m = document.getElementById('courtD').getScreenCTM();"
        " return [m.a * x * 100 + m.e, m.d * y * 100 + m.f]; }",
        [x, y],
    )
    return float(point[0]), float(point[1])


def tap_spot(pg: Page, x: float, y: float) -> None:
    pg.mouse.click(*court_xy(pg, x, y))


def drill_miss(pg: Page) -> None:
    """Answer the open Drill question wrong and go on: at Rotate, every marker in the back row, left to right."""
    if pg.inner_text("#dq").endswith("Rotation"):
        pg.locator("#courtD").scroll_into_view_if_needed()
        for i in range(8):
            if pg.locator("#nextBtn").is_enabled():
                break
            tap_spot(pg, 0.1 + 0.2 * (i % 5), 0.93)
        pg.click("#nextBtn")
    else:
        pg.click("#offBtn")
    pg.click("#nextBtn")


ROT_NAME = re.compile(r"^(?:Review \d+/\d+ · )?(H|R)([1-6]) · Rotation$")


def rotate_lineup(pg: Page, ri: int, role: str) -> tuple[list[str], dict[str, tuple[float, float]]]:
    """The markers Rotate asks for in order (setter, you, your overlap partners) and each right spot."""
    spots = {
        str(o["p"]): (float(o["x"]), float(o["y"])) for o in pg.evaluate(f"window.ksvLearn.players({ri}, 'start')")
    }
    order = [] if role == "S" else ["S"]
    order.append(role)
    if role not in spots:
        return order, spots
    grid = {(round(x * 3 - 0.5), y > 0.42): p for p, (x, y) in spots.items()}
    col, back = round(spots[role][0] * 3 - 0.5), spots[role][1] > 0.42
    serving = "L" not in spots
    server = grid[(2, True)] if serving else None
    if role == server:
        return order, spots
    for key in [(col, not back), (col - 1, back), (col + 1, back)]:
        mate = grid.get(key)
        if mate and mate != server and mate not in order:
            order.append(mate)
    return order, spots


def rotate_question(pg: Page) -> tuple[int, str]:
    """The rotation index and how the open Rotate question names it (H or R)."""
    name = ROT_NAME.match(pg.inner_text("#dq"))
    if not name:
        return -1, ""
    how, n = name.group(1), int(name.group(2))
    if how == "R":
        return n - 1, how
    setters = [
        next(o for o in pg.evaluate(f"window.ksvLearn.players({ri}, 'start')") if o["p"] == "S") for ri in range(6)
    ]
    zone = {(0, False): 4, (1, False): 3, (2, False): 2, (0, True): 5, (1, True): 6, (2, True): 1}
    for ri, o in enumerate(setters):
        if zone[(round(o["x"] * 3 - 0.5), o["y"] > 0.42)] == n:
            return ri, how
    return -1, how


def markers(pg: Page) -> list[str]:
    return [str(t) for t in pg.eval_on_selector_all("#courtD g.mk", "els => els.map(e => e.dataset.p)")]


def answer_rotate(pg: Page, ctx: str, role: str, move: bool = False, wrong: bool = False) -> tuple[int, str]:
    """Place every Rotate marker in the asked order, on its right spot unless wrong, and check the prompts."""
    ri, how = rotate_question(pg)
    if ri < 0:
        fail(f"{ctx}: Rotate question {pg.inner_text('#dq')!r} does not name the rotation as H or R alone")
        return ri, how
    ctx = f"{ctx} R{ri + 1} as {how}"
    pg.locator("#courtD").evaluate("e => e.scrollIntoView({ block: 'center' })")
    if markers(pg):
        fail(f"{ctx}: teammates {markers(pg)} shown before the answer")
    order, spots = rotate_lineup(pg, ri, role)
    own = order.index(role)
    for k, mate in enumerate(order):
        who = "you" if mate == role else "the setter (S)" if mate == "S" else mate
        want = f"Tap where {who} stand{'' if mate == role else 's'}."
        prompt = pg.inner_text("#dsub")
        if prompt != want:
            fail(f"{ctx}: prompt {prompt!r}, expected {want!r}")
        if k <= own and want != ("Tap where you stand." if k == own else "Tap where the setter (S) stands."):
            fail(f"{ctx}: step {k + 1} asks {mate}, so the prompts up to yours differ by role")
        if pg.locator("#nextBtn").is_enabled():
            fail(f"{ctx}: Continue enabled before every marker is placed")
        if mate not in spots:
            pg.click("#offBtn")
            continue
        x, y = spots[mate]
        if wrong and k == 0:
            x += -1 / 3 if x > 0.5 else 1 / 3
        elif wrong and mate == role:
            x, y = 1 - x if x != 0.5 else 0.17, 0.21 if y > 0.42 else 0.71
        tap_spot(pg, x, y)
        if move and k == 0 and (mate != role or len(order) == 1):
            tap_spot(pg, x, y)
            if pg.inner_text("#dsub") != want:
                fail(f"{ctx}: a tap on the placed {mate} does not pick it up: {pg.inner_text('#dsub')!r}")
            tap_spot(pg, 0.5, 0.93)
            tap_spot(pg, 0.5, 0.93)
            tap_spot(pg, x, y)
        if mate == role and k < len(order) - 1:
            prompt, court = pg.inner_text("#dsub"), pg.inner_html("#courtD")
            tap_spot(pg, x, y)
            pg.click("#offBtn")
            if pg.inner_text("#dsub") != prompt or pg.inner_html("#courtD") != court:
                fail(f"{ctx}: your marker moved after your partners were asked: {pg.inner_text('#dsub')!r}")
    placed = sorted(markers(pg))
    if placed != sorted(m for m in order if m in spots):
        fail(f"{ctx}: placed markers {placed}, expected {order}")
    if not pg.inner_text("#dsub").startswith("All placed") or not pg.locator("#nextBtn").is_enabled():
        fail(f"{ctx}: Continue not ready after placing {order}: {pg.inner_text('#dsub')!r}")
    pg.click("#nextBtn")
    grades = pg.inner_text("#fb .rotgrades")
    right = " · ".join(f"{'You' if m == role else m}: right" for m in order)
    if not wrong and grades != right:
        fail(f"{ctx}: grades {grades!r}, expected {right!r}")
    if wrong and not (grades.startswith(f"{order[0]}: wrong") and "Not there" in pg.inner_text("#fb")):
        fail(f"{ctx}: the setter one zone off and a wrong you graded {grades!r}: {pg.inner_text('#fb')!r}")
    shown = sorted(markers(pg))
    if shown != sorted(spots):
        fail(f"{ctx}: feedback shows {shown}, not the lineup {sorted(spots)}")
    return ri, how


def check_drill_rotate(browser: Browser, tag: str, quick: bool) -> None:
    """Rotate from the name alone: no teammates first, H or R only, placement order per role, grading, storage."""
    section("DRILL rotate from the name")
    ctx = browser.new_context(viewport={"width": 390, "height": 664}, is_mobile=True, has_touch=True)
    ctx.add_init_script(
        "if (!localStorage.getItem('ksv51:role')) {"
        " localStorage.setItem('ksv51:role', '\"OH1\"');"
        " localStorage.setItem('ksv51:drillSteps', '[\"start\"]'); }"
    )
    pg = ctx.new_page()
    errs: list[str] = []
    pg.on("pageerror", collect_errors(errs))
    pg.goto(URL)
    wait_ready(pg)
    pg.click("#tabDrill")
    pg.click('.vis[data-vis="drill"] button[data-v="all"]')
    if pg.get_attribute('#dName [data-n="mixed"]', "aria-checked") != "true":
        fail(f"{tag} Rotate names do not default to Mixed")
    seen: set[tuple[str, int]] = set()
    names: set[str] = set()
    for rm in RULES:
        pick_rules(pg, rm)
        for role in MODE_ROLES[rm]:
            pick_role(pg, role)
            for n in range(3 if quick else 6):
                ri, how = answer_rotate(pg, f"{tag} {rm} {role}", role, move=n == 0)
                seen.add((rm, ri))
                names.add(how)
                pg.click("#nextBtn")
        if rm == "official":
            pick_role(pg, "L")
            for _ in range(30):
                if {("official", 2), ("official", 5)} <= seen:
                    break
                ri, how = answer_rotate(pg, f"{tag} {rm} L", "L")
                seen.add((rm, ri))
                pg.click("#nextBtn")
    if names != {"H", "R"}:
        fail(f"{tag} Mixed names asked only {names}")
    if not {("official", 2), ("official", 5)} <= seen:
        fail(f"{tag} Official R3 and R6 never came up at Rotate: {sorted(seen)}")
    pick_rules(pg, "simple")
    pick_role(pg, "OH1")
    before = pg.evaluate("JSON.parse(localStorage.getItem('ksv51:stats2') || '{}')")
    ri, _ = answer_rotate(pg, f"{tag} wrong", "OH1", wrong=True)
    after = pg.evaluate("JSON.parse(localStorage.getItem('ksv51:stats2') || '{}')")
    key = f"OH1|{ri}|start"
    old = before.get(key, {"ok": 0, "miss": 0})
    if after.get(key) != {"ok": old["ok"], "miss": old["miss"] + 1}:
        fail(f"{tag} a wrong Rotate answer counted {old} -> {after.get(key)}, not one miss")
    if re.search(r"\(H\d\) rotation", pg.inner_text("#weak")):
        fail(f"{tag} the weak spots pair R and H for a Rotate question: {pg.inner_text('#weak')!r}")
    pg.click("#nextBtn")
    open_fold(pg, "#dOpts")
    pg.click('#dName [data-n="h"]')
    answer_rotate(pg, f"{tag} before H", "OH1")
    pg.click("#nextBtn")
    for _ in range(4):
        answer_rotate(pg, f"{tag} H only", "OH1")
        if not pg.inner_text("#dq").startswith("H"):
            fail(f"{tag} Name as H asked {pg.inner_text('#dq')!r}")
        pg.click("#nextBtn")
    pg.reload()
    wait_ready(pg)
    pg.click("#tabDrill")
    if pg.get_attribute('#dName [data-n="h"]', "aria-checked") != "true" or not pg.inner_text("#dq").startswith("H"):
        fail(f"{tag} Name as H not restored: {pg.inner_text('#dq')!r}")
    pg.evaluate("localStorage.setItem('ksv51:drillName', '\"x\"')")
    pg.reload()
    wait_ready(pg)
    if pg.get_attribute('#dName [data-n="mixed"]', "aria-checked") != "true":
        fail(f"{tag} a bad stored Rotate name did not read as Mixed")
    check_page(pg, f"{tag} drill rotate")
    if errs:
        fail(f"{tag} drill rotate JS errors: {errs[:3]}")
    ctx.close()


def match_combos(quick: bool, all_combos: bool) -> list[tuple[str, ...]]:
    """The step combinations to play: every single step, all steps and two picked with the seed."""
    every = [c for r in range(1, 5) for c in itertools.combinations(STEPS, r)]
    if all_combos:
        return every
    if quick:
        return list(QUICK_COMBOS)
    fixed = [c for c in every if len(c) in (1, len(STEPS))]
    return fixed + random.sample([c for c in every if c not in fixed], 2)


def sweep_match(pg: Page, tag: str, combos: list[tuple[str, ...]], quick: bool) -> None:
    """The given step combinations with mixed orders, neighbour on/off and rules; then no steps."""
    section(f"MATCH: {len(combos)} step combos")
    pg.click("#tabGame")
    for ci, combo in enumerate(combos):
        rm = random.choice(RULES)
        pick_rules(pg, rm)
        role = MODE_ROLES[rm][ci % len(MODE_ROLES[rm])]
        pick_role(pg, role)
        if pg.is_visible("#gSettings"):
            pg.click("#gSettings")
        open_fold(pg, "#gOpts")
        for s_ in STEPS:
            if pg.is_checked(f"#gs-{s_}") != (s_ in combo):
                pg.click(f"#gs-{s_}")
        pg.check(f'input[name="gOrder"][value="{"mixed" if ci % 2 else "order"}"]')
        if random.random() < 0.5:
            pg.click("#nbGame")
        pg.click(f'.vis[data-vis="game"] button[data-v="{random.choice(["none", "ref", "all"])}"]')
        if pg.is_visible("#gSettings"):
            pg.click("#gSettings")
        pg.click("#gStart")
        exp = len(combo) * 6
        sn = pg.inner_text("#gStepName")
        m = re.search(r"of (\d+)", sn)
        if not m or int(m.group(1)) != exp:
            fail(f"{tag} combo {combo}: expected {exp} moments, got {sn}")
        ok = play_match(pg, f"{tag} match {combo} {role}")
        if ok:
            check_page(pg, f"{tag} match end {combo}")
            if pg.is_visible("#gReplay"):
                pg.click("#gReplay")
                play_match(pg, f"{tag} replay {combo}")
            pg.click("#gAgain")
            # quit mid-match
            for _ in range(3):
                if vis_en(pg, "#gNext"):
                    pg.click("#gNext")
                elif pg.locator("#gOff").is_enabled():
                    tap(pg, "#courtG")
            pg.click("#gQuit")
            if not pg.is_visible("#gSetup"):
                fail(f"{tag} quit did not return to setup")
    # no steps selected -> start disabled
    open_fold(pg, "#gOpts")
    for s_ in STEPS:
        if pg.is_checked(f"#gs-{s_}"):
            pg.click(f"#gs-{s_}")
    if pg.locator("#gStart").is_enabled():
        fail(f"{tag} start enabled with no steps")
    for s_ in ["rec"] if quick else STEPS:
        pg.click(f"#gs-{s_}")
    # role / rules change mid match
    pg.click("#gStart")
    tap(pg, "#courtG")
    pick_role(pg, "S")
    if not pg.is_visible("#gSetup"):
        fail(f"{tag} role change mid-match didn't reset")
    pg.click("#gStart")
    open_setup(pg)
    pick_rules(pg, "simple" if pg.get_attribute('[data-rm="official"]', "aria-checked") == "true" else "official")
    if not pg.is_visible("#gSetup"):
        fail(f"{tag} rules change mid-match didn't reset")
    pg.click("#gStart")
    pg.click("#tabSets")
    pg.click("#tabGame")
    play_match(pg, f"{tag} match after tab switch")
    # change vis mid match; Rotate moments have nobody on court, so no picker
    pg.click("#gAgain")
    for _ in range(40):
        if pg.is_visible("#gVisPlay") or pg.is_visible("#gEnd"):
            break
        if not pg.inner_text("#gStepName").startswith("Rotation"):
            fail(f"{tag} Show on court picker hidden at {pg.inner_text('#gStepName')}")
            break
        action = next_action(pg, "#gnb", "#gNext", "#gOff", "#gEnd")
        if action == "next":
            pg.click("#gNext")
        elif action == "nb":
            pg.locator("#gnb button:enabled").first.click()
        else:
            tap(pg, "#courtG")
    if pg.is_visible("#gVisPlay"):
        pg.click('.vis.compact button[data-v="all"]')
    play_match(pg, f"{tag} match vis change")


def sweep_sets(pg: Page, tag: str) -> None:
    section("SETS")
    pg.click("#tabSets")
    for s_ in ["1", "0", "2", "Shoot", "4", "7", "6", "A", "B", "C"]:
        pg.click(f'#setchips button[data-s="{s_}"]')
    for _ in range(12):
        btns = pg.locator("#setanswers button:enabled")
        if btns.count():
            btns.nth(random.randrange(btns.count())).click()
        if vis_en(pg, "#snext"):
            pg.click("#snext")
        else:
            fail(f"{tag} sets quiz: no next")
            break
    check_page(pg, f"{tag} sets")


def check_persistence(pg: Page, tag: str) -> None:
    section("PERSISTENCE")
    pg.click("#tabLearn")
    pick_rules(pg, "official")
    pick_role(pg, "OP")
    pg.click("#tabDrill")
    pg.click('.vis[data-vis="drill"] button[data-v="ref"]')
    pg.reload()
    wait_ready(pg)
    if pg.get_attribute('.role[data-r="OP"]', "aria-pressed") != "true":
        fail(f"{tag} role not remembered")
    if pg.get_attribute('[data-rm="official"]', "aria-checked") != "true":
        fail(f"{tag} rules mode not remembered")
    if pg.get_attribute('.vis[data-vis="drill"] button[data-v="ref"]', "aria-checked") != "true":
        fail(f"{tag} drill vis not remembered")
    pick_rules(pg, "simple")


CONFIGS: dict[str, tuple[ViewportSize, bool, Literal["light", "dark"]]] = {
    "m": ({"width": 390, "height": 844}, True, "light"),
    "d": ({"width": 1280, "height": 900}, False, "dark"),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mode", nargs="?", default="m", choices=sorted(CONFIGS))
    parser.add_argument("--quick", action="store_true", help="reduced sweep for the edit-and-test loop")
    parser.add_argument("--all-combos", action="store_true", help="play all 15 match step combinations")
    parser.add_argument("--seed", type=int, default=7, help="random seed, printed on failure for a replay")
    args = parser.parse_args()
    random.seed(args.seed)
    combos = match_combos(args.quick, args.all_combos)
    print(f"Seed {args.seed}. Match combos: {combos}", flush=True)
    vp, mobile, scheme = CONFIGS[args.mode]
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctxb = b.new_context(viewport=vp, is_mobile=mobile, has_touch=mobile, color_scheme=scheme)
        pg = ctxb.new_page()
        errs: list[str] = []
        pg.on("pageerror", collect_errors(errs))
        pg.goto(URL)
        wait_ready(pg)
        print("start", flush=True)
        tag = f"[{vp['width']} {scheme}]"
        check_page(pg, tag + " initial")
        check_header(pg, tag)
        check_court_look(pg, tag, mobile)
        sweep_learn(pg, tag, args.quick)
        sweep_drill(pg, tag, args.quick)
        check_drill_steps(b, tag)
        check_learn_fit(b, tag, args.quick)
        check_zones(b, tag)
        check_drill_rotate(b, tag, args.quick)
        sweep_match(pg, tag, combos, args.quick)
        sweep_sets(pg, tag)
        check_persistence(pg, tag)
        if errs:
            fail(f"{tag} JS errors: {errs[:3]}")
        ctxb.close()
        b.close()
    print(f"\nTOTAL FAILURES: {len(FAIL)} ({time.monotonic() - START:.0f} s)")
    if FAIL:
        flags = (" --quick" if args.quick else "") + (" --all-combos" if args.all_combos else "")
        print(f"Seed {args.seed}. Replay: python src/tests/qa.py {args.mode}{flags} --seed {args.seed}", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
