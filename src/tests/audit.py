"""Check the rotation data for consistency, under both rule sets.

Covers rotation order, the Simplified middle-pair reset into R3 and R6,
overlap legality of every reception shape, the serve lineups, the base
defence spots, the Learn move captions and the walk-through tables in
docs/v2.md section 5. Prints
"DATA AUDIT: no issues" on success.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from data import ATTACK_LINE as AL  # noqa: E402
from data import (  # noqa: E402
    BASE_DEF,
    MIDDLES,
    ROWS,
    RULES_MODES,
    SETS,
    UNCONFIRMED_SETS,
    ZONE_ORDER,
    Row,
    RulesMode,
    lineup,
    middle_pair,
    rotation_zones,
    server,
)

ORDER = ZONE_ORDER
BASE_ZONE = {"OH1": 4, "OH2": 4, "MB": 3, "MB1": 3, "MB2": 3, "S": 2, "OP": 2}
RESETS = (2, 5)
issues: list[str] = []


def next_zone(zone: int) -> int:
    return 6 if zone == 1 else zone - 1


def zones(r: Row, real: bool = True) -> dict[int, str]:
    z = rotation_zones(r)
    if real and r["liberofor"]:
        z = {k: (r["liberofor"] if p == "L" else p) for k, p in z.items()}
    return z


def check_rotation_order(mode: RulesMode) -> None:
    """Everyone moves one zone clockwise, except the Simplified middle pair when it resets."""
    for i in range(6):
        a, b = lineup(i, mode), lineup((i + 1) % 6, mode)
        za, zb = zones(a, real=mode == "official"), zones(b, real=mode == "official")
        for zz, p in za.items():
            if mode == "simple" and p in ("MB", "L"):
                continue
            if zb[next_zone(zz)] != p:
                issues.append(
                    f"{mode} rotation {a['name']}->{b['name']}: {p} zone {zz} should go to {next_zone(zz)}, "
                    f"found {zb[next_zone(zz)]}"
                )


def check_middle_pair() -> None:
    """Simplified: MB always front, L always back; the pair rotates, and resets into R3 and R6."""
    for i in range(6):
        r = lineup(i, "simple")
        front, back = middle_pair(i)
        z = rotation_zones(r)
        if z[front] != "MB" or z[back] != "L":
            issues.append(f"simple {r['name']}: middle pair zones {front}/{back} hold {z[front]}/{z[back]}")
        if "MB" not in r["front"] or "L" not in r["back"]:
            issues.append(f"simple {r['name']}: MB not front or L not back")
        if any(p in MIDDLES for p in r["front"] + r["back"] + [q for q, *_ in r["rec"] + r["ar"]]):
            issues.append(f"simple {r['name']}: MB1 or MB2 left in the lineup")
        prev_front, prev_back = middle_pair((i + 5) % 6)
        if i in RESETS:
            if (prev_front, prev_back, front, back) != (2, 5, 4, 1):
                issues.append(f"simple {r['name']}: middle pair should reset from 2/5 to 4/1")
        elif (front, back) != (next_zone(prev_front), next_zone(prev_back)):
            issues.append(f"simple {r['name']}: middle pair did not rotate")


def check_row(i: int, mode: RulesMode) -> None:
    r = lineup(i, mode)
    tag = f"{mode} {r['name']}"
    a = zones(r)
    sz = [k for k, p in a.items() if p == "S"][0]
    if sz != r["setter"]:
        issues.append(f"{tag} setter zone {sz} != label {r['setter']}")
    if mode == "official":
        if r["liberofor"] not in MIDDLES or r["liberofor"] in r["front"] or r["liberofor"] in r["back"]:
            issues.append(f"{tag}: libero replacement wrong")
        other = "MB1" if r["liberofor"] == "MB2" else "MB2"
        if other not in r["front"]:
            issues.append(f"{tag}: other middle not front row")
    elif r["liberofor"] not in ("", "SUB") or (r["liberofor"] == "SUB") != (i in RESETS):
        issues.append(f"{tag}: libero replaces {r['liberofor']!r}, expected SUB only in R3 and R6")
    # overlap in reception
    zp = rotation_zones(r)
    pos = {p: (x, y) for p, x, y in r["rec"]}
    if set(pos) != set(zp.values()):
        issues.append(f"{tag}: rec players mismatch")
        return
    for f, bk in [(4, 5), (3, 6), (2, 1)]:
        if not pos[zp[f]][1] < pos[zp[bk]][1]:
            issues.append(f"{tag} overlap: {zp[f]} (z{f}) not in front of {zp[bk]} (z{bk})")
    for row in ([4, 3, 2], [5, 6, 1]):
        for left, right in zip(row, row[1:], strict=False):
            if not pos[zp[left]][0] < pos[zp[right]][0]:
                issues.append(f"{tag} overlap: {zp[left]} (z{left}) not left of {zp[right]} (z{right})")
    # after reception
    arp = {p: k for p, x, y, k in r["ar"]}
    if set(arp) != set(pos):
        issues.append(f"{tag}: AR players mismatch")
    for p, k in arp.items():
        if k == "front" and p not in r["front"]:
            issues.append(f"{tag}: {p} attacks at net but is back row")
        if k == "back" and p in r["front"]:
            issues.append(f"{tag}: {p} back-row attack but front row")
        if p in r["front"] and p != "S" and k != "front":
            issues.append(f"{tag}: front-row {p} not attacking")
    for p, _x, y, k in r["ar"]:
        if k == "back" and y <= AL:
            issues.append(f"{tag}: back-row attacker {p} in front of 3m line")
    # serve
    sf, sb = r["serve"]
    serving = server(i, mode)
    on = set(r["front"] + r["back"])
    if zp[1] == "L":
        on = (on - {"L"}) | {serving}
    if serving == "L":
        issues.append(f"{tag}: the libero serves")
    if serving != zones(r, real=False)[1] and zp[1] != "L":
        issues.append(f"{tag}: server {serving} is not in zone 1")
    if set(sf + sb) != on:
        issues.append(f"{tag}: serve players {set(sf + sb)} != expected {on}")
    if set(sf) != set(r["front"]):
        issues.append(f"{tag}: serve front row differs from rotation front row")
    for p, z in zip(sf, [4, 3, 2], strict=False):
        if BASE_ZONE[p] != z:
            issues.append(f"{tag} serve: {p} at {z}, expected {BASE_ZONE[p]}")
    if "S" in sb and sb[2] != "S" or "OP" in sb and sb[2] != "OP":
        issues.append(f"{tag} serve: S/OP not in zone 1")
    base = dict(zip([4, 3, 2, 5, 6, 1], sf + sb, strict=True))
    if "L" in base.values() and base[5] != "L":
        issues.append(f"{tag} serve: libero not in zone 5")
    if zp[1] == "L" and base[6] != serving:
        issues.append(f"{tag} serve: {serving} serves for the libero but does not defend zone 6")
    if mode == "simple" and ("SUB" in base.values()) != (i in RESETS):
        issues.append(f"{tag} serve: SUB should be on court only in R3 and R6")
    if base[1 if r["setter"] in (1, 6, 5) else 2] != "S":
        issues.append(f"{tag} serve: setter in the wrong base zone")


MOVE_MAX = 78
AR_WORDS = {"set": ["setting spot"], "front": ["3 m line"], "back": ["zone 1", "back-row attack"], None: ["cover"]}


def check_moves(i: int, mode: RulesMode) -> None:
    """Every player has one short move caption per phase, and it matches their spot."""
    r = lineup(i, mode)
    front, back = r["serve"]
    on_court = {
        "serve": front + back,
        "rec": [p for p, _, _ in r["rec"]],
        "ar": [p for p, _, _, _ in r["ar"]],
    }
    if set(r["move"]) != set(on_court):
        issues.append(f"{mode} {r['name']}: move phases {sorted(r['move'])}")
    for phase, players in on_court.items():
        notes = r["move"].get(phase, {})
        if set(notes) != set(players):
            issues.append(f"{mode} {r['name']} {phase}: move notes for {sorted(notes)}, on court {sorted(players)}")
        for p, text in notes.items():
            if len(text) > MOVE_MAX or not text.endswith("."):
                issues.append(f"{mode} {r['name']} {phase} {p}: caption over {MOVE_MAX} characters or unfinished")
    for zone, p in zip(ORDER, front + back, strict=True):
        text = r["move"]["serve"].get(p, "")
        if f"zone {zone}" not in text or text.startswith("Serve") != (p == server(i, mode)):
            issues.append(f"{mode} {r['name']} serve {p}: caption does not send them to zone {zone}: {text!r}")
    for p, _, _, kind in r["ar"]:
        text = r["move"]["ar"].get(p, "")
        if not all(word in text for word in AR_WORDS[kind]):
            issues.append(f"{mode} {r['name']} ar {p} ({kind}): caption lacks {AR_WORDS[kind]}: {text!r}")


def cell_lineup(cell: str) -> list[str] | None:
    """Reads the first 'A B C / D E F' lineup in a table cell; L(MB2) reads as L."""
    m = re.search(
        r"((?:[A-Z][A-Z0-9]*(?:\([A-Z0-9]+\))? ){2}[A-Z][A-Z0-9]*(?:\([A-Z0-9]+\))?) / "
        r"((?:[A-Z][A-Z0-9]*(?:\([A-Z0-9]+\))? ){2}[A-Z][A-Z0-9]*(?:\([A-Z0-9]+\))?)",
        cell,
    )
    if not m:
        return None
    return [re.sub(r"\(.*\)", "", p) for p in (m[1] + " " + m[2]).split()]


def walkthrough(heading: str) -> list[list[str]]:
    doc = (ROOT / "docs" / "v2.md").read_text()
    part = doc.split(f"### Walk-through: {heading}", 1)[1].split("\n### ", 1)[0]
    return [[c.strip() for c in line.strip("|").split("|")] for line in part.splitlines() if re.match(r"\| R\d", line)]


def check_walkthrough(mode: RulesMode, heading: str) -> None:
    """The docs/v2.md walk-through tables must match lineup(), rotation by rotation."""
    table = walkthrough(heading)
    if len(table) != 6:
        issues.append(f"walk-through {heading}: {len(table)} rows, expected 6")
        return
    for i, cells in enumerate(table):
        r = lineup(i, mode)
        rotation, serve = cell_lineup(cells[1]), cell_lineup(cells[2])
        rot_real = r["front"] + r["back"]
        if mode == "official" and i in RESETS:
            rot_real = [server(i, mode) if p == "L" else p for p in rot_real]
        if rotation is not None and rotation != rot_real:
            issues.append(f"walk-through {heading} {r['name']}: rotation {rotation} != {rot_real}")
        if serve is not None and serve != r["serve"][0] + r["serve"][1]:
            issues.append(f"walk-through {heading} {r['name']}: serve {serve} != {r['serve'][0] + r['serve'][1]}")
        reset = re.search(r"MB (\d) → (\d), L (\d) → (\d)", cells[1])
        if mode == "simple" and (reset is not None) != (i in RESETS):
            issues.append(f"walk-through {heading} {r['name']}: pair reset text only in R3 and R6")
        if reset:
            (pf, pb), (f, b) = middle_pair(i - 1), middle_pair(i)
            if [int(x) for x in reset.groups()] != [pf, f, pb, b]:
                issues.append(f"walk-through {heading} {r['name']}: reset {reset[0]} != MB {pf} → {f}, L {pb} → {b}")
        if mode == "simple" and i in RESETS and "SUB" not in cells[2]:
            issues.append(f"walk-through {heading} {r['name']}: SUB should serve")


for mode in RULES_MODES:
    check_rotation_order(mode)
    for i in range(6):
        check_row(i, mode)
        check_moves(i, mode)
check_middle_pair()
check_walkthrough("official", "Official")
check_walkthrough("simple", "Simplified KSV")
for i in range(6):
    official, simple = lineup(i, "official"), lineup(i, "simple")
    coords = [(x, y) for _, x, y in official["rec"]], [(x, y) for _, x, y in simple["rec"]]
    if coords[0] != coords[1] or [a[1:] for a in official["ar"]] != [a[1:] for a in simple["ar"]]:
        issues.append(f"{official['name']}: Simplified moved a spot; it may only rename players")
if set(BASE_DEF) != set(ORDER):
    issues.append(f"base defence zones {sorted(BASE_DEF)} != {sorted(ORDER)}")
for z, (_x, y, kind) in BASE_DEF.items():
    front = z in (4, 3, 2)
    if front and not y < AL or not front and not y > AL:
        issues.append(f"base defence zone {z} at y {y} on the wrong side of the 3 m line")
    if kind != ("zone" if front else None):
        issues.append(f"base defence zone {z} has kind {kind}")
SET_NAMES = [s[0] for s in SETS]
for name in UNCONFIRMED_SETS:
    if name not in SET_NAMES:
        issues.append(f"unconfirmed set {name} is not in SETS")
if len(set(SET_NAMES)) != len(SET_NAMES) or len({s[1:3] for s in SETS}) != len(SETS):
    issues.append("two sets share a name or a path")
for name in ("Po", "Til"):
    if name in SET_NAMES:
        issues.append(f"removed set {name} is in SETS")


def third(x: float) -> str:
    return "left" if x < 1 / 3 else "right" if x > 2 / 3 else "mid"


BACK_THIRDS = sorted(third(s[1]) for s in SETS if s[3] == "back")
if BACK_THIRDS != ["left", "mid", "right"]:
    issues.append(f"back-row sets land in {BACK_THIRDS}, expected one per back zone")
if len(ROWS) != 6:
    issues.append(f"{len(ROWS)} rotations, expected 6")
print("\n".join(issues) if issues else "DATA AUDIT: no issues")
sys.exit(1 if issues else 0)
