"""Playwright test of the Learn tab in index.html.

Walks every role, rotation and step of both rule sets with the Next button and
checks the cue, the overlap boundary lines, the Our serve rule text, that Next
stays in view on a phone, and the SUB and MB texts.

Usage: python src/tests/learn_test.py
"""

import json
import re
import sys
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
URL = (ROOT / "index.html").as_uri() + "?ff=all"
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
  return { tag: document.querySelector('#learnTag').textContent, title: title ? title.textContent : '',
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
    here = on_court(page, role)
    if phase == "serve" and ("may stand anywhere" not in state["cue"] or "may not block" not in state["cue"]):
        fail(f"{tag}: Our serve cue lacks the serving-team rule: {state['cue']!r}")
    if phase in ("start", "rec") and here:
        overlap = re.search(r"Overlap: stay ([^.]*)\.", state["cue"])
        if not overlap:
            fail(f"{tag}: no overlap sentence: {state['cue']!r}")
        elif not state["bounds"] and "right at these limits" not in state["cue"]:
            fail(f"{tag}: no boundary lines")
        for bound in state["bounds"]:
            if overlap and bound["p"] not in re.findall(r"[A-Z][A-Z0-9]*", overlap.group(1)):
                fail(f"{tag}: line for {bound['p']} not in {overlap.group(0)!r}")
            if bound["stroke"] != f"var(--route-{ROUTE_KEY[bound['p']]})":
                fail(f"{tag}: line for {bound['p']} coloured {bound['stroke']}")
            if bound["x1"] != bound["x2"] and bound["y1"] != bound["y2"]:
                fail(f"{tag}: line for {bound['p']} is not straight along or across the court")
    elif state["bounds"]:
        fail(f"{tag}: boundary lines outside Rotation and Reception or off court: {state['bounds']}")


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
    """With the longest cue the Next button stays inside the phone viewport."""
    open_app(page, {"role": "S", "rulesMode": "simple"})
    learn(page, 0, "rec")
    page.evaluate("window.scrollTo(0, document.querySelector('#courtL').getBoundingClientRect().top + scrollY)")
    box: dict[str, float] = page.evaluate(
        "(() => { const r = document.querySelector('#lNext').getBoundingClientRect();"
        " return { top: r.top, bottom: r.bottom, height: innerHeight }; })()"
    )
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
        for error in errors:
            fail(f"page error: {error}")
        browser.close()
    print(f"LEARN TEST: {len(FAIL)} failures")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
