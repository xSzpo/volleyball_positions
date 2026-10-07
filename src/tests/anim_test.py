"""Playwright test of the Learn animation (learn-animation).

Reception opens at rest on the reception spots with the overlap limits and no
ball; it plays only on Play, and Play gives one nudge per open. Rotation opens
on its still lineup too and plays only on Play: it builds the lineup from the
setter, one marker per stage, and ends on the still. Our serve and Base are
static with no controls, no nudge and no play.
Reception plays their serve, the pass, the set, and our spike over the net with
everyone to base defence, then fades back to the reception spots; Pause and
Step keep their frame. Checks the stage end positions, the ball on the Our
serve and Base stills, the controls (Replay, Pause, Step, speed), that no
route plays on open, that Next and the chips never animate or wait, the still
captions for exchanges and MB serving in Simplified R3 and R6, the caption length and
height, reduced motion and ?anim=0, the movement trails (through the stage and a
run carried on), that the ball never waits in a player's hands, L's run in
front of the deep outside hitter,
the passer, the 3-2 cover at the spike, the top speed, no
marker passing through another, and the controls in the court panel on a short
phone.

Usage: python src/tests/anim_test.py
"""

import math
import re
import sys
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, Page, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from data import ATTACK_LINE, BASE_DEF, lineup, rotation_lineup, server  # noqa: E402

BASE = (ROOT / "index.html").as_uri()
FAIL: list[str] = []
MODES = {
    "simple": ["MB", "OH1", "OH2", "OP", "S", "L"],
    "official": ["MB1", "MB2", "OH1", "OH2", "OP", "S", "L"],
}
PHASES = ["start", "serve", "rec", "ar"]
CONTROLS = ["#lReplay", "#lPlay", "#lBack", "#lStep", "#lSpeed", "#lNext"]

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
        "(s) => { localStorage.clear(); localStorage.setItem('ksv51:officialReset', JSON.stringify('1'));"
        " for (const [k, v] of Object.entries(s))"
        " if (v === null) localStorage.removeItem('ksv51:' + k);"
        " else localStorage.setItem('ksv51:' + k, JSON.stringify(v)); }",
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


NUDGES = """() => { if (window.__nudges) return; window.__nudges = 0;
  new MutationObserver((ms) => ms.forEach((m) => {
    if (!(m.oldValue || '').includes('nudge') && m.target.classList.contains('nudge')) window.__nudges++;
  })).observe(document.querySelector('#lPlay'),
    { attributes: true, attributeFilter: ['class'], attributeOldValue: true }); }"""


def spots(ri: int, phase: str, mode: str = "simple") -> dict[str, tuple[float, float]]:
    """The data spots of a phase; at Our serve the server stands at their base spot."""
    row = lineup(ri, mode)  # type: ignore[arg-type]
    if phase == "serve":
        front, back = row["serve"]
        return {p: BASE_DEF[z][:2] for z, p in zip((4, 3, 2, 5, 6, 1), front + back, strict=True)}
    if phase == "rec":
        return {p: (x, y) for p, x, y in row["rec"]}
    return {p: (x, y) for p, x, y, _ in row["ar"]}


def wait_done(page: Page) -> None:
    page.wait_for_function("!window.ksvLearn.anim()", timeout=15000)


def play_end(page: Page, ri: int, phase: str) -> dict[str, tuple[float, float]]:
    """Where the app's play of a phase ends."""
    ends: dict[str, dict[str, float]] = page.evaluate(f"window.ksvLearn.track({ri}, '{phase}', 1).pop().pos")
    return {p: (v["x"], v["y"]) for p, v in ends.items()}


def rest(page: Page, ri: int, phase: str, mode: str = "simple") -> dict[str, tuple[float, float]]:
    """The Learn rest picture with the animation on: Reception on the reception spots, Base on base defence."""
    if phase == "ar":
        return reception_plan(ri, mode)[1]
    return spots(ri, phase, mode)


BALL = """() => { const g = document.querySelector('#courtL .ball');
  if (!g) return null;
  const t = g.getAttribute('transform') || '';
  const m = t.match(/scale\\(([\\d.]+)\\)/), at = t.match(/translate\\((-?[\\d.]+)[ ,](-?[\\d.]+)\\)/);
  return { opacity: g.getAttribute('opacity'), r: m ? +m[1] : 0, at: at ? [+at[1], +at[2]] : null,
    seams: g.querySelectorAll('path.seam').length,
    panels: [...g.querySelectorAll('path[fill]')].map((e) => e.getAttribute('fill')) }; }"""
SERVE_BALL, THEIR_SERVE, SPIKE_BALL = (0.3, -0.08), (0.3, -0.09), (0.62, -0.09)
HELD = 6 + 1 + 6 * 0.65  # marker radius, its edge and the ball radius, in court units


def check_ball_clear(tag: str, at: list[float], markers: dict[str, list[float]]) -> None:
    """A resting ball leaves every label whole: its centre is HELD or more from every marker centre."""
    p, near = min(((p, math.dist(at, m)) for p, m in markers.items()), key=lambda x: x[1])
    if near < HELD - 0.05:
        fail(f"{tag}: the ball at {at} covers {p}'s label ({near:.1f} from its centre, need {HELD:.1f})")


def check_still_ball(page: Page, tag: str, phase: str, markers: dict[str, list[float]]) -> None:
    """No ball at Rotation and Reception; on the other stills a ball that covers no label, over the net."""
    ball = page.evaluate(BALL)
    if phase in ("start", "rec"):
        if ball:
            fail(f"{tag}: a ball on the {phase} still")
        return
    if not ball or ball["opacity"] != "1" or not ball["at"]:
        fail(f"{tag}: no ball on the still picture: {ball}")
        return
    check_ball_clear(tag, ball["at"], markers)
    want = {"serve": SERVE_BALL, "ar": SPIKE_BALL}.get(phase)
    if want and not close(ball["at"], want):
        fail(f"{tag}: the ball rests at {ball['at']}, expected {want} over the net")


def check_opens_at_rest(page: Page) -> None:
    """Next into Reception opens on its still; Play runs from the start of the play back to it. Base stays still."""
    open_app(page, "", {"role": "OH1", "rulesMode": "simple"})
    learn(page, 0, "serve")
    page.click("#lNext")
    if page.inner_text("#learnTag") != "R1 (H1) · Reception":
        fail(f"the tag does not move with Next: {page.inner_text('#learnTag')!r}")
    page.wait_for_timeout(300)
    if anim(page) or page.locator("#courtL .am").count():
        fail(f"Reception plays when it opens: {anim(page)}")
    if not page.is_visible("#lAnim") or not page.is_visible("#lDots") or not page.is_enabled("#lPlay"):
        fail("Reception: the controls do not show at rest")
    end = rest(page, 0, "rec")
    got = page.evaluate(MARKERS, "#courtL .mk")
    if sorted(got) != sorted(end):
        fail(f"Reception: the rest picture shows {sorted(got)}, expected {sorted(end)}")
    check_positions("Reception at rest", got, end)
    check_reception_rest(page, "Reception at rest")
    if not page.locator("#courtL .bnd").count():
        fail("Reception at rest: no overlap lines for OH1 in R1")
    page.click("#lPlay")
    state = anim(page)
    if not state or not state["playing"]:
        fail(f"Reception: Play does not start the play: {state}")
        return
    if not page.is_disabled("#lStep"):
        fail("Reception: Step is enabled while playing")
    start: dict[str, Any] = page.evaluate(
        """(markers) => { document.querySelector('#lReplay').click();
        document.querySelector('#lPlay').click();
        const b = document.querySelector('#courtL .ball');
        const at = (b.getAttribute('transform') || '').match(/translate\\((-?[\\d.]+)[ ,](-?[\\d.]+)\\)/);
        return { t: window.ksvLearn.anim().t, pos: eval(markers)('#courtL .am'),
          ball: b.getAttribute('opacity') === '1' && at ? [+at[1], +at[2]] : null,
          lines: document.querySelectorAll('#courtL .bnd').length }; }""",
        MARKERS,
    )
    if start["t"] >= 700:
        fail(f"Reception: paused only at {start['t']}")
    check_positions("Reception play start", start["pos"], end)
    if start["lines"]:
        fail("Reception: the overlap limits stay while the play runs")
    if not start["ball"] or math.dist(start["ball"], [v * 100 for v in THEIR_SERVE]) > 1:
        fail(f"Reception: the ball starts at {start['ball']}, expected near {THEIR_SERVE}")
    page.click("#lPlay")
    wait_done(page)
    if page.locator("#courtL .am").count() or page.locator("#courtL .trail").count():
        fail("Reception: the animation markers or trails stay after the play")
    check_reception_rest(page, "Reception after the play")
    if page.locator("#lDots i.on").count():
        fail("Reception: dots stay on at rest")
    page.click("#lReplay")
    if not (anim(page) or {}).get("playing"):
        fail("Reception: Replay does not play again")
    wait_done(page)
    if "You (OH1):" not in page.inner_text("#lCap"):
        fail(f"the caption does not start with your move: {page.inner_text('#lCap')!r}")
    page.click("#lNext")
    page.wait_for_timeout(300)
    if page.inner_text("#learnTag") != "R1 (H1) · Base" or anim(page) or page.is_visible("#lPlay"):
        fail(f"Base: opens {page.inner_text('#learnTag')!r} with a play or controls: {anim(page)}")
    got = page.evaluate(MARKERS, "#courtL .mk")
    check_positions("Base at rest", got, rest(page, 0, "ar"))
    check_still_ball(page, "Base at rest", "ar", got)
    if "Our attack is over the net: defend." not in page.inner_text("#cue"):
        fail(f"Base at rest: the cue does not say to defend: {page.inner_text('#cue')!r}")


def check_rest_pictures(page: Page) -> None:
    """Every rotation and rule set: each screen opens on its still, and nothing plays.

    Our serve rests with everyone on base and the ball over the net, and has no play. Base rests on base defence by
    job, with the ball over the net, and has no play. Reception rests on the reception spots with the overlap limits
    and no ball; its play ends on base defence with the ball over the net.
    """
    for mode, roles in MODES.items():
        open_app(page, "", {"role": roles[0], "rulesMode": mode})
        for ri in range(6):
            for phase in PHASES:
                learn(page, ri, phase)
                tag = f"{mode} R{ri + 1} {phase}"
                if anim(page):
                    fail(f"{tag}: plays on open")
                got = page.evaluate(MARKERS, "#courtL .mk")
                check_still_ball(page, tag, phase, got)
                if phase == "start":
                    continue
                want = rest(page, ri, phase, mode)
                if sorted(got) != sorted(want):
                    fail(f"{tag}: rest picture {sorted(got)}, expected {sorted(want)}")
                check_positions(f"{tag} at rest", got, want)
                if phase != "rec":
                    if page.evaluate(f"window.ksvLearn.stages({ri}, '{phase}')"):
                        fail(f"{tag}: has animation stages")
                    continue
                ends = play_end(page, ri, phase)
                check_reception_rest(page, tag, ri, mode)
                ball = page.evaluate(f"window.ksvLearn.stages({ri}, 'rec').pop().ball")
                if not ball or not ball["to"]["y"] < 0:
                    fail(f"{tag}: the last stage does not play the ball over the net: {ball}")
                want = reception_plan(ri, mode)[1]
                check_positions(f"{tag} play end", {p: [x * 100, y * 100] for p, (x, y) in ends.items()}, want)


def check_reception_rest(page: Page, tag: str, ri: int = 0, mode: str = "simple") -> None:
    """Reception at rest: the reception spots, your overlap limits, no ball, and the reception cue."""
    check_positions(f"{tag}: reception spots", page.evaluate(MARKERS, "#courtL .mk"), spots(ri, "rec", mode))
    if page.locator("#courtL .am, #courtL .trail").count():
        fail(f"{tag}: animation markers or trails on the still")
    if page.evaluate(BALL):
        fail(f"{tag}: a ball on the Reception still")
    want = page.evaluate("(a) => window.ksvLearn.bounds(...a)", [ri, "rec"])
    if page.locator("#courtL .bnd").count() != want:
        fail(f"{tag}: {page.locator('#courtL .bnd').count()} overlap lines, expected {want}")
    cue = page.inner_text("#cue")
    if page.locator("#courtL .me-ring").count() and "Overlap:" not in cue:
        fail(f"{tag}: the cue has no overlap text: {cue!r}")


