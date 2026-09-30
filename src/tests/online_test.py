"""Playwright end-to-end test of online multiplayer (separate phones) in index.html.

Runs against the Firebase Realtime Database and Auth emulators:

    python src/tests/online_test.py

Without the emulators running, the script restarts itself under
``firebase emulators:exec --only auth,database`` (config in infra/firebase.json;
needs the Firebase CLI and Java, and /opt/homebrew/opt/openjdk/bin is added to PATH).
"""

import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, Page, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
# A stored role skips the first-visit role sheet, which covers the page.
SEED_ROLE = "if (!localStorage.getItem('ksv51:role')) localStorage.setItem('ksv51:role', JSON.stringify('OH1'))"
sys.path.insert(0, str(ROOT / "src"))
from data import SETS, lineup  # noqa: E402

# The app opens in Simplified KSV.
ROWS = [lineup(ri, "simple") for ri in range(6)]

SHOTS = ROOT / "src" / "tests" / "_out"
SHOTS.mkdir(exist_ok=True)
PROJECT = "ksv-volleyball-xszpo"
NAMESPACE = f"{PROJECT}-default-rtdb"
PORTS = (9000, 9099)
NB_GRACE_MS = 5000
LIVE, STALE, FRESH = "111111", "000042", "000043"
EVIL_UID = "EvilEvilEvilEvilEvilEvil0000"
LABELS = {"perfect": "Spot on", "close": "Close enough", "miss": "Not there", "none": "No answer"}


def press_next(page: Page) -> None:
    """Presses Continue or Next and waits out the short lock that stops a double tap skipping the feedback."""
    page.click("#gNext")
    page.wait_for_selector("#gNext:not([aria-disabled])", state="attached")


def run_under_emulators() -> None:
    """Restarts this script inside ``firebase emulators:exec`` and always stops the emulators afterwards."""
    busy = []
    for port in PORTS:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                busy.append(port)
    if busy:
        sys.exit(
            f"Port(s) {busy} are in use, probably by an emulator left from an earlier run. "
            f"Stop it first, for example: lsof -ti :{busy[0]} | xargs kill"
        )
    env = dict(os.environ)
    env["PATH"] = "/opt/homebrew/opt/openjdk/bin:" + env.get("PATH", "")
    firebase = shutil.which("firebase", path=env["PATH"])
    assert firebase, "Firebase CLI not found; install it with npm install -g firebase-tools"
    command = f'"{sys.executable}" "{Path(__file__).resolve()}"'
    process = subprocess.Popen(
        [firebase, "emulators:exec", "--only", "auth,database", "--project", PROJECT, command],
        cwd=ROOT / "infra",
        env=env,
        start_new_session=True,
    )
    try:
        code = process.wait()
    except KeyboardInterrupt:
        code = 130
    finally:
        # The emulators run as Java children in the same session; kill the whole group so none is left behind.
        try:
            os.killpg(process.pid, signal.SIGTERM)
            time.sleep(1)
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        (ROOT / "infra" / "database-debug.log").unlink(missing_ok=True)
    sys.exit(code)


def admin(emulator_db: str, method: str, path: str, value: object = None) -> Any:
    """Reads or writes the emulator database as an admin, bypassing the rules (plays a hostile or old client)."""
    data = None if value is None else json.dumps(value).encode()
    request = urllib.request.Request(
        f"http://{emulator_db}/{path}.json?ns={NAMESPACE}",
        data=data,
        method=method,
        headers={"Authorization": "Bearer owner"},
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read() or b"null")


def check_rules(emulator_db: str) -> None:
    """Asserts that the emulator enforces infra/database.rules.json (no anonymous writes)."""
    request = urllib.request.Request(f"http://{emulator_db}/rooms/123456.json?ns={NAMESPACE}", data=b"1", method="PUT")
    try:
        urllib.request.urlopen(request)
    except urllib.error.HTTPError as e:
        assert e.code == 401, f"unexpected status {e.code}"
        return
    raise AssertionError("the emulator accepted an unauthenticated write; rules are not loaded")


def serve() -> str:
    """Serves the repository root over HTTP and returns the base URL."""

    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Quiet, directory=str(ROOT)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_address[1]}"


def phone(browser: Browser, url: str, errors: list[str]) -> Page:
    """Opens the app in a fresh browser context, like a separate phone."""
    context = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    page = context.new_page()
    page.add_init_script(SEED_ROLE)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(url)
    page.wait_for_timeout(300)
    return page


def pick_role(page: Page, role: str) -> None:
    """Selects the player's role in the setup bar."""
    if page.is_hidden("#setupPanel"):
        page.click("#roleChip")
    page.click(f'.role[data-r="{role}"]')


def open_online(page: Page, name: str, rec_only: bool = False, only: str = "") -> None:
    """Opens Match, picks the online room and types the player's name; optionally keeps one step only."""
    page.click("#tabGame")
    page.check('input[name="gPlayers"][value="online"]')
    page.fill("#onName", name)
    keep = "rec" if rec_only else only
    if keep:
        page.click("#gOpts summary")
        for step in ("start", "serve", "rec", "ar"):
            page.set_checked(f"#gs-{step}", step == keep)


def db_call(page: Page, script: str) -> str:
    """Runs ``script`` with ``db`` bound to the page's database; returns "ok" or the error code."""
    return str(
        page.evaluate(
            f"""async () => {{
                const db = firebase.database();
                try {{ {script}; return "ok"; }} catch (e) {{ return e.code || String(e); }}
            }}"""
        )
    )


def uid_of(page: Page) -> str:
    """Returns the page's anonymous user id."""
    return str(page.evaluate("firebase.auth().currentUser.uid"))


