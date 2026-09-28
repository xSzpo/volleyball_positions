"""Build index.html from data.py, template.html and the cheat sheet PDFs.

The PDFs in downloads/ are base64-embedded so the download buttons work
without extra files.
"""

import base64
import json
from pathlib import Path

from data import ATTACK_LINE, ROWS, SETS, SETTER_X, UNCONFIRMED_SETS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "downloads"

rows = [
    dict(
        name=r["name"],
        setter=r["setter"],
        liberofor=r["liberofor"],
        front=r["front"],
        back=r["back"],
        rec=[list(x) for x in r["rec"]],
        ar=[list(x) for x in r["ar"]],
        serve=[r["serve"][0], r["serve"][1]],
        note=r["note"],
    )
    for r in ROWS
]
data = dict(
    rows=rows,
    attackLine=ATTACK_LINE,
    sets=[list(s) for s in SETS],
    setterX=SETTER_X,
    unconfirmedSets=UNCONFIRMED_SETS,
)
t = (ROOT / "src" / "template.html").read_text()
t = t.replace("__DATA__", json.dumps(data))
t = t.replace("__PDF_SCHEMA__", base64.b64encode((OUT / "KSV_5-1_rotation_schema.pdf").read_bytes()).decode())
t = t.replace("__PDF_SETS__", base64.b64encode((OUT / "KSV_front_row_sets.pdf").read_bytes()).decode())
(ROOT / "index.html").write_text(t)
print(len(t))