def check_nudge(browser: Browser) -> None:
    """Play nudges once per open of Rotation or Reception, never on Our serve, Base, a loop or while playing."""
    for label, query, motion in (
        ("motion", "", None),
        ("reduced motion", "", "reduce"),
        ("?anim=0", "?anim=0", None),
    ):
        context = browser.new_context(viewport={"width": 390, "height": 844}, reduced_motion=motion)  # type: ignore[arg-type]
        page = context.new_page()
        open_app(page, query, {"role": "OH1", "rulesMode": "simple"})
        learn(page, 0, "start")
        page.evaluate(NUDGES)
        on = label == "motion"

        def expect(n: int, what: str, page: Page = page, label: str = label, on: bool = on) -> None:
            got, want = int(page.evaluate("window.__nudges")), n if on else 0
            if got != want:
                fail(f"{label}: {what}: {got} nudges, expected {want}")

        page.click("#lNext")
        expect(0, "Next into Our serve")
        page.click("#lNext")
        expect(1, "Next into Reception")
        page.wait_for_timeout(1200)
        if page.evaluate("document.querySelector('#lPlay').classList.contains('nudge')"):
            fail(f"{label}: the nudge class stays after it ran")
        expect(1, "Reception after 1.2 s (no loop)")
        page.click('.rot[data-i="3"]')
        expect(2, "a rotation chip to another Reception")
        page.keyboard.press("ArrowRight")
        expect(3, "the arrow key to the next Reception")
        page.click('.ph[data-k="ar"]')
        expect(3, "a chip to Base")
        page.click('.ph[data-k="start"]')
        expect(4, "Rotation")
        page.click('.ph[data-k="serve"]')
        expect(4, "a chip to Our serve")
        page.click("#tabSets")
        page.click("#tabLearn")
        expect(4, "a tab change back to Our serve")
        page.click('.ph[data-k="rec"]')
        expect(5, "back to Reception")
        if on:
            page.click("#lPlay")
        if page.evaluate("document.querySelector('#lPlay').classList.contains('nudge')"):
            fail(f"{label}: the nudge runs while playing")
        page.wait_for_timeout(300)
        expect(5, "while playing")
        page.click("#tabSets")
        page.click("#tabLearn")
        expect(6, "a tab change back to Reception")
        page.click("#roleChip")
        page.click('#roles .role[data-r="L"]')
        if page.is_visible("#setupPanel"):
            page.click("#roleChip")
        expect(6, "a role change")
        context.close()


NUDGE_BOXES = """async () => {
  const sels = ['#lPlay', '#lPanel', '#courtL', '#lAnim', '#lCap', '#lCtl', '#lNext'];
  const box = () => Object.fromEntries(sels.map((s) => {
    const r = document.querySelector(s).getBoundingClientRect();
    return [s, [r.x, r.y, r.width, r.height].map((v) => Math.round(v * 100) / 100)];
  }).concat([['page', [document.documentElement.scrollWidth, document.documentElement.scrollHeight,
    window.scrollX, window.scrollY, window.visualViewport ? visualViewport.scale : 1]]]));
  const b = document.querySelector('#lPlay');
  b.classList.remove('nudge');
  await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  const before = box();
  b.classList.add('nudge');
  const meta = ['offset', 'computedOffset', 'easing', 'composite'];
  const props = new Set();
  let running = 0;
  for (const a of document.getAnimations().filter((a) => a.effect && a.effect.target === b)) {
    running++;
    for (const k of a.effect.getKeyframes())
      for (const p of Object.keys(k)) if (!meta.includes(p)) props.add(p);
  }
  const samples = [];
  for (let i = 0; i < 8; i++) {
    await new Promise((r) => setTimeout(r, 90));
    samples.push(box());
  }
  return { before, samples, props: [...props], running };
}"""
COLOUR_PROPS = {
    "backgroundColor",
    "borderColor",
    "borderTopColor",
    "borderRightColor",
    "borderBottomColor",
    "borderLeftColor",
    "color",
    "fill",
}


def check_nudge_colour_only(browser: Browser) -> None:
    """The Play nudge changes colour only: no box on the Learn screen or the page moves while it runs."""
    context = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    page = context.new_page()
    open_app(page, "", {"role": "OH1", "rulesMode": "simple"})
    learn(page, 0, "rec")
    page.wait_for_timeout(900)
    got = page.evaluate(NUDGE_BOXES)
    if not got["running"]:
        fail("nudge: adding the class starts no animation on #lPlay")
    if not got["props"] or set(got["props"]) - COLOUR_PROPS:
        fail(f"nudge: the keyframes change {sorted(got['props'])}, expected colour properties only")
    for n, sample in enumerate(got["samples"]):
        for sel, want in got["before"].items():
            if sample[sel] != want:
                fail(f"nudge: sample {n}: {sel} is {sample[sel]}, was {want}")
    context.close()


def check_no_autoplay(page: Page) -> None:
    """No route plays: load, reload, Next, the chips, the arrow keys, a role change and a rules change."""
    open_app(page, "", {"role": "OH1", "rulesMode": "simple"})
    if page.inner_text("#learnTag") != "R1 (H1) · Reception" or anim(page):
        fail(f"a fresh load onto {page.inner_text('#learnTag')!r} plays: {anim(page)}")
    page.reload()
    page.wait_for_function("document.readyState === 'complete' && !!document.querySelector('#lNext')")
    if anim(page):
        fail("a reload plays Reception")
    page.click('.ph[data-k="serve"]')
    if anim(page):
        fail("a phase chip plays Our serve")
    page.click("#lNext")
    if anim(page):
        fail("Next plays Reception")
    page.click('.rot[data-i="2"]')
    if anim(page):
        fail("a rotation chip plays Reception")
    page.keyboard.press("ArrowLeft")
    page.wait_for_timeout(200)
    if anim(page) or page.inner_text("#learnTag") != "R2 (H6) · Reception":
        fail(f"the arrow key plays or does not move: {page.inner_text('#learnTag')!r}")
    page.click('.ph[data-k="serve"]')
    page.click("#roleChip")
    page.click('#roles .role[data-r="L"]')
    if page.is_visible("#setupPanel"):
        page.click("#roleChip")
    if page.get_attribute("#roleChip", "data-role") != "L" or anim(page):
        fail(f"a role change plays Our serve or does not apply: {page.get_attribute('#roleChip', 'data-role')!r}")
    page.click("#roleChip")
    page.click('.rulesmode [data-rm="official"]')
    if page.is_visible("#setupPanel"):
        page.click("#roleChip")
    if page.get_attribute('.rulesmode [aria-checked="true"]', "data-rm") != "official" or anim(page):
        fail("a rules change plays Our serve or does not apply")
    check_positions(
        "Our serve after the rules change", page.evaluate(MARKERS, "#courtL .mk"), spots(1, "serve", "official")
    )


def check_static(page: Page) -> None:
    """Rotation opens on its still with the controls and plays nothing; Next reads in full and Base does not play."""
    open_app(page, "", {"role": "S", "rulesMode": "official"})
    for ri, phase in ((0, "start"), (3, "start")):
        learn(page, ri, phase)
        if anim(page):
            fail(f"R{ri + 1} {phase}: a chip tap plays an animation")
        if not page.is_visible("#lPlay") or page.locator("#lDots i").count() != 7:
            fail(f"R{ri + 1} {phase}: the controls or the seven stage dots do not show")
        if not page.inner_text("#lNext").lower().startswith("next:"):
            fail(f"R{ri + 1} {phase}: Next reads {page.inner_text('#lNext')!r}")
        if page.locator("#courtL .am").count():
            fail(f"R{ri + 1} {phase}: animation markers on the still")
    learn(page, 0, "rec")
    page.click("#lNext")
    if anim(page) or page.inner_text("#learnTag") != "R1 (H1) · Base":
        fail("Next into Base animates or does not move the tag")
    check_positions("Base", page.evaluate(MARKERS, "#courtL .mk"), reception_plan(0, "official")[1])
    if not page.inner_text("#lNext").lower().startswith("next:"):
        fail(f"Base: Next reads {page.inner_text('#lNext')!r}")
    page.click("#lNext")
    if anim(page) or page.inner_text("#learnTag") != "R2 (H6) · Rotation":
        fail("Next into the next Rotation animates")
    stages: list[dict[str, Any]] = page.evaluate("window.ksvLearn.stages(0, 'start')")
    if len(stages) != 7:
        fail(f"Rotation has {len(stages)} build stages, expected 7")


HIT_Y, APPROACH_Y = 0.08, 0.17
MARKER_R = 0.06
GAP = 0.14  # a marker width plus its ring
MIN_MOVE = 0.04
COVER_NEAR = 0.35  # the three close covers, 1 to 3 m from the hitter
COVER_MIN = 0.11
COVER_BEHIND = 0.05
DEEP_COVER = {"back": (0.44, 0.56), "side": (0.62, 0.44)}
SET_MAX_MS = 1100
COVER_L = (0.30, 0.39)  # R1: the hit at (0.15, 0.08)
TRAILS = """() => [...document.querySelectorAll('#courtL .trail')]
  .filter((l) => l.getAttribute('visibility') === 'visible').map((l) => l.dataset.p)"""
TRAIL_LENGTHS = """() => Object.fromEntries([...document.querySelectorAll('#courtL .trail')]
  .filter((l) => l.getAttribute('visibility') === 'visible')
  .map((l) => { const q = [...l.points];
    return [l.dataset.p, q.slice(1).reduce((s, b, i) => s + Math.hypot(b.x - q[i].x, b.y - q[i].y), 0)]; }))"""
RECEIVERS = ("OH1", "OH2", "L")
TOP_SPEED = 5.0  # m/s; 1 unit is 9 m
TRAIL_FADE_MS = 400
BALL_WAIT_MS = 400
DEEP_LIMIT = 0.85
CAPTION_MS = 2500
BUILD_MS = 450
SWAP_MS = 500
BUILD_HOLD_MS = 300
POP_MS = 250
BUILD_TOTAL_MAX_MS = 3600
BUILD_PLAY_MAX_MS = 5000
WALK_MAX = 112
WALK_LINE = "Against the rotation: Setter, Outside, Middle, Opposite, Outside, Middle."
HELD = (MARKER_R * 100 + 1 + 0.65 * MARKER_R * 100) / 100


def base_zone(p: str, front: bool, row: Any = None) -> int:
    """Base defence by job: OH 4, MB 3, S/OP 2 in the front row; S/OP 1, L 5, OH 6 behind; the row's `base` wins."""
    if row is not None and p in row.get("base", {}):
        return int(row["base"][p])
    job = p.rstrip("12")
    if front:
        return {"OH": 4, "MB": 3}.get(job, 2)
    return {"L": 5, "OH": 6, "S": 1, "OP": 1}.get(job, 6)


def reception_plan(ri: int, mode: str) -> tuple[list[str], dict[str, tuple[float, float]], str]:
    """Who leaves at the serve contact (setter and the front attackers who do not receive), base defence, the hitter."""
    row = lineup(ri, mode)  # type: ignore[arg-type]
    ar = {p: (x, y) for p, x, y, _ in row["ar"]}
    rec = {p: (x, y) for p, x, y in row["rec"]}
    kind = {p: k for p, _, _, k in row["ar"]}
    order = list(rec)
    attackers = [p for p in order if kind[p] in ("front", "back")]
    hitter = min((p for p in attackers if kind[p] == "front"), key=lambda p: ar[p][0])
    # A back-row attacker who does not hit covers instead, and waits out of the passing lanes until the pass.
    release = [p for p in order if kind[p] == "set" or (kind[p] == "front" and p not in RECEIVERS)]
    release = [p for p in release if math.dist(rec[p], ar[p]) >= MIN_MOVE]
    end = {p: BASE_DEF[base_zone(p, p in row["front"], row)][:2] for p in order}
    return release, end, hitter


def trail_movers(stage: dict[str, Any]) -> list[str]:
    """The players who move far enough in a stage to leave a trail."""
    return [
        p
        for p in stage["moves"]
        if abs(stage["to"][p]["x"] - stage["from"][p]["x"]) + abs(stage["to"][p]["y"] - stage["from"][p]["y"]) >= 0.01
    ]


