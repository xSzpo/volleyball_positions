"""Playwright test of Report a problem in index.html.

Runs against the Firebase Realtime Database and Auth emulators:

    python src/tests/report_test.py

Without the emulators running, the script restarts itself under
``firebase emulators:exec --only auth,database`` (config in infra/firebase.json;
needs the Firebase CLI and Java, and /opt/homebrew/opt/openjdk/bin is added to PATH).
html2canvas is stubbed in the browser for most checks; one check loads the real,
pinned script from jsdelivr and takes a real screenshot.
"""

import json
import os
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
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

ROOT = Path(__file__).resolve().parents[2]
PROJECT = "ksv-volleyball-xszpo"
NAMESPACE = f"{PROJECT}-default-rtdb"
PORTS = (9000, 9099)
NAME, CODE = "Zed Secretname", "482715"
SEED = (
    "localStorage.setItem('ksv51:role', JSON.stringify('OH1'));"
    f"localStorage.setItem('ksv51:onName', JSON.stringify('{NAME}'));"
    f"localStorage.setItem('ksv51:room', JSON.stringify('{CODE}'))"
)
STUB = """
// Clones the page as html2canvas does, runs onclone on it and returns every rendered, not hidden
// element whose own text or input value holds a secret, plus "pReady" if that button is hidden.
const cloneLeaks = (onclone, secrets) => {
    const frame = document.createElement('iframe');
    frame.style.cssText = 'position:fixed;left:0;top:0;width:390px;height:664px;visibility:hidden';
    document.body.appendChild(frame);
    const doc = frame.contentDocument;
    doc.replaceChild(doc.importNode(document.documentElement, true), doc.documentElement);
    onclone(doc);
    const shown = (el) => el.getClientRects().length > 0
        && doc.defaultView.getComputedStyle(el).visibility !== 'hidden';
    const has = (text) => secrets.some((x) => (text || '').includes(x));
    const leaks = [];
    doc.body.querySelectorAll('*').forEach((el) => {
        const own = [...el.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join('');
        if (has(own) && shown(el)) leaks.push(el.id || el.className || el.tagName);
    });
    const live = [...document.querySelectorAll('input')];
    doc.querySelectorAll('input').forEach((el, i) => {
        if (has(live[i].value) && shown(el)) leaks.push(el.id || 'input');
    });
    const ready = doc.getElementById('pReady');
    if (ready && ready.getClientRects().length && !shown(ready)) leaks.push('pReady');
    frame.remove();
    return leaks;
};
window.html2canvas = async (el, opts) => {
    window.h2cCalls = (window.h2cCalls || 0) + 1;
    window.h2cOpts = { width: opts.width, height: opts.height, scale: opts.scale,
                       ignores: opts.ignoreElements(document.getElementById('reportSheet')) };
    if (window.h2cSecrets) window.h2cLeaks = cloneLeaks(opts.onclone, window.h2cSecrets);
    if (window.h2cMode === 'throw') throw new Error('capture failed');
    const c = document.createElement('canvas');
    c.width = Math.round(opts.width * opts.scale);
    c.height = Math.round(opts.height * opts.scale);
    const g = c.getContext('2d');
    if (window.h2cMode === 'noise') {
        const img = g.createImageData(c.width, c.height);
        for (let i = 0; i < img.data.length; i++) img.data[i] = Math.random() * 256;
        g.putImageData(img, 0, 0);
    } else {
        g.fillStyle = '#3a7';
        g.fillRect(0, 0, c.width, c.height);
    }
    return c;
};
"""
KEYS = {"comment", "createdAt", "tab", "role", "rules", "view", "theme", "viewport", "ua", "version", "flags"}
SHOT_CHARS = 333000
FAIL: list[str] = []


def fail(message: str) -> None:
    FAIL.append(message)
    print("FAIL:", message, flush=True)


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


