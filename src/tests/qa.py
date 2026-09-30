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

from playwright.sync_api import Error, Page, ViewportSize, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

FAIL: list[str] = []
START = time.monotonic()


def section(name: str) -> None:
    print(f"# {name} ({time.monotonic() - START:.0f} s)", flush=True)


def fail(m: str) -> None:
    FAIL.append(m)
    print("FAIL:", m, flush=True)


URL = (ROOT / "index.html").as_uri() + "?ff=all"
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
NEXT_ACTION_JS = """([nb, next, off, end]) => {
  const shown = (e) => !!e && e.getClientRects().length > 0 && getComputedStyle(e).visibility !== "hidden";
  const usable = (e) => shown(e) && !e.disabled && !e.closest('[aria-disabled="true"]');
  if (end && shown(document.querySelector(end))) return "end";
  if ([...document.querySelectorAll(nb + " button")].some(usable)) return "nb";
  if (usable(document.querySelector(next))) return "next";
  const o = document.querySelector(off);
  if (o && !o.disabled) return "answer";
  return null;
}"""


def collect_errors(errs: list[str]) -> Callable[[Error], None]:
    return lambda e: errs.append(str(e))


def vis_en(pg: Page, sel: str) -> bool:
    loc = pg.locator(sel)
    return loc.count() > 0 and loc.first.is_visible() and loc.first.is_enabled()


def next_action(pg: Page, nb: str, next_: str, off: str, end: str | None = None) -> str | None:
    """Wait until a forward control is usable and name it; None if there is none."""
    try:
        handle = pg.wait_for_function(NEXT_ACTION_JS, arg=[nb, next_, off, end], timeout=3000)
    except Error:
        return None
    action = handle.json_value()
    return str(action)


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
        pg.click("#setupDone")


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


def check_header(pg: Page, tag: str) -> None:
    """First visit opens the role sheet; a pick closes it; the header chip reopens it with the rules."""
    if not pg.is_visible("#setupPanel") or not pg.is_visible("#setupNudge"):
        fail(f"{tag} first visit: role sheet not open with nudge")
    if pg.is_visible(".rulesmode"):
        fail(f"{tag} first visit: the role sheet has more than one job")
    if not pg.is_visible("#subtitle"):
        fail(f"{tag} first visit: subtitle hidden")
    if pg.get_attribute("#howTo", "open") is None:
        fail(f"{tag} first visit: how-to not open")
    pg.click('.role[data-r="OH1"]')
    if pg.is_visible("#setupPanel"):
        fail(f"{tag} role pick did not close the sheet")
    if pg.inner_text("#roleChip").strip() != "OH1" or "Outside 1" not in (
        pg.get_attribute("#roleChip", "aria-label") or ""
    ):
        fail(f"{tag} role chip does not show the role")
    pg.click("#roleChip")
    if not pg.is_visible("#setupPanel") or pg.get_attribute("#roleChip", "aria-expanded") != "true":
        fail(f"{tag} role chip did not open the sheet")
    pg.click('.rulesmode [data-rm="official"]')
    if "Official rules" not in (pg.get_attribute("#roleChip", "aria-label") or ""):
        fail(f"{tag} role chip label does not name the rules")
    pg.click('.rulesmode [data-rm="simple"]')
    if not pg.evaluate("document.querySelector('.wrap').inert"):
        fail(f"{tag} the page behind the open sheet is not inert")
    for key in ["Tab"] * 12 + ["Shift+Tab"] * 12:
        pg.keyboard.press(key)
        if not pg.evaluate("document.getElementById('setup').contains(document.activeElement)"):
            fail(f"{tag} Tab left the open sheet")
            break
    learn_tag = pg.inner_text("#learnTag")
    pg.evaluate("document.body.dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowRight', bubbles: true}))")
    if pg.inner_text("#learnTag") != learn_tag:
        fail(f"{tag} an arrow key behind the open sheet changed the rotation")
    pg.keyboard.press("Escape")
    if pg.is_visible("#setupPanel"):
        fail(f"{tag} Escape did not close the sheet")
    if pg.evaluate("document.querySelector('.wrap').inert") or pg.evaluate("document.activeElement.id") != "roleChip":
        fail(f"{tag} closing the sheet did not restore the page and focus the role chip")
    pg.click("#roleChip")
    pg.mouse.click(5, 5)
    if pg.is_visible("#setupPanel"):
        fail(f"{tag} a tap outside did not close the sheet")
    pg.reload()
    wait_ready(pg)
    if pg.is_visible("#setupPanel") or pg.is_visible("#setupNudge") or pg.is_visible("#subtitle"):
        fail(f"{tag} returning visit: role sheet or subtitle shown")
    if pg.get_attribute("#howTo", "open") is not None:
        fail(f"{tag} returning visit: how-to open")
    pg.click("#tabSets")
    if not pg.is_visible("#roleChip"):
        fail(f"{tag} role chip hidden on Sets")
    pg.click("#tabLearn")
    for sel in ["#checks", "#thumbsBox", "#allRots"]:
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
    if pg.inner_text("#learnTag").strip() != "R1 (S1) · Reception":
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
    pg.click('.ph[data-k="ar"]')
    if (
        not pg.locator("#courtL .rt").count()
        or pg.locator("#courtL .rt").count() != pg.locator("#courtL .rt .halo").count()
    ):
        fail(f"{tag} after reception routes missing or without a halo")
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
    feedback = pg.inner_text("#fb")
    if "you are off" not in feedback and "you are on court" not in feedback:
        fail(f"{tag} a tap on the Drill off court pill scored as a spot: {feedback!r}")
    texts: list[str] = pg.eval_on_selector_all("#courtD > text", "els => els.map(e => e.textContent)")
    if ("you are off" in feedback) != ("you: off court" in texts):
        fail(f"{tag} Drill feedback pill {texts} does not match {feedback!r}")
    pg.click("#tabLearn")


def check_page(pg: Page, ctx: str) -> None:
    t = pg.inner_text("body")
    if re.search(r"\bundefined\b|\bNaN\b|\[object|\bnull\b", t):
        fail(f"{ctx}: bad text in page")
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
    # change vis mid match
    pg.click("#gAgain")
    pg.click('.vis.compact button[data-v="all"]')
    play_match(pg, f"{tag} match vis change")


def sweep_sets(pg: Page, tag: str) -> None:
    section("SETS")
    pg.click("#tabSets")
    for s_ in ["1", "0", "2", "Shoot", "4", "Po", "Til", "7", "6"]:
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


def check_downloads(pg: Page, tag: str) -> None:
    section("DOWNLOADS")
    for k in ["schema", "sets"]:
        try:
            with pg.expect_download(timeout=5000) as d:
                pg.click(f'[data-dl="{k}"]')
            path = d.value.path()
            with open(path, "rb") as fh:
                data = fh.read(5)
            if data != b"%PDF-":
                fail(f"{tag} download {k} not a PDF")
        except Exception as e:
            fail(f"{tag} download {k} failed: {e}")


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
        ctxb = b.new_context(
            viewport=vp, is_mobile=mobile, has_touch=mobile, color_scheme=scheme, accept_downloads=True
        )
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
        sweep_match(pg, tag, combos, args.quick)
        sweep_sets(pg, tag)
        check_downloads(pg, tag)
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
