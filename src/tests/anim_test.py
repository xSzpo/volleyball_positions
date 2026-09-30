"""Playwright test of the Learn animation (learn-animation).

Base opens at rest on where its play ends, Reception on the reception spots
with the overlap limits and no ball; each plays only on Play, and Play gives
one nudge per screen open. Rotation and Our serve are static with no controls,
no nudge and no play.
Reception plays their serve, the pass, the set, and our spike over the net with
everyone to base defence, then fades back to the reception spots; Pause and
Step keep their frame. Base plays from the spike to base defence and rests
there. Checks the stage end positions, the ball on the Our serve and Base
stills, the controls (Replay, Pause, Step, speed), that no route plays on open,
that Next and the chips never animate or wait, the still and lead-in captions
for exchanges and the middle pair reset, the caption length and
height, reduced motion and ?anim=0, the movement trails (through the stage and a
run carried on), that the ball never waits in a player's hands, L's run in
front of the deep outside hitter,
the passer, the setter's cover, the deep outside hitter, the top speed, no
marker passing through another, the controls in the court panel on a short
phone, and that the flag off leaves no trace.

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
from data import BASE_DEF, lineup  # noqa: E402

BASE = (ROOT / "index.html").as_uri()
FAIL: list[str] = []
MODES = {
    "simple": ["MB", "OH1", "OH2", "OP", "S", "L"],
    "official": ["MB1", "MB2", "OH1", "OH2", "OP", "S", "L"],
}
PHASES = ["start", "serve", "rec", "ar"]
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


def spike_end(page: Page, ri: int) -> dict[str, tuple[float, float]]:
    """Where the Reception play stands at our spike, before its last stage: where Base starts."""
    first: dict[str, dict[str, float]] = page.evaluate(f"window.ksvLearn.track({ri}, 'rec', 1)[0].pos")
    at = {p: (v["x"], v["y"]) for p, v in first.items()}
    for stage in page.evaluate(f"window.ksvLearn.stages({ri}, 'rec')")[:-1]:
        at.update({p: (v["x"], v["y"]) for p, v in stage["to"].items()})
    return at


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
    """Next into Reception and Base opens on its still; Play runs from the start of the play back to it."""
    open_app(page, "?ff=all", {"role": "OH1", "rulesMode": "simple"})
    learn(page, 0, "serve")
    for phase, label in (("rec", "Reception"), ("ar", "Base")):
        page.click("#lNext")
        if page.inner_text("#learnTag") != f"R1 (S1) · {label}":
            fail(f"the tag does not move with Next: {page.inner_text('#learnTag')!r}")
        page.wait_for_timeout(300)
        if anim(page) or page.locator("#courtL .am").count():
            fail(f"{label} plays when it opens: {anim(page)}")
        if not page.is_visible("#lAnim") or not page.is_visible("#lDots") or not page.is_enabled("#lPlay"):
            fail(f"{label}: the controls do not show at rest")
        end = rest(page, 0, phase)
        got = page.evaluate(MARKERS, "#courtL .mk")
        if sorted(got) != sorted(end):
            fail(f"{label}: the rest picture shows {sorted(got)}, expected {sorted(end)}")
        check_positions(f"{label} at rest", got, end)
        if phase == "rec":
            check_reception_rest(page, "Reception at rest")
            if not page.locator("#courtL .bnd").count():
                fail("Reception at rest: no overlap lines for OH1 in R1")
        if phase == "ar" and "Our attack is over the net: defend." not in page.inner_text("#cue"):
            fail(f"Base at rest: the cue does not say to defend: {page.inner_text('#cue')!r}")
        page.click("#lPlay")
        state = anim(page)
        if not state or not state["playing"]:
            fail(f"{label}: Play does not start the play: {state}")
            continue
        if not page.is_disabled("#lStep"):
            fail(f"{label}: Step is enabled while playing")
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
        first = spike_end(page, 0) if phase == "ar" else spots(0, phase)
        if start["t"] >= 700:
            fail(f"{label}: paused after the lead-in at {start['t']}")
        check_positions(f"{label} play start", start["pos"], first)
        if start["lines"]:
            fail(f"{label}: the overlap limits stay while the play runs")
        if start["ball"]:
            check_ball_clear(f"{label} lead-in", start["ball"], start["pos"])
        ball_from = {"rec": (THEIR_SERVE, 0.01)}.get(phase)
        if not start["ball"] or (
            ball_from and math.dist(start["ball"], [v * 100 for v in ball_from[0]]) > 100 * ball_from[1]
        ):
            fail(f"{label}: the lead-in ball is at {start['ball']}, expected near {ball_from}")
        page.click("#lPlay")
        wait_done(page)
        if page.locator("#courtL .am").count() or page.locator("#courtL .trail").count():
            fail(f"{label}: the animation markers or trails stay after the play")
        check_positions(f"{label} after the play", page.evaluate(MARKERS, "#courtL .mk"), end)
        check_still_ball(page, f"{label} after the play", phase, page.evaluate(MARKERS, "#courtL .mk"))
        if phase == "rec":
            check_reception_rest(page, "Reception after the play")
        if page.locator("#lDots i.on").count():
            fail(f"{label}: dots stay on at rest")
        page.click("#lReplay")
        if not (anim(page) or {}).get("playing"):
            fail(f"{label}: Replay does not play again")
        wait_done(page)
    if "You (OH1):" not in page.inner_text("#lCap"):
        fail(f"the caption does not start with your move: {page.inner_text('#lCap')!r}")


def check_rest_pictures(page: Page) -> None:
    """Every rotation and rule set: each screen opens on its still, and nothing plays.

    Our serve rests with everyone on base and the ball over the net, and has no play. Base rests where its play
    ends, on base defence by job, with the ball. Reception rests on the reception spots with the overlap limits and
    no ball; its play ends on base defence with the ball over the net.
    """
    for mode, roles in MODES.items():
        open_app(page, "?ff=all", {"role": roles[0], "rulesMode": mode})
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
                if phase == "serve":
                    if page.evaluate(f"window.ksvLearn.stages({ri}, 'serve')"):
                        fail(f"{tag}: Our serve has animation stages")
                    continue
                ends = play_end(page, ri, phase)
                if phase == "rec":
                    check_reception_rest(page, tag, ri, mode)
                    want = reception_plan(ri, mode)[1]
                    ball = page.evaluate(f"window.ksvLearn.stages({ri}, 'rec').pop().ball")
                    if not ball or not ball["to"]["y"] < 0:
                        fail(f"{tag}: the last stage does not play the ball over the net: {ball}")
                check_positions(f"{tag} play end", {p: [x * 100, y * 100] for p, (x, y) in ends.items()}, want)
            first: dict[str, Any] = page.evaluate(
                f"({{ ball: window.ksvLearn.stages({ri}, 'ar')[0].ball.from,"
                f" pos: window.ksvLearn.track({ri}, 'ar', 1)[0].pos }})"
            )
            check_ball_clear(
                f"{mode} R{ri + 1} Base lead-in",
                [first["ball"]["x"] * 100, first["ball"]["y"] * 100],
                {p: [v["x"] * 100, v["y"] * 100] for p, v in first["pos"].items()},
            )
            starts: dict[str, dict[str, float]] = page.evaluate(f"window.ksvLearn.track({ri}, 'ar', 1)[0].pos")
            check_positions(
                f"{mode} R{ri + 1} Base play start",
                {p: [v["x"] * 100, v["y"] * 100] for p, v in starts.items()},
                spike_end(page, ri),
            )


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
    """Play gets the nudge class once per open of Reception or Base, never on Our serve, a loop or while playing."""
    for label, query, motion in (
        ("motion", "?ff=all", None),
        ("reduced motion", "?ff=all", "reduce"),
        ("?anim=0", "?ff=all&anim=0", None),
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
        expect(4, "a chip to Base")
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
    open_app(page, "?ff=all", {"role": "OH1", "rulesMode": "simple"})
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
    open_app(page, "?ff=all", {"role": "OH1", "rulesMode": "simple"})
    if page.inner_text("#learnTag") != "R1 (S1) · Reception" or anim(page):
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
    if anim(page) or page.inner_text("#learnTag") != "R2 (S6) · Reception":
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
    """Rotation never plays and shows no controls; Next reads in full there. Next into Base does not play."""
    open_app(page, "?ff=all", {"role": "S", "rulesMode": "simple"})
    for ri, phase in ((0, "start"), (3, "start")):
        learn(page, ri, phase)
        if anim(page):
            fail(f"R{ri + 1} {phase}: a chip tap plays an animation")
        if page.is_visible("#lAnim") or page.is_visible("#lDots"):
            fail(f"R{ri + 1} {phase}: controls show")
        if not page.inner_text("#lNext").lower().startswith("next:"):
            fail(f"R{ri + 1} {phase}: Next reads {page.inner_text('#lNext')!r}")
        if page.locator("#courtL .am").count():
            fail(f"R{ri + 1} {phase}: animation markers on a static screen")
    learn(page, 0, "rec")
    page.click("#lNext")
    if anim(page) or page.inner_text("#learnTag") != "R1 (S1) · Base":
        fail("Next into Base animates or does not move the tag")
    check_positions("Base", page.evaluate(MARKERS, "#courtL .mk"), reception_plan(0, "simple")[1])
    if not page.inner_text("#lNext").lower().startswith("next:"):
        fail(f"Base: Next reads {page.inner_text('#lNext')!r}")
    page.click("#lNext")
    if anim(page) or page.inner_text("#learnTag") != "R2 (S6) · Rotation":
        fail("Next into the next Rotation animates")
    stages: list[dict[str, Any]] = page.evaluate("window.ksvLearn.stages(0, 'start')")
    if stages:
        fail(f"Rotation has animation stages: {stages}")


HIT_Y, APPROACH_Y, BACK_HIT_Y = 0.08, 0.17, 0.5
MARKER_R = 0.06
GAP = 0.14  # a marker width plus its ring
MIN_MOVE = 0.04
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
HELD = (MARKER_R * 100 + 1 + 0.65 * MARKER_R * 100) / 100


def base_zone(p: str, front: bool) -> int:
    """Base defence by job: OH 4, MB 3, S/OP 2 in the front row; S/OP 1, L 5, OH 6 in the back row."""
    job = p.rstrip("12")
    if front:
        return {"OH": 4, "MB": 3}.get(job, 2)
    return {"L": 5, "OH": 6, "S": 1, "OP": 1}.get(job, 6)


def reception_plan(ri: int, mode: str) -> tuple[list[str], dict[str, tuple[float, float]], str]:
    """Who leaves at the serve contact (setter and the attackers who do not receive), base defence, the hitter."""
    row = lineup(ri, mode)  # type: ignore[arg-type]
    ar = {p: (x, y) for p, x, y, _ in row["ar"]}
    rec = {p: (x, y) for p, x, y in row["rec"]}
    kind = {p: k for p, _, _, k in row["ar"]}
    order = list(rec)
    attackers = [p for p in order if kind[p] in ("front", "back")]
    hitter = min((p for p in attackers if kind[p] == "front"), key=lambda p: ar[p][0])
    release = [p for p in order if kind[p] == "set" or (p in attackers and p not in RECEIVERS)]
    release = [p for p in release if math.dist(rec[p], ar[p]) >= MIN_MOVE]
    end = {p: BASE_DEF[base_zone(p, p in row["front"])][:2] for p in order}
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


def check_reception_stages(page: Page) -> None:
    """Step runs one stage and pauses: serve and setter, pass and approach, set and cover, spike and defence.

    Step stays on the last stage; Play runs on and fades back to the reception spots. Base replays the last stage.
    """
    open_app(page, "?ff=all", {"role": "OH1", "rulesMode": "simple"})
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
            for p, spot in ar.items():
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
    page.click('.ph[data-k="ar"]')
    base: list[dict[str, Any]] = page.evaluate("window.ksvLearn.stages(0, 'ar')")
    if len(base) != 1 or not base[0]["ball"]:
        fail(f"Base plays {len(base)} stages, expected the spike with the ball")
    page.click("#lStep")
    wait_paused(page)
    check_positions("after the spike", page.evaluate(MARKERS, "#courtL .am"), end)
    captions: list[str] = page.evaluate("window.ksvLearn.captions(0, 'rec', 'L')")
    if (
        len(captions) != 4
        or captions[1] != "You (L): Pass the serve high to the setter at the net."
        or not captions[2].startswith("You (L): Cover")
        or captions[3] != "You (L): Go to zone 5 and defend while they play the ball."
    ):
        fail(f"Reception captions for L: {captions}")
    if page.evaluate("window.ksvLearn.captions(0, 'ar', 'L')") != [
        "You (L): Go to zone 5 and defend while they play the ball."
    ]:
        fail(f"Base captions for L: {page.evaluate("window.ksvLearn.captions(0, 'ar', 'L')")}")
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


def check_reception_ends(page: Page) -> None:
    """Every rotation, both rule sets: release at the serve, the set and cover, then the spike and base defence.

    The setter covers from within 0.2 of the set spot, the middle is at its quick take-off when the pass reaches
    the setter and then only drops back to cover close,
    L covers from the guide's zone 5 spot and the back-row outside hitter stays deep.
    """
    zones = {z: spot[:2] for z, spot in BASE_DEF.items()}
    for mode, roles in MODES.items():
        open_app(page, "?ff=all", {"role": roles[0], "rulesMode": mode})
        for ri in range(6):
            tag = f"{mode} R{ri + 1} Reception"
            row = lineup(ri, mode)  # type: ignore[arg-type]
            release, end, hitter = reception_plan(ri, mode)
            stages: list[dict[str, Any]] = page.evaluate(f"window.ksvLearn.stages({ri}, 'rec')")
            if len(stages) != 4 or sorted(stages[0]["moves"]) != sorted(release):
                fail(f"{tag}: stages move {[st['moves'] for st in stages]}, expected {release} at the serve contact")
                continue
            kind = {p: k for p, _, _, k in row["ar"]}
            # The setter may wait for an attacker who starts in front of the set spot to get out of the way.
            if any(stages[0]["delays"][p] > (1000 if kind[p] == "set" else 0) for p in release):
                fail(f"{tag}: someone waits after the serve contact: {stages[0]['delays']}")
            ar = {p: (x, y) for p, x, y, _ in row["ar"]}
            rec = {p: (x, y) for p, x, y in row["rec"]}
            track: list[dict[str, Any]] = page.evaluate(f"window.ksvLearn.track({ri}, 'rec', 600)")
            base: list[dict[str, Any]] = page.evaluate(f"window.ksvLearn.track({ri}, 'ar', 600)")
            s3 = stages[2]
            at_set = {p: s["pos"][p] for s in track if s["t"] <= s3["start"] + s3["dur"] for p in s["pos"]}
            at_set = {p: (v["x"], v["y"]) for p, v in at_set.items()}
            hit = at_set[hitter]
            if abs(hit[1] - HIT_Y) > 0.005:
                fail(f"{tag}: {hitter} hits at {hit}")
            setter = next(p for p in kind if kind[p] == "set")
            far = max(
                math.dist((s["pos"][setter]["x"], s["pos"][setter]["y"]), ar[setter])
                for s in track
                if s3["start"] <= s["t"] <= s3["start"] + s3["dur"]
            )
            if far > 0.2:
                fail(f"{tag}: the setter goes {far:.2f} from the set spot while covering")
            middle = next(p for p in s3["moves"] if p.startswith("MB"))
            if not 0.22 <= math.dist(at_set[middle], hit) <= 0.34:
                fail(f"{tag}: {middle} does not cover close to {hitter}: {at_set[middle]}")
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
            for p, spot in at_set.items():
                if p in (hitter, middle) or kind[p] not in ("front", "back"):
                    continue
                want = APPROACH_Y if kind[p] == "front" else BACK_HIT_Y
                if abs(spot[1] - want) > 0.005:
                    fail(f"{tag}: {p} does not finish the approach: {spot}")
            if math.dist(at_set["L"], ar["L"]) > 0.005:
                fail(f"{tag}: L covers from {at_set['L']}, not the guide's spot {ar['L']}")
            deep = next(p for p in row["back"] if p.startswith("OH"))
            lowest = min(s["pos"][deep]["y"] for s in track)
            if lowest < min(rec[deep][1], ar[deep][1]) - 0.005 or at_set[deep][1] < 0.85:
                fail(f"{tag}: the deep {deep} comes to y {lowest:.2f}, ends the cover at {at_set[deep]}")
            for play, ends in (("Reception", track), ("Base", base)):
                last = {p: (v["x"], v["y"]) for p, v in ends[-1]["pos"].items()}
                check_positions(f"{tag} {play} end", {p: [x * 100, y * 100] for p, (x, y) in last.items()}, end)
                held = sorted(z for z, spot in zones.items() for p in last if math.dist(last[p], spot) < 0.005)
                if held != [1, 2, 3, 4, 5, 6]:
                    fail(f"{tag} {play}: after the spike the defence holds zones {held}")
                if "S" in row["back"] and math.dist(last["S"], zones[1]) > 0.005:
                    fail(f"{tag} {play}: the back-row setter ends at {last['S']}, not zone 1")
            for play in ("rec", "ar"):
                final = page.evaluate(f"window.ksvLearn.stages({ri}, '{play}')")[-1]
                if not final["notes"].get(hitter, "").startswith("Spike over the net"):
                    fail(f"{tag} {play}: the last stage is not {hitter}'s spike: {final['notes'].get(hitter)!r}")
                if not final["ball"] or not final["ball"]["to"]["y"] < 0:
                    fail(f"{tag} {play}: the last stage does not play the ball over the net: {final['ball']}")


def check_ball_moving(page: Page) -> None:
    """The ball never waits in a player's hands, and long runs carry on into the next stage instead.

    Every rotation, both rule sets: the pass flies about 1 s and reaches the setter at the set spot, the next contact
    follows each ball's arrival within BALL_WAIT_MS, the hold comes only after the last stage, a run carried on starts
    the player's next move only when it ends, and L's run in stage 2 stays in front of y DEEP_LIMIT.
    """
    for mode, roles in MODES.items():
        open_app(page, "?ff=all", {"role": roles[0], "rulesMode": mode})
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
            for n, stage in enumerate(stages):
                for p in stage["moves"]:
                    begin = stage["start"] + stage["delays"][p]
                    if begin < ends.get(p, 0) - 1:
                        fail(f"{tag} stage {n + 1}: {p} starts a move at {begin:.0f} ms, before the last ends")
                    ends[p] = stage["start"] + stage["arrive"][p]
            deepest = max((q["y"] for q in stages[1]["paths"].get("L", [])), default=0)
            if deepest > DEEP_LIMIT:
                fail(f"{tag} stage 2: L runs back to y {deepest:.2f}")


def check_caption_timing(page: Page) -> None:
    """While a play runs, your caption changes only for a new line of yours and stays CAPTION_MS of play.

    Every rotation, role and rule set, from the caption plan; then one Reception played at 1× on the page.
    """
    for mode, roles in MODES.items():
        open_app(page, "?ff=all", {"role": roles[0], "rulesMode": mode})
        for ri in range(6):
            for phase in ("rec", "ar"):
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
    open_app(page, "?ff=all", {"role": "OH1", "rulesMode": "simple"})
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
        open_app(page, "?ff=all", {"role": role, "rulesMode": mode})
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
    """No run turns back, and none is longer than 1.3 times the straight line.

    A front-row side switch behind the middle may be longer.
    """
    for mode, roles in MODES.items():
        open_app(page, "?ff=all", {"role": roles[0], "rulesMode": mode})
        for ri in range(6):
            for phase in ("rec", "ar"):
                stages: list[dict[str, Any]] = page.evaluate(f"window.ksvLearn.stages({ri}, '{phase}')")
                for n, stage in enumerate(stages):
                    for p, raw in stage["paths"].items():
                        path = [(q["x"], q["y"]) for q in raw]
                        legs = [(b[0] - a[0], b[1] - a[1]) for a, b in zip(path, path[1:], strict=False)]
                        if any(u[0] * v[0] + u[1] * v[1] < 0 for u, v in zip(legs, legs[1:], strict=False)):
                            fail(f"{mode} R{ri + 1} {phase} stage {n + 1}: {p} turns back on {path}")
                        straight = math.dist(path[0], path[-1])
                        length = sum(math.hypot(*leg) for leg in legs)
                        to_base = phase == "ar" or (phase == "rec" and n == len(stages) - 1)
                        switch = (path[0][0] - 0.5) * (path[-1][0] - 0.5) < 0 and len(path) == 3 and to_base
                        limit = 1.4 if switch else 1.3
                        if straight and length > limit * straight + 1e-3:
                            fail(f"{mode} R{ri + 1} {phase} stage {n + 1}: {p} runs {length:.2f} for {straight:.2f}")


def check_switch_behind(page: Page) -> None:
    """After the spike (Reception and Base), a front-row player who switches sides crosses GAP behind the middle."""
    for mode, roles in MODES.items():
        open_app(page, "?ff=all", {"role": roles[0], "rulesMode": mode})
        for ri in range(6):
            row = lineup(ri, mode)  # type: ignore[arg-type]
            middle = next(p for p in row["front"] if p.startswith("MB"))
            for phase in ("rec", "ar"):
                stage = page.evaluate(f"window.ksvLearn.stages({ri}, '{phase}')")[-1]
                mid = stage["to"].get(middle) or stage["from"][middle]
                for p, raw in stage["paths"].items():
                    path = [(q["x"] - mid["x"], q["y"]) for q in raw]
                    if p not in row["front"] or abs(path[0][0]) < 0.2 or path[0][0] * path[-1][0] >= 0:
                        continue
                    a, b = next((a, b) for a, b in zip(path, path[1:], strict=False) if a[0] * b[0] <= 0)
                    y = a[1] - (b[1] - a[1]) * a[0] / ((b[0] - a[0]) or 1)
                    if y < mid["y"] + GAP:
                        fail(f"{mode} R{ri + 1} {phase} after the spike: {p} crosses the middle at y {y:.2f}")


def check_no_overlap(page: Page) -> None:
    """No marker passes through another at any moment, and no run is faster than TOP_SPEED.

    Every animated phase, rotation and rule set, sampled about every 10 ms; the ball may touch a marker.
    """
    for mode, roles in MODES.items():
        open_app(page, "?ff=all", {"role": roles[0], "rulesMode": mode})
        for ri in range(6):
            for phase in ("rec", "ar"):
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
    open_app(page, "?ff=all", {"role": "S", "rulesMode": "simple"})
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
    if page.inner_text("#learnTag") != "R2 (S6) · Base" or anim(page):
        fail(f"Next mid-play waits or plays: tag {page.inner_text('#learnTag')!r}, {anim(page)}")
    page.click("#lPlay")
    page.click('.rot[data-i="4"]')
    if page.inner_text("#learnTag") != "R5 (S3) · Base" or anim(page):
        fail(f"a rotation chip mid-play does not open that Base at rest: {anim(page)}")
    page.click('.ph[data-k="rec"]')
    if anim(page):
        fail("a chip to Reception plays")
    page.click("#lPlay")
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
    page.click("#lReplay")
    page.wait_for_timeout(1000)
    state = anim(page)
    if not state or not 300 <= state["t"] <= 700:
        fail(f"at 0.5× one second plays {state and state['t']} ms of the phase")


def check_still_captions(page: Page) -> None:
    """The exchanges and the middle pair reset that no longer animate stay in the still captions."""
    open_app(page, "?ff=all", {"role": "MB", "rulesMode": "simple"})
    for ri in (2, 5):
        tag = f"Simplified R{ri + 1}"
        still = page.evaluate(f"window.ksvLearn.still({ri}, 'start', 'MB')")
        if still != "You (MB): Walk along the net from zone 2 to zone 4: the middle pair resets.":
            fail(f"{tag} Rotation still caption for MB: {still!r}")
        if page.evaluate(f"window.ksvLearn.still({ri}, 'serve', 'L')") != (
            "You (L): Go off at the sideline: the libero may not serve."
        ):
            fail(f"{tag} Our serve still caption for L")
        if page.evaluate(f"window.ksvLearn.still({ri}, 'serve', 'SUB')") != (
            "You (SUB): Come on for the libero: you serve from the spot behind the end line."
        ):
            fail(f"{tag} Our serve still caption for SUB")
        learn(page, ri, "serve")
        check_positions(f"{tag} Our serve still picture", page.evaluate(MARKERS, "#courtL .mk"), spots(ri, "serve"))
        for api in ("lead", "still"):
            if page.evaluate(f"window.ksvLearn.{api}({ri}, 'rec', 'L')") != (
                "You (L): Come back on for SUB and take your reception spot."
            ):
                fail(f"{tag} Reception {api} caption for L")
        if page.evaluate(f"window.ksvLearn.still({ri}, 'ar', 'L')") != (
            "You (L): Go to zone 5 and defend while they play the ball."
        ):
            fail(f"{tag} Base rest caption for L")
    learn(page, 1, "ar")
    page.click("#lNext")
    got = page.evaluate(MARKERS, "#courtL .mk")
    if not close(got["MB"], (0.17, 0.21)) or not close(got["L"], (0.83, 0.71)):
        fail(f"R3 Rotation: MB at {got.get('MB')}, L at {got.get('L')}")
    if "middle pair resets" not in page.inner_text("#lCap"):
        fail(f"R3 Rotation caption: {page.inner_text('#lCap')!r}")
    if re.search(r"go to base|rally goes on", page.inner_text("#learn"), re.I):
        fail("a rotate or 'go to base' text shows")


def check_captions(page: Page) -> None:
    """Every stage and still caption is one line or two at 390 px, at most 90 characters, with no template leaks."""
    for mode, roles in MODES.items():
        open_app(page, "?ff=all", {"role": roles[0], "rulesMode": mode})
        result: list[dict[str, Any]] = page.evaluate(
            """(roles) => { const cap = document.querySelector('#lCap'), out = [];
            const line = parseFloat(getComputedStyle(cap).lineHeight);
            for (const r of roles) for (let ri = 0; ri < 6; ri++) for (const ph of ['start','serve','rec','ar'])
              for (const [still, c] of [[true, window.ksvLearn.still(ri, ph, r)],
                  [true, window.ksvLearn.lead(ri, ph, r)],
                  ...window.ksvLearn.captions(ri, ph, r).map((c) => [false, c])]) {
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
            if len(item["c"]) > 90 or re.search(r"undefined|NaN|null|\$\{", item["c"]):
                fail(f"{tag}: caption {item['c']!r} ({len(item['c'])} characters)")
            if item["lines"] > 2.05:
                fail(f"{tag}: caption takes {item['lines']:.1f} lines: {item['c']!r}")


def check_reduced(browser: Browser) -> None:
    """Reduced motion and ?anim=0: no glide, Reception lists its stages on the reception still, only Next in the row.

    Base shows base defence with the ball, no routes and one caption.
    """
    for label, query, motion in (("reduced motion", "?ff=all", "reduce"), ("?anim=0", "?ff=all&anim=0", None)):
        context = browser.new_context(viewport={"width": 390, "height": 844}, reduced_motion=motion)  # type: ignore[arg-type]
        page = context.new_page()
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
        open_app(page, "?ff=all", {"role": "S", "rulesMode": "simple"})
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
            fail(f"390 × {height}: Reception and Base did not play")
        context.close()


def check_official(page: Page) -> None:
    """Official R3 and R6: the Rotation step shows the real lineup and the exchanges stay in the still captions."""
    for ri, (on, serves) in ((2, ("MB2", "MB1")), (5, ("MB1", "MB2"))):
        open_app(page, "?ff=all", {"role": serves, "rulesMode": "official"})
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
            api = "lead" if phase == "rec" else "still"
            still = page.evaluate(f"window.ksvLearn.{api}({ri}, '{phase}', '{r}')")
            if still != want:
                fail(f"{tag} {phase} still caption for {r}: {still!r}")


def check_passer(page: Page) -> None:
    """The serve goes to a guide rule 01 receiver, the passer changes across rotations and the caption names them."""
    for mode, roles in MODES.items():
        open_app(page, "?ff=all", {"role": roles[0], "rulesMode": mode})
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


def check_serve_static(page: Page) -> None:
    """Our serve is static in every rotation and rule set: no controls, no nudge, and nothing plays.

    Opened by Next, a phase chip, a rotation chip, the arrow keys and the Learn tab; Play, Replay and Step
    pressed by script (they are hidden) do nothing. The hidden controls bar keeps its height.
    """
    for mode, roles in MODES.items():
        open_app(page, "?ff=all", {"role": roles[0], "rulesMode": mode})
        learn(page, 5, "start")
        page.evaluate(NUDGES)

        def still(tag: str, ri: int, mode: str = mode) -> None:
            page.wait_for_timeout(100)
            if not re.fullmatch(rf"R{ri + 1} \(S\d\) · Our serve", page.inner_text("#learnTag")):
                fail(f"{tag}: opens {page.inner_text('#learnTag')!r}")
            if anim(page) or page.locator("#courtL .am, #courtL .trail").count():
                fail(f"{tag}: Our serve plays")
            if page.is_visible("#lAnim") or page.is_visible("#lDots") or page.is_visible("#lPlay"):
                fail(f"{tag}: Our serve shows the animation controls")
            if not page.evaluate("document.querySelector('#lAnim').offsetHeight"):
                fail(f"{tag}: the hidden controls bar loses its height")
            check_positions(f"{tag} still", page.evaluate(MARKERS, "#courtL .mk"), spots(ri, "serve", mode))
            for sel in ("#lPlay", "#lReplay", "#lStep"):
                page.evaluate(f"document.querySelector('{sel}').click()")
                page.wait_for_timeout(50)
                if anim(page) or page.locator("#courtL .am").count():
                    fail(f"{tag}: {sel} plays Our serve")

        for ri in range(6):
            tag = f"{mode} R{ri + 1} Our serve"
            learn(page, ri, "start")
            page.click("#lNext")
            still(f"{tag} by Next", ri)
            page.keyboard.press("ArrowRight")
            still(f"{tag} by the arrow key", (ri + 1) % 6)
            page.click(f'.rot[data-i="{ri}"]')
            still(f"{tag} by a rotation chip", ri)
            page.click("#tabSets")
            page.click("#tabLearn")
            still(f"{tag} by the Learn tab", ri)
            page.click('.ph[data-k="rec"]')
            page.click('.ph[data-k="serve"]')
            still(f"{tag} by a phase chip", ri)
            if page.evaluate(f"window.ksvLearn.stages({ri}, 'serve')"):
                fail(f"{tag}: has animation stages")
        nudges = int(page.evaluate("window.__nudges"))
        if nudges != 6:
            fail(f"{mode}: {nudges} nudges, expected 6 (one per Reception chip, none on Our serve)")


def check_trails_in_play(page: Page) -> None:
    """While Reception plays, a trail shows through its stage and while its run carries on, then fades out."""
    open_app(page, "?ff=all", {"role": "OH1", "rulesMode": "simple"})
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
    open_app(page, "?ff=all", {"role": "OH1", "rulesMode": "simple"})
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
        check_opens_at_rest(page)
        check_rest_pictures(page)
        check_no_autoplay(page)
        check_static(page)
        check_reception_stages(page)
        check_reception_ends(page)
        check_ball_moving(page)
        check_caption_timing(page)
        check_rest_list(page)
        check_path_shapes(page)
        check_switch_behind(page)
        check_no_overlap(page)
        check_passer(page)
        check_serve_static(page)
        check_trails_in_play(page)
        check_fade_back(page)
        check_never_blocks(page)
        check_speed(page)
        check_still_captions(page)
        check_captions(page)
        check_flag_off(page)
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
