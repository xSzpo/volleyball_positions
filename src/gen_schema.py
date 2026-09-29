"""Generate the rotation schema cheat sheet as SVG, PNG and PDF in downloads/."""

import math
from pathlib import Path

import cairosvg

from data import ATTACK_LINE as AL
from data import BASE_DEF, ROWS
from pdf import svg_to_pdf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "downloads"


COL = {
    "S": ("#F2B53A", "#1B2A3A"),
    "OP": ("#1E1E1E", "#FFF"),
    "MB1": ("#8E2436", "#FFF"),
    "MB2": ("#8E2436", "#FFF"),
    "OH1": ("#27598C", "#FFF"),
    "OH2": ("#27598C", "#FFF"),
    "L": ("#D63A78", "#FFF"),
}
NAVY = "#1B3350"
ORANGE = "#F08A1C"
RED = "#E03131"
GREEN = "#1FA05A"
GREY = "#7C8A99"
MOVE = "#33414F"
ZONES = {4: (0, 0), 3: (1, 0), 2: (2, 0), 5: (0, 1), 6: (1, 1), 1: (2, 1)}
ORDER = [4, 3, 2, 5, 6, 1]
OVERLAP = [(4, 3), (3, 2), (5, 6), (6, 1), (4, 5), (3, 6), (2, 1)]
XS = [0.17, 0.5, 0.83]
FY, BY = 0.21, 0.71
SERVE_SPOT = (0.88, 1.1)

CW, CH = 280, 190
LABEL_W, GAP, TOP, ROW_H = 160, 40, 350, 246
W = LABEL_W + 4 * CW + 3 * GAP + 50
H = TOP + 6 * ROW_H + 150
o: list[str] = []
a = o.append


def grid(front: list[str], back: list[str]) -> list[tuple[str, float, float]]:
    return [(p, XS[i], FY) for i, p in enumerate(front)] + [(p, XS[i], BY) for i, p in enumerate(back)]


def chip(p: str, cx: float, cy: float, ring: str | None = None) -> str:
    bg, fg = COL[p]
    w = 46 if len(p) > 1 else 34
    s = ""
    if ring:
        s += f'<circle cx="{cx}" cy="{cy}" r="25" fill="none" stroke="{ring}" stroke-width="3"/>'
    return s + (
        f'<rect x="{cx - w / 2}" y="{cy - 14}" width="{w}" height="28" rx="7" fill="{bg}" stroke="#FFF" '
        'stroke-width="1.5"/>'
        f'<text x="{cx}" y="{cy + 5}" text-anchor="middle" font-size="14" font-weight="bold" fill="{fg}">{p}</text>'
    )


def base(x: float, y: float) -> str:
    s = f'<rect x="{x}" y="{y}" width="{CW}" height="{CH}" rx="4" fill="#F3F6F9" stroke="{NAVY}" stroke-width="2"/>'
    s += f'<line x1="{x}" y1="{y}" x2="{x + CW}" y2="{y}" stroke="{NAVY}" stroke-width="6"/>'
    s += (
        f'<line x1="{x}" y1="{y + CH * AL}" x2="{x + CW}" y2="{y + CH * AL}" stroke="#AEBBC8" stroke-width="1.5" '
        'stroke-dasharray="6 5"/>'
    )
    for z, (c, r) in ZONES.items():
        zy = y + (CH * AL - 6 if r == 0 else CH - 7)
        s += (
            f'<text x="{x + (c + 1) * CW / 3 - 7}" y="{zy}" text-anchor="end" font-size="19" font-weight="bold" '
            f'fill="{NAVY}" opacity="0.17">{z}</text>'
        )
    return s


def arrow(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    color: str,
    marker: str,
    dash: str | None = None,
    width: float = 2,
    op: float = 1,
) -> str:
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}"{d} opacity="{op}" '
        f'marker-end="url(#{marker})"/>'
    )


def shorten(
    x1: float, y1: float, x2: float, y2: float, a: float = 16, b: float = 18
) -> tuple[float, float, float, float]:
    L = math.hypot(x2 - x1, y2 - y1) or 1
    ux, uy = (x2 - x1) / L, (y2 - y1) / L
    return x1 + ux * a, y1 + uy * a, x2 - ux * b, y2 - uy * b


a(
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="DejaVu Sans, '
    'Arial, sans-serif">'
)


