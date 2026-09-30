"""Playwright test of the Learn animation (learn-animation).

Plays Reception → After reception stage by stage and checks the end positions
of each stage, the controls (Replay, Pause, Step, speed), that Next and the
chips never wait for a transition, the rotate and pair-reset captions, the
caption length and height, reduced motion and ?anim=0, the sticky controls on
a short phone, and that the flag off leaves no trace.

Usage: python src/tests/anim_test.py
"""

import re
import sys
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, Page, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from data import lineup  # noqa: E402

BASE = (ROOT / "index.html").as_uri()
FAIL: list[str] = []
MODES = {
    "simple": ["MB", "OH1", "OH2", "OP", "S", "L"],
    "official": ["MB1", "MB2", "OH1", "OH2", "OP", "S", "L"],
}
PHASES = ["start", "serve", "rec", "ar"]
ROTATE = "The rally goes on. We win the point and rotate."
CONTROLS = ["#lReplay", "#lPlay", "#lStep", "#lSpeed", "#lNext"]

MARKERS = """(sel) => Object.fromEntries([...document.querySelectorAll(sel)].map(g => {
  const m = g.getAttribute('transform');
  if (m) { const [x, y] = m.match(/-?[\\d.]+/g).map(Number); return [g.dataset.p, [x, y]]; }
  const c = [...g.querySelectorAll('circle')].filter(e => !e.classList.contains('hit')).pop();
  return [g.dataset.p, [+c.getAttribute('cx'), +c.getAttribute('cy')]];
}))"""


def fail(message: str) -> None:
    FAIL.append(message)
    print("FAIL:", message, flush=True)


def open_app(page: Page, query: str, stored: dict[str, Any]) -> None:
    page.goto(BASE + query)
    page.evaluate(
        "(s) => { localStorage.clear();"
        " for (const [k, v] of Object.entries(s)) localStorage.setItem('ksv51:' + k, JSON.stringify(v)); }",
        stored,
    )
    page.goto(BASE + query)
    page.wait_for_function("document.readyState === 'complete' && !!document.querySelector('#lNext')")


def learn(page: Page, rotation: int, phase: str) -> None:
    page.click(f'.rot[data-i="{rotation}"]')
    page.click(f'.ph[data-k="{phase}"]')


def anim(page: Page) -> dict[str, Any] | None:
    state: dict[str, Any] | None = page.evaluate("window.ksvLearn.anim()")
    return state


def wait_paused(page: Page) -> None:
    page.wait_for_function("!window.ksvLearn.anim() || !window.ksvLearn.anim().playing", timeout=15000)


def close(a: list[float], b: tuple[float, float]) -> bool:
    return abs(a[0] - b[0] * 100) < 0.2 and abs(a[1] - b[1] * 100) < 0.2


def check_positions(tag: str, got: dict[str, list[float]], want: dict[str, tuple[float, float]]) -> None:
    for p, spot in want.items():
        if p not in got or not close(got[p], spot):
            fail(f"{tag}: {p} at {got.get(p)}, expected {spot}")


def check_stages(page: Page) -> None:
    """Step runs one stage and pauses: setter, then attackers, then passers, and the end state matches the data."""
    open_app(page, "?ff=all", {"role": "OH1", "rulesMode": "simple"})
    learn(page, 0, "rec")
    if anim(page):
        fail("a jump to another step plays a transition")
    row = lineup(0, "simple")
    rec = {p: (x, y) for p, x, y in row["rec"]}
    ar = {p: (x, y) for p, x, y, _ in row["ar"]}
    kind = {p: k for p, _, _, k in row["ar"]}
    page.click("#lNext")
    state = anim(page)
    if not state or not state["playing"]:
        fail(f"Next does not play the transition: {state}")
        return
    if page.inner_text("#learnTag") != "R1 (S1) · After reception":
        fail(f"the tag does not move with Next: {page.inner_text('#learnTag')!r}")
    if not 3000 <= state["total"] <= 5000:
        fail(f"Reception → After reception takes {state['total']} ms at 1×, expected 3-5 s")
    if not page.is_disabled("#lStep"):
        fail("Step is enabled while playing")
    page.click("#lPlay")
    if anim(page)["playing"] or page.get_attribute("#lPlay", "aria-label") != "Play":  # type: ignore[index]
        fail("Pause does not pause")
    stage_kinds: list[tuple[str | None, ...]] = [("set",), ("front", "back"), (None,)]
    for stage in range(3):
        before = anim(page)
        page.click("#lStep")
        wait_paused(page)
        state = anim(page)
        if stage < 2:
            if not state or abs(state["t"] - state["ends"][stage]) > 1:
                fail(f"Step {stage + 1} stopped at {state}, expected the end of stage {stage + 1}")
                continue
            if state["stage"] != stage or page.locator("#lDots i.on").count() != stage + 1:
                fail(f"stage {stage + 1}: dots {page.locator('#lDots i.on').count()} on, stage {state['stage']}")
            got = page.evaluate(MARKERS, "#courtL .am")
            moved = {p: ar[p] if any(kind[p] in kinds for kinds in stage_kinds[: stage + 1]) else rec[p] for p in ar}
            check_positions(f"after Step {stage + 1}", got, moved)
        elif state:
            fail(f"the last Step does not reach the end state: {state}, before {before}")
    if page.locator("#courtL .am").count() or page.locator("#courtL .rt").count() == 0:
        fail("the end state is not the static court with routes")
    check_positions("end state", page.evaluate(MARKERS, "#courtL .mk"), ar)
    if "You (OH1):" not in page.inner_text("#lCap"):
        fail(f"the caption does not start with your move: {page.inner_text('#lCap')!r}")


