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
    answered_by = {"tap": 0, "off": 0, "neighbour": 0}
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
            continue
        if pg.is_visible("#gReveal"):
            rows = pg.locator("#rList li").all_inner_texts()
            assert len(rows) == 3, f"reveal lists {len(rows)} players"
            for row in rows:
                assert re.search(r"Spot on|Close enough|Not there", row), f"reveal row has no verdict: {row!r}"
                assert re.search(r"\+\d+", row), f"reveal row has no points: {row!r}"
            assert pg.locator("#rWhy li").count() >= 1, "reveal has no explanation"
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
        if pg.is_visible("#gNext") and pg.is_enabled("#gNext"):
            pg.click("#gNext")
            continue
        if pg.is_enabled("#gOff"):
            chips_before = pg.locator(CHIPS).count()
            if random.random() < 0.3:
                pg.click("#gOff")
                how = "off"
            else:
                box = pg.locator("#courtG").bounding_box()
                assert box is not None
                pg.mouse.click(box["x"] + box["width"] * random.random(), box["y"] + box["height"] * random.random())
                how = "tap"
            check_hidden(pg, chips_before, how)
            answered_by[how] += 1
            continue
        print("STUCK")
        break
    print("ended:", pg.is_visible("#gEnd"), "actions", n)
    print("answers checked:", answered_by)
    assert all(answered_by.values()), f"not every answer path was checked: {answered_by}"
    print("first 9 turns:", order_seen[:9])
    pg.locator("#gEnd").screenshot(path=str(SHOTS / "mp3.png"))
    # rematch works
    pg.click("#gAgain")
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
