"""Generate the front row sets cheat sheet as SVG, PNG and PDF in downloads/."""

from pathlib import Path

import cairosvg

from data import SETS, SETTER_X
from pdf import svg_to_pdf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "downloads"


NAVY = "#1B3350"
ORANGE = "#F08A1C"
FAM = {
    "left": ("#27598C", "Left side (zone 4)"),
    "mid": ("#C2410C", "Middle (zone 3), in front of the setter"),
    "right": ("#1E1E1E", "Right side (zone 2)"),
}
FAM["right"] = ("#1E1E1E", "Behind the setter / right side (zone 2)")
W, H = 1450, 1025
NL, NR = 230, 1230  # antennas
NT = 520  # net top
SY = NT - 40  # contact height (setter's hands)
PH = 330  # max peak height


def P(x: float) -> float:
    return NL + x * (NR - NL)


def curve(lx: float, peak: float) -> tuple[float, float, float, float, float, float]:
    sx = P(SETTER_X)
    ex = P(lx)
    ey = SY + 10
    cy = SY - 2 * peak * PH
    cx = (sx + ex) / 2
    return sx, SY, cx, cy, ex, ey


def at(t: float, sx: float, sy: float, cx: float, cy: float, ex: float, ey: float) -> tuple[float, float]:
    return (
        (1 - t) ** 2 * sx + 2 * (1 - t) * t * cx + t * t * ex,
        (1 - t) ** 2 * sy + 2 * (1 - t) * t * cy + t * t * ey,
    )


o: list[str] = []
a = o.append
a(
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="DejaVu Sans, '
    'Arial, sans-serif">'
)
a(f'<rect width="{W}" height="{H}" fill="#FFF"/>')
a(f'<text x="50" y="66" font-size="34" font-weight="bold" fill="{NAVY}">Front row sets</text>')
a(f'<rect x="50" y="82" width="80" height="5" fill="{ORANGE}"/>')
a(
    '<text x="50" y="116" font-size="15" fill="#5A6878">Seen from our side of the net. The setter stands right of the '
    "middle; each line shows where the ball lands and how high it goes.</text>"
)
# net
a(f'<rect x="{NL - 30}" y="{NT}" width="{NR - NL + 60}" height="90" fill="#F3F0FA" stroke="#5B2A86" stroke-width="7"/>')
for i in range(1, 40):
    x = NL - 30 + i * (NR - NL + 60) / 40
    a(f'<line x1="{x}" y1="{NT}" x2="{x}" y2="{NT + 90}" stroke="#CFC6DE" stroke-width="1"/>')
for j in range(1, 5):
    a(f'<line x1="{NL - 30}" y1="{NT + j * 18}" x2="{NR + 30}" y2="{NT + j * 18}" stroke="#CFC6DE" stroke-width="1"/>')
for x in (NL, NR):
    a(
        f'<line x1="{x}" y1="{NT - 110}" x2="{x}" y2="{NT + 95}" stroke="#E03131" stroke-width="6" stroke-dasharray="9 '
        '7"/>'
    )
a(f'<text x="{NL}" y="{NT + 125}" text-anchor="middle" font-size="13" fill="#5A6878">left antenna</text>')
a(f'<text x="{NR}" y="{NT + 125}" text-anchor="middle" font-size="13" fill="#5A6878">right antenna</text>')
# zones under net
for i, z in enumerate(["zone 4", "zone 3", "zone 2"]):
    a(
        f'<text x="{NL + (i + 0.5) * (NR - NL) / 3}" y="{NT + 125}" text-anchor="middle" font-size="13" '
        f'fill="#9AA6B2">{z}</text>'
    )
# curves
labels = []
for name, lx, peak, fam, _desc in SETS:
    col = FAM[fam][0]
    sx, sy, cx, cy, ex, ey = curve(lx, peak)
    a(f'<path d="M{sx},{sy} Q{cx},{cy} {ex},{ey}" fill="none" stroke="{col}" stroke-width="3"/>')
    a(f'<circle cx="{ex}" cy="{ey}" r="5" fill="{col}"/>')
    t = 0.5 if name in ("1", "6", "4", "7", "0") else 0.72
    if name == "Po":
        t = 0.5
    lxp, lyp = at(t, sx, sy, cx, cy, ex, ey)
    labels.append((name, lxp, lyp, col))
for name, x, y, col in labels:
    w = 22 + 11 * len(name)
    a(
        f'<rect x="{x - w / 2}" y="{y - 16}" width="{w}" height="30" rx="6" fill="#FFF" stroke="{col}" '
        'stroke-width="2.5"/>'
    )
    a(f'<text x="{x}" y="{y + 6}" text-anchor="middle" font-size="16" font-weight="bold" fill="{col}">{name}</text>')
# setter
sx = P(SETTER_X)
a(
    f'<circle cx="{sx}" cy="{SY}" r="17" fill="#F2B53A" stroke="#FFF" stroke-width="3"/><text x="{sx}" y="{SY + 6}" '
    f'text-anchor="middle" font-size="16" font-weight="bold" fill="{NAVY}">S</text>'
)
a(f'<text x="{sx}" y="{NT + 150}" text-anchor="middle" font-size="13" font-weight="bold" fill="{NAVY}">setter</text>')
a(
    f'<line x1="{sx}" y1="{NT + 95}" x2="{sx}" y2="{NT + 135}" stroke="{NAVY}" stroke-width="1.5" stroke-dasharray="3 '
    '3"/>'
)

# table
ty = 720
colw = (W - 100) / 3
for i, fam in enumerate(["left", "mid", "right"]):
    col, title = FAM[fam]
    x = 50 + i * colw
    a(f'<rect x="{x}" y="{ty}" width="{colw - 24}" height="5" fill="{col}"/>')
    a(f'<text x="{x}" y="{ty + 32}" font-size="16" font-weight="bold" fill="{col}">{title}</text>')
    yy = ty + 64
    for name, _lx, _peak, f, desc in SETS:
        if f != fam:
            continue
        a(f'<text x="{x}" y="{yy}" font-size="20" font-weight="bold" fill="{NAVY}">{name}</text>')
        words = desc.split()
        line = ""
        ly = yy
        for wd in words:
            if len(line + " " + wd) > 38:
                a(f'<text x="{x + 72}" y="{ly}" font-size="14" fill="#33414F">{line.strip()}</text>')
                line = ""
                ly += 19
            line += " " + wd
        a(f'<text x="{x + 72}" y="{ly}" font-size="14" fill="#33414F">{line.strip()}</text>')
        yy = ly + 38
a(
    f'<text x="50" y="{H - 30}" font-size="12" fill="#8A96A3">KSV | Front row sets · lower arc = faster tempo · set '
    "names as used in the KSV guide</text>"
)
a("</svg>")
svg = "\n".join(o)
(OUT / "KSV_front_row_sets.svg").write_text(svg)
cairosvg.svg2png(bytestring=svg.encode(), write_to=str(OUT / "KSV_front_row_sets.png"), scale=1.5)
svg_to_pdf(svg, OUT / "KSV_front_row_sets.pdf")