def check_never_blocks(page: Page) -> None:
    """Next, the chips and the court answer at once while a transition plays; markers ignore taps."""
    open_app(page, "?ff=all", {"role": "S", "rulesMode": "simple"})
    learn(page, 1, "rec")
    page.click("#lNext")
    page.wait_for_timeout(300)
    hit = page.evaluate(
        "(() => { const g = document.querySelector('#courtL .am[data-p=\"S\"]').getBoundingClientRect();"
        " const el = document.elementFromPoint(g.x + g.width / 2, g.y + g.height / 2);"
        " return !!(el && el.closest('.am')); })()"
    )
    if hit:
        fail("a marker takes taps while a transition plays")
    page.click("#lNext")
    if page.inner_text("#learnTag") != "R3 (S5) · Rotation":
        fail(f"Next waits for the transition: tag {page.inner_text('#learnTag')!r}")
    state = anim(page)
    if not state or not state["playing"] or state["t"] > 400:
        fail(f"Next mid-transition does not start the next one: {state}")
    page.click('.rot[data-i="4"]')
    if anim(page) or page.inner_text("#learnTag") != "R5 (S3) · Rotation":
        fail("a rotation chip does not snap to the end state")
    page.click('.ph[data-k="serve"]')
    if not anim(page):
        fail("tapping the next phase chip does not play that transition")
    page.click('.ph[data-k="ar"]')
    if anim(page):
        fail("jumping two phases plays a transition")
    page.click("#lReplay")
    if not anim(page):
        fail("Replay does not restart the transition")
    page.click("#tabSets")
    page.click("#tabLearn")
    if anim(page):
        fail("a tab change leaves the frame loop running")


def check_speed(page: Page) -> None:
    open_app(page, "?ff=all", {"role": "L", "rulesMode": "simple"})
    page.click("#lSpeed")
    if page.inner_text("#lSpeed") != "0.5×" or page.evaluate("localStorage.getItem('ksv51:animSpeed')") != "0.5":
        fail(f"speed button: {page.inner_text('#lSpeed')!r}")
    page.reload()
    page.wait_for_function("document.readyState === 'complete'")
    if page.inner_text("#lSpeed") != "0.5×":
        fail("the speed is not kept across a reload")
    page.click("#lNext")
    page.wait_for_timeout(1000)
    state = anim(page)
    if not state or not 300 <= state["t"] <= 700:
        fail(f"at 0.5× one second plays {state and state['t']} ms of the transition")


def check_rotate_and_reset(page: Page) -> None:
    """After reception → next rotation says the rally goes on; into R3 the middle pair resets."""
    open_app(page, "?ff=all", {"role": "MB", "rulesMode": "simple"})
    learn(page, 0, "ar")
    page.click("#lNext")
    if page.inner_text("#lCap") != ROTATE:
        fail(f"After reception → R2 caption: {page.inner_text('#lCap')!r}")
    if re.search(r"go to base", page.inner_text("#learn"), re.I):
        fail("a 'go to base' banner shows")
    learn(page, 1, "ar")
    page.click("#lNext")
    captions: list[str] = page.evaluate("window.ksvLearn.captions(2, 'start', 'MB')")
    if captions != [ROTATE, "You (MB): Walk along the net from zone 2 to zone 4: the middle pair resets."]:
        fail(f"R2 → R3 captions for MB: {captions}")
    page.wait_for_function("!window.ksvLearn.anim()", timeout=15000)
    got = page.evaluate(MARKERS, "#courtL .mk")
    if not close(got["MB"], (0.17, 0.21)) or not close(got["L"], (0.83, 0.71)):
        fail(f"after the reset MB is at {got.get('MB')}, L at {got.get('L')}")
    serve: list[str] = page.evaluate("window.ksvLearn.captions(2, 'serve', 'OH1')")
    if len(serve) != 3 or "Libero: Go off at the sideline" not in serve[0] or not serve[2].startswith("Substitute: Serve"):
        fail(f"R3 Our serve does not swap L for SUB first: {serve}")
    rec: list[str] = page.evaluate("window.ksvLearn.captions(2, 'rec', 'L')")
    if rec[0] != "You (L): Come back on for SUB and take your reception spot.":
        fail(f"R3 Reception does not bring L back on for SUB: {rec}")


