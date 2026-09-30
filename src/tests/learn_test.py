"""Playwright test of the Learn tab in index.html.

Walks every role, rotation and step of both rule sets with the Next button and
checks the cue, the overlap boundary lines and when they count (at the
whistle, from 1 October 2026), the Our serve rule text, that Next stays in
view on a phone, the SUB and MB texts, the Official walk-through table of
docs/v2.md and the Official libero rules.

Usage: python src/tests/learn_test.py
"""

import json
import re
import sys
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
URL = (ROOT / "index.html").as_uri() + "?ff=all&anim=0"
FAIL: list[str] = []
MODES = {
    "simple": ["MB", "OH1", "OH2", "OP", "S", "L"],
    "official": ["MB1", "MB2", "OH1", "OH2", "OP", "S", "L"],
}
PHASES = ["start", "serve", "rec", "ar"]
PHASE_NAMES = {"start": "Rotation", "serve": "Our serve", "rec": "Reception", "ar": "After reception"}
ROUTE_KEY = {"S": "s", "OP": "op", "MB": "mb", "MB1": "mb", "MB2": "mb", "OH1": "oh", "OH2": "oh", "L": "l"}
ROUTE_KEY["SUB"] = "sub"
ROTATION_NAMES = ["R1 (S1)", "R2 (S6)", "R3 (S5)", "R4 (S4)", "R5 (S3)", "R6 (S2)"]
# (mode, role, rotation, phase) -> (overlap sentence, partners whose limit is inside your marker)
EXPECTED = {
    ("official", "L", 0, "start"): ("Overlap: stay behind MB1, right of OH2 and left of S.", []),
    ("simple", "MB", 2, "start"): ("Overlap: stay in front of S and left of OH2.", []),
    ("simple", "S", 0, "rec"): ("Overlap: stay behind OH1 and right of L.", []),
    ("official", "OH2", 1, "rec"): ("Overlap: stay in front of L and left of OP.", ["L"]),
    ("simple", "L", 1, "rec"): ("Overlap: stay behind OH2 and left of S.", ["OH2", "S"]),
    # Official R3 and R6: the serving middle is off court when they serve, so it is nobody's limit.
    ("official", "OP", 2, "start"): ("Overlap: stay right of OH2.", []),
    ("official", "OH1", 2, "start"): ("Overlap: stay behind OH2 and right of S.", []),
    ("official", "OH2", 5, "start"): ("Overlap: stay behind OH1 and right of OP.", []),
}
# (mode, role, rotation): the middle who serves from zone 1 at the Rotation step and has no overlap limits.
SERVING_MIDDLE = {("official", "MB1", 2), ("official", "MB2", 5)}
# The overlap limits count at the whistle for the serve; before 1 October 2026 they counted at the service hit.
OLD_TIMING = re.compile(r"service hit|when the ball is served|at the serve\b|until the serve is made", re.IGNORECASE)
WHISTLE_MOVE = "From the server's first movement you may move."
OVERLAP_WHEN = {
    "start": "This is your rotation order. It counts at the whistle when the other team serves."
    " We serve now, so you may stand anywhere.",
    "rec": "These limits count at the whistle, not during the pass. " + WHISTLE_MOVE,
}
# Caption words -> the axis and direction your line must run from your marker.
SIDE = {"behind": ("y", -1), "in front of": ("y", 1), "right of": ("x", -1), "left of": ("x", 1)}

STATE = """() => {
  const court = document.querySelector('#courtL');
  const bounds = [...court.querySelectorAll('.bnd')].map(g => {
    const line = g.querySelector('line.route');
    return { p: g.dataset.p, stroke: line.getAttribute('stroke'),
      x1: +line.getAttribute('x1'), y1: +line.getAttribute('y1'),
      x2: +line.getAttribute('x2'), y2: +line.getAttribute('y2') };
  });
  const cue = document.querySelector('#cue');
  const title = cue.querySelector('b');
  const mine = court.querySelector('.me-ring circle');
  return { me: mine ? { x: +mine.getAttribute('cx'), y: +mine.getAttribute('cy') } : null,
    tag: document.querySelector('#learnTag').textContent, title: title ? title.textContent : '',
    cue: cue.innerText, bounds };
}"""