def admin(emulator_db: str, path: str) -> Any:
    """Reads the emulator database as an admin, bypassing the rules."""
    request = urllib.request.Request(
        f"http://{emulator_db}/{path}.json?ns={NAMESPACE}", headers={"Authorization": "Bearer owner"}
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read() or b"null")


def serve() -> str:
    """Serves the repository root over HTTP and returns the base URL."""

    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Quiet, directory=str(ROOT)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_address[1]}"


def phone(browser: Browser, url: str, errors: list[str], stub: bool = True, width: int = 390) -> tuple[Page, list[str]]:
    """Opens the app on a phone 664 px high; returns the page and the html2canvas requests it makes."""
    context = browser.new_context(viewport={"width": width, "height": 664}, is_mobile=True, has_touch=True)
    page = context.new_page()
    page.add_init_script(SEED)
    if stub:
        page.add_init_script(STUB)
    requests: list[str] = []
    page.on("request", lambda r: requests.append(r.url) if "html2canvas" in r.url else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(url)
    page.wait_for_timeout(300)
    return page, requests


def open_sheet(page: Page, timeout: int = 5000) -> None:
    """Opens the sheet from the header icon, or from the role list below 480 px, and waits for the screenshot."""
    if page.is_visible("#reportBtn"):
        page.click("#reportBtn")
    else:
        page.click("#roleChip")
        page.click("#reportItem")
    page.wait_for_function(
        "document.getElementById('reportShotNote').textContent !== 'Taking a screenshot…'", timeout=timeout
    )


def reports(emulator_db: str) -> dict[str, dict[str, Any]]:
    return admin(emulator_db, "reports") or {}


def send(page: Page, text: str, expect: str) -> None:
    page.fill("#reportText", text)
    page.click("#reportSend")
    page.wait_for_function(f"document.getElementById('reportMsg').textContent === {json.dumps(expect)}", timeout=20000)


def wait_closed(page: Page, what: str) -> None:
    """Fails unless the sheet closes by itself within 2.5 s of the "Thanks, sent." line."""
    try:
        page.wait_for_function("!document.getElementById('reportSheet').open", timeout=2500)
    except PlaywrightTimeoutError:
        fail(f"the sheet stays open after {what}")


def focused(page: Page, element_id: str) -> bool:
    """Waits up to 1 s for focus on ``element_id``; the dialog's close event, which moves it, is a queued task."""
    try:
        page.wait_for_function(f"document.activeElement.id === {json.dumps(element_id)}", timeout=1000)
    except PlaywrightTimeoutError:
        return False
    return True


def db_call(page: Page, script: str) -> str:
    """Runs ``script`` with ``db`` and a valid ``report()`` bound in the page; returns "ok" or the error code."""
    return str(
        page.evaluate(
            f"""async () => {{
                const db = firebase.database();
                const report = (extra) => ({{ ...window.ksvReport.context(), comment: "x",
                    createdAt: firebase.database.ServerValue.TIMESTAMP, ...extra }});
                try {{ {script}; return "ok"; }} catch (e) {{ return e.code || String(e); }}
            }}"""
        )
    )


def check_sheet(browser: Browser, url: str, emulator_db: str, errors: list[str]) -> Page:
    """The icon, the sheet, the stubbed capture, the required comment and the sent report's shape."""
    page, requests = phone(browser, url, errors)
    if page.is_visible("#reportSheet"):
        fail("the sheet is open before a tap")
    if page.is_visible("#reportBtn"):
        fail("the report icon is in the 390 px header row")
    for tab in ("#tabDrill", "#tabGame", "#tabSets", "#tabLearn"):
        page.click(tab)
        page.click("#roleChip")
        box = page.locator("#reportItem").bounding_box()
        if box is None or box["height"] < 44 or box["y"] + box["height"] > 664:
            fail(f"the role list has no 44 px Report a problem row on {tab}: {box}")
        page.click("#roleChip")
    page.click('.rot[data-i="2"]')
    page.click('.ph[data-k="rec"]')
    open_sheet(page)
    if not page.evaluate("document.getElementById('reportSheet').open"):
        fail("the role list row did not open the sheet")
    if page.is_visible("#setup"):
        fail("the role list stays open over the screenshot")
    opts = page.evaluate("window.h2cOpts")
    if page.evaluate("window.h2cCalls") != 1 or opts["width"] != 390 or opts["height"] != 664 or not opts["ignores"]:
        fail(f"the capture is not the visible app without the sheet: {opts}")
    if max(opts["width"], opts["height"]) * opts["scale"] > 1080:
        fail(f"the capture is over 1080 px on the long side: {opts}")
    src = page.get_attribute("#reportShot", "src") or ""
    if not page.is_visible("#reportShot") or not src.startswith("data:image/jpeg;base64,"):
        fail("no JPEG screenshot preview")
    if requests:
        fail(f"html2canvas was fetched while the page already had it: {requests}")
    send_box = page.locator("#reportSend").bounding_box()
    assert send_box is not None
    if send_box["y"] + send_box["height"] > 664 or send_box["height"] < 44:
        fail(f"Send is off a 390 x 664 screen or under 44 px: {send_box}")
    tag = page.inner_text("#learnTag")
    page.focus("#reportText")
    page.keyboard.press("ArrowRight")
    if page.inner_text("#learnTag") != tag:
        fail("an arrow key in the comment box changed the rotation")

    page.fill("#reportText", "   ")
    page.click("#reportSend")
    page.wait_for_timeout(300)
    if "Write a few words" not in page.inner_text("#reportMsg") or reports(emulator_db):
        fail(f"an empty comment was sent or not asked for: {page.inner_text('#reportMsg')!r}")
    if page.evaluate("document.activeElement.id") != "reportText":
        fail("an empty comment does not focus the comment box")

    send(page, "The ball is wrong in R3", "Thanks, sent.")
    if not page.evaluate("document.getElementById('reportSheet').open") or not page.is_visible("#reportMsg"):
        fail("the sheet closes before Thanks, sent. is shown")
    if page.input_value("#reportText") or not page.is_disabled("#reportSend"):
        fail("after a send the comment is not cleared or Send is not disabled")
    sent = reports(emulator_db)
    if len(sent) != 1:
        fail(f"expected one report, got {len(sent)}")
    report = next(iter(sent.values()))
    if set(report) != KEYS | {"image"}:
        fail(f"report fields are {sorted(report)}")
    if report["comment"] != "The ball is wrong in R3" or report["tab"] != "learn" or report["role"] != "OH1":
        fail(f"report content is wrong: { {k: report[k] for k in ('comment', 'tab', 'role')} }")
    if report["rules"] != "simple" or report["theme"] != "light" or report["version"] != "2":
        fail(f"report context is wrong: { {k: report[k] for k in ('rules', 'theme', 'version')} }")
    if report["view"] != "R3 rec" or not report["viewport"].startswith("390x664@"):
        fail(f"report view or viewport is wrong: {report['view']!r} {report['viewport']!r}")
    if report["flags"].get("bug-report") is not True or not isinstance(report["createdAt"], int):
        fail(f"report flags or createdAt are wrong: {report['flags']} {report['createdAt']}")
    if report["image"] != src:
        fail("the sent image is not the preview")
    uid = str(page.evaluate("firebase.auth().currentUser.uid"))
    payload = json.dumps(report)
    for secret in (uid, NAME, "Secretname", CODE):
        if secret in payload:
            fail(f"the report carries {secret!r}")
    wait_closed(page, "a good send")
    if not focused(page, "roleChip"):
        fail("the sheet closing after a send does not return focus to the role button")

    open_sheet(page)
    if page.input_value("#reportText") or page.inner_text("#reportCancel").strip().lower() != "cancel":
        fail("the sheet after a send does not open with an empty comment and Cancel")
    if page.inner_text("#reportMsg").strip() or page.is_disabled("#reportSend"):
        fail("the sheet after a send opens with a message or Send disabled")
    if page.evaluate("window.h2cCalls") != 2 or not page.is_visible("#reportShot"):
        fail("the sheet after a send does not take a fresh screenshot")
    page.keyboard.press("Escape")
    if page.evaluate("document.getElementById('reportSheet').open"):
        fail("Escape did not close the sheet")
    if not focused(page, "roleChip"):
        fail("closing the sheet does not return focus to the role button")

    page.click("#tabDrill")
    open_sheet(page)
    page.uncheck("#reportIncl")
    if page.is_visible("#reportShot"):
        fail("the preview stays with Include screenshot off")
    send(page, "No picture please", "Thanks, sent.")
    plain = [r for r in reports(emulator_db).values() if r["comment"] == "No picture please"]
    if len(plain) != 1 or "image" in plain[0] or plain[0]["tab"] != "drill" or not plain[0]["view"].startswith("R"):
        fail(f"the report without a screenshot is wrong: {plain}")
    page.keyboard.press("Escape")
    if page.evaluate("document.getElementById('reportSheet').open"):
        fail("Escape after a send did not close the sheet")

    page.evaluate("window.h2cMode = 'throw'")
    open_sheet(page)
    page.wait_for_timeout(1500)
    if not page.evaluate("document.getElementById('reportSheet').open"):
        fail("a sheet reopened after closing during the Thanks, sent. delay closed by itself")
    if not page.inner_text("#reportShotNote").startswith("No screenshot") or page.is_visible("#reportShot"):
        fail("a failed capture does not say the report goes without a screenshot")
    if not page.is_disabled("#reportIncl"):
        fail("Include screenshot is not disabled without a screenshot")
    send(page, "Capture broke", "Thanks, sent.")
    broke = [r for r in reports(emulator_db).values() if r["comment"] == "Capture broke"]
    if len(broke) != 1 or "image" in broke[0]:
        fail(f"a failed capture did not send without an image: {broke}")
    wait_closed(page, "a send without a screenshot")

    page.evaluate("window.h2cMode = 'noise'")
    open_sheet(page)
    noisy = page.get_attribute("#reportShot", "src") or ""
    if noisy and len(noisy) > SHOT_CHARS:
        fail(f"a busy screenshot is {len(noisy)} characters, over {SHOT_CHARS}")
    page.click("#reportCancel")
    page.evaluate("window.h2cMode = ''")
    return page


def check_failure(browser: Browser, url: str, emulator_db: str, errors: list[str]) -> None:
    """Without a connection the sheet says so and keeps the comment; Send again works."""
    page, _ = phone(browser, url, errors)
    page.route("**/firebasejs/**", lambda route: route.abort())
    open_sheet(page)
    send(page, "Offline report", "Could not send. Try again.")
    page.wait_for_timeout(1500)
    if not page.evaluate("document.getElementById('reportSheet').open"):
        fail("a failed send closed the sheet")
    if page.input_value("#reportText") != "Offline report":
        fail("a failed send lost the comment")
    if any(r["comment"] == "Offline report" for r in reports(emulator_db).values()):
        fail("a failed send still wrote a report")
    page.unroute("**/firebasejs/**")
    page.click("#reportSend")
    page.wait_for_function("document.getElementById('reportMsg').textContent === 'Thanks, sent.'", timeout=20000)
    wait_closed(page, "a send after a failed one")
    page.context.close()


def check_retry(page: Page, emulator_db: str) -> None:
    """A retry after a write that timed out but landed says sent and leaves one report."""
    page.click("#tabLearn")
    open_sheet(page)
    page.evaluate("firebase.database().goOffline()")
    send(page, "Retry after a timeout", "Could not send. Try again.")
    page.evaluate("firebase.database().goOnline()")
    landed = []
    for _ in range(50):
        landed = [r for r in reports(emulator_db).values() if r["comment"] == "Retry after a timeout"]
        if landed:
            break
        time.sleep(0.2)
    if len(landed) != 1:
        fail(f"the queued write did not land once: {len(landed)}")
    page.click("#reportSend")
    page.wait_for_function("document.getElementById('reportMsg').textContent === 'Thanks, sent.'", timeout=20000)
    copies = [r for r in reports(emulator_db).values() if r["comment"] == "Retry after a timeout"]
    if len(copies) != 1:
        fail(f"a retry after a timeout gave {len(copies)} reports")
    wait_closed(page, "a retry that landed")


def check_private(browser: Browser, url: str, errors: list[str]) -> None:
    """The screenshot hides player names and the room code on the Match screens that show them."""
    page, _ = phone(browser, url, errors)
    page.evaluate(f"window.h2cSecrets = {json.dumps(['Secretname', 'Quin', '482715', '482 715'])}")
    page.click("#tabGame")

    def leaks(where: str) -> None:
        page.evaluate("window.h2cLeaks = null")
        open_sheet(page)
        found = page.evaluate("window.h2cLeaks")
        if found is None or found:
            fail(f"the screenshot of {where} shows a name, a code or hides Continue: {found}")
        page.click("#reportCancel")

    page.check('input[name="gPlayers"][value="online"]')
    page.fill("#onCode", "482715")
    leaks("the online setup")
    page.check('input[name="gPlayers"][value="mp"]')
    page.fill('#mpList input[data-k="0"]', NAME)
    page.fill('#mpList input[data-k="1"]', "Quin Hidden")
    leaks("the same-device setup")
    page.click("#gStart")
    leaks("the pass screen")
    page.click("#pReady")
    leaks("a same-device turn")
    page.context.close()


def check_rules(page: Page, emulator_db: str) -> None:
    """The rules allow a valid create only: no read, update, delete, oversize or unknown field."""
    request = urllib.request.Request(
        f"http://{emulator_db}/reports.json?ns={NAMESPACE}", data=b'{"comment": "x"}', method="POST"
    )
    try:
        urllib.request.urlopen(request)
        fail("an unauthenticated report write was accepted")
    except urllib.error.HTTPError as e:
        if e.code != 401:
            fail(f"an unauthenticated report write gave {e.code}")
    some = next(iter(reports(emulator_db)))

    def push_image(base64_chars: int) -> str:
        image = f'"data:image/jpeg;base64," + "A".repeat({base64_chars})'
        return f'await db.ref("reports").push(report({{image: {image}}}))'

    denied = {
        "read all": 'await db.ref("reports").once("value")',
        "read one": f'await db.ref("reports/{some}").once("value")',
        "update": f'await db.ref("reports/{some}").update({{comment: "changed"}})',
        "overwrite": f'await db.ref("reports/{some}").set(report({{}}))',
        "child write": f'await db.ref("reports/{some}/comment").set("changed")',
        "delete": f'await db.ref("reports/{some}").remove()',
        "image oversize": push_image(349978),
        "image png": 'await db.ref("reports").push(report({image: "data:image/png;base64,AAAA"}))',
        "comment oversize": 'await db.ref("reports").push(report({comment: "x".repeat(1001)}))',
        "comment empty": 'await db.ref("reports").push(report({comment: ""}))',
        "no comment": 'const r = report({}); delete r.comment; await db.ref("reports").push(r)',
        "old createdAt": 'await db.ref("reports").push(report({createdAt: 1}))',
        "extra field": 'await db.ref("reports").push(report({name: "Zed"}))',
        "bad role": 'await db.ref("reports").push(report({role: "Zed"}))',
        "flags not an object": 'await db.ref("reports").push(report({flags: true}))',
        "bad flag": 'await db.ref("reports").push(report({flags: {"bug-report": "yes"}}))',
        "bad key": 'await db.ref("reports/short").set(report({}))',
    }
    for name, script in denied.items():
        result = db_call(page, script)
        if "PERMISSION_DENIED" not in result.upper():
            fail(f"the rules allow {name}: {result}")
    allowed = {
        "image at the limit": push_image(349977),
        "comment at the limit": 'await db.ref("reports").push(report({comment: "x".repeat(1000)}))',
    }
    for name, script in allowed.items():
        result = db_call(page, script)
        if result != "ok":
            fail(f"the rules deny {name}: {result}")


def check_real_capture(browser: Browser, url: str, errors: list[str]) -> None:
    """The real html2canvas loads once, with its SRI, and takes a JPEG of at most 1080 px and SHOT_CHARS."""
    page, requests = phone(browser, url, errors, stub=False)
    if requests or page.locator("script[src*=html2canvas]").count():
        fail("html2canvas loaded before the first tap")
    open_sheet(page, 30000)
    src = page.get_attribute("#reportShot", "src") or ""
    if not src.startswith("data:image/jpeg;base64,") or len(src) > SHOT_CHARS:
        fail(f"the real capture gave no JPEG under {SHOT_CHARS} characters: {page.inner_text('#reportShotNote')!r}")
    size = page.evaluate(
        "[document.getElementById('reportShot').naturalWidth, document.getElementById('reportShot').naturalHeight]"
    )
    if max(size) > 1080 or min(size) < 300:
        fail(f"the real screenshot is {size}")
    script = page.locator("script[src*=html2canvas]")
    if script.count() != 1 or not (script.get_attribute("integrity") or "").startswith("sha384-"):
        fail("html2canvas is not one script with SRI")
    page.click("#reportCancel")
    open_sheet(page, 30000)
    if len(requests) != 1 or page.locator("script[src*=html2canvas]").count() != 1:
        fail(f"html2canvas loaded again on the second tap: {requests}")
    page.context.close()


def check_wide(browser: Browser, url: str, errors: list[str]) -> None:
    """From 480 px the icon sits after the theme button, in the header row, and opens the sheet."""
    page, _ = phone(browser, url, errors, width=720)
    box = page.locator("#reportBtn").bounding_box()
    theme = page.locator("#themeBtn").bounding_box()
    assert box is not None and theme is not None
    if box["width"] < 44 or box["height"] < 44 or box["x"] < theme["x"] + theme["width"] or box["y"] != theme["y"]:
        fail(f"the report icon is not a 44 px target after the theme button: {box} {theme}")
    if page.evaluate("document.documentElement.scrollWidth > innerWidth"):
        fail("the header scrolls sideways with the report icon")
    page.click("#roleChip")
    if page.is_visible("#reportItem"):
        fail("the role list has a report row beside the icon")
    page.click("#roleChip")
    open_sheet(page)
    page.keyboard.press("Escape")
    if not focused(page, "reportBtn"):
        fail("closing the sheet does not return focus to the icon")
    page.context.close()


def check_flag_off(browser: Browser, url: str, errors: list[str]) -> None:
    """With bug-report off neither the icon nor the sheet is in the page."""
    page, _ = phone(browser, url.replace("ff=all", "ff=all,-bug-report"), errors)
    if page.locator("#reportBtn, #reportItem, #reportSheet").count():
        fail("bug-report off leaves the icon or the sheet in the page")
    page.context.close()


def main() -> None:
    """Runs the report scenarios against the emulators."""
    signal.alarm(500)
    emulator_db = os.environ["FIREBASE_DATABASE_EMULATOR_HOST"]
    emulator_auth = os.environ["FIREBASE_AUTH_EMULATOR_HOST"]
    url = f"{serve()}/index.html?emu={emulator_db},{emulator_auth}&ff=all&anim=0"
    errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = check_sheet(browser, url, emulator_db, errors)
        check_retry(page, emulator_db)
        check_rules(page, emulator_db)
        check_private(browser, url, errors)
        check_failure(browser, url, emulator_db, errors)
        check_real_capture(browser, url, errors)
        check_wide(browser, url, errors)
        check_flag_off(browser, url, errors)
        browser.close()
    if errors:
        fail(f"page errors: {errors}")
    print(f"REPORT TEST: {'ok' if not FAIL else f'{len(FAIL)} failures'}")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    if "FIREBASE_DATABASE_EMULATOR_HOST" not in os.environ:
        run_under_emulators()
    main()