def mk(i: str, c: str) -> str:
    return (
        f'<marker id="{i}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path '
        f'd="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>'
    )


a("<defs>" + mk("mr", RED) + mk("mg", GREY) + mk("mm", MOVE) + mk("ms", GREEN) + "</defs>")
a(f'<rect width="{W}" height="{H}" fill="#FFF"/>')
a(f'<text x="40" y="62" font-size="32" font-weight="bold" fill="{NAVY}">5-1 system · Receiving rotations</text>')
a(f'<rect x="40" y="76" width="80" height="5" fill="{ORANGE}"/>')
a(
    '<text x="40" y="108" font-size="15" fill="#5A6878">Based on the KSV guide "Receiving positions and movements". '
    "Net at the top of every court, dashed line = 3 m line.</text>"
)
a(
    '<text x="40" y="130" font-size="15" fill="#5A6878">OP = diagonal (D) in the guide. R1 = setter in position 1 '
    "(H1), R2 = H6, R3 = H5, R4 = H4, R5 = H3, R6 = H2.</text>"
)
RULES = [
    ("Three players receive", ["The two outside hitters and the libero", "form the receiving unit."]),
    ("Front-row outside starts left", ["Changes only when the setter", "is in position 1 (R1)."]),
    ("Back row follows the attack", ["Complete the movement shown", "after the attacking action."]),
    ("Opposite goes straight to 1", ["When starting in the back row, prepare", "immediately for the back-row attack."]),
]
a(f'<text x="40" y="170" font-size="15" font-weight="bold" fill="{NAVY}">Rules of thumb</text>')
rw = (W - 80) / 4
for i, (t, lines) in enumerate(RULES):
    rx = 40 + i * rw
    a(
        f'<rect x="{rx}" y="182" width="{rw - 14}" height="84" rx="8" fill="#FFF6EC" stroke="{ORANGE}" '
        'stroke-width="1.5"/>'
    )
    a(
        f'<circle cx="{rx + 20}" cy="204" r="11" fill="{ORANGE}"/><text x="{rx + 20}" y="209" text-anchor="middle" '
        f'font-size="13" font-weight="bold" fill="#FFF">{i + 1}</text>'
    )
    a(f'<text x="{rx + 38}" y="209" font-size="14" font-weight="bold" fill="{NAVY}">{t}</text>')
    for j, ln in enumerate(lines):
        a(f'<text x="{rx + 16}" y="{234 + j * 19}" font-size="13" fill="#33414F">{ln}</text>')
CHECKS = [
    "Where is the setter?",
    "Who is in front/behind and beside me?",
    "Am I on court, or is the libero in?",
    "What is my job after the pass?",
]
a(f'<text x="40" y="298" font-size="15" font-weight="bold" fill="{NAVY}">Before every serve</text>')
cx: float = 232
for i, c in enumerate(CHECKS):
    a(
        f'<circle cx="{cx}" cy="293" r="10" fill="{NAVY}"/><text x="{cx}" y="298" text-anchor="middle" font-size="12" '
        f'font-weight="bold" fill="#FFF">{i + 1}</text><text x="{cx + 16}" y="298" font-size="14" '
        f'fill="#33414F">{c}</text>'
    )
    cx += 16 + len(c) * 7.6 + 34
x0s = [LABEL_W + i * (CW + GAP) + 10 for i in range(4)]
for i, hd in enumerate(["ROTATION", "RECEPTION", "MOVEMENT AFTER RECEPTION", "OUR SERVE: BASE DEFENCE"]):
    a(
        f'<text x="{x0s[i]}" y="{TOP - 14}" font-size="13" font-weight="bold" letter-spacing="1" '
        f'fill="#5A6878">{hd}</text>'
    )