def tap_spot(page: Page, role: str, ri: int, phase: str = "rec", check: bool = True) -> None:
    """Taps the role's correct spot for ``phase`` in rotation ``ri``, then presses Continue."""
    spots = [(s[0], s[1], s[2]) for s in (ROWS[ri]["ar"] if phase == "ar" else ROWS[ri]["rec"])]
    tap_at(page, *next((x, y) for p, x, y in spots if p == role))
    if check:
        press_next(page)


def tap_at(page: Page, x: float, y: float) -> None:
    """Taps the match court at normalised court coordinates."""
    page.locator("#courtG").scroll_into_view_if_needed()
    cx, cy = page.evaluate(
        """([x, y]) => {
            const m = document.getElementById('courtG').getScreenCTM();
            return [m.a * x * 100 + m.e, m.d * y * 100 + m.f];
        }""",
        [x, y],
    )
    page.mouse.click(cx, cy)


def answer(page: Page, role: str, ri: int, off: bool = False, neighbour: bool = True) -> None:
    """Answers the current moment and checks that nothing is revealed yet."""
    page.wait_for_selector("#gOff:enabled")
    if off:
        page.click("#gOff")
        press_next(page)
    else:
        tap_spot(page, role, ri)
    feedback = page.inner_text("#gFb")
    assert "Answer saved" in feedback, f"no neutral saved state: {feedback!r}"
    assert not re.search(r"Spot on|Close enough|Not there|\+\d", feedback), f"feedback leaks: {feedback!r}"
    if page.locator("#gnb button:enabled").count():
        assert page.is_visible("#gNext"), "Continue is hidden while the neighbour check is open"
        if neighbour:
            page.locator("#gnb button").first.click()
    else:
        assert neighbour, "this moment was meant to leave a neighbour question open, but there is none"


def check_reveal(page: Page, expected: dict[str, str]) -> dict[str, int]:
    """Checks each player's verdict on the reveal screen and returns their points."""
    page.wait_for_selector("#gReveal", state="visible")
    rows = page.locator("#rList li").all_inner_texts()
    assert len(rows) == len(expected), f"reveal lists {len(rows)} players: {rows}"
    points = {}
    for name, verdict in expected.items():
        row = next((r for r in rows if name in r), None)
        assert row, f"reveal row for {name} missing: {rows}"
        assert LABELS[verdict] in row, f"{name} should be {LABELS[verdict]!r}: {row!r}"
        found = re.search(r"\+(\d+)\s*$", row)
        assert found, f"reveal row has no points: {row!r}"
        points[name] = int(found.group(1))
        if verdict != "none":
            parts, total = breakdown_total(row)
            assert parts == total == points[name], f"breakdown does not add up to the points: {row!r}"
        if verdict == "perfect":
            assert points[name] >= 100, f"spot on scored {points[name]}: {row!r}"
        if verdict in ("miss", "none"):
            assert points[name] in (0, 30), f"{verdict} scored {points[name]}: {row!r}"
    assert page.locator("#rWhy li").count() >= 1, "reveal has no explanation"
    return points


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


def strip(page: Page) -> dict[str, tuple[int, bool]]:
    """Reads the scoreboard strip in play: name to (score, answered)."""
    chips = page.locator("#gStrip .pchip").all_inner_texts()
    found = [re.fullmatch(r"\s*(.*?)\s+(\d+)\s*(✓ answered)?\s*", c, re.S) for c in chips]
    assert all(found), f"unreadable strip chips: {chips}"
    return {m.group(1): (int(m.group(2)), bool(m.group(3))) for m in found if m}


def board(page: Page) -> dict[str, int]:
    """Reads the score chips on the reveal screen."""
    chips = page.locator("#rBoard .pchip").all_inner_texts()
    found = [re.fullmatch(r"\s*(.*?)\s+(\d+)\s*", c, re.S) for c in chips]
    assert all(found), f"unreadable score chips: {chips}"
    return {m.group(1): int(m.group(2)) for m in found if m}


def rejoin(page: Page, code: str) -> None:
    """Reloads the page, like a phone that dropped out, and joins the same room again."""
    page.reload()
    page.wait_for_timeout(300)
    page.click("#tabGame")
    assert page.input_value("#onCode") == code, "room code not remembered"
    page.click("#onJoin")


def double_click(page: Page, element_id: str) -> None:
    """Clicks a button twice before any update arrives, like an impatient double tap."""
    page.evaluate(f"() => {{ const b = document.getElementById('{element_id}'); b.click(); b.click(); }}")


def responsive(page: Page) -> None:
    """Fails if the page's main thread is blocked for 2 seconds."""
    page.wait_for_function("true", timeout=2000)