def check_captions(page: Page) -> None:
    """Every stage caption is one line or two at 390 px, at most 90 characters, with no template leaks."""
    for mode, roles in MODES.items():
        open_app(page, "?ff=all", {"role": roles[0], "rulesMode": mode})
        result: list[dict[str, Any]] = page.evaluate(
            """(roles) => { const cap = document.querySelector('#lCap'), out = [];
            const line = parseFloat(getComputedStyle(cap).lineHeight);
            for (const r of roles) for (let ri = 0; ri < 6; ri++) for (const ph of ['start','serve','rec','ar'])
              for (const c of window.ksvLearn.captions(ri, ph, r)) {
                cap.textContent = c; out.push({ r, ri, ph, c, lines: cap.getBoundingClientRect().height / line });
              }
            return out; }""",
            roles,
        )
        for item in result:
            tag = f"{mode} {item['r']} R{item['ri'] + 1} {item['ph']}"
            if not item["c"] or len(item["c"]) > 90 or re.search(r"undefined|NaN|null|\$\{", item["c"]):
                fail(f"{tag}: caption {item['c']!r} ({len(item['c'])} characters)")
            if item["lines"] > 2.05:
                fail(f"{tag}: caption takes {item['lines']:.1f} lines: {item['c']!r}")


def check_reduced(browser: Browser) -> None:
    """Reduced motion and ?anim=0: no glide, the stages as a list, only Next in the row."""
    for label, query, motion in (("reduced motion", "?ff=all", "reduce"), ("?anim=0", "?ff=all&anim=0", None)):
        context = browser.new_context(viewport={"width": 390, "height": 844}, reduced_motion=motion)  # type: ignore[arg-type]
        page = context.new_page()
        open_app(page, query, {"role": "OH1", "rulesMode": "simple"})
        learn(page, 0, "rec")
        if page.is_visible("#lAnim") or page.is_visible("#lDots") or not page.is_visible("#lNext"):
            fail(f"{label}: controls shown: Replay/Pause/Step/speed and dots must be hidden, Next shown")
        page.click("#lNext")
        if anim(page) or page.locator("#courtL .am").count():
            fail(f"{label}: Next plays a glide")
        if page.locator("#courtL .rt").count() == 0:
            fail(f"{label}: routes do not show at once")
        if page.locator("#lCap ol li").count() != 3:
            fail(f"{label}: the caption is not the list of three stages: {page.inner_text('#lCap')!r}")
        context.close()


def check_phone(browser: Browser) -> None:
    """At 390 × 664 the whole control row stays in view while a transition plays."""
    context = browser.new_context(viewport={"width": 390, "height": 664}, is_mobile=True, has_touch=True)
    page = context.new_page()
    open_app(page, "?ff=all", {"role": "S", "rulesMode": "simple"})
    learn(page, 0, "rec")
    page.click("#lNext")
    page.evaluate("window.scrollTo(0, 0)")
    for sel in CONTROLS:
        box = page.locator(sel).bounding_box()
        if not box or box["y"] < 0 or box["y"] + box["height"] > 665:
            fail(f"390 × 664: {sel} is outside the viewport: {box}")
        elif box["width"] < 44 or box["height"] < 44:
            fail(f"390 × 664: {sel} is {box['width']:.0f} × {box['height']:.0f}")
    if not anim(page):
        fail("390 × 664: the transition did not play")
    context.close()


def check_flag_off(page: Page) -> None:
    open_app(page, "?ff=all,-learn-animation", {"role": "OH1", "rulesMode": "simple"})
    for sel in ("#lCap", "#lAnim", "#lDots", "#lReplay"):
        if page.locator(sel).count():
            fail(f"learn-animation off: {sel} is in the DOM")
    page.click("#lNext")
    if anim(page):
        fail("learn-animation off: Next plays a transition")


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        page = context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        check_stages(page)
        check_never_blocks(page)
        check_speed(page)
        check_rotate_and_reset(page)
        check_captions(page)
        check_flag_off(page)
        check_reduced(browser)
        check_phone(browser)
        for error in errors:
            fail(f"page error: {error}")
        browser.close()
    print(f"ANIM TEST: {len(FAIL)} failures")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