def fail(message: str) -> None:
    FAIL.append(message)
    print("FAIL:", message, flush=True)


def open_app(page: Page, stored: dict[str, str]) -> None:
    page.goto(URL)
    page.evaluate(
        "(s) => { localStorage.clear();"
        " for (const [k, v] of Object.entries(s)) localStorage.setItem('ksv51:' + k, JSON.stringify(v)); }",
        stored,
    )
    page.goto(URL)
    page.wait_for_function("document.readyState === 'complete' && !!document.querySelector('#lNext')")
    page.click("#tabLearn")


def learn(page: Page, rotation: int, phase: str) -> None:
    page.click(f'.rot[data-i="{rotation}"]')
    page.click(f'.ph[data-k="{phase}"]')


def on_court(page: Page, role: str) -> bool:
    shown: list[str] = page.eval_on_selector_all("#courtL .mk", "els => els.map(e => e.dataset.p)")
    return role in shown


def check_step(page: Page, mode: str, role: str, rotation: int, phase: str) -> None:
    tag = f"{mode} {role} {ROTATION_NAMES[rotation]} {phase}"
    state: dict[str, Any] = page.evaluate(STATE)
    if state["tag"] != f"{ROTATION_NAMES[rotation]} · {PHASE_NAMES[phase]}":
        fail(f"{tag}: Next showed {state['tag']!r}")
        return
    if not state["title"].strip() or len(state["cue"]) < 30:
        fail(f"{tag}: cue is empty: {state['cue']!r}")
    if re.search(r"undefined|NaN|null|\$\{", state["cue"]):
        fail(f"{tag}: cue has a template leak: {state['cue']!r}")
    if OLD_TIMING.search(state["cue"]):
        fail(f"{tag}: cue uses the old overlap timing: {state['cue']!r}")
    here = on_court(page, role)
    if phase == "serve" and (
        "may stand anywhere" not in state["cue"]
        or "may not block" not in state["cue"]
        or "front zone above the net" not in state["cue"]
    ):
        fail(f"{tag}: Our serve cue lacks the serving-team rule: {state['cue']!r}")
    if phase == "start" and (mode, role, rotation) in SERVING_MIDDLE:
        if not here or state["bounds"] or "Overlap:" in state["cue"] or "no overlap limits" not in state["cue"]:
            fail(f"{tag}: the serving middle should be on court with no limits: {state['cue']!r}, {state['bounds']}")
    elif phase in ("start", "rec") and here:
        if OVERLAP_WHEN[phase] not in state["cue"]:
            fail(f"{tag}: cue does not say when the overlap limits count: {state['cue']!r}")
        check_overlap(tag, state, EXPECTED.get((mode, role, rotation, phase)))
        for bound in state["bounds"]:
            if bound["stroke"] != f"var(--route-{ROUTE_KEY[bound['p']]})":
                fail(f"{tag}: line for {bound['p']} coloured {bound['stroke']}")
            if bound["x1"] != bound["x2"] and bound["y1"] != bound["y2"]:
                fail(f"{tag}: line for {bound['p']} is not straight along or across the court")
    elif state["bounds"]:
        fail(f"{tag}: boundary lines outside Rotation and Reception or off court: {state['bounds']}")


