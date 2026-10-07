"""Playwright test of the Learn tab in index.html.

Walks every role, rotation and step of both rule sets with the Next button and
checks the cue, the overlap boundary lines and when they count (at the
whistle, from 1 October 2026), the Our serve rule text, that Next stays in
view on a phone, the Simplified MB and L texts, the Official walk-through table of
docs/v2.md, the middle cycle line in the cue and the Official libero rules.

Usage: python src/tests/learn_test.py
"""

import json
import re
import sys
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
URL = (ROOT / "index.html").as_uri() + "?anim=0"
FAIL: list[str] = []
MODES = {
    "simple": ["MB", "OH1", "OH2", "OP", "S", "L"],
    "official": ["MB1", "MB2", "OH1", "OH2", "OP", "S", "L"],
}
PHASES = ["start", "serve", "rec", "ar"]
PHASE_NAMES = {"start": "Rotation", "serve": "Our serve", "rec": "Reception", "ar": "Base"}
ROUTE_KEY = {"S": "s", "OP": "op", "MB": "mb", "MB1": "mb", "MB2": "mb", "OH1": "oh", "OH2": "oh", "L": "l"}
ROUTE_KEY["OM"] = "mb"
ROTATION_NAMES = ["R1 (H1)", "R2 (H6)", "R3 (H5)", "R4 (H4)", "R5 (H3)", "R6 (H2)"]
OLD_NAME = re.compile(r"\(S\d\)")
# (mode, role, rotation, phase) -> (overlap sentence, partners whose limit is inside your marker)
EXPECTED = {
    ("official", "L", 0, "start"): ("Overlap: stay behind MB1, right of OH2 and left of S.", []),
    ("simple", "S", 0, "rec"): ("Overlap: stay behind OH1 and right of L.", []),
    ("official", "OH2", 1, "rec"): ("Overlap: stay in front of L and left of OP.", ["L"]),
    ("simple", "L", 1, "rec"): ("Overlap: stay behind OH2 and left of S.", ["OH2", "S"]),
    # Official R3 and R6: the serving middle is off court when they serve, so it is nobody's limit.
    ("official", "OP", 2, "start"): ("Overlap: stay right of OH2.", []),
    ("official", "OH1", 2, "start"): ("Overlap: stay behind OH2 and right of S.", []),
    ("official", "OH2", 5, "start"): ("Overlap: stay behind OH1 and right of OP.", []),
}
# (mode, role, rotation): the middle who serves from zone 1 at the Rotation step and has no overlap limits.
SERVING_MIDDLE = {("official", "MB1", 2), ("official", "MB2", 5), ("simple", "MB", 2), ("simple", "MB", 5)}
# The overlap limits count at the whistle for the serve; before 1 October 2026 they counted at the service hit.
OLD_TIMING = re.compile(r"service hit|when the ball is served|at the serve\b|until the serve is made", re.IGNORECASE)
THUMB_MOVE = "Once the server moves, so can you."
WHISTLE_MOVE = "From the server's first movement you may move freely."
OVERLAP_WHEN = {
    "start": "This is your rotation order. It counts at the referee's whistle when the other team serves."
    " We serve now, so you may stand anywhere in your court.",
    "rec": "These limits count at the referee's whistle, not during the pass. " + WHISTLE_MOVE,
}
# Simplified R3/R6 Rotation: OM's zone 4 slot is MB's at the whistle for their serve, so its limit reads MB.
OM_LIMIT = {"MB": "OM"}
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
  const rect = court.querySelector('rect.larea');
  const kids = [...court.children];
  const at = (el) => kids.indexOf(el.closest('#courtL > *'));
  const area = rect ? { x: +rect.getAttribute('x'), y: +rect.getAttribute('y'),
    w: +rect.getAttribute('width'), h: +rect.getAttribute('height'),
    events: rect.getAttribute('pointer-events'), count: court.querySelectorAll('rect.larea').length,
    under: [...court.querySelectorAll('g.zones, .mk, .bnd')].every((el) => at(el) > at(rect)) } : null;
  return { area, me: mine ? { x: +mine.getAttribute('cx'), y: +mine.getAttribute('cy') } : null,
    tag: document.querySelector('#learnTag').textContent, title: title ? title.textContent : '',
    cue: cue.innerText, bounds };
}"""


def fail(message: str) -> None:
    FAIL.append(message)
    print("FAIL:", message, flush=True)


def open_app(page: Page, stored: dict[str, str], url: str = URL) -> None:
    page.goto(url)
    page.evaluate(
        "(s) => { localStorage.clear(); localStorage.setItem('ksv51:officialReset', JSON.stringify('1'));"
        " for (const [k, v] of Object.entries(s))"
        " if (v === null) localStorage.removeItem('ksv51:' + k);"
        " else localStorage.setItem('ksv51:' + k, JSON.stringify(v)); }",
        stored,
    )
    page.goto(url)
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
    if OLD_NAME.search(page.inner_text("body")):
        fail(f"{tag}: a rotation label still uses S")
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
        if state["area"]:
            fail(f"{tag}: the serving middle has an overlap area: {state['area']}")
        if not here or state["bounds"] or "Overlap:" in state["cue"] or "no overlap limits" not in state["cue"]:
            fail(f"{tag}: the serving middle should be on court with no limits: {state['cue']!r}, {state['bounds']}")
    elif phase in ("start", "rec") and here:
        if OVERLAP_WHEN[phase] not in state["cue"]:
            fail(f"{tag}: cue does not say when the overlap limits count: {state['cue']!r}")
        alias = OM_LIMIT if (mode, phase) == ("simple", "start") and rotation in (2, 5) else {}
        check_overlap(tag, state, EXPECTED.get((mode, role, rotation, phase)), alias)
        check_area(page, tag, state, rotation, phase)
        for bound in state["bounds"]:
            if bound["stroke"] != f"var(--route-{ROUTE_KEY[bound['p']]})":
                fail(f"{tag}: line for {bound['p']} coloured {bound['stroke']}")
            if bound["x1"] != bound["x2"] and bound["y1"] != bound["y2"]:
                fail(f"{tag}: line for {bound['p']} is not straight along or across the court")
    elif state["bounds"] or state["area"]:
        fail(f"{tag}: overlap lines or area outside Rotation and Reception or off court: {state['bounds']}")


def check_area(page: Page, tag: str, state: dict[str, Any], rotation: int, phase: str) -> None:
    """The shaded area runs from each partner's x or y to the next, else to the sideline, net or end line."""
    area = state["area"]
    if not area:
        fail(f"{tag}: no overlap area")
        return
    spots = {o["p"]: o for o in page.evaluate(f"window.ksvLearn.players({rotation}, '{phase}')")}
    edges = {"left": 0.0, "right": 100.0, "front": 0.0, "behind": 100.0}
    for partner in page.evaluate(f"window.ksvLearn.partners({rotation}, '{phase}')"):
        spot = spots[partner["p"]]
        edges[partner["side"]] = 100 * (spot["x"] if partner["side"] in ("left", "right") else spot["y"])
    drawn = {
        "left": area["x"],
        "right": area["x"] + area["w"],
        "front": area["y"],
        "behind": area["y"] + area["h"],
    }
    if any(abs(drawn[k] - edges[k]) > 0.01 for k in edges):
        fail(f"{tag}: overlap area {drawn}, expected {edges}")
    me = state["me"]
    if me and not (drawn["left"] <= me["x"] <= drawn["right"] and drawn["front"] <= me["y"] <= drawn["behind"]):
        fail(f"{tag}: your marker is outside the overlap area: {drawn}, me {me}")
    if area["count"] != 1 or area["events"] != "none" or not area["under"]:
        fail(f"{tag}: overlap area not one rect under the zone numbers, lines and markers: {area}")