def check_permissions(browser: Browser, url: str, host: Page, code: str, errors: list[str]) -> None:
    """A second player cannot take over, change or delete what belongs to the host.

    Runs from a third phone, because the SDK applies denied writes locally until the server refuses them.
    """
    eve = phone(browser, url, errors)
    eve.click("#tabGame")
    eve.check('input[name="gPlayers"][value="online"]')
    eve.wait_for_function("window.firebase?.apps?.length > 0")
    room = f"rooms/{code}"
    assert db_call(eve, "await firebase.auth().signInAnonymously()") == "ok"
    anna, ben = uid_of(host), uid_of(eve)
    player = '{name: "Eve", role: "S", color: "#123456", joinedAt: firebase.database.ServerValue.TIMESTAMP}'
    assert db_call(eve, f'await db.ref("{room}/players/{ben}").set({player})') == "ok", "a player cannot join"
    fake = '{q: "miss", pts: 0, done: true}'
    attempts = {
        "take the host while it is online": f'await db.ref("{room}/meta/host").set("{ben}")',
        "change the match state": f'await db.ref("{room}/meta/state").set("done")',
        "delete another player": f'await db.ref("{room}/players/{anna}").remove()',
        "change another player's score": f'await db.ref("{room}/players/{anna}/score").set(999)',
        "write another player's answer": f'await db.ref("{room}/answers/0/{anna}").set({fake})',
        "write a huge answer index": f'await db.ref("{room}/answers/4294967294/{ben}").set({fake})',
        "give itself a script colour": f'await db.ref("{room}/players/{ben}/color").set("red;<b>")',
        "reset another player's score": f'await db.ref("{room}/players/{anna}/score").remove()',
        "reset another player's results": f'await db.ref("{room}/players/{anna}/results").remove()',
        "clear the answers": f'await db.ref("{room}/answers").remove()',
        "store a breakdown that is not a number": f'await db.ref("{room}/answers/0/{ben}").set('
        '{q: "miss", pts: 0, done: true, bd: {base: "<b>"}})',
        "store an unknown breakdown field": f'await db.ref("{room}/answers/0/{ben}").set('
        '{q: "miss", pts: 0, done: true, bd: {bonus: 1}})',
        "delete the whole room": f'await db.ref("{room}").remove()',
        "create a room with letters in the code": 'await db.ref("rooms/ABC123/meta").set({host: "x", '
        'createdAt: firebase.database.ServerValue.TIMESTAMP, state: "lobby", i: 0})',
    }
    for what, script in attempts.items():
        result = db_call(eve, script)
        assert "PERMISSION_DENIED" in result.upper(), f"a guest could {what}: {result}"
    assert db_call(eve, f'await db.ref("{room}/players/{ben}").remove()') == "ok", "a player cannot leave"
    eve.context.close()
    print("guest writes outside its own nodes are denied")