def check_overlap(tag: str, state: dict[str, Any], expected: tuple[str, list[str]] | None) -> None:
    """Every partner in the caption has a line running to their side, or is named as a limit you stand at."""
    overlap = re.search(r"Overlap: stay ([^.]*)\.", state["cue"])
    if not overlap:
        fail(f"{tag}: no overlap sentence: {state['cue']!r}")
        return
    tight_match = re.search(r"You stand right at the (.*) limits?\.", state["cue"])
    tight = tight_match.group(1).split(" and ") if tight_match else []
    sides = dict(
        (partner, words)
        for words, partner in re.findall(r"(behind|in front of|right of|left of) ([A-Z][A-Z0-9]*)", overlap.group(1))
    )
    lines = {bound["p"]: bound for bound in state["bounds"]}
    if expected and (overlap.group(0), tight) != expected:
        fail(f"{tag}: caption {overlap.group(0)!r}, tight {tight}, expected {expected}")
    if set(lines) | set(tight) != set(sides) or set(lines) & set(tight):
        fail(f"{tag}: lines {sorted(lines)} and tight {tight} do not match {overlap.group(0)!r}")
    if lines and "Each line ends at a limit you may not cross." not in state["cue"]:
        fail(f"{tag}: lines drawn without the line sentence: {state['cue']!r}")
    for partner, bound in lines.items():
        if partner not in sides or not state["me"]:
            continue
        axis, direction = SIDE[sides[partner]]
        if (bound[f"{axis}2"] - state["me"][axis]) * direction <= 0:
            fail(f"{tag}: line for {partner} ({sides[partner]}) runs the wrong way: {bound}, me {state['me']}")


def check_walk(page: Page, mode: str, role: str) -> None:
    """Next steps through the four steps of every rotation and wraps from R6 to R1."""
    open_app(page, {"role": role, "rulesMode": mode})
    learn(page, 0, "start")
    for rotation in range(6):
        for at, phase in enumerate(PHASES):
            check_step(page, mode, role, rotation, phase)
            expected = PHASE_NAMES[PHASES[at + 1]] if at < 3 else ROTATION_NAMES[(rotation + 1) % 6]
            if page.text_content("#lNext") != f"Next: {expected} ▸":
                fail(f"{mode} {role} R{rotation + 1} {phase}: Next reads {page.text_content('#lNext')!r}")
            page.click("#lNext")
    if page.inner_text("#learnTag") != f"{ROTATION_NAMES[0]} · {PHASE_NAMES['start']}":
        fail(f"{mode} {role}: Next after R6 After reception shows {page.inner_text('#learnTag')!r}")


def check_next_in_view(page: Page) -> None:
    """On a short phone Next belongs below the fold, yet it is drawn inside the viewport."""
    page.set_viewport_size({"width": 390, "height": 664})
    open_app(page, {"role": "S", "rulesMode": "simple"})
    learn(page, 0, "rec")
    page.evaluate("window.scrollTo(0, 0)")
    box: dict[str, float] = page.evaluate(
        "(() => { const r = document.querySelector('#lNext').getBoundingClientRect();"
        " const main = document.querySelector('.learnmain').getBoundingClientRect();"
        " return { top: r.top, bottom: r.bottom, height: innerHeight, natural: main.bottom}; })()"
    )
    page.set_viewport_size({"width": 390, "height": 844})
    if box["natural"] <= box["height"]:
        fail(f"Learn fits on a 664 px screen, so the sticky check proves nothing: {box}")
    if box["top"] < 0 or box["bottom"] > box["height"] + 1:
        fail(f"Next is outside the viewport: {box}")
    if box["bottom"] - box["top"] < 44:
        fail(f"Next tap target is {box['bottom'] - box['top']:.0f} px high")


