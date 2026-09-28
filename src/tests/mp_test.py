"""Playwright end-to-end test of same-device multiplayer in index.html."""

import random
import re
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
SHOTS = ROOT / "src" / "tests" / "_out"
SHOTS.mkdir(exist_ok=True)
VERDICT = re.compile(r"Spot on|Close enough|Not there|\+\d")
CHIPS = "#courtG g[opacity]"


def press_next(page: Page) -> None:
    """Presses Check or Continue and waits out the short lock that stops a double tap skipping the feedback."""
    page.click("#gNext")
    page.wait_for_selector("#gNext:not([aria-disabled])", state="attached")


def check_hidden(pg: Page, chips_before: int, how: str) -> None:
    """Asserts that a player's answer reveals nothing before the reveal screen."""
    feedback = pg.inner_text("#gFb")
    assert "Answer saved" in feedback, f"{how}: no neutral saved state: {feedback!r}"
    assert not VERDICT.search(feedback), f"{how}: feedback leaks the verdict: {feedback!r}"
    chips_after = pg.locator(CHIPS).count()
    assert chips_after == chips_before, (
        f"{how}: court shows {chips_after} chips after the answer, {chips_before} before"
    )
    assert pg.is_visible("#gNext") and pg.is_enabled("#gNext"), f"{how}: next button not available"


def chip_scores(pg: Page, selector: str) -> dict[str, int]:
    """Reads name and score from score chips."""
    found = [re.fullmatch(r"\s*(.*?)\s+(\d+)\s*", c, re.S) for c in pg.locator(f"{selector} .pchip").all_inner_texts()]
    return {m.group(1): int(m.group(2)) for m in found if m}


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
        subtotal = int(scaled.group(2))
    return subtotal + part(r"Set call: [^+]*\+(\d+)") + part(r"Neighbour: [^+]*\+(\d+)"), int(total.group(1))