def check_overlap(
    tag: str, state: dict[str, Any], expected: tuple[str, list[str]] | None, alias: dict[str, str]
) -> None:
    """Every partner in the caption has a line running to their side, or is named as a limit you stand at."""
    overlap = re.search(r"Overlap: stay ([^.]*)\.", state["cue"])
    if not overlap:
        fail(f"{tag}: no overlap sentence: {state['cue']!r}")
        return
    tight_match = re.search(r"You stand right at the (.*) limits?\.", state["cue"])
    tight = [alias.get(p, p) for p in tight_match.group(1).split(" and ")] if tight_match else []
    sides = dict(
        (alias.get(partner, partner), words)
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
            label = "Base" if phase == "rec" else f"Next: {expected}"
            if page.text_content("#lNext") != f"{label} ▸":
                fail(f"{mode} {role} R{rotation + 1} {phase}: Next reads {page.text_content('#lNext')!r}")
            page.click("#lNext")
    if page.inner_text("#learnTag") != f"{ROTATION_NAMES[0]} · {PHASE_NAMES['start']}":
        fail(f"{mode} {role}: Next after R6 Base shows {page.inner_text('#learnTag')!r}")


def check_reception_animated(page: Page) -> None:
    """With the animation on, Reception rests on the reception spots with the overlap lines and no ball."""
    for mode, roles in MODES.items():
        for role in roles:
            open_app(page, {"role": role, "rulesMode": mode}, URL.replace("?anim=0", ""))
            for rotation in range(6):
                learn(page, rotation, "rec")
                check_step(page, mode, role, rotation, "rec")
                tag = f"{mode} {role} {ROTATION_NAMES[rotation]} animated Reception"
                got: dict[str, list[float]] = page.evaluate(
                    """() => Object.fromEntries([...document.querySelectorAll('#courtL .mk')].map((g) => {
                    const c = [...g.querySelectorAll('circle')].filter((e) => !e.classList.contains('hit')).pop();
                    return [g.dataset.p, [+c.getAttribute('cx') / 100, +c.getAttribute('cy') / 100]]; }))"""
                )
                want = {o["p"]: [o["x"], o["y"]] for o in page.evaluate(f"window.ksvLearn.players({rotation}, 'rec')")}
                if sorted(got) != sorted(want) or any(
                    abs(got[p][0] - want[p][0]) > 1e-3 or abs(got[p][1] - want[p][1]) > 1e-3 for p in want
                ):
                    fail(f"{tag}: markers {got}, expected {want}")
                if page.locator("#courtL .ball").count():
                    fail(f"{tag}: a ball on the still")


PASSERS_LINE = "OH1, OH2 and L pass; everyone else keeps out of the lanes."
# Court geometry in SVG units: tags, markers (your ring included), zone digits, overlap lines with their halos.
PASS_TAGS = """() => {
  const court = document.querySelector('#courtL');
  const box = (b) => [b.x, b.y, b.x + b.width, b.y + b.height];
  const tags = [...court.querySelectorAll('.ptag')].map((g) => ({ p: g.dataset.p,
    box: box(g.querySelector('rect').getBBox()) }));
  const marks = [...court.querySelectorAll('.mk')].map((g) => {
    const c = g.querySelector(':scope > circle:not(.hit)');
    return { p: g.dataset.p, x: +c.getAttribute('cx'), y: +c.getAttribute('cy'),
      r: g.querySelector('.me-ring') ? 8.9 : +c.getAttribute('r') + 0.5 };
  });
  const zones = [...court.querySelectorAll('g.zones text')].map((t) => {
    const b = t.getBBox(), base = +t.getAttribute('y'), size = +t.getAttribute('font-size');
    return [b.x, base - 0.72 * size, b.x + b.width, base];
  });
  const lines = [...court.querySelectorAll('.bnd line')].map((l) => ({
    a: [+l.getAttribute('x1'), +l.getAttribute('y1')], b: [+l.getAttribute('x2'), +l.getAttribute('y2')],
    w: +l.getAttribute('stroke-width') / 2 }));
  return { tags, marks, zones, lines };
}"""


def boxes_cross(first: list[float], second: list[float]) -> bool:
    return first[0] < second[2] and second[0] < first[2] and first[1] < second[3] and second[1] < first[3]


def circle_in_box(box: list[float], x: float, y: float, r: float) -> bool:
    nearest_x, nearest_y = max(box[0], min(box[2], x)), max(box[1], min(box[3], y))
    return bool((nearest_x - x) ** 2 + (nearest_y - y) ** 2 < r * r)


def line_in_box(box: list[float], line: dict[str, Any]) -> bool:
    (x1, y1), (x2, y2), w = line["a"], line["b"], line["w"]
    steps = int(max(abs(x2 - x1), abs(y2 - y1)) / 0.25) + 1
    return any(
        box[0] - w < x1 + (x2 - x1) * i / steps < box[2] + w and box[1] - w < y1 + (y2 - y1) * i / steps < box[3] + w
        for i in range(steps + 1)
    )


def check_pass_tags(page: Page) -> None:
    """A "pass" tag on exactly the three receivers on every Reception still, clear of everything else."""
    page.set_viewport_size({"width": 390, "height": 664})
    checked = 0
    for mode, roles in MODES.items():
        for role in roles:
            open_app(page, {"role": role, "rulesMode": mode})
            for rotation in range(6):
                learn(page, rotation, "rec")
                tag = f"{mode} {role} {ROTATION_NAMES[rotation]} pass tags"
                got: dict[str, Any] = page.evaluate(PASS_TAGS)
                tags = got["tags"]
                if sorted(t["p"] for t in tags) != ["L", "OH1", "OH2"]:
                    fail(f"{tag}: tags on {[t['p'] for t in tags]}")
                if PASSERS_LINE not in page.inner_text("#cue"):
                    fail(f"{tag}: the cue lacks the passers line")
                for k, t in enumerate(tags):
                    box = t["box"]
                    if box[0] < -4 or box[2] > 104 or box[1] < 1.2 or box[3] > 103:
                        fail(f"{tag}: {t['p']} tag outside the court picture: {box}")
                    for m in got["marks"]:
                        if circle_in_box(box, m["x"], m["y"], m["r"]):
                            fail(f"{tag}: {t['p']} tag covers the {m['p']} marker")
                    if any(boxes_cross(box, z) for z in got["zones"]):
                        fail(f"{tag}: {t['p']} tag covers a zone number")
                    if any(line_in_box(box, line) for line in got["lines"]):
                        fail(f"{tag}: {t['p']} tag covers an overlap line")
                    if any(boxes_cross(box, other["box"]) for other in tags[k + 1 :]):
                        fail(f"{tag}: {t['p']} tag overlaps another tag")
                checked += 1
            for phase in ("start", "serve", "ar"):
                learn(page, 0, phase)
                if page.locator("#courtL .ptag").count() or PASSERS_LINE in page.inner_text("#cue"):
                    fail(f"{mode} {role} {PHASE_NAMES[phase]}: pass tags or the passers line off Reception")
    open_app(page, {"role": "OH1", "rulesMode": "simple"}, URL.replace("?anim=0", ""))
    learn(page, 0, "rec")
    page.click("#lPlay")
    shown = page.evaluate(
        "[...document.querySelectorAll('#courtL .am .ptag')].filter(g => g.getAttribute('visibility') !== 'hidden')"
        ".map(g => g.dataset.p).sort()"
    )
    if shown != ["L", "OH1", "OH2"]:
        fail(f"Reception play before the pass: tags on {shown}")
    learn(page, 0, "rec")
    page.click("#lStep")
    page.wait_for_function("() => window.ksvLearn.anim() && !window.ksvLearn.anim().playing")
    shown = page.evaluate(
        "[...document.querySelectorAll('#courtL .ptag')].filter(g => g.getAttribute('visibility') !== 'hidden').length"
    )
    if shown:
        fail(f"Reception play from the pass on: {shown} tags still shown")
    page.set_viewport_size({"width": 390, "height": 844})
    print(f"pass tags: three receivers clear of markers, zones, lines and each other on {checked} stills; play")


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
    """Simplified MB and L texts come from describe() for every rotation and step; MB serves in R3 and R6."""
    open_app(page, {"role": "MB", "rulesMode": "simple"})
    texts: list[dict[str, Any]] = page.evaluate(
        "roles => roles.flatMap(r => [0,1,2,3,4,5].flatMap(ri => ['start','serve','rec','ar']"
        ".map(ph => ({ r, ri, ph, ...window.ksvLearn.describe(ri, ph, r) }))))",
        ["L", "MB"],
    )
    for text in texts:
        tag = f"{text['r']} R{text['ri'] + 1} {text['ph']}"
        if not text["t"] or not text["d"]:
            fail(f"{tag}: empty describe text {json.dumps(text)}")
        if "official" in text["d"].lower() or "SUB" in text["d"] or "resets" in text["d"]:
            fail(f"{tag}: Simplified text mentions the official rules, SUB or a reset: {text['d']!r}")
    by = {(t["r"], t["ri"], t["ph"]): t for t in texts}
    for rotation in (2, 5):
        tag = f"R{rotation + 1}"
        if (
            by[("MB", rotation, "start")]["t"] != "Zone 1, back row"
            or "serve" not in by[("MB", rotation, "start")]["d"]
        ):
            fail(f"MB {tag} Rotation: {by[('MB', rotation, 'start')]!r}")
        if "you serve" not in by[("MB", rotation, "serve")]["d"]:
            fail(f"MB {tag} Our serve: {by[('MB', rotation, 'serve')]['d']!r}")
        for phase in ("start", "serve"):
            text = by[("L", rotation, phase)]
            if text["t"] != "Off court" or "MB is in zone 1 and serves" not in text["d"]:
                fail(f"L {tag} {phase}: {text!r}")
    for rotation in (0, 1, 3, 4):
        if by[("MB", rotation, "start")]["t"] == "Zone 1, back row":
            fail(f"MB R{rotation + 1} Rotation is in zone 1")


def check_rules_of_thumb(page: Page) -> None:
    """Learn keeps only the Rules of thumb fold, closed, worded for each rule set and the whistle timing."""
    for mode, want, unwanted in (
        ("simple", ("MB serves from zone 1", "MB plays the front middle"), ("MB1", "19.3", "SUB")),
        ("official", ("The libero replaces the back-row middle", "19.3"), ("SUB", "other middle")),
    ):
        open_app(page, {"role": "L", "rulesMode": mode})
        html = page.content()
        for gone in ("How to learn", "Before every serve", 'id="howTo"', 'id="checks"'):
            if gone in html:
                fail(f"{mode}: the page still has {gone!r}")
        if page.get_attribute("#thumbsBox", "open") is not None:
            fail(f"{mode}: Rules of thumb open by default")
        text = " ".join((page.text_content("#thumbsBox") or "").split())
        if "whistle" not in text or THUMB_MOVE not in text:
            fail(f"{mode} Rules of thumb lack the whistle timing: {text!r}")
        if OLD_TIMING.search(text):
            fail(f"{mode} Rules of thumb use the old overlap timing: {text!r}")
        if "1 October 2026" in text:
            fail(f"{mode} Rules of thumb still date the Volleyball Danmark rule, which is in force")
        if "@" in text:
            fail(f"{mode} Rules of thumb show a placeholder: {text!r}")
        for word in want:
            if word not in text:
                fail(f"{mode} Rules of thumb lack {word!r}")
        for word in unwanted:
            if word in text:
                fail(f"{mode} Rules of thumb mention {word!r}")
        middles = page.locator("#thumbs li", has_text="middle").last.inner_text()
        if us_libero_rule(middles):
            fail(f"{mode} the middles rule of thumb teaches a US libero rule: {middles!r}")
        titles = page.locator("#thumbs li > b").all_text_contents()
        if titles[:2] != ["Walk from the setter", "Same job, opposite corners"] or "H in" not in titles[-1]:
            fail(f"{mode}: Rules of thumb do not start with the walk and the corners and end with H: {titles}")
        first = " ".join(" ".join((page.locator("#thumbs li").nth(i).text_content() or "").split()) for i in (0, 1))
        for word in (
            "count up",
            "Setter, Outside, Middle, Opposite, Outside, Middle",
            "The libero replaces whichever middle is in the back row.",
            "diagonally opposite",
        ):
            if word not in first:
                fail(f"{mode}: the walk and corners rules lack {word!r}: {first!r}")
        mine = page.locator("#thumbs li.mine b").all_text_contents()
        if not any("middle" in title for title in mine):
            fail(f"{mode} L: the middles rule is not marked as your rule: {mine}")


def area_from_data(ri: int, role: str) -> dict[str, float]:
    """Official Reception area edges for ``role`` from data.py: column partner and row neighbours by lineup."""
    sys.path.insert(0, str(ROOT / "src"))
    from data import ROWS

    row = ROWS[ri]
    spot = {p: (x, y) for p, x, y in row["rec"]}
    front, back = row["front"], row["back"]
    line, other = (front, back) if role in front else (back, front)
    i = line.index(role)
    edges = {"left": 0.0, "right": 100.0, "front": 0.0, "behind": 100.0}
    edges["behind" if line is front else "front"] = 100 * spot[other[i]][1]
    if i > 0:
        edges["left"] = 100 * spot[line[i - 1]][0]
    if i < 2:
        edges["right"] = 100 * spot[line[i + 1]][0]
    return edges


def check_area_from_data(page: Page) -> None:
    """The Reception area of every Official role in every rotation, against data.py and not the app's partners."""
    sys.path.insert(0, str(ROOT / "src"))
    from data import ROWS

    hand = {"left": 7.0, "right": 80.0, "front": 0.0, "behind": 73.0}
    if any(abs(area_from_data(0, "MB1")[k] - v) > 0.01 for k, v in hand.items()):
        fail(f"R1 MB1 area from data.py reads {area_from_data(0, 'MB1')}")
    checked = 0
    for role in MODES["official"]:
        open_app(page, {"role": role, "rulesMode": "official"})
        for ri, row in enumerate(ROWS):
            if role not in row["front"] + row["back"]:
                continue
            learn(page, ri, "rec")
            area = page.evaluate(STATE)["area"]
            want = area_from_data(ri, role)
            drawn = (
                {"left": area["x"], "right": area["x"] + area["w"], "front": area["y"], "behind": area["y"] + area["h"]}
                if area
                else None
            )
            if not drawn or any(abs(drawn[k] - want[k]) > 0.01 for k in want):
                fail(f"official {role} {ROTATION_NAMES[ri]} Reception: area {drawn}, data.py gives {want}")
            checked += 1
    print(f"overlap area: {checked} Official Reception areas match data.py", flush=True)


def middle_cycle(middle: str) -> tuple[list[str], str]:
    """The H names where a middle is front row (zone 4, 3, 2 in turn) and the one where it serves, from data.py."""
    sys.path.insert(0, str(ROOT / "src"))
    from data import ROWS, server

    front = {}
    serves = ""
    for ri, row in enumerate(ROWS):
        h = f"H{row['setter']}"
        if middle in row["front"]:
            front[row["front"].index(middle)] = h
        elif server(ri, "official") == middle:
            serves = h
    return [front[i] for i in range(3)], serves


def check_middle_cycle(page: Page) -> None:
    """Official lists the middle cycle, yours as MB1 and MB2, with the rotations of data.py; Simplified does not."""
    for middle in ("MB1", "MB2"):
        front, serves = middle_cycle(middle)
        open_app(page, {"role": middle, "rulesMode": "official"})
        item = page.locator("#thumbs li", has_text="4, 3, 2, serve, off, off")
        if item.count() != 1:
            fail(f"official {middle}: no single middle cycle rule of thumb")
            continue
        text = " ".join((item.text_content() or "").split())
        want = f"{middle} is in the front row in {front[0]}, {front[1]} and {front[2]} and serves in {serves}."
        if want not in text:
            fail(f"official {middle}: the cycle rule lacks {want!r}: {text!r}")
        if "your rule" not in text:
            fail(f"official {middle}: the cycle rule is not marked as yours")
    open_app(page, {"role": "OH1", "rulesMode": "official"})
    if "your rule" in (page.locator("#thumbs li", has_text="4, 3, 2, serve, off, off").text_content() or ""):
        fail("official OH1: the middle cycle rule is marked as yours")
    open_app(page, {"role": "MB", "rulesMode": "simple"})
    if "off, off" in (page.text_content("#thumbs") or ""):
        fail("simple: the Official middle cycle rule of thumb is listed")


def check_learn_cycle(page: Page) -> None:
    """An Official MB1 or MB2 sees its cycle step under the Learn cue on every screen; nobody else does."""
    from qa import cycle_step

    for middle in ("MB1", "MB2"):
        open_app(page, {"role": middle, "rulesMode": "official"})
        for ri in range(6):
            page.click(f'.rot[data-i="{ri}"]')
            for phase in PHASES:
                page.click(f'.ph[data-k="{phase}"]')
                step = cycle_step(middle, ri, "rec" if phase == "ar" else phase)
                want = f"Your cycle: 4, 3, 2, serve, off, off — you are at {step}."
                lines = page.locator("#cue .cycle").all_inner_texts()
                if lines != [want]:
                    fail(f"official {middle} R{ri + 1} {phase}: the cue cycle line reads {lines}, expected {want!r}")
    for mode, role in (("official", "OH1"), ("official", "L"), ("simple", "MB")):
        open_app(page, {"role": role, "rulesMode": mode})
        for ri in range(6):
            page.click(f'.rot[data-i="{ri}"]')
            for phase in PHASES:
                page.click(f'.ph[data-k="{phase}"]')
                if page.locator("#cue .cycle").count():
                    fail(f"{mode} {role} R{ri + 1} {phase}: the cue shows a middle cycle line")


def check_rotation_names(page: Page) -> None:
    """Rotations are named with the Danish H in the table and the rotation chips, and Rules of thumb explain it."""
    for mode, roles in MODES.items():
        open_app(page, {"role": roles[0], "rulesMode": mode})
        page.evaluate("document.querySelectorAll('details.fold').forEach(d => d.open = true)")
        text = page.inner_text("body")
        if OLD_NAME.search(text):
            fail(f"{mode}: a rotation label still uses S")
        for name in ROTATION_NAMES:
            if name not in page.inner_text("#rotTable"):
                fail(f"{mode}: the all-rotations table lacks {name}")
        labels: list[str] = page.eval_on_selector_all(
            "[aria-label]", "els => els.map(e => e.getAttribute('aria-label'))"
        )
        if not all(any(name in label for label in labels) for name in ROTATION_NAMES):
            fail(f"{mode}: the rotation chip aria-labels lack the H names: {labels}")
        if any(OLD_NAME.search(label) for label in labels):
            fail(f"{mode}: an aria-label still uses S")
        chips: list[list[str]] = page.eval_on_selector_all(
            ".rot", "els => els.map(e => [e.textContent.trim(), e.getAttribute('aria-label')])"
        )
        if chips != [[name.split(" ")[1].strip("()"), name] for name in ROTATION_NAMES]:
            fail(f"{mode}: the rotation chips do not read H1 H6 H5 H4 H3 H2 with the full name as aria-label: {chips}")
        thumbs = " ".join(page.inner_text("#thumbs").split())
        if "hæver" not in thumbs or "setter's zone" not in thumbs:
            fail(f"{mode}: Rules of thumb do not explain H: {thumbs!r}")


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


def check_table_off(page: Page) -> None:
    """The all-rotations table's Rotation column says who serves when L is off, and gives L's zone otherwise."""
    for mode, server in (("simple", ("MB", "MB")), ("official", ("MB1", "MB2"))):
        open_app(page, {"role": "L", "rulesMode": mode})
        page.evaluate("document.querySelectorAll('details.fold').forEach(d => d.open = true)")
        cells = page.locator("#rotTable tbody tr td:nth-child(2)").all_inner_texts()
        for ri, cell in enumerate(cells):
            want = f"Off ({server[ri == 5]} serves from zone 1)" if ri in (2, 5) else None
            if (cell != want) if want else not re.fullmatch(r"Zone [1-6]", cell):
                fail(f"{mode} L table R{ri + 1} Rotation: {cell!r}, expected {want or 'Zone <n>'}")


def check_official_walkthrough(page: Page) -> None:
    """The app matches the Official walk-through table for all six rotations."""
    open_app(page, {"role": "OH1", "rulesMode": "official"})
    rows = walkthrough_rows()
    if len(rows) != 6:
        fail(f"Official walk-through has {len(rows)} rows")
    for ri, cells in enumerate(rows):
        tag = f"Official walk-through {ROTATION_NAMES[ri]}"
        if len(cells) != 5:
            fail(f"{tag}: {len(cells)} columns, expected Rot, Rotation step, Our serve, Reception, Attack")
            continue
        _, rotation, serve, reception, after = cells
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
            fail(f"{tag}: Attack kinds {kinds}; the table says {after!r}")
        if "back-row attack" in after and kinds.get("OP") != "back":
            fail(f"{tag}: OP is {kinds.get('OP')!r} after reception; the table says {after!r}")


def us_libero_rule(text: str) -> bool:
    """True when a text lets the libero serve, or go off and come straight back in (US rules)."""
    if re.search(r"straight back|right back on", text, re.IGNORECASE):
        return True
    for clause in re.split(r"[.;:]", re.sub(r"^You \(\w+\):", "", text)):
        serves = re.search(r"\b(libero|L)\b(?:\W+\w+){0,3}?\W+serv", clause, re.IGNORECASE)
        if serves and not re.search(r"\b(not|never|cannot)\b.*\bserv", serves[0], re.IGNORECASE):
            return True
    return False


def check_official_libero(page: Page) -> None:
    """Official libero rules: no US libero rules, the 19.3 text on exchange screens and the finger-set rule."""
    for text, want in (
        ("You (L): Serve, then run to zone 6.", False),
        ("L serves from zone 1.", True),
        ("The libero serves in R3.", True),
        ("Go off, then come straight back in.", True),
        ("Go off at the sideline: the libero may not serve.", False),
        ("When they serve, the libero is in for you.", False),
        ("The libero is in for you while your team serves.", False),
        ("The libero may also serve here.", True),
    ):
        if us_libero_rule(text) != want:
            fail(f"us_libero_rule({text!r}) is {not want}")
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
    for text in texts:
        if us_libero_rule(text):
            fail(f"Official text teaches a US libero rule: {text!r}")
    for ri in range(6):
        if "nobody may attack that ball above the net" not in page.evaluate(
            f"window.ksvLearn.describe({ri}, 'ar', 'L').d"
        ):
            fail(f"Official {ROTATION_NAMES[ri]} Attack: L text in Drill and Match lacks the finger-set rule")
        learn(page, ri, "ar")
        if "overhand finger pass in the front zone, nobody may attack that ball above the net" not in page.inner_text(
            "#cue"
        ):
            fail(f"Official {ROTATION_NAMES[ri]} Base: L's cue lacks the overhand finger pass rule")
    for ri in range(6):
        for ph in PHASES:
            learn(page, ri, ph)
            shown = "FIVB 19.3" in page.inner_text("#cue")
            want = ri in (2, 5) and ph in ("start", "rec")
            if shown != want:
                fail(f"Official {ROTATION_NAMES[ri]} {ph}: libero rule in the cue is {shown}, expected {want}")
            if want and "may not serve (19.3.1.3)" not in page.inner_text("#cue"):
                fail(f"Official {ROTATION_NAMES[ri]} {ph}: the libero rule does not cite 19.3.1.3 for the serve")
    open_app(page, {"role": "L", "rulesMode": "simple"})
    learn(page, 2, "serve")
    if "FIVB 19.3" in page.inner_text("#cue"):
        fail("Simplified shows the Official libero rule text")
    learn(page, 2, "ar")
    if "nobody may attack that ball above the net" in page.inner_text("#cue"):
        fail("Simplified Base shows the Official finger-set rule")


def check_hint_below_next(page: Page) -> None:
    """Learn has no rules box, and the hint comes after Next in the DOM and on a 390 x 664 screen."""
    page.set_viewport_size({"width": 390, "height": 664})
    open_app(page, {"role": "L", "rulesMode": "official"})
    for ri, phase in ((0, "rec"), (2, "rec"), (2, "start"), (3, "ar")):
        learn(page, ri, phase)
        tag = f"{ROTATION_NAMES[ri]} {phase}"
        if page.locator("#sheet").count() or "rules to remember" in page.inner_text("#learn").lower():
            fail(f"{tag}: Learn still shows the rules to remember box")
        order = page.evaluate(
            "['#lNext', '#cue', '#thumbsBox', '#allRots'].map(s => document.querySelector(s))"
            ".every((e, i, all) => !i || all[i - 1].compareDocumentPosition(e) & Node.DOCUMENT_POSITION_FOLLOWING)"
        )
        if not order:
            fail(f"{tag}: the order is not Next, hint, Rules of thumb, all rotations")
        page.evaluate("document.querySelector('#cue').scrollIntoView({block: 'end'})")
        box: dict[str, float] = page.evaluate(
            "(() => { const n = document.querySelector('#lNext').getBoundingClientRect(),"
            " c = document.querySelector('#cue').getBoundingClientRect();"
            " return { next: n.bottom, top: c.top, bottom: c.bottom, height: innerHeight }; })()"
        )
        if box["next"] > box["top"] or box["bottom"] > box["height"] + 1:
            fail(f"{tag}: Next covers the hint or the hint is off screen: {box}")
        want = ri == 2 and phase in ("start", "rec")
        if ("FIVB 19.3" in page.inner_text("#cue")) != want:
            fail(f"{tag}: the libero rule under Next is {not want}, expected {want}")
        if phase == "ar" and "nobody may attack that ball above the net" not in page.inner_text("#cue"):
            fail(f"{tag}: the finger-set rule is not in the hint")
    page.set_viewport_size({"width": 390, "height": 844})


def check_title_ball(page: Page) -> None:
    """A decorative volleyball sits beside the title, cap height, in one header row at 360 and 390 px.

    The row holds the title, the role button, the theme button and the report icon, each button 44 px.
    """
    for width, height in ((390, 664), (360, 640)):
        page.set_viewport_size({"width": width, "height": height})
        for stored in ({"role": "OH1", "rulesMode": "simple"}, {"role": "MB1", "rulesMode": "official"}):
            open_app(page, stored)
            tag = f"{width} px, {stored['role']}"
            if (
                page.get_attribute("#titleBall", "aria-hidden") != "true"
                or not page.locator("h1 #titleBall .ball").count()
            ):
                fail(f"{tag}: the title has no decorative volleyball")
            geo: dict[str, Any] = page.evaluate(
                "(() => { const r = s => document.querySelector(s).getBoundingClientRect();"
                " const h1 = document.querySelector('h1'), size = parseFloat(getComputedStyle(h1).fontSize);"
                " const with_ball = h1.offsetHeight; document.querySelector('#titleBall').style.display = 'none';"
                " const without = h1.offsetHeight; document.querySelector('#titleBall').style.display = '';"
                " return { ball: r('#titleBall').toJSON(), chip: r('#roleChip').toJSON(),"
                " theme: r('#themeBtn').toJSON(), report: r('#reportBtn').toJSON(),"
                " size, with_ball, without, scroll: document.documentElement.scrollWidth > innerWidth }; })()"
            )
            ball, chip, theme, report = geo["ball"], geo["chip"], geo["theme"], geo["report"]
            if not 0.6 * geo["size"] <= ball["height"] <= 0.8 * geo["size"]:
                fail(
                    f"{tag}: the title ball is not cap height: {ball['height']:.1f} px for a {geo['size']:.0f} px title"
                )
            row = [chip, theme, report]
            if (
                ball["right"] > chip["left"]
                or chip["right"] > theme["left"]
                or theme["right"] > report["left"]
                or report["right"] > width
                or any(abs(b["top"] - chip["top"]) > 1 for b in row)
            ):
                fail(f"{tag}: the title, role button, theme button and report icon are not in one row: {geo}")
            if any(b["height"] < 44 or b["width"] < 44 for b in row):
                fail(f"{tag}: a header button is under 44 px: {row}")
            if geo["with_ball"] != geo["without"]:
                fail(f"{tag}: the title ball adds a line to the title: {geo}")
            if geo["scroll"]:
                fail(f"{tag}: the header scrolls sideways")
    page.set_viewport_size({"width": 390, "height": 844})


def check_role_text(page: Page) -> None:
    """Below 480 px the role button shows the role code over the rules name; from 480 px the full names."""
    for width, rules, want in (
        (479, "simple", "OP Simplified"),
        (360, "simple", "OP Simplified"),
        (479, "official", "MB1 Official"),
        (360, "official", "MB1 Official"),
        (480, "simple", "Opposite · Simplified"),
        (480, "official", "Middle 1 · Official"),
    ):
        page.set_viewport_size({"width": width, "height": 844})
        role = "OP" if rules == "simple" else "MB1"
        open_app(page, {"role": role, "rulesMode": rules})
        text = " ".join(page.inner_text("#roleChip").split())
        label = page.get_attribute("#roleChip", "aria-label") or ""
        name = "Opposite" if role == "OP" else "Middle 1"
        if text != want:
            fail(f"{width} px: the role button reads {text!r}, expected {want!r}")
        if name not in label or ("Simplified" if rules == "simple" else "Official") not in label:
            fail(f"{width} px: the role button label does not name the role and rules: {label!r}")
    page.set_viewport_size({"width": 390, "height": 844})


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
        check_area_from_data(page)
        check_reception_animated(page)
        check_pass_tags(page)
        check_next_in_view(page)
        check_texts(page)
        check_rules_of_thumb(page)
        check_middle_cycle(page)
        check_learn_cycle(page)
        check_rotation_names(page)
        check_table_off(page)
        check_official_walkthrough(page)
        check_official_libero(page)
        check_hint_below_next(page)
        check_title_ball(page)
        check_role_text(page)
        for error in errors:
            fail(f"page error: {error}")
        browser.close()
    print(f"LEARN TEST: {len(FAIL)} failures")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