def trails_at(stages: list[dict[str, Any]], t: float) -> list[str]:
    """The trails that show at t: a run's trail stays through its stage and while it carries on, then fades."""
    shown = []
    for k, stage in enumerate(stages):
        after = stages[k + 1]["start"] if k + 1 < len(stages) else math.inf
        for p in trail_movers(stage):
            gone = max(after, stage["start"] + stage["arrive"][p])
            if stage["start"] + stage["delays"][p] < t < gone + TRAIL_FADE_MS:
                shown.append(p)
    return shown


ZONES = (4, 3, 2, 5, 6, 1)
WALK_ARROWS = """() => [...document.querySelectorAll('#courtL g.walk')]
  .filter((g) => +g.getAttribute('opacity') > 0).map((g) => { const l = g.querySelector('line');
    const v = (n) => +l.getAttribute(n) / 100;
    return { from: g.dataset.from, to: g.dataset.to, x1: v('x1'), y1: v('y1'), x2: v('x2'), y2: v('y2') }; })"""
SHOWN = """() => [...document.querySelectorAll('#courtL .am')]
  .filter((g) => +(g.getAttribute('opacity') ?? 1) > 0).map((g) => g.dataset.p).sort()"""


def rotation_zones(ri: int, mode: str) -> dict[str, int]:
    """The Rotation step's zones: in R3 and R6 the serving middle stands in zone 1 and L is off."""
    return dict(zip(rotation_lineup(ri, mode), ZONES, strict=True))  # type: ignore[arg-type]


def build_order(zones: dict[str, int]) -> list[str]:
    """The zone walk: the player in each zone from the setter's up, 6 wrapping to 1."""
    by_zone = {z: p for p, z in zones.items()}
    return [by_zone[(zones["S"] - 1 + k) % 6 + 1] for k in range(6)]


WALK_JOBS = ("S", "OH", "MB", "OP", "OH", "MB")


def job(p: str) -> str:
    """A role's job in the walk: L and OM play the middle."""
    return "MB" if p in ("L", "OM") else p.rstrip("12")


def back_middle(ri: int, mode: str) -> str:
    """The middle the libero replaces at the Rotation step: none in Simplified, where L plays the back middle."""
    return lineup(ri, mode)["liberofor"]  # type: ignore[arg-type]


def walk_line(zones: dict[str, int]) -> str:
    """The one caption of the Rotation build."""
    end = "The libero replaces the back middle." if "L" in zones else "The zone 1 middle serves, libero off."
    return f"{WALK_LINE} {end}"


def check_build_stages(page: Page, mode: str, ri: int) -> None:
    """The Rotation build of one rotation: order, the libero swap, spots, end, timing and the one caption."""
    tag = f"{mode} R{ri + 1} Rotation build"
    zones = rotation_zones(ri, mode)
    back = back_middle(ri, mode)
    swap = bool(back) and "L" in zones
    order = [back if p == "L" and swap else p for p in build_order(zones)]
    walk_zones = {back if p == "L" and swap else p: z for p, z in zones.items()}
    n = zones["S"]
    want = {"OP": (n + 2) % 6 + 1, "OH1": n % 6 + 1, "OH2": (n + 3) % 6 + 1}
    for p, z in want.items():
        if zones[p] != z:
            fail(f"{tag}: {p} is in zone {zones[p]}, the rule gives {z}")
    if ri in (2, 5) and ("L" in zones or zones.get(server(ri, mode)) != 1):  # type: ignore[arg-type]
        fail(f"{tag}: expected the serving middle in zone 1 and no L: {zones}")
    if tuple(job(p) for p in order) != WALK_JOBS:
        fail(f"{tag}: the walk from the setter's zone meets {order}, expected the jobs {WALK_JOBS}")
    stages: list[dict[str, Any]] = page.evaluate(f"window.ksvLearn.stages({ri}, 'start')")
    got = [st["appear"] for st in stages]
    if got != [*order, *(["L"] if swap else [])]:
        fail(f"{tag}: the markers appear as {got}, expected {order}{' and then L' if swap else ''}")
    leaves = [st["leave"] for st in stages]
    if leaves != [None] * 6 + ([back] if swap else []):
        fail(f"{tag}: the stages take off {leaves}, expected {back} only in the swap stage")
    walks = [st["walk"] for st in stages]
    pairs = [tuple(w) for w in walks[1:6] if w]
    if (
        walks[0] is not None
        or any(w is not None for w in walks[6:])
        or pairs != list(zip(order, order[1:], strict=False))
        or any(walk_zones[a] % 6 + 1 != walk_zones[b] for a, b in pairs)
    ):
        fail(f"{tag}: the walk arrows are {walks}, expected each from zone n to zone n + 1, none on S or the swap")
    if any(st["moves"] or st["ball"] for st in stages):
        fail(f"{tag}: a build stage moves a player or the ball")
    still = {o["p"]: (o["x"], o["y"]) for o in page.evaluate(f"window.ksvLearn.players({ri}, 'start')")}
    if set(still) != set(zones):
        fail(f"{tag}: the still has {sorted(still)}, expected {sorted(zones)}")
    for st in stages:
        at = page.evaluate("(a) => window.ksvLearn.at(...a)", [ri, "start", st["start"] + 1])
        p = st["appear"]
        spot = still.get("L" if p == back and swap else p, (9, 9))
        if math.dist((at[p]["x"], at[p]["y"]), spot) > 1e-6:
            fail(f"{tag}: {p} appears at {at[p]}, expected its Rotation spot {spot}")
    track = page.evaluate(f"window.ksvLearn.track({ri}, 'start', 1)")[-1]
    end = {p: (v["x"], v["y"]) for p, v in track["pos"].items()}
    if any(math.dist(end.get(p, (9, 9)), still[p]) > 1e-6 for p in still):
        fail(f"{tag}: the build ends on {end}, not the still {still}")
    ms = page.evaluate("window.ksvLearn.buildMs()")
    if ms != {"marker": BUILD_MS, "swap": SWAP_MS, "hold": BUILD_HOLD_MS, "pop": POP_MS}:
        fail(f"{tag}: the build timings are {ms}")
    runs = [(st["start"], st["dur"]) for st in stages]
    want_runs = [(k * BUILD_MS, BUILD_MS) for k in range(6)] + ([(6 * BUILD_MS, SWAP_MS)] if swap else [])
    if runs != want_runs:
        fail(f"{tag}: the stages run {runs}, expected {want_runs}")
    total = track["t"]
    if total != runs[-1][0] + runs[-1][1] + BUILD_HOLD_MS or total > BUILD_TOTAL_MAX_MS:
        fail(f"{tag}: the build lasts {total} ms, expected the stages plus a {BUILD_HOLD_MS} ms hold")
    line = walk_line(zones)
    for role in MODES[mode]:
        captions = page.evaluate("(a) => window.ksvLearn.captions(...a)", [ri, "start", role])
        if set(captions) != {line}:
            fail(f"{tag} as {role}: the stage captions are {captions}, expected {line!r}")
        plan = page.evaluate("(a) => window.ksvLearn.captionPlan(...a)", [ri, "start", role])
        if plan != [{"t": 0, "text": line}]:
            fail(f"{tag} as {role}: the caption plan is {plan}, expected {line!r} once")


def check_build_off_court(page: Page) -> None:
    """The middle the libero replaces stays off court through the build: the pill solid, no ring of yours."""
    for ri in (0, 3):
        role = back_middle(ri, "official")
        tag = f"official R{ri + 1} Rotation build as {role}"
        open_app(page, "", {"role": role, "rulesMode": "official"})
        learn(page, ri, "start")
        for k in range(7):
            page.click("#lStep")
            wait_paused(page)
            pill = page.locator("#courtL .offpill")
            if pill.get_attribute("stroke-dasharray") is not None or page.locator("#courtL .me-ring").count():
                fail(f"{tag}: after {k + 1} Step(s) you show on court, though the libero replaces you")


def check_rotation_build(page: Page) -> None:
    """Rotation builds its lineup from the setter in every rotation and both rule sets.

    One marker appears per stage on its Rotation spot (in Official the back middle first and then L in its place),
    nobody moves, and the play ends on the still with the overlap lines and one caption of at most two lines, no
    Then: list. Step and Step back walk the stages, and Step back from the first stage returns to the still. R3 and
    R6 build the serving middle in zone 1 and no L.
    """
    for mode in MODES:
        open_app(page, "", {"role": "OH1", "rulesMode": mode})
        for ri in range(6):
            check_build_stages(page, mode, ri)
    for mode, ri in (("simple", 0), ("official", 2)):
        role = "OH1" if mode == "simple" else server(ri, mode)  # type: ignore[arg-type]
        tag = f"{mode} R{ri + 1} Rotation as {role}"
        open_app(page, "", {"role": role, "rulesMode": mode})
        learn(page, ri, "start")
        zones = rotation_zones(ri, mode)
        back = back_middle(ri, mode)
        swap = bool(back) and "L" in zones
        order = [back if p == "L" and swap else p for p in build_order(zones)]
        line = walk_line(zones)
        still = {o["p"]: (o["x"], o["y"]) for o in page.evaluate(f"window.ksvLearn.players({ri}, 'start')")}
        spot = {**still, back: still["L"]} if swap else still
        if anim(page) or page.locator("#courtL .am").count() or page.locator("#courtL .mk").count() != 6:
            fail(f"{tag}: does not open on the full still")
        if not page.is_disabled("#lBack"):
            fail(f"{tag}: Step back is enabled on the still")
        for k in range(1, 8 if swap else 7):
            page.click("#lStep")
            wait_paused(page)
            shown = page.evaluate(SHOWN)
            want = sorted(order[:k]) if k <= 6 else sorted(still)
            if shown != want:
                fail(f"{tag}: after {k} Step(s) the court shows {shown}, expected {want}")
            check_positions(f"{tag} step {k}", page.evaluate(MARKERS, "#courtL .am"), {p: spot[p] for p in want})
            if page.locator("#courtL .bnd").count():
                fail(f"{tag}: overlap lines show during the build")
            arrows = page.evaluate(WALK_ARROWS)
            upto = min(k, 6)
            if [(a["from"], a["to"]) for a in arrows] != list(zip(order[: upto - 1], order[1:upto], strict=True)):
                fail(f"{tag}: after {k} Step(s) the walk arrows are {arrows}, expected {order[:upto]} in order")
            for a in arrows:
                start, end = (a["x1"], a["y1"]), (a["x2"], a["y2"])
                if math.dist(start, spot[a["from"]]) > 0.1 or math.dist(end, spot[a["to"]]) > 0.1:
                    fail(f"{tag}: the walk arrow {a} does not run from {a['from']} to {a['to']}")
            if page.locator("#courtL line[marker-end]:not(.walk line)").count():
                fail(f"{tag}: the rotation arrows show during the build")
            if page.inner_text("#lCap").strip() != line:
                fail(f"{tag}: after {k} Step(s) the caption is {page.inner_text('#lCap')!r}, expected {line!r}")
            if k == 2:
                page.click("#lBack")
                if page.evaluate(SHOWN) != [order[0]]:
                    fail(f"{tag}: Step back shows {page.evaluate(SHOWN)}, expected [{order[0]!r}]")
                page.click("#lBack")
                if anim(page) or page.locator("#courtL .mk").count() != 6:
                    fail(f"{tag}: Step back from the first stage does not return to the still")
                for _ in range(2):
                    page.click("#lStep")
                    wait_paused(page)
        learn(page, ri, "start")
        page.evaluate(
            """() => { window.buildRun = null; let t0 = null;
            const poll = () => { const a = window.ksvLearn.anim();
              if (a?.playing && t0 === null) t0 = performance.now();
              if (t0 === null || a) requestAnimationFrame(poll);
              else window.buildRun = performance.now() - t0; };
            requestAnimationFrame(poll); }"""
        )
        page.click("#lPlay")
        page.wait_for_timeout(200)
        if page.inner_text("#lCap").strip() != line:
            fail(f"{tag}: while it plays the caption is {page.inner_text('#lCap')!r}, expected {line!r}")
        page.wait_for_function("window.buildRun !== null", timeout=25000)
        run = page.evaluate("window.buildRun")
        if run >= BUILD_PLAY_MAX_MS:
            fail(f"{tag}: the build played at 1× for {run:.0f} ms, expected under {BUILD_PLAY_MAX_MS}")
        check_positions(f"{tag} end", page.evaluate(MARKERS, "#courtL .mk"), still)
        if page.locator("#courtL g.walk").count() or page.locator("#courtL line[marker-end]").count() < 6:
            fail(f"{tag}: the still after the play does not show the rotation arrows instead of the walk")
        if mode == "official" and ("L" in still or role not in still):
            fail(f"{tag}: the build shows L or leaves out the serving middle: {sorted(still)}")
        if mode == "simple" and not page.locator("#courtL .bnd").count():
            fail(f"{tag}: the overlap lines do not show at the end")
        if page.locator("#lCap .then").count() or page.inner_text("#lCap").strip() != line:
            fail(f"{tag}: after the play the caption is {page.inner_text('#lCap')!r}, expected only {line!r}")
        lines = page.evaluate(
            "() => { const e = document.querySelector('#lCap');"
            " return e.getBoundingClientRect().height / parseFloat(getComputedStyle(e).lineHeight); }"
        )
        if round(lines) > 2:
            fail(f"{tag}: the caption takes {lines:.1f} lines at 390 px, expected at most 2")


