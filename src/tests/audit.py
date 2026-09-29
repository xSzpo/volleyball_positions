"""Check the rotation data for consistency.

Covers rotation order, overlap legality of every reception shape, the
serve lineups and the base defence spots. Prints "DATA AUDIT: no issues" on success.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from data import ATTACK_LINE as AL  # noqa: E402
from data import BASE_DEF, ROWS, SETS, UNCONFIRMED_SETS, Row  # noqa: E402

ORDER = [4, 3, 2, 5, 6, 1]
issues: list[str] = []


def zones(r: Row, real: bool = True) -> dict[int, str]:
    ps = r["front"] + r["back"]
    z = {ORDER[i]: p for i, p in enumerate(ps)}
    if real:
        z = {k: (r["liberofor"] if p == "L" else p) for k, p in z.items()}
    return z


# a. rotation order clockwise
for i in range(6):
    a = zones(ROWS[i])
    b = zones(ROWS[(i + 1) % 6])
    for zz, p in a.items():
        nz = 6 if zz == 1 else zz - 1
        if b[nz] != p:
            issues.append(
                f"rotation {ROWS[i]['name']}->{ROWS[(i + 1) % 6]['name']}: "
                f"{p} zone {zz} should go to {nz}, found {b[nz]}"
            )
    # f setter label
    sz = [k for k, p in a.items() if p == "S"][0]
    if sz != ROWS[i]["setter"]:
        issues.append(f"{ROWS[i]['name']} setter zone {sz} != label {ROWS[i]['setter']}")
    # b libero replaces back-row middle
    r = ROWS[i]
    if r["liberofor"] not in ("MB1", "MB2") or r["liberofor"] in r["front"] or r["liberofor"] in r["back"]:
        issues.append(f"{r['name']}: libero replacement wrong")
    other = "MB1" if r["liberofor"] == "MB2" else "MB2"
    if other not in r["front"]:
        issues.append(f"{r['name']}: other middle not front row")
    # c overlap in reception
    zp = {ORDER[j]: p for j, p in enumerate(r["front"] + r["back"])}
    pos = {p: (x, y) for p, x, y in r["rec"]}
    if set(pos) != set(zp.values()):
        issues.append(f"{r['name']}: rec players mismatch")
    for f, bk in [(4, 5), (3, 6), (2, 1)]:
        if not pos[zp[f]][1] < pos[zp[bk]][1]:
            issues.append(f"{r['name']} overlap: {zp[f]} (z{f}) not in front of {zp[bk]} (z{bk})")
    for row in ([4, 3, 2], [5, 6, 1]):
        for left, right in zip(row, row[1:], strict=False):
            if not pos[zp[left]][0] < pos[zp[right]][0]:
                issues.append(f"{r['name']} overlap: {zp[left]} (z{left}) not left of {zp[right]} (z{right})")
    # d AR
    arp = {p: k for p, x, y, k in r["ar"]}
    if set(arp) != set(pos):
        issues.append(f"{r['name']}: AR players mismatch")
    for p, k in arp.items():
        if k == "front" and p not in r["front"]:
            issues.append(f"{r['name']}: {p} attacks at net but is back row")
        if k == "back" and p in r["front"]:
            issues.append(f"{r['name']}: {p} back-row attack but front row")
        if p in r["front"] and p != "S" and k != "front":
            issues.append(f"{r['name']}: front-row {p} not attacking")
    for p, _x, y, k in r["ar"]:
        if k == "back" and y <= AL:
            issues.append(f"{r['name']}: back-row attacker {p} in front of 3m line")
    # e serve
    sf, sb = r["serve"]
    server = zones(r, False)[1]
    on = set(r["front"] + r["back"])
    if server == "L":
        on = (on - {"L"}) | {r["liberofor"]}
    if set(sf + sb) != on:
        issues.append(f"{r['name']}: serve players {set(sf + sb)} != expected {on}")
    if set(sf) != set(r["front"]):
        issues.append(f"{r['name']}: serve front row differs from rotation front row")
    for p, z in zip(sf, [4, 3, 2], strict=False):
        exp = {"OH1": 4, "OH2": 4, "MB1": 3, "MB2": 3, "S": 2, "OP": 2}[p]
        if exp != z:
            issues.append(f"{r['name']} serve: {p} at {z}, expected {exp}")
    if "S" in sb and sb[2] != "S" or "OP" in sb and sb[2] != "OP":
        issues.append(f"{r['name']} serve: S/OP not in zone 1")
    base = dict(zip([4, 3, 2, 5, 6, 1], sf + sb, strict=True))
    if "L" in base.values() and base[5] != "L":
        issues.append(f"{r['name']} serve: libero not in zone 5")
    if base[1 if r["setter"] in (1, 6, 5) else 2] != "S":
        issues.append(f"{r['name']} serve: setter in the wrong base zone")
if set(BASE_DEF) != set(ORDER):
    issues.append(f"base defence zones {sorted(BASE_DEF)} != {sorted(ORDER)}")
for z, (_x, y, kind) in BASE_DEF.items():
    front = z in (4, 3, 2)
    if front and not y < AL or not front and not y > AL:
        issues.append(f"base defence zone {z} at y {y} on the wrong side of the 3 m line")
    if kind != ("block" if front else None):
        issues.append(f"base defence zone {z} has kind {kind}")
for name in UNCONFIRMED_SETS:
    if name not in [s[0] for s in SETS]:
        issues.append(f"unconfirmed set {name} is not in SETS")
print("\n".join(issues) if issues else "DATA AUDIT: no issues")
sys.exit(1 if issues else 0)
