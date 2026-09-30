"""Playwright test of the Learn animation (learn-animation).

Our serve and Reception play once when the screen opens and end on their still
picture; Rotation and After reception are static with no controls. Checks the
stage end positions, the controls (Replay, Pause, Step, speed), that Next and
the chips never animate or wait, the still captions for exchanges and the
middle pair reset, the caption length and height, reduced motion and ?anim=0,
Reception through the set and spike to the after-reception spots, the movement
trails, the controls in the court panel on a short phone, and that the flag off
leaves no trace.

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
from data import BASE_DEF, lineup, server  # noqa: E402

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


SERVE_SPOT = (0.88, 1.1)


def spots(ri: int, phase: str, mode: str = "simple") -> dict[str, tuple[float, float]]:
    """The Learn still picture from the data; at Our serve the server stands on the serve spot."""
    row = lineup(ri, mode)  # type: ignore[arg-type]
    if phase == "serve":
        front, back = row["serve"]
        base = {p: BASE_DEF[z][:2] for z, p in zip((4, 3, 2, 5, 6, 1), front + back, strict=True)}
        return {**base, server(ri, mode): SERVE_SPOT}  # type: ignore[arg-type]
    if phase == "rec":
        return {p: (x, y) for p, x, y in row["rec"]}
    return {p: (x, y) for p, x, y, _ in row["ar"]}


def wait_done(page: Page) -> None:
    page.wait_for_function("!window.ksvLearn.anim()", timeout=15000)


def check_opens_and_returns(page: Page) -> None:
    """Next into Our serve and Reception plays once and ends on the still picture; Replay plays again."""
    open_app(page, "?ff=all", {"role": "OH1", "rulesMode": "simple"})
    learn(page, 0, "start")
    wait_done(page)
    for phase, label in (("serve", "Our serve"), ("rec", "Reception")):
        page.click("#lNext")
        if page.inner_text("#learnTag") != f"R1 (S1) · {label}":
            fail(f"the tag does not move with Next: {page.inner_text('#learnTag')!r}")
        state = anim(page)
        if not state or not state["playing"] or state["t"] > 400:
            fail(f"{label} does not play when it opens: {state}")
            continue
        if not page.is_visible("#lAnim") or not page.is_visible("#lDots"):
            fail(f"{label}: the controls do not show")
        if not page.is_disabled("#lStep"):
            fail(f"{label}: Step is enabled while playing")
        still = spots(0, phase)
        if sorted(page.evaluate(MARKERS, "#courtL .am")) != sorted(still):
            fail(f"{label}: the animation has other players than the still picture")
        wait_done(page)
        if page.locator("#courtL .am").count() or page.locator("#courtL .trail").count():
            fail(f"{label}: the animation markers or trails stay after the play")
        end = page.evaluate(MARKERS, "#courtL .mk")
        if sorted(end) != sorted(still):
            fail(f"{label}: the end picture shows {sorted(end)}, expected {sorted(still)}")
        check_positions(f"{label} end", end, still)
        if page.locator("#lDots i.on").count():
            fail(f"{label}: dots stay on at rest")
        page.click("#lReplay")
        if not (anim(page) or {}).get("playing"):
            fail(f"{label}: Replay does not play again")
        wait_done(page)
        page.click("#lPlay")
        if not (anim(page) or {}).get("playing"):
            fail(f"{label}: Play at rest does not play")
        wait_done(page)
    if "You (OH1):" not in page.inner_text("#lCap"):
        fail(f"the caption does not start with your move: {page.inner_text('#lCap')!r}")


def check_no_autoplay(page: Page) -> None:
    """Loading onto Reception, a reload, a role change and a rules change show the still picture only."""
    open_app(page, "?ff=all", {"role": "OH1", "rulesMode": "simple"})
    if page.inner_text("#learnTag") != "R1 (S1) · Reception" or anim(page):
        fail(f"a fresh load onto {page.inner_text('#learnTag')!r} plays: {anim(page)}")
    page.reload()
    page.wait_for_function("document.readyState === 'complete' && !!document.querySelector('#lNext')")
    if anim(page):
        fail("a reload plays Reception")
    page.click('.ph[data-k="serve"]')
    wait_done(page)
    page.click("#roleChip")
    page.click('#roles .role[data-r="L"]')
    if page.is_visible("#setupPanel"):
        page.click("#setupDone")
    if page.inner_text("#roleChip").strip() != "L" or anim(page):
        fail(f"a role change plays Our serve or does not apply: {page.inner_text('#roleChip')!r}")
    page.click("#roleChip")
    page.click('.rulesmode [data-rm="official"]')
    if page.is_visible("#setupPanel"):
        page.click("#setupDone")
    if page.get_attribute('.rulesmode [aria-checked="true"]', "data-rm") != "official" or anim(page):
        fail("a rules change plays Our serve or does not apply")
    check_positions(
        "Our serve after the rules change", page.evaluate(MARKERS, "#courtL .mk"), spots(0, "serve", "official")
    )


def check_static(page: Page) -> None:
    """Rotation and After reception never play and show no controls; Next reads in full there."""
    open_app(page, "?ff=all", {"role": "S", "rulesMode": "simple"})
    for ri, phase in ((0, "start"), (0, "ar"), (3, "start"), (3, "ar")):
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
    wait_done(page)
    page.click("#lNext")
    if anim(page) or page.inner_text("#learnTag") != "R1 (S1) · After reception":
        fail("Next into After reception animates or does not move the tag")
    check_positions("After reception", page.evaluate(MARKERS, "#courtL .mk"), spots(0, "ar"))
    page.click("#lNext")
    if anim(page) or page.inner_text("#learnTag") != "R2 (S6) · Rotation":
        fail("Next into the next Rotation animates")
    for key in ("start", "ar"):
        stages: list[dict[str, Any]] = page.evaluate(f"window.ksvLearn.stages(0, '{key}')")
        if stages:
            fail(f"{key} has animation stages: {stages}")


HIT_Y, APPROACH_Y, BACK_HIT_Y = 0.08, 0.17, 0.5
MARKER_R = 0.06
TRAILS = """() => [...document.querySelectorAll('#courtL .trail')]
  .filter((l) => l.getAttribute('visibility') === 'visible').map((l) => l.dataset.p)"""
TRAIL_LENGTHS = """() => Object.fromEntries([...document.querySelectorAll('#courtL .trail')]
  .filter((l) => l.getAttribute('visibility') === 'visible')
  .map((l) => [l.dataset.p, Math.hypot(l.getAttribute('x2') - l.getAttribute('x1'),
    l.getAttribute('y2') - l.getAttribute('y1'))]))"""


def base_zone(p: str, front: bool) -> int:
    """Base defence by job: OH 4, MB 3, S/OP 2 in the front row; S/OP 1, L 5, OH 6 in the back row."""
    job = p.rstrip("12")
    if front:
        return {"OH": 4, "MB": 3}.get(job, 2)
    return {"L": 5, "OH": 6, "S": 1, "OP": 1}.get(job, 6)


def reception_plan(ri: int, mode: str) -> tuple[list[list[str]], dict[str, tuple[float, float]], str]:
    """The movers per Reception stage, the base defence end positions and the zone 4 hitter."""
    row = lineup(ri, mode)  # type: ignore[arg-type]
    ar = {p: (x, y) for p, x, y, _ in row["ar"]}
    kind = {p: k for p, _, _, k in row["ar"]}
    order = [p for p, _, _ in row["rec"]]
    attackers = [p for p in order if kind[p] in ("front", "back")]
    hitter = min((p for p in attackers if kind[p] == "front"), key=lambda p: ar[p][0])
    moves = [[p for p in order if kind[p] == "set"], attackers, order, order]
    end = {p: BASE_DEF[base_zone(p, p in row["front"])][:2] for p in order}
    return moves, end, hitter


def trail_movers(stage: dict[str, Any]) -> list[str]:
    """The players who move far enough in a stage to leave a trail."""
    return [
        p
        for p in stage["moves"]
        if abs(stage["to"][p]["x"] - stage["from"][p]["x"]) + abs(stage["to"][p]["y"] - stage["from"][p]["y"]) >= 0.01
    ]


def check_reception_stages(page: Page) -> None:
    """Step runs one stage and pauses: serve and setter, pass and approach, set and cover, spike and defence."""
    open_app(page, "?ff=all", {"role": "OH1", "rulesMode": "simple"})
    learn(page, 0, "start")
    page.click('.ph[data-k="rec"]')
    wait_done(page)
    rec = spots(0, "rec")
    ar = spots(0, "ar")
    moves, end, hitter = reception_plan(0, "simple")
    stages: list[dict[str, Any]] = page.evaluate("window.ksvLearn.stages(0, 'rec')")
    if [sorted(st["moves"]) for st in stages] != [sorted(m) for m in moves]:
        fail(f"Reception stages move {[st['moves'] for st in stages]}, expected {moves}")
    if not all(st["ball"] for st in stages):
        fail("a Reception stage has no ball")
    after_pass = {p: ar[p] if p in moves[0] + moves[1] else rec[p] for p in rec}
    trails: list[str] = []
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
            check_positions("after the pass", got, after_pass)
        if stage == 3:
            check_positions("after the spike", got, end)
        trails += trail_movers(stages[stage])
        if sorted(page.evaluate(TRAILS)) != sorted(trails):
            fail(f"after Step {stage + 1}: trails {sorted(page.evaluate(TRAILS))}, expected {sorted(trails)}")
    page.click("#lReplay")
    if not (anim(page) or {}).get("playing"):
        page.click("#lPlay")
    ends = (anim(page) or {}).get("ends", [0, 0, 0, 0])
    page.wait_for_function(f"(window.ksvLearn.anim() || {{t: 1e9}}).t > {(ends[1] + ends[2]) / 2}", timeout=15000)
    mid = page.evaluate(TRAIL_LENGTHS)
    if not set(trail_movers(stages[0]) + trail_movers(stages[1])) <= set(mid) or not all(v > 1 for v in mid.values()):
        fail(f"mid stage 3: trails {mid}, expected at least the setter and the attackers")
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
    check_positions("back on the still picture", page.evaluate(MARKERS, "#courtL .mk"), rec)
    captions: list[str] = page.evaluate("window.ksvLearn.captions(0, 'rec', 'L')")
    if captions[1] != "You (L): Pass the serve high to the setter at the net." or captions[-1] != (
        "You (L): Go to zone 5 and defend while they play the ball."
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


def check_reception_ends(page: Page) -> None:
    """Every rotation, both rule sets: set and 3-2 cup, then the spike and base defence in every zone."""
    zones = {z: spot[:2] for z, spot in BASE_DEF.items()}
    for mode, roles in MODES.items():
        open_app(page, "?ff=all", {"role": roles[0], "rulesMode": mode})
        for ri in range(6):
            tag = f"{mode} R{ri + 1} Reception"
            row = lineup(ri, mode)  # type: ignore[arg-type]
            moves, end, hitter = reception_plan(ri, mode)
            stages: list[dict[str, Any]] = page.evaluate(f"window.ksvLearn.stages({ri}, 'rec')")
            if [sorted(st["moves"]) for st in stages] != [sorted(m) for m in moves]:
                fail(f"{tag}: stages move {[st['moves'] for st in stages]}, expected {moves}")
                continue
            kind = {p: k for p, _, _, k in row["ar"]}
            at_set = {p: (v["x"], v["y"]) for p, v in stages[2]["to"].items()}
            hit = at_set[hitter]
            if abs(hit[1] - HIT_Y) > 0.005:
                fail(f"{tag}: {hitter} hits at {hit}")
            for p, spot in at_set.items():
                if p == hitter:
                    continue
                gap = math.dist(spot, hit)
                if kind[p] == "front" and abs(spot[1] - APPROACH_Y) > 0.005 and not 0.22 <= gap <= 0.34:
                    fail(f"{tag}: {p} neither finishes the approach nor covers close: {spot}")
                if kind[p] == "back" and abs(spot[1] - BACK_HIT_Y) > 0.005 and not 0.22 <= gap <= 0.34:
                    fail(f"{tag}: {p} does not take off behind the 3 m line: {spot}")
            close_cover = [p for p, spot in at_set.items() if p != hitter and 0.22 <= math.dist(spot, hit) <= 0.34]
            setter = next(p for p in kind if kind[p] == "set")
            if len(close_cover) != 3 or setter not in close_cover or "L" not in close_cover:
                fail(f"{tag}: the close cover is {close_cover}, expected the setter, L and a front player")
            track: list[dict[str, Any]] = page.evaluate(f"window.ksvLearn.track({ri}, 'rec', 1)")
            last = {p: (v["x"], v["y"]) for p, v in track[-1]["pos"].items()}
            check_positions(f"{tag} end", {p: [x * 100, y * 100] for p, (x, y) in last.items()}, end)
            held = sorted(z for z, spot in zones.items() for p in last if math.dist(last[p], spot) < 0.005)
            if held != [1, 2, 3, 4, 5, 6]:
                fail(f"{tag}: after the spike the defence holds zones {held}")
            if "S" in row["back"] and math.dist(last["S"], zones[1]) > 0.005:
                fail(f"{tag}: the back-row setter ends at {last['S']}, not zone 1")
            spike = stages[-1]["notes"].get(hitter, "")
            if not spike.startswith("Spike over the net"):
                fail(f"{tag}: the last stage is not {hitter}'s spike: {spike!r}")


def check_no_overlap(page: Page) -> None:
    """No two markers overlap whenever the players stand still, in any animated phase, rotation and rule set."""
    for mode, roles in MODES.items():
        open_app(page, "?ff=all", {"role": roles[0], "rulesMode": mode})
        for ri in range(6):
            for phase in ("serve", "rec"):
                track: list[dict[str, Any]] = page.evaluate(f"window.ksvLearn.track({ri}, '{phase}', 300)")
                seen: set[tuple[str, str]] = set()
                for now, then in zip(track, track[1:], strict=False):
                    if now["pos"] != then["pos"]:
                        continue
                    pos = now["pos"]
                    names = sorted(pos)
                    for i, a in enumerate(names):
                        for b in names[i + 1 :]:
                            gap = math.dist((pos[a]["x"], pos[a]["y"]), (pos[b]["x"], pos[b]["y"]))
                            if gap < 2 * MARKER_R - 1e-6 and (a, b) not in seen:
                                seen.add((a, b))
                                fail(f"{mode} R{ri + 1} {phase} t={now['t']:.0f}: {a} and {b} overlap ({gap:.3f})")


def check_never_blocks(page: Page) -> None:
    """Next, the chips and the court answer at once while a phase plays; markers ignore taps."""
    open_app(page, "?ff=all", {"role": "S", "rulesMode": "simple"})
    learn(page, 1, "serve")
    page.wait_for_timeout(300)
    hit = page.evaluate(
        "(() => { const g = document.querySelector('#courtL .am[data-p=\"S\"]').getBoundingClientRect();"
        " const el = document.elementFromPoint(g.x + g.width / 2, g.y + g.height / 2);"
        " return !!(el && el.closest('.am')); })()"
    )
    if hit:
        fail("a marker takes taps while a phase plays")
    page.click("#lNext")
    if page.inner_text("#learnTag") != "R2 (S6) · Reception":
        fail(f"Next waits for the animation: tag {page.inner_text('#learnTag')!r}")
    state = anim(page)
    if not state or not state["playing"] or state["t"] > 400:
        fail(f"Next mid-play does not start Reception at once: {state}")
    page.click('.rot[data-i="4"]')
    state = anim(page)
    if page.inner_text("#learnTag") != "R5 (S3) · Reception" or not state or state["t"] > 400:
        fail(f"a rotation chip does not open that Reception: {state}")
    page.click('.ph[data-k="ar"]')
    if anim(page):
        fail("a chip to After reception plays")
    page.click('.ph[data-k="serve"]')
    if not anim(page):
        fail("a chip back to Our serve does not play it")
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
        wait_done(page)
        check_positions(f"{tag} Our serve still picture", page.evaluate(MARKERS, "#courtL .mk"), spots(ri, "serve"))
        if page.evaluate(f"window.ksvLearn.still({ri}, 'rec', 'L')") != (
            "You (L): Come back on for SUB and take your reception spot."
        ):
            fail(f"{tag} Reception still caption for L")
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
    """Reduced motion and ?anim=0: no glide, Our serve and Reception list their stages, only Next in the row."""
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
            count = 2 if phase == "serve" else 4
            if page.locator("#lCap ol li").count() != count:
                fail(f"{label} {phase}: the caption is not the list of {count} stages: {page.inner_text('#lCap')!r}")
        page.click("#lNext")
        if page.locator("#courtL .rt").count() == 0 or page.locator("#lCap ol").count():
            fail(f"{label}: After reception has no routes or lists stages")
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
            if step == 1:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        if played < 2:
            fail(f"390 × {height}: Our serve and Reception did not play")
        context.close()


def check_official(page: Page) -> None:
    """Official R3 and R6: the Rotation step shows the real lineup and the exchanges stay in the still captions."""
    for ri, (on, serves) in ((2, ("MB2", "MB1")), (5, ("MB1", "MB2"))):
        open_app(page, "?ff=all", {"role": serves, "rulesMode": "official"})
        tag = f"Official R{ri + 1}"
        serve: list[dict[str, Any]] = page.evaluate(f"window.ksvLearn.stages({ri}, 'serve')")
        if [st["moves"] for st in serve] != [[serves], [serves]] or not serve[0]["ball"]:
            fail(f"{tag} Our serve: stages move {[st['moves'] for st in serve]}, expected {serves} to serve")
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
        }
        for (phase, r), want in checks.items():
            still = page.evaluate(f"window.ksvLearn.still({ri}, '{phase}', '{r}')")
            if still != want:
                fail(f"{tag} {phase} still caption for {r}: {still!r}")


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
        check_opens_and_returns(page)
        check_no_autoplay(page)
        check_static(page)
        check_reception_stages(page)
        check_reception_ends(page)
        check_no_overlap(page)
        check_never_blocks(page)
        check_speed(page)
        check_still_captions(page)
        check_captions(page)
        check_flag_off(page)
        check_reduced(browser)
        check_phone(browser)
        check_official(page)
        for error in errors:
            fail(f"page error: {error}")
        browser.close()
    print(f"ANIM TEST: {len(FAIL)} failures")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