def main_match(browser: Browser, url: str, emulator_db: str, errors: list[str]) -> tuple[Page, Page]:
    """Plays a six-moment online match between a host and a guest with known taps."""
    host = phone(browser, url, errors)
    guest = phone(browser, url, errors)

    pick_role(host, "OH1")
    open_online(host, "Anna", rec_only=True)
    host.check("#nbGame")
    host.click("#onCreate")
    host.wait_for_selector("#gLobby", state="visible", timeout=20000)
    shown = host.inner_text("#lCode").strip()
    assert re.fullmatch(r"[0-9]{3} [0-9]{3}", shown), f"bad room code {shown!r}"
    code = shown.replace(" ", "")
    assert host.is_visible("#lStart"), "host has no Start button"
    denied = db_call(host, 'await db.ref("rooms/000000/players/someone/online").set(true)')
    assert "PERMISSION_DENIED" in denied.upper(), f"presence write into a missing room: {denied}"
    print("room created:", code)

    pick_role(guest, "L")
    open_online(guest, "Ben")
    guest.fill("#onCode", "12a")
    assert guest.input_value("#onCode") == "12", "the code field accepts letters"
    guest.fill("#onCode", "999999")
    guest.click("#onJoin")
    guest.wait_for_function("document.getElementById('onErr').textContent.length > 0", timeout=20000)
    error = guest.inner_text("#onErr")
    assert "no room" in error.lower(), f"bad code gives the wrong error: {error!r}"

    guest.evaluate(
        """() => {
            window.__connected = 0;
            const proto = firebase.database.Reference.prototype, on = proto.on;
            proto.on = function (...args) {
                if (this.key === "connected") window.__connected++;
                return on.apply(this, args);
            };
        }"""
    )
    guest.fill("#onCode", code)
    guest.evaluate(
        """() => {
            const input = document.getElementById("onCode");
            for (let k = 0; k < 2; k++) input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter" }));
        }"""
    )
    guest.wait_for_selector("#gLobby", state="visible", timeout=20000)
    assert guest.is_hidden("#lStart") and guest.is_visible("#lWait"), "guest can start the match"
    for page in (host, guest):
        page.wait_for_function("document.querySelectorAll('#lList li').length === 2")
        page.wait_for_function("document.getElementById('lList').textContent.split('online').length === 3")
        lobby = page.inner_text("#lList")
        assert "Anna" in lobby and "Ben" in lobby and "Libero" in lobby, f"lobby: {lobby!r}"
        assert lobby.count("online") == 2, f"presence missing: {lobby!r}"
    assert guest.evaluate("window.__connected") == 1, "pressing Enter twice joins the room twice"
    assert not guest.inner_text("#onErr"), f"pressing Enter twice shows an error: {guest.inner_text('#onErr')!r}"
    host.locator("#gLobby").screenshot(path=str(SHOTS / "online0.png"))
    print("lobby shows both")

    assert guest.is_disabled('.rulesmode [data-rm="official"]'), "a guest can change the rules in the lobby"
    if host.is_hidden("#setupPanel"):
        host.click("#roleChip")
    host.click('.rulesmode [data-rm="official"]')
    guest.wait_for_function("document.getElementById('lSet').textContent.includes('Official')")
    host.click('.rulesmode [data-rm="simple"]')
    guest.wait_for_function("document.getElementById('lSet').textContent.includes('Simplified')")
    host.click("#setupDone")
    print("lobby rules follow the host")

    check_permissions(browser, url, host, code, errors)

    host.click("#lStart")
    guest.wait_for_selector("#gPlay", state="visible")
    assert guest.is_disabled('.rulesmode [data-rm="official"]'), "rules can change during an online match"
    assert "Set by the host" in guest.inner_text("#rmSub"), "locked rules switch not explained"

    totals = {"Anna": 0, "Ben": 0}
    moments = 6
    for i in range(moments):
        for page in (host, guest):
            page.wait_for_selector("#gPlay", state="visible")
            page.wait_for_function(f"document.getElementById('gStepName').textContent.includes('moment {i + 1} of')")
        expected = {"Anna": "perfect", "Ben": "perfect"}
        guest.wait_for_selector("#gOff:enabled")
        seen = strip(guest)
        assert {k: seen[k] for k in totals} == {k: (v, False) for k, v in totals.items()}, (
            f"moment {i + 1}: guest strip {seen}, expected {totals} and nobody answered"
        )
        assert guest.locator("#gStrip .pchip.me").count() == 1, "own strip entry not highlighted"
        assert guest.evaluate("document.documentElement.scrollWidth <= innerWidth"), "strip scrolls sideways"
        if i == 1:
            answer(host, "OH1", i)
            host.wait_for_selector("#wReveal", state="visible")
            assert "Ben" in host.inner_text("#wText"), "host is not told who is missing"
            double_click(host, "wReveal")
            expected["Ben"] = "none"
        elif i == 2:
            host.wait_for_selector("#gOff:enabled")
            tap_at(host, 0.5, 0.03)
            tap_spot(host, "OH1", i, check=False)
            host.wait_for_timeout(1000)
            assert admin(emulator_db, "GET", f"rooms/{code}/answers/{i}") is None, "a tap without Continue was saved"
            assert not strip(guest)["Anna"][1], "answered shown before Continue"
            answer(host, "OH1", i)
            guest.wait_for_function("document.getElementById('gStrip').textContent.includes('✓ answered')")
            assert strip(guest)["Anna"] == (totals["Anna"], True), f"strip after the host's Continue: {strip(guest)}"
            answer(guest, "L", i, off=True)
            expected["Ben"] = "miss"
        elif i == 3:
            answer(guest, "L", i, neighbour=False)
            assert "neighbour question" in guest.inner_text("#wText"), "pending player not told to continue"
            rejoin(guest, code)
            guest.wait_for_selector("#gWait", state="visible", timeout=20000)
            answer(host, "OH1", i)
            host.wait_for_selector("#gReveal", state="visible", timeout=4000)
            print("rejoin during the neighbour check marks the answer done")
        elif i == 4:
            answer(host, "OH1", i)
            answer(guest, "L", i, neighbour=False)
            host.wait_for_function("document.getElementById('wText').textContent.includes('neighbour check')")
            host.wait_for_selector("#gReveal", state="visible", timeout=NB_GRACE_MS + 4000)
            print("an unanswered neighbour question stops blocking after the grace period")
        else:
            answer(host, "OH1", i)
            answer(guest, "L", i)
        for page in (host, guest):
            points = check_reveal(page, expected)
        for name in totals:
            totals[name] += points[name]
        assert board(host) == totals, f"scores {board(host)} do not add up to {totals}"
        assert guest.is_hidden("#rNext") and guest.is_visible("#rWait"), "guest can advance the match"
        if i == 0:
            host.locator("#gReveal").screenshot(path=str(SHOTS / "online1.png"))
        if i == 2:
            rejoin(guest, code)
            check_reveal(guest, expected)
            assert board(guest) == totals, f"rejoin restored {board(guest)}, expected {totals}"
            print("rejoin restores the reveal and scores")
        if i == moments - 1:
            inject(emulator_db, code)
            for page in (host, guest):
                page.wait_for_function("document.querySelectorAll('#rBoard .pchip').length === 3")
                responsive(page)
                assert page.evaluate("window.__pwned") is None, "remote player data ran script"
            print("hostile player data rendered safely and the page stays responsive")
        double_click(host, "rNext")
        print("moment", i + 1, "ok")

    for page in (host, guest):
        page.wait_for_selector("#gEnd", state="visible")
        ranking = page.locator("#gStats .rank li").all_inner_texts()
        assert len(ranking) == 3, f"ranking lists {len(ranking)} players"
        for name, total in totals.items():
            row = next(r for r in ranking if name in r)
            assert re.search(rf"\s{total}\s*$", row), f"final score for {name} is not {total}: {row!r}"
        assert page.evaluate("window.__pwned") is None, "remote player data ran script"
    host.locator("#gEnd").screenshot(path=str(SHOTS / "online2.png"))
    print("final ranking matches the reveals:", totals)

    persistent_room(host, guest, emulator_db, code)

    host.check('input[name="gPlayers"][value="solo"]')
    host.click("#gStart")
    host.wait_for_selector("#gPlay", state="visible")
    host.click("#gOff")
    press_next(host)
    assert host.is_hidden("#gWait"), "the online wait box shows in a solo match"
    assert host.is_hidden("#gStrip"), "solo match shows the scoreboard strip"
    host.click("#gQuit")
    print("solo match after online play has no wait box")
    return host, guest


def board_of(page: Page, selector: str) -> dict[str, int]:
    """Reads name and the last number from each element, like a ranking row or a score chip."""
    rows = page.locator(selector).all_inner_texts()
    found = [re.search(r"(Anna|Ben)\b.*?(\d+)\s*$", r, re.S) for r in rows]
    return {m.group(1): int(m.group(2)) for m in found if m}


def in_lobby(page: Page, players: int) -> None:
    """Waits until the page shows the room's lobby with ``players`` players listed."""
    page.wait_for_selector("#gLobby", state="visible", timeout=20000)
    page.wait_for_function(f"document.querySelectorAll('#lList li').length === {players}")


def moment_one(page: Page) -> None:
    """Waits for the first moment of a match."""
    page.wait_for_selector("#gPlay", state="visible", timeout=20000)
    page.wait_for_function("document.getElementById('gStepName').textContent.includes('moment 1 of')")