def check_reception_stages(page: Page) -> None:
    """Step runs one stage and pauses: serve and setter, pass and approach, set and cover, spike and defence.

    Step stays on the last stage; Play runs on and fades back to the reception spots.
    """
    open_app(page, "", {"role": "OH1", "rulesMode": "simple"})
    learn(page, 0, "start")
    page.click('.ph[data-k="rec"]')
    ar = spots(0, "ar")
    release, end, hitter = reception_plan(0, "simple")
    stages: list[dict[str, Any]] = page.evaluate("window.ksvLearn.stages(0, 'rec')")
    if len(stages) != 4 or sorted(stages[0]["moves"]) != sorted(release):
        fail(f"Reception stages move {[st['moves'] for st in stages]}, expected {release} at the serve contact")
        return
    if not all(st["ball"] for st in stages):
        fail("a Reception stage has no ball")
    for stage in range(4):
        page.click("#lStep")
        wait_paused(page)
        state = anim(page)
        if not state or abs(state["t"] - state["ends"][stage]) > 1:
            fail(f"Step {stage + 1} stopped at {state}, expected the end of stage {stage + 1}")
            continue
        if state["stage"] != stage or page.locator("#lDots i.on").count() != stage + 1:
            fail(f"stage {stage + 1}: dots {page.locator('#lDots i.on').count()} on, stage {state['stage']}")
        got = page.evaluate(MARKERS, "#courtL .am")
        if stage == 0:
            check_ball(page, got["L"])
        if stage == 1:
            for p, spot in {**ar, "L": COVER_L, "OH2": DEEP_COVER["back"]}.items():
                if p == "MB":
                    if abs(got[p][1] / 100 - APPROACH_Y) > 0.06:
                        fail(f"after the pass: MB at {got[p]}, not at the quick take-off")
                    continue
                if math.dist((got[p][0] / 100, got[p][1] / 100), spot) >= MIN_MOVE:
                    fail(f"after the pass: {p} at {got[p]}, expected {spot}")
        if stage == 3:
            check_positions("after the spike", got, end)
            ball = page.evaluate(BALL)
            if not ball or not ball["at"] or not ball["at"][1] < 0:
                fail(f"after the spike the ball is not over the net: {ball}")
        trails = trails_at(stages, state["t"])
        if sorted(page.evaluate(TRAILS)) != sorted(trails):
            fail(f"after Step {stage + 1}: trails {sorted(page.evaluate(TRAILS))}, expected {sorted(trails)}")
    held = anim(page)
    page.click("#lStep")
    page.wait_for_timeout(1500)
    state = anim(page)
    if not state or not held or state["t"] != held["t"] or state["fading"]:
        fail(f"Step on the last stage leaves its frame: {held} then {state}")
    check_positions("Step on the last stage", page.evaluate(MARKERS, "#courtL .am"), end)
    page.click("#lReplay")
    if (anim(page) or {}).get("playing"):
        page.click("#lPlay")
    wait_paused(page)
    for _ in range(3):
        page.click("#lStep")
        wait_paused(page)
    if (anim(page) or {}).get("stage") != 2:
        fail(f"Replay, pause and Step three times stopped at {anim(page)}, expected the end of stage 3")
    mid = page.evaluate(TRAIL_LENGTHS)
    if set(mid) != set(trail_movers(stages[2])) or not all(v > 0.5 for v in mid.values()):
        fail(f"paused at the end of stage 3: trails {mid}, expected the set and cover moves")
    page.click("#lReplay")
    state = anim(page)
    fresh = page.evaluate(TRAIL_LENGTHS)
    if not state or state["t"] > 200 or any(v > 1 for v in fresh.values()):
        fail(f"Replay keeps the old trails: {fresh} at {state and state['t']}")
    if not (anim(page) or {}).get("playing"):
        page.click("#lPlay")
    wait_done(page)
    if page.locator("#courtL .trail").count():
        fail("the trails stay on the still picture")
    check_reception_rest(page, "back on the rest picture")
    captions: list[str] = page.evaluate("window.ksvLearn.captions(0, 'rec', 'L')")
    if (
        len(captions) != 4
        or captions[1] != "You (L): Pass the serve high to the setter at the net."
        or not captions[2].startswith("You (L): Cover")
        or captions[3] != "You (L): Go to zone 5 and defend while they play the ball."
    ):
        fail(f"Reception captions for L: {captions}")
    if hitter != "OP" or "set op in zone 4" not in page.evaluate("window.ksvLearn.captions(0, 'rec', 'S')")[2].lower():
        fail(f"R1: the setter does not set the zone 4 hitter {hitter}")


def check_ball(page: Page, passer: list[float]) -> None:
    """The ball is a volleyball with seams, about two thirds of a marker, and stops at the passer's edge."""
    ball: dict[str, Any] = page.evaluate(
        """() => { const g = document.querySelector('#courtL .ball');
        const t = g.getAttribute('transform') || '';
        const m = t.match(/scale\\(([\\d.]+)\\)/), at = t.match(/translate\\((-?[\\d.]+)[ ,](-?[\\d.]+)\\)/);
        return { opacity: g.getAttribute('opacity'), r: m ? +m[1] : 0, at: at ? [+at[1], +at[2]] : null,
          seams: g.querySelectorAll('path.seam').length,
          panels: [...g.querySelectorAll('path[fill]')].map((e) => e.getAttribute('fill')) }; }"""
    )
    if ball["opacity"] != "1" or not 0.6 * 6 <= ball["r"] <= 0.7 * 6:
        fail(f"the ball is not shown at 0.6 to 0.7 of the marker radius: {ball}")
    if ball["seams"] < 3 or len(ball["panels"]) < 2:
        fail(f"the ball has no volleyball seams or panels: {ball}")
    if not ball["at"] or math.dist(ball["at"], passer) < MARKER_R * 100:
        fail(f"the ball covers the passer's label: ball at {ball['at']}, passer at {passer}")