def check_texts(page: Page) -> None:
    """Simplified SUB and MB texts come from describe() for every rotation and step."""
    open_app(page, {"role": "MB", "rulesMode": "simple"})
    texts: list[dict[str, Any]] = page.evaluate(
        "roles => roles.flatMap(r => [0,1,2,3,4,5].flatMap(ri => ['start','serve','rec','ar']"
        ".map(ph => ({ r, ri, ph, ...window.ksvLearn.describe(ri, ph, r) }))))",
        ["SUB", "MB"],
    )
    for text in texts:
        tag = f"{text['r']} R{text['ri'] + 1} {text['ph']}"
        if not text["t"] or not text["d"]:
            fail(f"{tag}: empty describe text {json.dumps(text)}")
        if "official" in text["d"].lower():
            fail(f"{tag}: Simplified text mentions the official rules: {text['d']!r}")
    sub = {(t["ri"], t["ph"]): t["d"] for t in texts if t["r"] == "SUB"}
    for rotation in (2, 5):
        if "may not serve" not in sub[(rotation, "serve")]:
            fail(f"SUB R{rotation + 1} Our serve: {sub[(rotation, 'serve')]!r}")
        if "libero comes back" not in sub[(rotation, "rec")]:
            fail(f"SUB R{rotation + 1} Reception: {sub[(rotation, 'rec')]!r}")


def check_rule_folds(page: Page) -> None:
    """The pre-serve checklist and the rules of thumb teach the whistle timing, not the service hit."""
    open_app(page, {"role": "OH1", "rulesMode": "simple"})
    for fold in ("#checks", "#thumbsBox"):
        text = " ".join((page.text_content(fold) or "").split())
        if "whistle" not in text or WHISTLE_MOVE not in text:
            fail(f"{fold} lacks the whistle timing: {text!r}")
        if OLD_TIMING.search(text):
            fail(f"{fold} uses the old overlap timing: {text!r}")
    if "1 October 2026" not in (page.text_content("#thumbsBox") or ""):
        fail("rules of thumb do not date the Volleyball Danmark rule")


def walkthrough_rows() -> list[list[str]]:
    """The Official walk-through table of docs/v2.md section 5, one list of cells per rotation."""
    doc = (ROOT / "docs" / "v2.md").read_text()
    part = doc.split("### Walk-through: Official", 1)[1].split("\n### ", 1)[0]
    return [[c.strip() for c in line.strip("|").split("|")] for line in part.splitlines() if re.match(r"\| R\d", line)]


def lineup_in(cell: str) -> list[str]:
    """The first 'A B C / D E F' lineup in a cell; L(MB2) reads as L."""
    player = r"[A-Z][A-Z0-9]*(?:\([A-Z0-9]+\))?"
    m = re.search(rf"((?:{player} ){{2}}{player}) / ((?:{player} ){{2}}{player})", cell)
    return [re.sub(r"\(.*\)", "", p) for p in (m[1] + " " + m[2]).split()] if m else []


def check_official_walkthrough(page: Page) -> None:
    """The app matches the Official walk-through table for all six rotations."""
    open_app(page, {"role": "OH1", "rulesMode": "official"})
    rows = walkthrough_rows()
    if len(rows) != 6:
        fail(f"Official walk-through has {len(rows)} rows")
    for ri, (_, rotation, serve, reception, after) in enumerate(rows):
        tag = f"Official walk-through {ROTATION_NAMES[ri]}"
        at: dict[str, list[dict[str, Any]]] = {
            ph: page.evaluate(f"window.ksvLearn.players({ri}, '{ph}')") for ph in PHASES
        }
        start = [o["p"] for o in at["start"]]
        if start != lineup_in(rotation):
            fail(f"{tag}: Rotation step {start} != {lineup_in(rotation)}")
        if ("L" in start) != ("L stays on" in rotation):
            fail(f"{tag}: L on court at the Rotation step is {'L' in start}; the table says {rotation!r}")
        if [o["p"] for o in at["serve"]] != lineup_in(serve):
            fail(f"{tag}: Our serve {[o['p'] for o in at['serve']]} != {lineup_in(serve)}")
        server = re.search(r"(\w+) serves", serve)
        runs = [
            r
            for r in start + ["L"]
            if "then run to zone" in page.evaluate(f"window.ksvLearn.describe({ri}, 'serve', '{r}').d")
        ]
        if not server or runs != [server[1]]:
            fail(f"{tag}: the server in the app is {runs}; the table says {serve!r}")
        replaced = re.search(r"L for (MB[12]) \(zone (\d)\)", reception)
        rec = [o["p"] for o in at["rec"]]
        if not replaced or "L" not in rec or replaced[1] in rec:
            fail(f"{tag}: Reception has {rec}; the table says {reception!r}")
        elif f"The libero takes your zone {replaced[2]}." not in page.evaluate(
            f"window.ksvLearn.describe({ri}, 'rec', '{replaced[1]}').d"
        ):
            fail(f"{tag}: the libero does not take zone {replaced[2]} for {replaced[1]}")
        kinds = {o["p"]: o["kind"] for o in at["ar"]}
        attackers = re.match(r"((?:\w+, )+\w+) attack", after)
        if attackers and any(kinds.get(p) not in ("front", "back") for p in attackers[1].split(", ")):
            fail(f"{tag}: After reception kinds {kinds}; the table says {after!r}")
        if "back-row attack" in after and kinds.get("OP") != "back":
            fail(f"{tag}: OP is {kinds.get('OP')!r} after reception; the table says {after!r}")