def persistent_room(host: Page, guest: Page, emulator_db: str, code: str) -> None:
    """After a match the room goes back to the lobby and can be played again, left and rejoined."""
    admin(emulator_db, "DELETE", f"rooms/{code}/players/{EVIL_UID}")
    for page, primary in ((host, "NEW MATCH"), (guest, "BACK TO LOBBY")):
        for button in ("#gToLobby", "#gSettings"):
            box = page.locator(button).bounding_box()
            assert page.is_visible(button) and box and box["y"] + box["height"] <= 844, f"{button} not in view"
        assert page.inner_text("#gToLobby") == primary, f"end screen primary reads {page.inner_text('#gToLobby')!r}"
        assert page.inner_text("#gSettings") == "LEAVE ROOM", "end screen has no Leave room"
        assert page.is_hidden("#gAgain") and page.is_hidden("#gReplay"), "online end screen offers solo actions"
    final = board_of(guest, "#gStats .rank li")
    guest.click("#gToLobby")
    in_lobby(guest, 2)
    assert guest.is_hidden("#lLive") and "host starts" in guest.inner_text("#lWait"), "guest lobby after the match"
    assert board_of(guest, "#lLastList .pchip") == final, "lobby does not show the last match's scores"
    assert host.is_visible("#gEnd"), "the guest going to the lobby moved the host"
    assert admin(emulator_db, "GET", f"rooms/{code}/meta/state") == "done", "a guest reset the room"
    before = admin(emulator_db, "GET", f"rooms/{code}/meta")
    assert before["activeAt"] > before["createdAt"], f"moving on does not refresh activeAt: {before}"
    admin(emulator_db, "PUT", f"rooms/{code}/meta/hostLeft", True)
    host.click("#gToLobby")
    for page in (host, guest):
        in_lobby(page, 2)
        page.wait_for_selector("#lList .lroles")
        assert board_of(page, "#lLastList .pchip") == final, "lobby after New match lost the last scores"
    room = admin(emulator_db, "GET", f"rooms/{code}")
    assert room["meta"]["state"] == "lobby" and "queue" not in room["meta"], f"room not reset: {room['meta']}"
    assert "hostLeft" not in room["meta"], "reset keeps an old room's hostLeft"
    assert room["meta"]["activeAt"] > before["activeAt"], "reset does not refresh activeAt"
    assert "answers" not in room, "answers kept after the reset"
    for player in room["players"].values():
        kept = {k for k in player if k not in ("name", "role", "color", "joinedAt", "online")}
        assert not kept, f"per-match fields kept after the reset: {kept}"
    ben = uid_of(guest)
    denied = db_call(host, f'await db.ref("rooms/{code}/players/{ben}/score").set(999)')
    assert "PERMISSION_DENIED" in denied.upper(), f"the host could set a guest's score: {denied}"
    print("Back to lobby resets the room for both")

    guest.click('#lList .lroles button[data-r="OH2"]')
    host.wait_for_function("document.getElementById('lList').textContent.includes('Outside 2')")
    assert guest.evaluate("JSON.parse(localStorage.getItem('ksv51:role'))") == "OH2", "lobby role not stored"
    assert guest.get_attribute('#roles .role[data-r="OH2"]', "aria-pressed") == "true", "setup bar not in sync"
    late = db_call(
        guest,
        f'await db.ref("rooms/{code}").update({{"answers/0/{ben}": {{q: "perfect", pts: 150, done: true}}, '
        f'"players/{ben}/score": 999, "players/{ben}/perfect": 5}})',
    )
    assert late == "ok", f"could not simulate a late answer write: {late}"
    host.click("#lStart")
    for page in (host, guest):
        moment_one(page)
    assert guest.is_disabled('#roles .role[data-r="MB"]'), "roles can change during an online match"
    guest.wait_for_function("!document.getElementById('gStrip').textContent.includes('999')")
    assert strip(guest) == {"Anna": (0, False), "Ben": (0, False)}, f"new match strip: {strip(guest)}"
    assert admin(emulator_db, "GET", f"rooms/{code}/answers") is None, "a late answer survived the new Start"
    answer(host, "OH1", 0)
    answer(guest, "OH2", 0)
    points = check_reveal(host, {"Anna": "perfect", "Ben": "perfect"})
    assert board(host) == points, f"second match did not start from zero: {board(host)}"
    assert "Outside 2" in next(r for r in host.locator("#rList li").all_inner_texts() if "Ben" in r)
    print("second match in the same room uses the new role, scores start from zero")

    host.click("#rNext")
    host.wait_for_function("document.getElementById('gStepName').textContent.includes('moment 2 of')")
    host.click("#gQuit")
    for page in (host, guest):
        in_lobby(page, 2)
    assert host.is_visible("#lStart") and guest.is_hidden("#lLive"), "lobby after the host quit is wrong"
    assert guest.is_hidden("#lLast"), "last match scores still shown after a new match started"
    assert admin(emulator_db, "GET", f"rooms/{code}/meta/state") == "lobby", "host Quit did not reset the room"
    print("host Quit brings everyone to the lobby")

    host.click("#lStart")
    for page in (host, guest):
        moment_one(page)
    guest.click("#gQuit")
    guest.wait_for_selector("#lLive", state="visible")
    assert "in progress" in guest.inner_text("#gLobby").lower(), "lobby does not say a match is running"
    answer(host, "OH1", 0)
    host.wait_for_selector("#gReveal", state="visible", timeout=10000)
    guest.click("#lJoinIn")
    check_reveal(guest, {"Anna": "perfect", "Ben": "none"})
    host.click("#rNext")
    guest.wait_for_function("document.getElementById('gStepName').textContent.includes('moment 2 of')")
    answer(guest, "OH2", 1)
    print("a guest can quit to the lobby and join in again")

    host.click("#gQuit")
    for page in (host, guest):
        in_lobby(page, 2)
    guest.reload()
    guest.wait_for_timeout(300)
    guest.click("#tabGame")
    guest.wait_for_selector("#onRejoin", state="visible", timeout=20000)
    label = guest.text_content("#onRejoin")
    assert label == f"Rejoin room {code[:3]} {code[3:]}", f"rejoin button reads {label!r}"
    guest.click("#onRejoin")
    in_lobby(guest, 2)
    assert uid_of(guest) == ben, "rejoin used a new player"
    host.wait_for_function("document.getElementById('lList').textContent.split('online').length === 3")
    assert "Outside 2" in host.inner_text("#lList"), "rejoin changed the role"
    print("Rejoin from the remembered room after a reload")

    guest.click("#lLeave")
    assert guest.is_visible("#gSetup"), "Leave room does not return to setup"
    assert guest.evaluate("localStorage.getItem('ksv51:room')") is None, "Leave room keeps the room code"
    host.wait_for_function("document.querySelectorAll('#lList li').length === 1")
    guest.click('input[name="gPlayers"][value="solo"]')
    guest.click('input[name="gPlayers"][value="online"]')
    guest.wait_for_function("document.getElementById('onRejoin').dataset.checked === '1'")
    assert guest.is_hidden("#onRejoin"), "Rejoin offered after leaving"
    host.click("#lLeave")
    assert admin(emulator_db, "GET", f"rooms/{code}/meta") is not None, "the room is gone after the host left"
    print("Leave room clears the remembered room; the room stays")