def to_segment(p: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
    """The distance from p to the segment a-b."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    k = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy or 1)))
    return math.dist(p, (a[0] + k * dx, a[1] + k * dy))


def turns_back(path: list[tuple[float, float]]) -> bool:
    """Whether a path turns more than a right angle at any corner."""
    return any(
        (b[0] - a[0]) * (c[0] - b[0]) + (b[1] - a[1]) * (c[1] - b[1]) < -1e-6
        for a, b, c in zip(path, path[1:], path[2:], strict=False)
    )


def check_reception_ends(page: Page) -> None:
    """Every rotation, both rule sets: release at the serve, the set and cover, then the spike and base defence.

    The setter sets from within 0.2 of the set spot, the set flies at most SET_MAX_MS and lands as the hitter's run
    ends. At the spike a 3-2 cover stands round the hitter: the setter, the middle and L 1 to 3 m from the hitter,
    behind and inside and a marker width clear of its run, and two deep covers behind them (the back-row outside
    hitter, and the right-side attacker who does not hit). The middle is at its quick take-off when the pass reaches
    the setter and then only drops back to cover.
    """
    zones = {z: spot[:2] for z, spot in BASE_DEF.items()}
    for mode, roles in MODES.items():
        open_app(page, "", {"role": roles[0], "rulesMode": mode})
        for ri in range(6):
            tag = f"{mode} R{ri + 1} Reception"
            row = lineup(ri, mode)  # type: ignore[arg-type]
            release, end, hitter = reception_plan(ri, mode)
            stages: list[dict[str, Any]] = page.evaluate(f"window.ksvLearn.stages({ri}, 'rec')")
            if len(stages) != 4 or sorted(stages[0]["moves"]) != sorted(release):
                fail(f"{tag}: stages move {[st['moves'] for st in stages]}, expected {release} at the serve contact")
                continue
            kind = {p: k for p, _, _, k in row["ar"]}
            # The setter may wait for an attacker who starts in front of the set spot to get out of the way, and the
            # front middle for the setter's run across its way to the front zone; it still takes off as the pass lands.
            waits = {
                p: 1000 if kind[p] == "set" else 1300 if p in row["front"] and p.startswith("MB") else 0
                for p in release
            }
            if any(stages[0]["delays"][p] > waits[p] for p in release):
                fail(f"{tag}: someone waits after the serve contact: {stages[0]['delays']}")
            ar = {p: (x, y) for p, x, y, _ in row["ar"]}
            track: list[dict[str, Any]] = page.evaluate(f"window.ksvLearn.track({ri}, 'rec', 600)")
            s3 = stages[2]
            at_set = {p: s["pos"][p] for s in track if s["t"] <= s3["start"] + s3["dur"] for p in s["pos"]}
            at_set = {p: (v["x"], v["y"]) for p, v in at_set.items()}
            hit = at_set[hitter]
            if abs(hit[1] - HIT_Y) > 0.005:
                fail(f"{tag}: {hitter} hits at {hit}")
            setter = next(p for p in kind if kind[p] == "set")
            middle = next(p for p in s3["moves"] if p.startswith("MB"))
            set_from = s3["from"][setter]
            if math.dist((set_from["x"], set_from["y"]), ar[setter]) > 0.2:
                fail(f"{tag}: the setter sets from {set_from}, not within 0.2 of the set spot {ar[setter]}")
            set_ms, hitter_ms = s3["ball"]["ms"], s3["arrive"][hitter]
            if set_ms > SET_MAX_MS or abs(set_ms - hitter_ms) > 20:
                fail(f"{tag}: the set flies {set_ms:.0f} ms, {hitter} gets to the net at {hitter_ms:.0f} ms")
            run = [(q["x"], q["y"]) for q in s3["paths"][hitter]]
            close = sorted(
                p
                for p, spot in at_set.items()
                if p != hitter
                and COVER_MIN <= math.dist(spot, hit) <= COVER_NEAR
                and spot[1] >= hit[1] + COVER_BEHIND
                and spot[0] - hit[0] >= GAP
                and min(to_segment(spot, a, b) for a, b in zip(run, run[1:], strict=False)) >= GAP
            )
            if close != sorted({setter, middle, "L"}):
                fail(f"{tag}: close cover behind and inside {hitter} at {hit} is {close}: {at_set}")
            side = next(p for p in kind if kind[p] in ("front", "back") and p not in (hitter, middle))
            deep = next(p for p in row["back"] if p.startswith("OH"))
            for p, want in ((deep, DEEP_COVER["back"]), (side, DEEP_COVER["side"])):
                if math.dist(at_set[p], want) > 0.05 or math.dist(at_set[p], hit) <= COVER_NEAR:
                    fail(f"{tag}: {p} covers from {at_set[p]}, not deep behind the close cover at {want}")
            take_off = (stages[1]["paths"].get(middle) or [{"y": 1.0}])[-1]
            if abs(take_off["y"] - APPROACH_Y) > 0.06:
                fail(f"{tag}: {middle} is not ready for the quick when the pass reaches the setter: {take_off}")
            if middle in stages[1]["arrive"]:
                pass_ms, ready_ms = stages[1]["ball"]["ms"], stages[1]["arrive"][middle]
                if abs(pass_ms - ready_ms) > 20:
                    fail(f"{tag}: the pass reaches the setter at {pass_ms} ms, {middle} takes off at {ready_ms} ms")
                if take_off["x"] >= ar[setter][0]:
                    fail(f"{tag}: {middle} takes off at x {take_off['x']:.2f}, not left of the set spot {ar[setter]}")
            netward = [v["y"] for v in s3["paths"][middle]]
            if any(b < a - 0.005 for a, b in zip(netward, netward[1:], strict=False)):
                fail(f"{tag}: {middle} runs towards the net during the set: {s3['paths'][middle]}")
            last = {p: (v["x"], v["y"]) for p, v in track[-1]["pos"].items()}
            check_positions(f"{tag} end", {p: [x * 100, y * 100] for p, (x, y) in last.items()}, end)
            held = sorted(z for z, spot in zones.items() for p in last if math.dist(last[p], spot) < 0.005)
            if held != [1, 2, 3, 4, 5, 6]:
                fail(f"{tag}: after the spike the defence holds zones {held}")
            if "S" in row["back"] and math.dist(last["S"], zones[1]) > 0.005:
                fail(f"{tag}: the back-row setter ends at {last['S']}, not zone 1")
            final = stages[-1]
            if not final["notes"].get(hitter, "").startswith("Spike over the net"):
                fail(f"{tag}: the last stage is not {hitter}'s spike: {final['notes'].get(hitter)!r}")
            if not final["ball"] or not final["ball"]["to"]["y"] < 0:
                fail(f"{tag}: the last stage does not play the ball over the net: {final['ball']}")


def check_quick_in_front(page: Page) -> None:
    """Every rotation, both rule sets: from the pass to the set the front middle stays in front of the 3 m line.

    The quick opens in the middle of the front zone, so the back-row hitter's lane on the 3 m line stays clear.
    """
    for mode, roles in MODES.items():
        open_app(page, "", {"role": roles[0], "rulesMode": mode})
        for ri in range(6):
            row = lineup(ri, mode)  # type: ignore[arg-type]
            middle = next(p for p in row["front"] if p.startswith("MB"))
            stages: list[dict[str, Any]] = page.evaluate(f"window.ksvLearn.stages({ri}, 'rec')")
            track: list[dict[str, Any]] = page.evaluate(f"window.ksvLearn.track({ri}, 'rec', 600)")
            pass_at, set_at = stages[1]["start"], stages[2]["start"]
            deepest = max(s["pos"][middle]["y"] for s in track if pass_at <= s["t"] <= set_at)
            if deepest >= ATTACK_LINE - 0.05:
                fail(f"{mode} R{ri + 1}: {middle} goes back to y {deepest:.2f} between the pass and the set")
    print("quick: the front middle stays in front of the 3 m line from the pass to the set", flush=True)


def check_cover_runs(page: Page) -> None:
    """Every rotation, both rule sets: no detour leaves the court, and the back-row opposite runs straight to cover.

    A detour waypoint stays between the sidelines and no deeper than the end line or its run's own ends. A back-row
    opposite who neither receives nor attacks waits for the pass, then runs to its deep cover, not via its `ar` spot.
    The front middle's quick caption says where it takes off: left of the setter. The zone 4 hitter approaches
    outside-in, ending at least 0.05 inside where it starts.
    """
    for mode, roles in MODES.items():
        open_app(page, "", {"role": roles[0], "rulesMode": mode})
        for ri in range(6):
            tag = f"{mode} R{ri + 1} Reception"
            row = lineup(ri, mode)  # type: ignore[arg-type]
            stages: list[dict[str, Any]] = page.evaluate(f"window.ksvLearn.stages({ri}, 'rec')")
            for n, stage in enumerate(stages):
                for p, raw in stage["paths"].items():
                    path = [(q["x"], q["y"]) for q in raw]
                    deepest = max(1.0, path[0][1], path[-1][1])
                    out = [q for q in path[1:-1] if not 0 <= q[0] <= 1 or q[1] > deepest + 1e-9]
                    if out:
                        fail(f"{tag} stage {n + 1}: {p} detours off the court through {out}")
            kind = {p: k for p, _, _, k in row["ar"]}
            for p in (p for p in row["back"] if kind.get(p) == "back"):
                run = stages[1]["paths"].get(p)
                end = (run[-1]["x"], run[-1]["y"]) if run else None
                if p in stages[0]["moves"] or end is None or math.dist(end, DEEP_COVER["side"]) > 0.05:
                    fail(
                        f"{tag}: {p} runs {stages[0]['paths'].get(p)} then {run}, not straight to {DEEP_COVER['side']}"
                    )
            middle = next(p for p in row["front"] if p.startswith("MB"))
            captions = " ".join(page.evaluate("(a) => window.ksvLearn.captions(...a)", [ri, "rec", middle]))
            if "in front of the setter" in captions or "left of the setter" not in captions:
                fail(f"{tag}: {middle}'s quick caption does not say left of the setter: {captions!r}")
            hitter = min((s for s in row["ar"] if s[3] == "front"), key=lambda s: s[1])[0]
            approach = stages[2]["paths"].get(hitter)
            if not approach or approach[-1]["x"] - approach[0]["x"] < 0.05:
                fail(f"{tag}: the zone 4 hitter {hitter} approaches {approach}, not outside-in")
    print(
        "covers: detours inside the court, the back-row opposite straight to cover, the quick left of the setter, "
        "the zone 4 hitter outside-in"
    )


def check_ball_moving(page: Page) -> None:
    """The ball never waits in a player's hands, and long runs carry on into the next stage instead.

    Every rotation, both rule sets: the pass flies about 1 s and reaches the setter at the set spot, the next contact
    follows each ball's arrival within BALL_WAIT_MS, the hold comes only after the last stage, a run carried on starts
    the player's next move only when it ends and, into the pass, the set or the spike, never turns back into it, and
    L's run in stage 2 stays in front of y DEEP_LIMIT.
    """
    for mode, roles in MODES.items():
        open_app(page, "", {"role": roles[0], "rulesMode": mode})
        for ri in range(6):
            tag = f"{mode} R{ri + 1} Reception"
            stages: list[dict[str, Any]] = page.evaluate(f"window.ksvLearn.stages({ri}, 'rec')")
            total = page.evaluate(f"window.ksvLearn.track({ri}, 'rec', 1)")[-1]["t"]
            for k, (stage, after) in enumerate(zip(stages, stages[1:], strict=False)):
                wait = after["start"] - stage["start"] - stage["ball"]["ms"]
                if not 0 <= wait <= BALL_WAIT_MS:
                    fail(f"{tag}: after stage {k + 1} the ball waits {wait:.0f} ms for the next contact")
            last = stages[-1]
            if total - last["start"] - last["dur"] > 1000:
                fail(f"{tag}: the play holds {total - last['start'] - last['dur']:.0f} ms after the last stage")
            pass_ms = stages[1]["ball"]["ms"]
            if not 1000 <= pass_ms <= 1300:
                fail(f"{tag}: the pass flies {pass_ms:.0f} ms")
            ready = stages[0]["start"] + stages[0]["arrive"].get("S", 0)
            if ready > stages[1]["start"] + pass_ms + 1:
                fail(f"{tag}: the setter reaches the set spot at {ready:.0f} ms, after the pass")
            passer = next(p for p, note in stages[0]["notes"].items() if note.startswith("Their serve comes to you"))
            _, _, hitter = reception_plan(ri, mode)
            for k, who in enumerate((passer, "S", hitter)):
                stage = stages[k]
                pos = page.evaluate(
                    "(a) => window.ksvLearn.at(...a)", [ri, "rec", stage["start"] + stage["ball"]["ms"]]
                )
                off = math.dist((pos[who]["x"], pos[who]["y"]), (stage["ball"]["to"]["x"], stage["ball"]["to"]["y"]))
                if off > HELD + 0.01:
                    fail(f"{tag}: stage {k + 1}'s ball lands {off:.2f} from {who}")
            ends: dict[str, float] = {}
            runs: dict[str, list[tuple[float, float]]] = {}
            for n, stage in enumerate(stages):
                for p in stage["moves"]:
                    begin = stage["start"] + stage["delays"][p]
                    if begin < ends.get(p, 0) - 1:
                        fail(f"{tag} stage {n + 1}: {p} starts a move at {begin:.0f} ms, before the last ends")
                    path = [(q["x"], q["y"]) for q in stage["paths"][p]]
                    carried = n >= 1 and ends.get(p, 0) > stage["start"] + 1
                    joined = runs[p] + path[1:] if carried else path
                    if turns_back(joined):
                        fail(f"{tag} stage {n + 1}: {p}'s run turns back: {joined}")
                    ends[p] = stage["start"] + stage["arrive"][p]
                    runs[p] = path
            deepest = max((q["y"] for q in stages[1]["paths"].get("L", [])), default=0)
            if deepest > DEEP_LIMIT:
                fail(f"{tag} stage 2: L runs back to y {deepest:.2f}")


def check_caption_timing(page: Page) -> None:
    """While a play runs, your caption changes only for a new line of yours and stays CAPTION_MS of play.

    Every rotation, role and rule set, from the caption plan; then one Reception played at 1× on the page.
    """
    for mode, roles in MODES.items():
        open_app(page, "", {"role": roles[0], "rulesMode": mode})
        for ri in range(6):
            phase = "rec"
            total = page.evaluate(f"window.ksvLearn.track({ri}, '{phase}', 1)")[-1]["t"]
            stages = page.evaluate(f"window.ksvLearn.stages({ri}, '{phase}')")
            for role in roles:
                plan = page.evaluate("(a) => window.ksvLearn.captionPlan(...a)", [ri, phase, role])
                tag = f"{mode} R{ri + 1} {phase} {role}"
                times = [c["t"] for c in plan]
                if any(b - a < CAPTION_MS for a, b in zip(times, times[1:], strict=False)) or times[-1] >= total:
                    fail(f"{tag}: captions change at {times} (play {total:.0f} ms)")
                others = [c["text"] for c in plan[1:] if not c["text"].startswith(f"You ({role})")]
                if others and any(role in st["notes"] for st in stages):
                    fail(f"{tag}: the caption changes to someone else's line: {others}")
    open_app(page, "", {"role": "OH1", "rulesMode": "simple"})
    learn(page, 0, "rec")
    page.evaluate(
        """() => { window.capLog = [];
        new MutationObserver(() => { const a = window.ksvLearn.anim();
          if (a) window.capLog.push([a.t, document.querySelector('#lCap').innerText]); })
          .observe(document.querySelector('#lCap'), { childList: true, subtree: true, characterData: true }); }"""
    )
    page.click("#lPlay")
    wait_done(page)
    log = page.evaluate("window.capLog")
    times = [t for t, _ in log]
    if len(log) < 2 or any(b - a < CAPTION_MS - 50 for a, b in zip(times, times[1:], strict=False)):
        fail(f"R1 Reception played at 1×: the caption changes at {times}")


def check_rest_list(page: Page) -> None:
    """After the Reception play the rest caption keeps the reception cue and lists your lines under Then:."""
    for mode, role in (("simple", "OH1"), ("official", "MB2")):
        open_app(page, "", {"role": role, "rulesMode": mode})
        learn(page, 3, "rec")
        if page.locator("#lCap .then").count():
            fail(f"{mode}: the Then: list shows before the play")
        page.click("#lPlay")
        wait_done(page)
        still = page.evaluate(f"window.ksvLearn.still(3, 'rec', '{role}')")
        want = page.evaluate(f"window.ksvLearn.captions(3, 'rec', '{role}')")
        items = page.locator("#lCap .then li").all_inner_texts()
        if items != want or not page.inner_text("#lCap").startswith(still):
            fail(f"{mode}: after the play the caption is {page.inner_text('#lCap')!r}, expected {still!r} then {want}")
        page.click("#lNext")
        page.click('.ph[data-k="rec"]')
        if page.locator("#lCap .then").count():
            fail(f"{mode}: the Then: list stays after leaving the screen")


def check_path_shapes(page: Page) -> None:
    """No run turns back, and none is longer than 1.3 times the straight line."""
    for mode, roles in MODES.items():
        open_app(page, "", {"role": roles[0], "rulesMode": mode})
        for ri in range(6):
            phase = "rec"
            stages: list[dict[str, Any]] = page.evaluate(f"window.ksvLearn.stages({ri}, '{phase}')")
            for n, stage in enumerate(stages):
                for p, raw in stage["paths"].items():
                    path = [(q["x"], q["y"]) for q in raw]
                    legs = [(b[0] - a[0], b[1] - a[1]) for a, b in zip(path, path[1:], strict=False)]
                    if any(u[0] * v[0] + u[1] * v[1] < 0 for u, v in zip(legs, legs[1:], strict=False)):
                        fail(f"{mode} R{ri + 1} {phase} stage {n + 1}: {p} turns back on {path}")
                    straight = math.dist(path[0], path[-1])
                    length = sum(math.hypot(*leg) for leg in legs)
                    if straight and length > 1.3 * straight + 1e-3:
                        fail(f"{mode} R{ri + 1} {phase} stage {n + 1}: {p} runs {length:.2f} for {straight:.2f}")


def check_r1_sides(page: Page) -> None:
    """R1: OP plays left and OH1 right (the guide), with no side switch at Our serve, at Base or after the spike."""
    for mode, roles in MODES.items():
        open_app(page, "", {"role": roles[0], "rulesMode": mode})
        stage = page.evaluate("window.ksvLearn.stages(0, 'rec')")[-1]
        serve = {o["p"]: o["x"] for o in page.evaluate("window.ksvLearn.players(0, 'serve')")}
        for p, zone in (("OP", 4), ("OH1", 2)):
            path = stage["paths"].get(p) or [stage["from"][p], stage["to"][p]]
            left = path[0]["x"] < 0.5
            if left != (zone == 4) or any((q["x"] < 0.5) != left for q in path):
                fail(f"{mode} R1 after the spike: {p} runs {path[0]['x']:.2f} to {path[-1]['x']:.2f}")
            if "cross" in stage["notes"][p].lower() or f"zone {zone}" not in stage["notes"][p]:
                fail(f"{mode} R1 after the spike: {p} caption {stage['notes'][p]!r}")
            still = page.evaluate(f"window.ksvLearn.still(0, 'ar', '{p}')")
            if f"zone {zone}" not in still or "cross" in still.lower():
                fail(f"{mode} R1 Base: {p} caption {still!r}")
            if (serve[p] < 0.5) != (zone == 4):
                fail(f"{mode} R1 Our serve: {p} at x {serve[p]:.2f}, not in zone {zone}")


def check_cross_captions(page: Page) -> None:
    """After the spike, a run to base across the centre line by more than 0.3 is captioned as a cross; no other is."""
    for mode, roles in MODES.items():
        open_app(page, "", {"role": roles[0], "rulesMode": mode})
        crossed = 0
        for ri in range(6):
            stage = page.evaluate(f"window.ksvLearn.stages({ri}, 'rec')")[-1]
            for p in stage["moves"]:
                a, b = stage["from"][p]["x"], stage["to"][p]["x"]
                switch = (a - 0.5) * (b - 0.5) < 0 and abs(a - b) > 0.3
                crossed += switch
                still = page.evaluate(f"window.ksvLearn.still({ri}, 'ar', '{p}')")
                for tag, text in (("caption", stage["notes"][p]), ("Base still caption", still)):
                    if ("cross" in text.lower()) != switch or len(stage["notes"][p]) > 78:
                        fail(f"{mode} R{ri + 1} after the spike: {p} {a:.2f} to {b:.2f}, {tag} {text!r}")
        if not crossed:
            fail(f"{mode}: no run after the spike crosses the court")


def check_no_overlap(page: Page) -> None:
    """No marker passes through another at any moment, and no run is faster than TOP_SPEED.

    Every Reception play, rotation and rule set, sampled about every 10 ms; the ball may touch a marker.
    """
    for mode, roles in MODES.items():
        open_app(page, "", {"role": roles[0], "rulesMode": mode})
        for ri in range(6):
            phase = "rec"
            track: list[dict[str, Any]] = page.evaluate(f"window.ksvLearn.track({ri}, '{phase}', 1000)")
            seen: set[tuple[str, str]] = set()
            fast = max(
                (
                    math.dist((a["pos"][p]["x"], a["pos"][p]["y"]), (b["pos"][p]["x"], b["pos"][p]["y"]))
                    * 9000
                    / (b["t"] - a["t"]),
                    p,
                )
                for a, b in zip(track, track[1:], strict=False)
                for p in a["pos"]
            )
            if fast[0] > TOP_SPEED:
                fail(f"{mode} R{ri + 1} {phase}: {fast[1]} runs at {fast[0]:.1f} m/s")
            for now in track:
                pos = now["pos"]
                names = sorted(pos)
                for i, a in enumerate(names):
                    for b in names[i + 1 :]:
                        gap = math.dist((pos[a]["x"], pos[a]["y"]), (pos[b]["x"], pos[b]["y"]))
                        if gap < GAP - 2e-3 and (a, b) not in seen:
                            seen.add((a, b))
                            fail(f"{mode} R{ri + 1} {phase} t={now['t']:.0f}: {a} and {b} touch ({gap:.3f})")


def check_never_blocks(page: Page) -> None:
    """Next, the chips and the court answer at once while a phase plays; markers ignore taps."""
    open_app(page, "", {"role": "S", "rulesMode": "simple"})
    learn(page, 1, "rec")
    page.click("#lPlay")
    page.wait_for_timeout(300)
    hit = page.evaluate(
        "(() => { const g = document.querySelector('#courtL .am[data-p=\"S\"]').getBoundingClientRect();"
        " const el = document.elementFromPoint(g.x + g.width / 2, g.y + g.height / 2);"
        " return !!(el && el.closest('.am')); })()"
    )
    if hit:
        fail("a marker takes taps while a phase plays")
    page.click("#lNext")
    if page.inner_text("#learnTag") != "R2 (H6) · Base" or anim(page):
        fail(f"Next mid-play waits or plays: tag {page.inner_text('#learnTag')!r}, {anim(page)}")
    page.click('.rot[data-i="4"]')
    if page.inner_text("#learnTag") != "R5 (H3) · Base" or anim(page):
        fail(f"a rotation chip does not open that Base at rest: {anim(page)}")
    page.click('.ph[data-k="rec"]')
    if anim(page):
        fail("a chip to Reception plays")
    page.click("#lPlay")
    page.click("#tabSets")
    page.click("#tabLearn")
    if anim(page):
        fail("a tab change leaves the frame loop running")


def check_speed(page: Page) -> None:
    open_app(page, "", {"role": "L", "rulesMode": "simple"})
    page.click("#lSpeed")
    if page.inner_text("#lSpeed") != "0.5×" or page.evaluate("localStorage.getItem('ksv51:animSpeed')") != "0.5":
        fail(f"speed button: {page.inner_text('#lSpeed')!r}")
    page.reload()
    page.wait_for_function("document.readyState === 'complete'")
    if page.inner_text("#lSpeed") != "0.5×":
        fail("the speed is not kept across a reload")
    page.click("#lReplay")
    page.wait_for_timeout(1000)
    state = anim(page)
    if not state or not 300 <= state["t"] <= 700:
        fail(f"at 0.5× one second plays {state and state['t']} ms of the phase")


def check_still_captions(page: Page) -> None:
    """The exchanges and MB serving in Simplified R3 and R6 stay in the still captions."""
    open_app(page, "", {"role": "MB", "rulesMode": "simple"})
    for ri in (2, 5):
        tag = f"Simplified R{ri + 1}"
        still = page.evaluate(f"window.ksvLearn.still({ri}, 'start', 'MB')")
        if still != "You (MB): Rotate to zone 1 and serve: the libero may not serve, so you stay on.":
            fail(f"{tag} Rotation still caption for MB: {still!r}")
        still = page.evaluate(f"window.ksvLearn.still({ri}, 'start', 'L')")
        if still != "You (L): Go off: the other middle comes on in zone 4 and MB serves from zone 1.":
            fail(f"{tag} Rotation still caption for L: {still!r}")
        if page.evaluate(f"window.ksvLearn.still({ri}, 'serve', 'L')") != (
            "You (L): Wait at the sideline while MB serves: the libero may not serve."
        ):
            fail(f"{tag} Our serve still caption for L")
        learn(page, ri, "serve")
        check_positions(f"{tag} Our serve still picture", page.evaluate(MARKERS, "#courtL .mk"), spots(ri, "serve"))
        if page.evaluate(f"window.ksvLearn.still({ri}, 'rec', 'L')") != (
            "You (L): Come back on in zone 1 and take your reception spot."
        ):
            fail(f"{tag} Reception still caption for L")
        if page.evaluate(f"window.ksvLearn.still({ri}, 'rec', 'MB')") != (
            "You (MB): Training convention: we lost the serve, so go back to the net in zone 4."
        ):
            fail(f"{tag} Reception still caption for MB")
        if page.evaluate(f"window.ksvLearn.still({ri}, 'ar', 'L')") != (
            "You (L): Go to zone 5 and defend while they play the ball."
        ):
            fail(f"{tag} Base rest caption for L")
    learn(page, 1, "ar")
    page.click("#lNext")
    got = page.evaluate(MARKERS, "#courtL .mk")
    if "L" in got or got["MB"][0] < 67 or got["MB"][1] < 42 or got["OM"][0] > 34 or got["OM"][1] > 42:
        fail(f"R3 Rotation: MB at {got.get('MB')}, the other middle at {got.get('OM')}, L at {got.get('L')}")
    if "Rotate to zone 1 and serve" not in page.inner_text("#lCap"):
        fail(f"R3 Rotation caption: {page.inner_text('#lCap')!r}")
    if re.search(r"go to base|rally goes on", page.inner_text("#learn"), re.I):
        fail("a rotate or 'go to base' text shows")


def check_captions(page: Page) -> None:
    """Every stage and still caption is one line or two at 390 px, at most 90 characters, with no template leaks.

    The Rotation build's one line, shared by every stage, may run to WALK_MAX characters.
    """
    for mode, roles in MODES.items():
        open_app(page, "", {"role": roles[0], "rulesMode": mode})
        result: list[dict[str, Any]] = page.evaluate(
            """(roles) => { const cap = document.querySelector('#lCap'), out = [];
            const line = parseFloat(getComputedStyle(cap).lineHeight);
            for (const r of roles) for (let ri = 0; ri < 6; ri++) for (const ph of ['start','serve','rec','ar'])
              for (const [still, c] of [[true, window.ksvLearn.still(ri, ph, r)],
                  ...[...new Set(window.ksvLearn.captions(ri, ph, r))].map((c) => [false, c])]) {
                cap.textContent = c;
                out.push({ r, ri, ph, still, c, lines: cap.getBoundingClientRect().height / line });
              }
            return out; }""",
            roles,
        )
        seen: dict[tuple[str, int, str], list[str]] = {}
        for item in result:
            tag = f"{mode} {item['r']} R{item['ri'] + 1} {item['ph']}"
            if item["ph"] in ("serve", "rec", "ar") and item["still"] and not item["c"]:
                fail(f"{tag}: no still caption")
            if not item["still"]:
                same = seen.setdefault((item["r"], item["ri"], item["ph"]), [])
                if item["c"] in same:
                    fail(f"{tag}: the caption shows twice: {item['c']!r}")
                same.append(item["c"])
                if not item["c"]:
                    fail(f"{tag}: empty stage caption")
            longest = WALK_MAX if item["ph"] == "start" and not item["still"] else 90
            if len(item["c"]) > longest or re.search(r"undefined|NaN|null|\$\{", item["c"]):
                fail(f"{tag}: caption {item['c']!r} ({len(item['c'])} characters)")
            if item["lines"] > 2.05:
                fail(f"{tag}: caption takes {item['lines']:.1f} lines: {item['c']!r}")


FRAME = """() => { const at = (e, ...names) => names.map((n) => e.getAttribute(n)).join(' ');
  const ball = document.querySelector('#courtL .ball'), cap = document.querySelector('#lCap');
  return { t: window.ksvLearn.anim() && Math.round(window.ksvLearn.anim().t),
    marks: [...document.querySelectorAll('#courtL .am')].map((g) => g.dataset.p + at(g, 'transform')),
    ball: ball && at(ball, 'opacity', 'transform'),
    trails: [...document.querySelectorAll('#courtL .trail')].map((l) =>
      l.getAttribute('visibility') === 'visible' ? at(l, 'points', 'opacity') : 'hidden'),
    dots: document.querySelectorAll('#lDots i.on').length,
    cap: cap.innerHTML, capOpacity: cap.style.opacity }; }"""
GLYPHS = """() => {
  const size = (id) => {
    const range = document.createRange();
    range.selectNodeContents(document.getElementById(id));
    const box = range.getBoundingClientRect();
    return [box.width, box.height];
  };
  return {
    back: document.getElementById("lBack").textContent,
    step: document.getElementById("lStep").textContent,
    backSize: size("lBack"),
    stepSize: size("lStep"),
    sameSize: size("lBack").every((side, i) => Math.abs(side - size("lStep")[i]) <= 2),
  };
}"""
BAR = """() => { const bar = document.querySelector('#lAnim').getBoundingClientRect();
  const box = (e) => { const b = e.getBoundingClientRect();
    return [e.id, b.left - bar.left, b.top - bar.top, b.width, b.height].map((v) => v.toFixed ? Math.round(v) : v); };
  const buttons = [...document.querySelectorAll('#lAnim button')].map(box);
  return [Math.round(bar.width), Math.round(bar.height), ...buttons]; }"""


def check_step_back(page: Page) -> None:
    """Step back after Step returns to the same frame; it stops on the start picture and never plays."""
    for mode in MODES:
        for ri in (0, 3):
            open_app(page, "", {"role": "OH1", "rulesMode": mode})
            learn(page, ri, "rec")
            tag = f"{mode} R{ri + 1} Reception"
            bar = page.evaluate(BAR)
            if page.get_attribute("#lBack", "aria-label") != "Step back" or not page.is_disabled("#lBack"):
                fail(f"{tag}: Step back is not disabled on the start picture")
            glyphs = page.evaluate(GLYPHS)
            if glyphs["back"] != "|◂" or glyphs["step"] != "▸|" or not glyphs["sameSize"]:
                fail(f"{tag}: Step back does not mirror Step: {glyphs}")
            count = len(page.evaluate(f"window.ksvLearn.stages({ri}, 'rec')"))
            frames = []
            for _ in range(count):
                page.click("#lStep")
                wait_paused(page)
                frames.append(page.evaluate(FRAME))
                if page.is_disabled("#lBack"):
                    fail(f"{tag}: Step back is disabled at the end of stage {len(frames)}")
            for k in range(count - 2, -1, -1):
                page.click("#lBack")
                got = page.evaluate(FRAME)
                if got != frames[k]:
                    fail(f"{tag}: Step back to the end of stage {k + 1} shows {got}, expected {frames[k]}")
                page.click("#lStep")
                wait_paused(page)
                if page.evaluate(FRAME) != frames[k + 1]:
                    fail(f"{tag}: Step after Step back does not return to the end of stage {k + 2}")
                page.click("#lBack")
            page.click("#lBack")
            if anim(page):
                fail(f"{tag}: Step back from the first stage leaves a play: {anim(page)}")
            check_reception_rest(page, f"{tag} after Step back", ri, mode)
            if not page.is_disabled("#lBack"):
                fail(f"{tag}: Step back is enabled back on the start picture")
            page.click("#lStep")
            wait_paused(page)
            page.click("#lBack")
            page.click("#lPlay")
            state = anim(page)
            if not state or not state["playing"] or not page.is_disabled("#lBack"):
                fail(f"{tag}: Step back is not disabled while playing: {state}")
            if page.evaluate(BAR) != bar:
                fail(f"{tag}: the bar moves while playing: {page.evaluate(BAR)} vs {bar}")
            page.wait_for_function("window.ksvLearn.anim() && window.ksvLearn.anim().fading", timeout=20000)
            page.evaluate("document.querySelector('#lBack').click()")
            state = anim(page)
            if not state or state["fading"] or state["playing"] or page.evaluate(FRAME) != frames[-1]:
                fail(f"{tag}: Step back in the fade-back does not show the end of the last stage: {state}")
            page.click("#lBack")
            page.click("#lPlay")
            page.wait_for_timeout(200)
            state = anim(page)
            if not state or not state["playing"] or state["t"] < frames[-2]["t"]:
                fail(f"{tag}: Play after Step back does not go on from there: {state}")
            page.click("#lPlay")


PAUSE_WHEN = """([lo, hi]) => { const a = window.ksvLearn.anim();
  if (!a || !a.playing || a.t <= lo) return false;
  if (a.t >= hi) return 'late';
  document.querySelector('#lPlay').click(); return true; }"""
RESUME_OPACITY = """(button) => new Promise((done) => { const cap = document.querySelector('#lCap');
  const html = cap.innerHTML, end = performance.now() + 300; let low = 1;
  document.querySelector(button).click();
  const look = () => {
    if (cap.innerHTML === html) low = Math.min(low, cap.style.opacity === '' ? 1 : +cap.style.opacity);
    if (performance.now() < end) requestAnimationFrame(look); else done(low); };
  requestAnimationFrame(look); })"""


def pause_between(page: Page, tag: str, lo: float, hi: float) -> bool:
    """Plays Reception from its still and pauses once play time is between lo and hi."""
    page.click("#lPlay")
    if page.wait_for_function(PAUSE_WHEN, arg=[lo, hi], timeout=20000).json_value() == "late":
        fail(f"{tag}: the play passed {hi} ms before it could pause")
        return False
    return True


def check_step_back_paused(page: Page) -> None:
    """Step back from a pause mid-stage and in the end hold, disabled in a Step run, no caption fade on resume."""
    for mode in MODES:
        for ri in (0, 3):
            open_app(page, "", {"role": "OH1", "rulesMode": mode})
            learn(page, ri, "rec")
            tag = f"{mode} R{ri + 1} Reception"
            count = len(page.evaluate(f"window.ksvLearn.stages({ri}, 'rec')"))
            frames = []
            for k in range(count):
                if k:
                    low = page.evaluate(RESUME_OPACITY, "#lStep")
                    if low < 0.99:
                        fail(f"{tag}: the caption fades to {low} when Step resumes after stage {k}")
                else:
                    page.click("#lStep")
                state = anim(page)
                if not state or not state["playing"] or not page.is_disabled("#lBack"):
                    fail(f"{tag}: Step back is not disabled during a Step run: {state}")
                wait_paused(page)
                frames.append(page.evaluate(FRAME))
            ends = page.evaluate("window.ksvLearn.anim().ends")
            low = page.evaluate(RESUME_OPACITY, "#lPlay")
            if low < 0.99:
                fail(f"{tag}: the caption fades to {low} when Play resumes")
            for k in (0, 2):
                learn(page, ri, "rec")
                lo = (ends[k - 1] if k else 0) + 100
                if not pause_between(page, f"{tag} stage {k + 1}", lo, ends[k] - 50):
                    continue
                page.click("#lBack")
                if k == 0:
                    if anim(page):
                        fail(f"{tag}: Step back mid stage 1 leaves a play: {anim(page)}")
                    check_reception_rest(page, f"{tag} after Step back mid stage 1", ri, mode)
                elif page.evaluate(FRAME) != frames[k - 1]:
                    fail(f"{tag}: Step back mid stage {k + 1} does not show the end of stage {k}")
            learn(page, ri, "rec")
            if pause_between(page, f"{tag} hold", ends[-1] + 50, ends[-1] + 800):
                page.click("#lBack")
                if page.evaluate(FRAME) != frames[-2]:
                    fail(f"{tag}: Step back in the end hold does not show the end of stage {count - 1}")


def check_reduced(browser: Browser) -> None:
    """Reduced motion and ?anim=0: no glide, Reception lists its stages on the reception still, only Next in the row.

    Base shows base defence with the ball, no routes and one caption.
    """
    for label, query, motion in (("reduced motion", "", "reduce"), ("?anim=0", "?anim=0", None)):
        context = browser.new_context(viewport={"width": 390, "height": 844}, reduced_motion=motion)  # type: ignore[arg-type]
        page = context.new_page()
        open_app(page, query, {"role": "OH1", "rulesMode": "simple"})
        learn(page, 0, "start")
        line = walk_line(rotation_zones(0, "simple"))
        still = page.evaluate("window.ksvLearn.still(0, 'start', 'OH1')")
        want = "\n".join(t for t in (still, line) if t)
        if page.locator("#lCap ol").count() or page.inner_text("#lCap").strip() != want or page.is_visible("#lAnim"):
            fail(f"{label} Rotation: the caption is {page.inner_text('#lCap')!r}, expected {want!r} and no list")
        if label == "reduced motion":
            open_app(page, query, {"role": "OH1", "rulesMode": "official"})
            learn(page, 2, "start")
            cap = page.inner_text("#lCap")
            if WALK_LINE not in cap or cap.count("serves") != 1:
                fail(f"{label} official R3 Rotation: the caption is {cap!r}, expected the walk and one serving line")
            open_app(page, query, {"role": "OH1", "rulesMode": "simple"})
            learn(page, 0, "start")
        for phase in ("serve", "rec"):
            page.click("#lNext")
            if anim(page) or page.locator("#courtL .am").count():
                fail(f"{label} {phase}: Next plays a glide")
            if page.is_visible("#lAnim") or page.is_visible("#lDots") or not page.is_visible("#lNext"):
                fail(f"{label} {phase}: Replay/Pause/Step/speed and dots must be hidden, Next shown")
            count = 0 if phase == "serve" else 4
            if phase == "rec":
                check_reception_rest(page, f"{label} Reception")
            if page.locator("#lCap ol li").count() != count:
                fail(f"{label} {phase}: the caption lists {page.inner_text('#lCap')!r}, expected {count} stages")
        page.click("#lNext")
        if page.locator("#courtL .rt").count() or page.locator("#lCap ol").count():
            fail(f"{label}: Base draws routes or lists stages")
        check_positions(f"{label} Base", page.evaluate(MARKERS, "#courtL .mk"), reception_plan(0, "simple")[1])
        check_still_ball(page, f"{label} Base", "ar", page.evaluate(MARKERS, "#courtL .mk"))
        context.close()


LAYOUT = """() => {
  const box = (e) => e.getBoundingClientRect();
  const row = box(document.querySelector('#lCtl'));
  const hit = (b) => b.bottom > row.top + 0.5 && b.top < innerHeight;
  const marks = [...document.querySelectorAll('#courtL .am, #courtL .mk')]
    .filter((g) => +(g.getAttribute('opacity') ?? 1) > 0)
    .map((g) => [g.dataset.p, box(g)]);
  const court = box(document.querySelector('#courtL')), cap = box(document.querySelector('#lCap'));
  const panel = box(document.querySelector('#lPanel')), bar = box(document.querySelector('#lAnim'));
  const pill = box(document.querySelector('#courtL .offpill'));
  const inside = (b) => b.left >= panel.left - 0.5 && b.right <= panel.right + 0.5
    && b.top >= panel.top - 0.5 && b.bottom <= panel.bottom + 0.5;
  const apart = (a, b) => a.right <= b.left || b.right <= a.left || a.bottom <= b.top || b.bottom <= a.top;
  const buttons = [...document.querySelectorAll('#lAnim button')].map(box);
  const clip = (m) => ({ left: m.left, right: m.right, top: m.top, bottom: Math.min(m.bottom, court.bottom) });
  return { rowHeight: row.height, nextHeight: box(document.querySelector('#lNext')).height,
    capCovered: hit(cap), courtCovered: hit(court) || court.top < 0, barCovered: hit(bar),
    barInPanel: inside(bar) && buttons.every(inside), barOffCourt: bar.top >= court.bottom - 0.5,
    barClear: buttons.every((b) => apart(b, pill) && marks.every(([, m]) => apart(b, clip(m)))),
    marksCovered: marks.filter(([, b]) => hit(b) || b.top < 0).map(([p]) => p) };
}"""


REST_FIT = """() => {
  const row = document.querySelector('#lCtl').getBoundingClientRect();
  const range = document.createRange(); range.selectNodeContents(document.querySelector('#lCap'));
  range.setEndBefore(document.querySelector('#lCap .then'));
  const cap = range.getBoundingClientRect();
  const court = document.querySelector('#courtL').getBoundingClientRect();
  return { capCovered: cap.bottom > row.top + 0.5, courtTop: court.top };
}"""


def check_phone(browser: Browser) -> None:
    """While a phase plays, the controls sit in the court panel and the sticky row covers nothing."""
    for height in (750, 664):
        context = browser.new_context(viewport={"width": 390, "height": height}, is_mobile=True, has_touch=True)
        page = context.new_page()
        open_app(page, "", {"role": "S", "rulesMode": "simple"})
        learn(page, 0, "ar")
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        played = 0
        for step in range(4):
            label = page.inner_text("#lNext")
            page.click("#lNext")
            tag = f"390 × {height}, Next {label!r}"
            if page.is_visible("#lPlay"):
                page.click("#lPlay")
            sels = CONTROLS if anim(page) else ["#lNext"]
            for sel in sels:
                box = page.locator(sel).bounding_box()
                if not box or box["y"] < 0 or box["y"] + box["height"] > height + 1:
                    fail(f"{tag}: {sel} is outside the viewport: {box}")
                elif box["width"] < 44 or box["height"] < 44:
                    fail(f"{tag}: {sel} is {box['width']:.0f} × {box['height']:.0f}")
            for _ in range(6):
                if not anim(page):
                    break
                got = page.evaluate(LAYOUT)
                if got["rowHeight"] > 58 or got["nextHeight"] > 50:
                    fail(f"{tag}: row {got['rowHeight']:.0f} px, Next {got['nextHeight']:.0f} px high")
                if got["capCovered"] or got["marksCovered"] or got["barCovered"]:
                    fail(
                        f"{tag}: the row covers the caption {got['capCovered']}, the controls {got['barCovered']}"
                        f" or markers {got['marksCovered']}"
                    )
                if not (got["barInPanel"] and got["barOffCourt"] and got["barClear"]):
                    fail(f"{tag}: the controls are not in the court panel below the court, clear of markers: {got}")
                if height == 750 and got["courtCovered"]:
                    fail(f"{tag}: the court is not all in view above the row")
                played += 1
                page.wait_for_timeout(400)
            wait_done(page)
            if page.locator("#lCap .then").count():
                got = page.evaluate(REST_FIT)
                if got["capCovered"] or got["courtTop"] < -0.5:
                    fail(f"{tag}: after the play the rest caption or the court is out of view: {got}")
            if step == 1:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        if played < 2:
            fail(f"390 × {height}: Reception did not play")
        context.close()


def check_official(page: Page) -> None:
    """Official R3 and R6: the Rotation step shows the real lineup and the exchanges stay in the still captions."""
    for ri, (on, serves) in ((2, ("MB2", "MB1")), (5, ("MB1", "MB2"))):
        open_app(page, "", {"role": serves, "rulesMode": "official"})
        tag = f"Official R{ri + 1}"
        if page.evaluate(f"window.ksvLearn.stages({ri}, 'serve')"):
            fail(f"{tag} Our serve has animation stages")
        learn(page, ri, "start")
        got = page.evaluate(MARKERS, "#courtL .mk")
        if "L" in got or serves not in got or on not in got:
            fail(f"{tag} Rotation step shows {sorted(got)}: expected {serves} and {on} on, L off")
        checks = {
            (
                "start",
                "L",
            ): f"You (L): Go off at the sideline: {on} comes on in zone 4 and {serves} serves from zone 1.",
            ("start", on): f"You ({on}): Come on for the libero and take zone 4.",
            ("start", serves): f"You ({serves}): Rotate to zone 1 and serve: the libero may not serve, so you stay on.",
            ("start", "OP"): f"The libero leaves; {on} comes on in zone 4. {serves} is in zone 1 and serves.",
            ("rec", serves): f"You ({serves}): Go off at the sideline: we lost the serve, so the libero comes back.",
            ("rec", "L"): f"You (L): Come back on for {serves} and take your reception spot.",
            ("serve", "L"): f"You (L): Wait at the sideline while {serves} serves: the libero may not serve.",
        }
        for (phase, r), want in checks.items():
            still = page.evaluate(f"window.ksvLearn.still({ri}, '{phase}', '{r}')")
            if still != want:
                fail(f"{tag} {phase} still caption for {r}: {still!r}")


def check_passer(page: Page) -> None:
    """The serve goes to a guide rule 01 receiver, the passer changes across rotations and the caption names them."""
    for mode, roles in MODES.items():
        open_app(page, "", {"role": roles[0], "rulesMode": mode})
        passers = set()
        for ri in range(6):
            tag = f"{mode} R{ri + 1} Reception"
            stages: list[dict[str, Any]] = page.evaluate(f"window.ksvLearn.stages({ri}, 'rec')")
            told = [p for p, n in stages[0]["notes"].items() if "serve comes to you" in n]
            if len(told) != 1 or told[0] not in RECEIVERS:
                fail(f"{tag}: the serve comes to {told}, expected one of {RECEIVERS}")
                continue
            passer = told[0]
            passers.add(passer)
            setter = next(p for p in stages[1]["notes"] if p == "S")
            if passer not in stages[1]["notes"][setter]:
                fail(f"{tag}: the setter's pass caption does not name {passer}: {stages[1]['notes'][setter]!r}")
        if passers != set(RECEIVERS):
            fail(f"{mode}: the passers are {sorted(passers)}, expected all of {RECEIVERS}")


STILL_NAMES = {"serve": "Our serve", "ar": "Base"}


def check_opens_still(page: Page, tag: str, ri: int, phase: str, mode: str, *taps: str) -> None:
    """Taps each selector (or presses key:Name) and checks the static screen that opens: no play, nudge or controls."""
    name = STILL_NAMES[phase]
    nudges = int(page.evaluate("window.__nudges"))
    for tap in taps:
        if tap.startswith("key:"):
            page.keyboard.press(tap.removeprefix("key:"))
        else:
            page.click(tap)
    page.wait_for_timeout(100)
    if not re.fullmatch(rf"R{ri + 1} \(H\d\) · {name}", page.inner_text("#learnTag")):
        fail(f"{tag}: opens {page.inner_text('#learnTag')!r}")
    if int(page.evaluate("window.__nudges")) != nudges:
        fail(f"{tag}: Play gets a nudge")
    if anim(page) or page.locator("#courtL .am, #courtL .trail").count():
        fail(f"{tag}: {name} plays")
    if page.is_visible("#lAnim") or page.is_visible("#lDots") or page.is_visible("#lPlay"):
        fail(f"{tag}: {name} shows the animation controls")
    if not page.evaluate("document.querySelector('#lAnim').offsetHeight"):
        fail(f"{tag}: the hidden controls bar loses its height")
    got = page.evaluate(MARKERS, "#courtL .mk")
    check_positions(f"{tag} still", got, rest(page, ri, phase, mode))
    check_still_ball(page, f"{tag} still", phase, got)
    for sel in ("#lPlay", "#lReplay", "#lBack", "#lStep"):
        page.evaluate(f"document.querySelector('{sel}').click()")
        page.wait_for_timeout(50)
        if anim(page) or page.locator("#courtL .am").count():
            fail(f"{tag}: {sel} plays {name}")


def check_static_phases(page: Page) -> None:
    """Our serve and Base are static in every rotation and rule set: no controls, no nudge, and nothing plays.

    Opened by Next, a phase chip, a rotation chip, the arrow keys and the Learn tab; Play, Replay and Step
    pressed by script (they are hidden) do nothing. The hidden controls bar keeps its height.
    """
    for mode, roles in MODES.items():
        open_app(page, "", {"role": roles[0], "rulesMode": mode})
        learn(page, 5, "start")
        page.evaluate(NUDGES)
        for phase, name in STILL_NAMES.items():
            before = PHASES[PHASES.index(phase) - 1]
            for ri in range(6):
                tag = f"{mode} R{ri + 1} {name}"
                learn(page, ri, before)
                check_opens_still(page, f"{tag} by Next", ri, phase, mode, "#lNext")
                check_opens_still(page, f"{tag} by the arrow key", (ri + 1) % 6, phase, mode, "key:ArrowRight")
                check_opens_still(page, f"{tag} by a rotation chip", ri, phase, mode, f'.rot[data-i="{ri}"]')
                check_opens_still(page, f"{tag} by the Learn tab", ri, phase, mode, "#tabSets", "#tabLearn")
                page.click(f'.ph[data-k="{before}"]')
                check_opens_still(page, f"{tag} by a phase chip", ri, phase, mode, f'.ph[data-k="{phase}"]')
                if page.evaluate(f"window.ksvLearn.stages({ri}, '{phase}')"):
                    fail(f"{tag}: has animation stages")


def check_trails_in_play(page: Page) -> None:
    """While Reception plays, a trail shows through its stage and while its run carries on, then fades out."""
    open_app(page, "", {"role": "OH1", "rulesMode": "simple"})
    learn(page, 3, "start")
    page.click('.ph[data-k="rec"]')
    stages: list[dict[str, Any]] = page.evaluate("window.ksvLearn.stages(3, 'rec')")
    page.click("#lPlay")
    seen = set()
    for _ in range(80):
        state, shown = page.evaluate(
            """() => [window.ksvLearn.anim(), [...document.querySelectorAll('#courtL .trail')]
            .filter((l) => l.getAttribute('visibility') === 'visible' && +(l.getAttribute('opacity') ?? 1) > 0)
            .map((l) => [+l.dataset.stage, l.dataset.p])]"""
        )
        if not state:
            break
        old = []
        for k, p in shown:
            after = stages[k + 1]["start"] if k + 1 < len(stages) else math.inf
            if (
                k > state["stage"]
                or state["t"] > max(after, stages[k]["start"] + stages[k]["arrive"][p]) + TRAIL_FADE_MS
            ):
                old.append((k + 1, p))
        if old:
            fail(f"at {state['t']:.0f} ms (stage {state['stage'] + 1}) finished trails {sorted(set(old))} still show")
            break
        seen |= {k for k, _ in shown}
        page.wait_for_timeout(120)
    if len(seen) < 3:
        fail(f"trails showed only for stages {sorted(seen)}")


def check_fade_back(page: Page) -> None:
    """A Reception play that runs to its end fades out in about 400 ms and fades back to the reception still.

    Pause keeps its frame and does not fade back.
    """
    open_app(page, "", {"role": "OH1", "rulesMode": "simple"})
    learn(page, 2, "start")
    page.click('.ph[data-k="rec"]')
    page.click("#lPlay")
    page.wait_for_timeout(1500)
    page.click("#lPlay")
    held = anim(page)
    page.wait_for_timeout(1500)
    state = anim(page)
    if not held or not state or state["t"] != held["t"] or state["playing"] or state["fading"]:
        fail(f"Pause does not keep its frame: {held} then {state}")
    if not page.locator("#courtL .am").count() or page.locator("#courtL .bnd").count():
        fail("Pause leaves the play's frame")
    page.evaluate(
        """() => { window.fadeWatch = {};
        const w = window.fadeWatch;
        const tick = (now) => {
          const a = window.ksvLearn.anim();
          if (a && a.fading && w.fadeAt === undefined) { w.fadeAt = now; w.t = a.t; w.total = a.total; }
          if (!a && w.fadeAt !== undefined) { w.doneAt = now; return; }
          requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick); }"""
    )
    page.click("#lPlay")
    page.wait_for_function("window.fadeWatch.doneAt !== undefined", timeout=20000)
    watch = page.evaluate("window.fadeWatch")
    if watch["t"] != watch["total"]:
        fail(f"the fade-back starts before the play ends: {watch}")
    took = watch["doneAt"] - watch["fadeAt"]
    if not 200 <= took <= 3000:
        fail(f"the fade-back took {took:.0f} ms, expected about 400")
    check_reception_rest(page, "after the fade-back", 2)
    if page.is_visible("#lPlay") and page.get_attribute("#lPlay", "aria-label") != "Play":
        fail("after the fade-back Play does not read Play")


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        page = context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        check_opens_at_rest(page)
        check_rest_pictures(page)
        check_no_autoplay(page)
        check_static(page)
        check_rotation_build(page)
        check_build_off_court(page)
        check_reception_stages(page)
        check_reception_ends(page)
        check_quick_in_front(page)
        check_ball_moving(page)
        check_cover_runs(page)
        check_caption_timing(page)
        check_rest_list(page)
        check_path_shapes(page)
        check_r1_sides(page)
        check_cross_captions(page)
        check_no_overlap(page)
        check_passer(page)
        check_static_phases(page)
        check_trails_in_play(page)
        check_fade_back(page)
        check_never_blocks(page)
        check_speed(page)
        check_step_back(page)
        check_step_back_paused(page)
        check_still_captions(page)
        check_captions(page)
        check_reduced(browser)
        check_nudge(browser)
        check_nudge_colour_only(browser)
        check_phone(browser)
        check_official(page)
        for error in errors:
            fail(f"page error: {error}")
        browser.close()
    print(f"ANIM TEST: {len(FAIL)} failures")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