for r, row in enumerate(ROWS):
    y = TOP + r * ROW_H
    a(f'<rect x="40" y="{y + 62}" width="108" height="40" rx="8" fill="none" stroke="{NAVY}" stroke-width="2.5"/>')
    a(
        f'<text x="94" y="{y + 89}" text-anchor="middle" font-size="18" font-weight="bold" fill="{NAVY}">{row["name"]} '
        f"(S{row['setter']})</text>"
    )
    a(f'<text x="94" y="{y + 124}" text-anchor="middle" font-size="12" fill="#5A6878">Setter in {row["setter"]}</text>')
    a(
        f'<text x="94" y="{y + 141}" text-anchor="middle" font-size="12" fill="{COL["L"][0]}">L for '
        f"{row['liberofor']}</text>"
    )
    zmap = {p: ORDER[i] for i, (p, _, _) in enumerate(grid(row["front"], row["back"]))}

    def X(x0: float, v: float) -> float:
        return x0 + v * CW

    def Y(v: float, top: float = y) -> float:
        return top + v * CH

    # 1 rotation
    x0 = x0s[0]
    s = base(x0, y)
    for (a1, b1), (a2, b2) in [
        ((0.27, FY), (0.39, FY)),
        ((0.61, FY), (0.73, FY)),
        ((0.83, 0.31), (0.83, 0.60)),
        ((0.73, BY), (0.61, BY)),
        ((0.39, BY), (0.27, BY)),
        ((0.17, 0.60), (0.17, 0.31)),
    ]:
        s += arrow(X(x0, a1), Y(b1), X(x0, a2), Y(b2), GREY, "mg", op=0.5)
    for p, px, py in grid(row["front"], row["back"]):
        s += chip(p, X(x0, px), Y(py))
    a(s)

    # 2 reception
    x0 = x0s[1]
    s = base(x0, y)
    pos = {zmap[p]: (X(x0, px), Y(py)) for p, px, py in row["rec"]}
    for z1, z2 in OVERLAP:
        (x1, y1), (x2, y2) = pos[z1], pos[z2]
        s += (
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{ORANGE}" stroke-width="1.8" stroke-dasharray="3 '
            '4" opacity="0.7"/>'
        )
    for p, px, py in row["rec"]:
        cx, cy = X(x0, px), Y(py)
        s += chip(p, cx, cy)
        bx = cx - (23 if len(p) > 1 else 17) + 1
        by = cy - 14
        s += (
            f'<circle cx="{bx}" cy="{by}" r="8.5" fill="#FFF" stroke="{ORANGE}" stroke-width="1.8"/>'
            f'<text x="{bx}" y="{by + 4}" text-anchor="middle" font-size="11" font-weight="bold" '
            f'fill="{NAVY}">{zmap[p]}</text>'
        )
    a(s)

    # 3 after reception
    x0 = x0s[2]
    s = base(x0, y)
    recpos = {p: (px, py) for p, px, py in row["rec"]}
    for p, px, py, kind in row["ar"]:
        rx, ry = recpos[p]
        if abs(rx - px) + abs(ry - py) > 0.07:
            x1, y1, x2, y2 = shorten(X(x0, rx), Y(ry), X(x0, px), Y(py))
            s += arrow(
                x1,
                y1,
                x2,
                y2,
                GREEN if kind == "set" else MOVE,
                "ms" if kind == "set" else "mm",
                width=2.2 if kind == "set" else 1.8,
                op=0.8,
            )
            s += (
                f'<circle cx="{X(x0, rx)}" cy="{Y(ry)}" r="3.5" fill="{GREEN if kind == "set" else MOVE}" '
                'opacity=".5"/>'
            )
    for _p, px, py, kind in row["ar"]:
        if kind == "front":
            s += arrow(X(x0, px), Y(py) - 16, X(x0, px), y + 9, RED, "mr", dash="6 4", width=2.5)
        if kind == "back":
            s += arrow(X(x0, px), Y(py) - 16, X(x0, px), Y(AL) + 4, RED, "mr", dash="6 4", width=2.5)
    for p, px, py, kind in row["ar"]:
        s += chip(p, X(x0, px), Y(py), ring=GREEN if kind == "set" else None)
    a(s)

    # 4 serve
    sx = x0s[3] - GAP / 2
    a(f'<line x1="{sx}" y1="{y - 6}" x2="{sx}" y2="{y + CH + 6}" stroke="{NAVY}" stroke-width="2.5"/>')
    x0 = x0s[3]
    s = base(x0, y)
    spots = [(p, *BASE_DEF[z][:2]) for p, z in zip(row["serve"][0] + row["serve"][1], ORDER, strict=True)]
    server = row["liberofor"] if row["back"][2] == "L" else row["back"][2]
    bx, by = next((px, py) for p, px, py in spots if p == server)
    fx, fy = X(x0, SERVE_SPOT[0]), Y(SERVE_SPOT[1])
    x1, y1, x2, y2 = shorten(fx, fy, X(x0, bx), Y(by), a=7)
    s += arrow(x1, y1, x2, y2, MOVE, "mm", width=1.8, op=0.8)
    s += f'<circle cx="{fx}" cy="{fy}" r="4" fill="{MOVE}" opacity=".7"/>'
    s += f'<text x="{fx + 8}" y="{fy + 4}" font-size="11" fill="#5A6878">serve</text>'
    for p, px, py in spots:
        s += chip(p, X(x0, px), Y(py))
    a(s)
    if r < 5:
        a(
            f'<line x1="40" y1="{y + ROW_H - 24}" x2="{W - 40}" y2="{y + ROW_H - 24}" stroke="#E1E6EC" '
            'stroke-width="1.5"/>'
        )