def inject(emulator_db: str, code: str) -> None:
    """Writes data no honest client can write (script in fields, huge array indices), as if the rules failed."""
    payload = '<img src=x onerror="window.__pwned=1">'
    admin(
        emulator_db,
        "PUT",
        f"rooms/{code}/players/{EVIL_UID}",
        {
            "name": payload,
            "role": "OP",
            "color": f'red;">{payload}',
            "score": payload,
            "perfect": payload,
            "joinedAt": 1,
            "online": False,
            "misses": {"0": {"ri": 99, "phase": "rec"}, "1": {"ri": 0, "phase": payload}},
            "results": {"4294967294": {"q": "miss", "pts": 0}},
        },
    )
    admin(emulator_db, "PUT", f"rooms/{code}/answers/4294967294/{EVIL_UID}", {"q": "miss", "pts": 0, "done": True})


def takeover(host: Page, guest: Page, browser: Browser, url: str, emulator_db: str, errors: list[str]) -> None:
    """Stale rooms, concurrent joins and a host that drops out mid-match and comes back."""
    old_meta = {"host": "x", "createdAt": 1000, "state": "lobby", "i": 0}
    admin(emulator_db, "PUT", f"rooms/{STALE}", {"meta": old_meta})
    for page in (host, guest):
        page.check('input[name="gPlayers"][value="online"]')
    guest.fill("#onCode", STALE)
    guest.click("#onJoin")
    guest.wait_for_function("document.getElementById('onErr').textContent.includes('expired')", timeout=20000)
    deadline = time.monotonic() + 5
    while admin(emulator_db, "GET", f"rooms/{STALE}") is not None:
        assert time.monotonic() < deadline, "a stale room is not deleted when a player hits it"
        time.sleep(0.2)
    print("stale room deleted on join")

    now = int(time.time() * 1000)
    admin(emulator_db, "PUT", f"rooms/{FRESH}", {"meta": {**old_meta, "activeAt": now}})
    guest.fill("#onCode", FRESH)
    guest.click("#onJoin")
    guest.wait_for_selector("#gLobby", state="visible", timeout=20000)
    guest.click("#lLeave")
    admin(emulator_db, "PUT", f"rooms/{STALE}", {"meta": {**old_meta, "createdAt": now, "activeAt": 1000}})
    guest.fill("#onCode", STALE)
    guest.click("#onJoin")
    guest.wait_for_function("document.getElementById('onErr').textContent.includes('expired')", timeout=20000)
    deadline = time.monotonic() + 5
    while admin(emulator_db, "GET", f"rooms/{STALE}") is not None:
        assert time.monotonic() < deadline, "a room with an old activeAt is not deleted on hit"
        time.sleep(0.2)
    print("staleness follows activeAt: an old room in recent use is joinable, an idle one is deleted")

    live_meta = {"host": "x", "createdAt": int(time.time() * 1000), "state": "lobby", "i": 0}
    admin(emulator_db, "PUT", f"rooms/{LIVE}", {"meta": live_meta})
    old_player = {"name": "Old", "role": "S", "color": "#000000", "joinedAt": 1000}
    admin(emulator_db, "PUT", f"rooms/{STALE}", {"meta": old_meta, "players": {EVIL_UID: old_player}})
    first = phone(browser, url, errors)
    first.evaluate(
        f"""() => {{
            const codes = [{int(LIVE)}, {int(STALE)}], random = crypto.getRandomValues.bind(crypto);
            crypto.getRandomValues = (a) => {{
                if (a instanceof Uint32Array && a.length === 1 && codes.length) {{
                    a[0] = codes.shift();
                    return a;
                }}
                return random(a);
            }};
        }}"""
    )
    pick_role(first, "OP")
    open_online(first, "Cid", rec_only=True)
    first.uncheck("#nbGame")
    first.click("#onCreate")
    first.wait_for_selector("#gLobby", state="visible", timeout=20000)
    code = first.inner_text("#lCode").replace(" ", "")
    assert code == STALE, f"create did not skip the live room and reuse the stale one: {code}"
    assert admin(emulator_db, "GET", f"rooms/{LIVE}/meta") == live_meta, "create touched a live room"
    assert EVIL_UID not in admin(emulator_db, "GET", f"rooms/{code}/players"), "a reused room kept old players"
    print("create skips a live room code and reuses a stale one")

    for page in (host, guest):
        page.fill("#onCode", code)
    for page in (host, guest):
        page.evaluate("document.getElementById('onJoin').click()")
    for page in (host, guest):
        page.wait_for_selector("#gLobby", state="visible", timeout=20000)
    first.wait_for_function("document.querySelectorAll('#lList li').length === 3")
    players = admin(emulator_db, "GET", f"rooms/{code}/players")
    colours = [p["color"] for p in players.values()]
    assert len(set(colours)) == 3, f"players joining at once share a colour: {colours}"
    print("colours distinct after joining at once:", colours)

    roles = {first: "OP", host: "OH1", guest: "OH2"}
    first.click("#lStart")
    for page, role in roles.items():
        page.wait_for_selector("#gPlay", state="visible")
        answer(page, role, 0)
    for page in roles:
        check_reveal(page, {"Cid": "perfect", "Anna": "perfect", "Ben": "perfect"})

    first.evaluate("firebase.database().goOffline()")
    new_host = None
    deadline = time.monotonic() + 30
    while new_host is None:
        assert time.monotonic() < deadline, "nobody took over from the offline host"
        new_host = next((p for p in (host, guest) if p.is_visible("#rNext")), None)
        time.sleep(0.2)
    other = guest if new_host is host else host
    new_name = "Anna" if new_host is host else "Ben"
    other.wait_for_function(
        f"document.getElementById('onNote').textContent.includes('{new_name} is now the host')", timeout=10000
    )
    print("host takeover during the reveal:", other.inner_text("#onNote"))

    first.click("#rNext")
    first.evaluate(
        f"""() => {{
            window.__stale = firebase.database().ref("rooms/{code}/meta/i").set(5).then(() => "ok", (e) => e.code);
        }}"""
    )
    first.evaluate("firebase.database().goOnline()")
    stale = str(
        first.evaluate("Promise.race([window.__stale, new Promise((r) => setTimeout(() => r('no reply'), 15000))])")
    )
    assert "PERMISSION_DENIED" in stale.upper(), f"the replaced host could still write meta: {stale}"
    first.wait_for_selector("#rWait", state="visible", timeout=10000)
    first.wait_for_timeout(1000)
    meta = admin(emulator_db, "GET", f"rooms/{code}/meta")
    assert meta["i"] == 0 and meta["state"] == "reveal", f"the replaced host changed the match: {meta}"
    assert meta["host"] == uid_of(new_host), "the old host took the room back"
    assert first.is_hidden("#rNext"), "the old host still has Next"
    print("the returning host is a guest and its stale writes are denied")

    new_host.click("#rNext")
    for page, role in roles.items():
        page.wait_for_function("document.getElementById('gStepName').textContent.includes('moment 2 of')")
        answer(page, role, 1)
    for page in roles:
        check_reveal(page, {"Cid": "perfect", "Anna": "perfect", "Ben": "perfect"})
    assert new_host.is_visible("#rNext") and first.is_hidden("#rNext"), "the new host cannot advance"
    new_host.click("#rQuit")
    for page in (new_host, other, first):
        page.wait_for_selector("#gLobby", state="visible", timeout=10000)