def check_official_libero(page: Page) -> None:
    """Official libero rules: no US libero rules, the 19.3 text on exchange screens and the finger-set rule."""
    open_app(page, {"role": "L", "rulesMode": "official"})
    order = [(ri, ph) for ri in range(6) for ph in PHASES]
    was_on = None
    for ri, ph in order + order[:1]:
        on = "L" in [o["p"] for o in page.evaluate(f"window.ksvLearn.players({ri}, '{ph}')")]
        if was_on is not None and on != was_on:
            if on and ph != "rec":
                fail(f"Official {ROTATION_NAMES[ri]} {ph}: the libero comes on without a completed rally")
            if not on and ph != "start":
                fail(f"Official {ROTATION_NAMES[ri]} {ph}: the libero goes off at {ph}")
        was_on = on
    texts: list[str] = page.evaluate(
        "roles => roles.flatMap(r => [0,1,2,3,4,5].flatMap(ri => ['start','serve','rec','ar']"
        ".flatMap(ph => [window.ksvLearn.describe(ri, ph, r).d, window.ksvLearn.still(ri, ph, r),"
        " ...window.ksvLearn.captions(ri, ph, r)])))",
        MODES["official"],
    )
    texts.append(page.inner_text("#sheet"))
    us_rule = re.compile(r"libero (serves|may serve|can serve)|straight back in", re.IGNORECASE)
    for text in texts:
        if us_rule.search(text):
            fail(f"Official text teaches a US libero rule: {text!r}")
    if "FIVB 19.3" not in page.inner_text("#sheet"):
        fail("Official libero rules to remember lack the 19.3 rule")
    for ri in range(6):
        if "nobody may attack that ball above the net" not in page.evaluate(
            f"window.ksvLearn.describe({ri}, 'ar', 'L').d"
        ):
            fail(f"Official {ROTATION_NAMES[ri]} After reception: L text lacks the finger-set rule")
    for ri in range(6):
        for ph in PHASES:
            learn(page, ri, ph)
            shown = "FIVB 19.3" in page.inner_text("#cue")
            want = ri in (2, 5) and ph in ("start", "rec")
            if shown != want:
                fail(f"Official {ROTATION_NAMES[ri]} {ph}: libero rule in the cue is {shown}, expected {want}")
    open_app(page, {"role": "L", "rulesMode": "simple"})
    learn(page, 2, "serve")
    if "FIVB 19.3" in page.inner_text("#cue") or "19.3" in page.inner_text("#sheet"):
        fail("Simplified shows the Official libero rule text")


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        page = context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        for mode, roles in MODES.items():
            for role in roles:
                check_walk(page, mode, role)
        check_next_in_view(page)
        check_texts(page)
        check_rule_folds(page)
        check_official_walkthrough(page)
        check_official_libero(page)
        for error in errors:
            fail(f"page error: {error}")
        browser.close()
    print(f"LEARN TEST: {len(FAIL)} failures")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