ly = TOP + 6 * ROW_H + 14
lx = 40
for p, t in [
    ("S", "Setter"),
    ("OP", "Opposite (D)"),
    ("MB1", "Middle 1 / 2"),
    ("OH1", "Outside 1 / 2"),
    ("L", "Libero"),
]:
    a(
        f'<rect x="{lx}" y="{ly}" width="16" height="16" rx="4" fill="{COL[p][0]}"/><text x="{lx + 24}" y="{ly + 13}" '
        f'font-size="14" fill="#33414F">{t}</text>'
    )
    lx += 150
a(
    arrow(lx + 10, ly + 8, lx + 60, ly + 8, RED, "mr", dash="6 4", width=2.5)
    + f'<text x="{lx + 70}" y="{ly + 13}" font-size="14" fill="#33414F">Attack approach</text>'
)
lx += 200
a(
    arrow(lx, ly + 8, lx + 40, ly + 8, MOVE, "mm")
    + f'<text x="{lx + 50}" y="{ly + 13}" font-size="14" fill="#33414F">Positioning movement</text>'
)
lx += 220
a(
    arrow(lx, ly + 8, lx + 40, ly + 8, GREEN, "ms", width=2.5)
    + f'<text x="{lx + 50}" y="{ly + 13}" font-size="14" fill="#33414F">Setter movement</text>'
)
ly2 = ly + 34
a(
    arrow(40, ly2 + 8, 80, ly2 + 8, GREY, "mg", op=0.6)
    + f'<text x="90" y="{ly2 + 13}" font-size="14" fill="#33414F">Rotation: one zone clockwise</text>'
)
a(
    f'<circle cx="340" cy="{ly2 + 8}" r="8.5" fill="#FFF" stroke="{ORANGE}" stroke-width="1.8"/><text x="340" '
    f'y="{ly2 + 12}" text-anchor="middle" font-size="11" font-weight="bold" fill="{NAVY}">4</text><text x="356" '
    f'y="{ly2 + 13}" font-size="14" fill="#33414F">Rotational position</text>'
)
a(
    f'<line x1="530" y1="{ly2 + 8}" x2="570" y2="{ly2 + 8}" stroke="{ORANGE}" stroke-width="1.8" stroke-dasharray="3 '
    f'4"/><text x="580" y="{ly2 + 13}" font-size="14" fill="#33414F">Overlap pair (when receiving)</text>'
)
a(
    f'<text x="930" y="{ly2 + 13}" font-size="14" fill="#33414F">Back-row opposite attacks from behind the 3 m '
    "line.</text>"
)
a(
    f'<text x="40" y="{ly2 + 56}" font-size="12" fill="#8A96A3">KSV | Receiving positions and movements · '
    "“Our serve” = base defence (not in the guide). R3 and R6: the middle in zone 1 serves, because the libero may "
    "not serve (FIVB).</text>"
)
a(
    f'<text x="40" y="{ly2 + 74}" font-size="12" fill="#8A96A3">The serving team has no overlap rule (FIVB 7.4, '
    "since 2025): stand in your defence spot before the serve; only the server moves. Rows still count for blocking "
    "and attacking.</text>"
)
a("</svg>")
svg = "\n".join(o)
(OUT / "KSV_5-1_rotation_schema.svg").write_text(svg)
cairosvg.svg2png(bytestring=svg.encode(), write_to=str(OUT / "KSV_5-1_rotation_schema.png"), scale=2)
svg_to_pdf(svg, OUT / "KSV_5-1_rotation_schema.pdf")
print(W, H)
