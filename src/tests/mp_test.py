"""Playwright end-to-end test of same-device multiplayer in index.html."""

import random
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
SHOTS = ROOT / "src" / "tests" / "_out"
SHOTS.mkdir(exist_ok=True)

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
    while n < 400:
        n += 1
        if pg.is_visible("#gEnd"):
            break
        if pg.is_visible("#gPass"):
            order_seen.append(pg.inner_text("#pName"))
            if shots == 0:
                pg.locator("#gPass").screenshot(path=str(SHOTS / "mp1.png"))
            pg.click("#pReady")
            continue
        if pg.is_visible("#gReveal"):
            if shots == 0:
                pg.locator("#gReveal").screenshot(path=str(SHOTS / "mp2.png"))
                shots = 1
            pg.click("#rNext")
            continue
        if pg.locator("#gnb button:enabled").count() and random.random() < 0.7:
            pg.locator("#gnb button").nth(random.randrange(5)).click()
            continue
        if pg.is_visible("#gNext") and pg.is_enabled("#gNext"):
            pg.click("#gNext")
            continue
        if pg.is_enabled("#gOff"):
            if random.random() < 0.3:
                pg.click("#gOff")
            else:
                box = pg.locator("#courtG").bounding_box()
                assert box is not None
                pg.mouse.click(box["x"] + box["width"] * random.random(), box["y"] + box["height"] * random.random())
            continue
        print("STUCK")
        break
    print("ended:", pg.is_visible("#gEnd"), "actions", n)
    print("first 9 turns:", order_seen[:9])
    pg.locator("#gEnd").screenshot(path=str(SHOTS / "mp3.png"))
    # rematch works
    pg.click("#gAgain")
    print("rematch pass visible:", pg.is_visible("#gPass"))
    # role change at top doesn't kill mp
    pg.click("#tabLearn")
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