def asked_set(page: Page) -> str:
    """Reads which set the question draws from the end point and height of its path."""
    numbers = [float(n) for n in re.findall(r"-?[0-9.]+", page.get_attribute("#gscNet path", "d") or "")]
    landing, peak = (numbers[4] - 80) / 840, (330 - numbers[3]) / 580
    return min(SETS, key=lambda s: abs(s[1] - landing) + abs(s[2] - peak))[0]


def set_answer_saved(page: Page, pick: str) -> None:
    page.click(f'#gsc .setchip[data-s="{pick}"]')
    text = page.inner_text("#gsc")
    assert "Saved." in text and "Correct." not in text and "It is" not in text, f"set call leaks: {text!r}"


def set_calls(browser: Browser, url: str, emulator_db: str, errors: list[str]) -> None:
    """Front-row and setter players answer set calls on their own phones; the reveal waits for them."""
    host = phone(browser, url, errors)
    guest = phone(browser, url, errors)
    pick_role(host, "OP")
    open_online(host, "Anna", only="ar")
    host.check("#setGame")
    host.click("#onCreate")
    host.wait_for_selector("#gLobby", state="visible", timeout=20000)
    code = host.inner_text("#lCode").replace(" ", "")
    pick_role(guest, "S")
    open_online(guest, "Sam")
    guest.fill("#onCode", code)
    guest.click("#onJoin")
    guest.wait_for_selector("#gLobby", state="visible", timeout=20000)
    host.wait_for_function("document.querySelectorAll('#lList li').length === 2")
    host.click("#lStart")
    sam = uid_of(guest)

    for page, role in ((guest, "S"), (host, "OP")):
        page.wait_for_selector("#gOff:enabled", timeout=20000)
        tap_spot(page, role, 0, "ar")
        page.wait_for_selector("#gsc")
        assert page.is_visible("#gNext"), "Continue is hidden while the set call check is open"
    guest_set = asked_set(guest)
    set_answer_saved(guest, guest_set)
    guest.wait_for_function("document.getElementById('wText').textContent.includes('(set call)')", timeout=10000)
    time.sleep(1.5)
    assert host.is_hidden("#gReveal"), "the reveal did not wait for an open set call check"
    press_next(host)
    host.wait_for_selector("#gReveal", state="visible", timeout=10000)
    rows = {name: next(r for r in host.locator("#rList li").all_inner_texts() if name in r) for name in ("Anna", "Sam")}
    assert f"Set call: {guest_set} ✓ +30" in rows["Sam"], f"setter's set call row: {rows['Sam']!r}"
    assert "Set call:" not in rows["Anna"], f"a skipped set call is shown: {rows['Anna']!r}"
    saved = admin(emulator_db, "GET", f"rooms/{code}/answers/0/{sam}/set")
    assert saved == {"ask": guest_set, "pick": guest_set, "ok": True}, f"set answer stored as {saved}"
    stored = admin(emulator_db, "GET", f"rooms/{code}/answers/0/{sam}")
    assert set(stored["bd"]) == {"base", "speed", "streak", "mult", "nb", "set"}, f"breakdown stored as {stored}"
    assert stored["bd"]["set"] == 30, f"set bonus not in the breakdown: {stored['bd']}"
    assert "bd" not in admin(emulator_db, "GET", f"rooms/{code}/players/{sam}/results/0"), "breakdown in results"
    print("set call answered by the setter, skipped by the attacker; the reveal waited for both")

    host.click("#rNext")
    evil = {"name": "Evil", "role": "S", "color": "#123456", "joinedAt": 1000, "online": False}
    admin(emulator_db, "PUT", f"rooms/{code}/players/{EVIL_UID}", evil)
    fake = {"q": "miss", "pts": 0, "done": True, "set": {"ask": "<img>", "pick": "Til", "ok": True}}
    admin(emulator_db, "PUT", f"rooms/{code}/answers/1/{EVIL_UID}", fake)
    for page, role in ((host, "OP"), (guest, "S")):
        page.wait_for_selector("#gOff:enabled", timeout=20000)
        tap_spot(page, role, 1, "ar")
        page.wait_for_selector("#gsc")
    host_set = asked_set(host)
    wrong = next(o for o in host.locator("#gsc .setchip").all_inner_texts() if o != host_set)
    set_answer_saved(host, wrong)
    set_answer_saved(guest, next(o for o in guest.locator("#gsc .setchip").all_inner_texts() if o != asked_set(guest)))
    guest.wait_for_selector("#gReveal", state="visible", timeout=10000)
    rows = {
        name: next(r for r in guest.locator("#rList li").all_inner_texts() if name in r) for name in ("Anna", "Evil")
    }
    assert f"Set call: {wrong} ✗, it is {host_set} +0" in rows["Anna"], f"attacker's set call row: {rows['Anna']!r}"
    assert "Set call:" not in rows["Evil"], f"a made-up set name is shown: {rows['Evil']!r}"
    print("wrong set call shown with the right one; made-up set names are dropped")
    for page in (host, guest):
        page.context.close()