random.seed(3)
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto((ROOT / "index.html").as_uri())
    pg.wait_for_timeout(300)
    pg.click("#tabGame")
    pg.check('input[name="gPlayers"][value="mp"]')
    pg.click("#mpAdd")
    pg.fill('#mpList input[data-k="0"]', "Anna")
    pg.fill('#mpList input[data-k="1"]', "Ben")
    pg.fill('#mpList input[data-k="2"]', "<Cat>")
    pg.select_option('#mpList select[data-k="2"]', "L")
    pg.locator("#gSetup").screenshot(path=str(SHOTS / "mp0.png"))
    pg.click("#gStart")
    order_seen = []
    shots = 0
    n = 0
    chips_before = 0
    answered_by = {"tap": 0, "off": 0, "neighbour": 0, "set": 0}
    set_lines = 0
    doubled = False
    moment_board = None
    moment_seen = None
    while n < 400:
        n += 1
        if pg.is_visible("#gEnd"):
            break
        if pg.is_visible("#gPass"):
            order_seen.append(pg.inner_text("#pName"))
            moment = pg.inner_text("#pMoment").split(" · turn")[0]
            board = pg.inner_text("#pBoard")
            if moment != moment_seen:
                moment_seen, moment_board = moment, board
            assert board == moment_board, f"pass screen leaks a score change: {moment_board!r} -> {board!r}"
            if shots == 0:
                pg.locator("#gPass").screenshot(path=str(SHOTS / "mp1.png"))
            pg.click("#pReady")
            strip = chip_scores(pg, "#gStrip")
            assert strip == chip_scores(pg, "#pBoard"), f"strip {strip} differs from the pass screen"
            assert pg.locator("#gStrip .pchip.me").count() == 1, "own strip entry not highlighted"
            assert pg.evaluate("document.documentElement.scrollWidth") <= 390, "strip scrolls sideways"
            continue
        if pg.is_visible("#gReveal"):
            rows = pg.locator("#rList li").all_inner_texts()
            assert len(rows) == 3, f"reveal lists {len(rows)} players"
            for row in rows:
                assert re.search(r"Spot on|Close enough|Not there", row), f"reveal row has no verdict: {row!r}"
                found = re.search(r"\+(\d+)\s*$", row)
                assert found, f"reveal row has no points: {row!r}"
                parts, total = breakdown_total(row)
                assert parts == total == int(found.group(1)), f"reveal breakdown does not add up: {row!r}"
            assert pg.locator("#rWhy li").count() >= 1, "reveal has no explanation"
            for row in rows:
                if "Set call:" in row:
                    assert re.search(r"Set call: \S+ (✓ \+30|✗, it is \S+ \+0)", row), (
                        f"unreadable set call line: {row!r}"
                    )
                    set_lines += 1
            if shots == 0:
                pg.locator("#gReveal").screenshot(path=str(SHOTS / "mp2.png"))
                shots = 1
            pg.click("#rNext")
            continue
        if pg.locator("#gnb button:enabled").count() and random.random() < 0.7:
            pg.locator("#gnb button").nth(random.randrange(5)).click()
            marked = pg.locator("#gnb button.right, #gnb button.wrong").count()
            assert marked == 0, f"neighbour check marks {marked} buttons right/wrong before the reveal"
            neighbour_text = pg.inner_text("#gnb")
            assert "Correct." not in neighbour_text and "It is" not in neighbour_text, (
                "neighbour check leaks the answer"
            )
            check_hidden(pg, chips_before, "neighbour")
            answered_by["neighbour"] += 1
            continue
        if pg.locator("#gsc button:enabled").count() and random.random() < 0.7:
            pg.locator("#gsc button").nth(random.randrange(4)).click()
            set_text = pg.inner_text("#gsc")
            assert "Saved." in set_text, "set call answer not saved"
            assert "Correct." not in set_text and "It is" not in set_text, "set call check leaks the answer"
            marked = pg.locator('#gsc button[aria-pressed="true"], #gsc button.faded').count()
            assert marked == 0, "set call check marks the answer before the reveal"
            check_hidden(pg, chips_before, "set call")
            answered_by["set"] += 1
            continue
        if pg.is_visible("#gNext") and pg.is_enabled("#gNext"):
            press_next(pg)
            continue
        if pg.is_enabled("#gOff"):
            assert pg.is_hidden("#gVisPlay"), "Show on court can be changed during a multiplayer match"
            chips_before = pg.locator(CHIPS).count()
            strip_before = pg.inner_text("#gStrip")
            assert not pg.is_enabled("#gNext") and pg.inner_text("#gNext") == "CHECK", "Check enabled before a pick"
            if random.random() < 0.3:
                pg.click("#gOff")
                how = "off"
            else:
                box = pg.locator("#courtG").bounding_box()
                assert box is not None
                for _ in range(2):
                    pg.mouse.click(
                        box["x"] + box["width"] * random.random(), box["y"] + box["height"] * random.random()
                    )
                    assert pg.locator("#courtG .myspot").count() == 1, "re-tap does not move the marker"
                    assert not VERDICT.search(pg.inner_text("#gFb")), "a tap before Check leaks the verdict"
                how = "tap"
            if not doubled:
                pg.evaluate("() => { const b = document.getElementById('gNext'); b.click(); b.click(); }")
                assert pg.is_hidden("#gPass") and pg.is_visible("#gFb"), "a double tap on Check passed the device"
                pg.wait_for_selector("#gNext:not([aria-disabled])", state="attached")
                doubled = True
            else:
                press_next(pg)
            check_hidden(pg, chips_before, how)
            assert pg.inner_text("#gStrip") == strip_before, "strip changes before the reveal"
            answered_by[how] += 1
            continue
        print("STUCK")
        break
    print("ended:", pg.is_visible("#gEnd"), "actions", n)
    print("answers checked:", answered_by)
    assert all(answered_by.values()), f"not every answer path was checked: {answered_by}"
    assert doubled, "the double tap on Check was not tried"
    assert set_lines == answered_by["set"], f"{answered_by['set']} set calls answered, {set_lines} on the reveals"
    assert "sets " in pg.inner_text("#gStats"), "final ranking has no set call score"
    print("first 9 turns:", order_seen[:9])
    pg.locator("#gEnd").screenshot(path=str(SHOTS / "mp3.png"))
    for button in ("#gAgain", "#gSettings"):
        box = pg.locator(button).bounding_box()
        assert pg.is_visible(button) and box and box["y"] + box["height"] <= 844, (
            f"{button} not in view on the end screen"
        )
    assert pg.inner_text("#gAgain") == "PLAY AGAIN", f"end screen primary reads {pg.inner_text('#gAgain')!r}"
    assert pg.is_hidden("#gToLobby") and pg.is_hidden("#gReplay"), "same-device end screen shows other buttons"
    pg.click("#gAgain")
    assert pg.is_visible("#gPass"), "Play again did not start a new same-device match"
    print("rematch pass visible:", pg.is_visible("#gPass"))
    # role change at top doesn't kill mp
    pg.click("#tabLearn")
    if pg.is_hidden("#setupPanel"):
        pg.click("#setupBar")
    pg.click('.role[data-r="S"]')
    pg.click("#tabGame")
    print("still in mp match:", pg.is_visible("#gPass"))
    pg.click("#pQuit")
    pg.reload()
    pg.wait_for_timeout(300)
    pg.click("#tabGame")
    print(
        "mp remembered:",
        pg.is_checked('input[name="gPlayers"][value="mp"]'),
        pg.input_value('#mpList input[data-k="0"]'),
    )
    # remove works after reload, when the list exists before the Rules switch is wired up
    rules_before = pg.evaluate("localStorage.getItem('ksv51:rulesMode')")
    pg.click('#mpList button[data-rm="2"]')
    assert pg.locator("#mpList .mprow").count() == 2, "remove player did nothing"
    assert pg.evaluate("localStorage.getItem('ksv51:rulesMode')") == rules_before, "remove player changed rulesMode"
    print("remove after reload: ok")
    pg.check('input[name="gPlayers"][value="solo"]')
    pg.click("#gStart")
    print("solo play visible:", pg.is_visible("#gPlay"), pg.is_hidden("#gWho"))
    print(errs)
    b.close()