def failed_join(browser: Browser, url: str, emulator_db: str, errors: list[str]) -> None:
    """A join that fails after the player node is written leaves no ghost online, and the match goes on."""
    host = phone(browser, url, errors)
    guest = phone(browser, url, errors)
    late = phone(browser, url, errors)
    pick_role(host, "OH1")
    open_online(host, "Anna", rec_only=True)
    host.uncheck("#nbGame")
    host.click("#onCreate")
    host.wait_for_selector("#gLobby", state="visible", timeout=20000)
    code = host.inner_text("#lCode").replace(" ", "")

    pick_role(guest, "OH2")
    guest.click("#tabGame")
    guest.click('.vis[data-vis="game"] [data-v="all"]')
    open_online(guest, "Ben")
    guest.fill("#onCode", code)
    guest.click("#onJoin")
    guest.wait_for_selector("#gLobby", state="visible", timeout=20000)

    pick_role(late, "MB")
    open_online(late, "Cal")
    late.wait_for_function("window.firebase?.apps?.length > 0")
    late.evaluate(
        """() => {
            const proto = firebase.database.Reference.prototype, once = proto.once;
            proto.once = function (...args) {
                if (this.key === "players") return Promise.reject(new Error("network down"));
                return once.apply(this, args);
            };
        }"""
    )
    late.fill("#onCode", code)
    late.click("#onJoin")
    late.wait_for_function("document.getElementById('onErr').textContent.length > 0", timeout=20000)
    node = admin(emulator_db, "GET", f"rooms/{code}/players/{uid_of(late)}")
    assert isinstance(node, dict) and node.get("online") is not True, f"a failed join left {node}"
    host.wait_for_function("document.querySelectorAll('#lList li').length === 3")
    cal = next(r for r in host.locator("#lList li").all_inner_texts() if "Cal" in r)
    assert "joining" in cal, f"lobby shows the failed joiner as {cal!r}"
    print("a failed join leaves the player shown as joining, never online")

    host.click("#lStart")
    guest.wait_for_selector("#gOff:enabled", timeout=20000)
    assert guest.is_hidden("#gVisPlay"), "Show on court can be changed during an online match"
    chips = "#courtG g[opacity]"
    assert guest.locator(chips).count() == 0, "the guest's own Show on court setting is used online"
    guest.evaluate("document.querySelector('#gVisPlay [data-v=\"ref\"]').click()")
    assert guest.locator(chips).count() == 0, "the in-play picker changes the online court"
    stored = guest.evaluate("JSON.parse(localStorage.getItem('ksv51:visGame'))")
    assert stored == "all", f"online play wrote the player's Show on court setting: {stored!r}"
    answer(host, "OH1", 0)
    answer(guest, "OH2", 0)
    for page in (host, guest):
        page.wait_for_selector("#gReveal", state="visible", timeout=10000)
    print("online uses the room's Show on court; the reveal skips the failed joiner")
    for page in (host, guest, late):
        page.context.close()


def main() -> None:
    """Runs the online scenarios against the emulators."""
    signal.alarm(600)
    emulator_db = os.environ["FIREBASE_DATABASE_EMULATOR_HOST"]
    emulator_auth = os.environ["FIREBASE_AUTH_EMULATOR_HOST"]
    check_rules(emulator_db)
    url = f"{serve()}/index.html?emu={emulator_db},{emulator_auth}&nbgrace={NB_GRACE_MS}&ff=all&anim=0"
    errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        host, guest = main_match(browser, url, emulator_db, errors)
        takeover(host, guest, browser, url, emulator_db, errors)
        set_calls(browser, url, emulator_db, errors)
        failed_join(browser, url, emulator_db, errors)
        browser.close()
    assert not errors, errors
    print("ONLINE TEST: ok")


if __name__ == "__main__":
    if "FIREBASE_DATABASE_EMULATOR_HOST" not in os.environ:
        run_under_emulators()
    main()
