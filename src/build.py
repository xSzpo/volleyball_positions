import json, base64
from data import ROWS, SETS, SETTER_X, ATTACK_LINE
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "downloads"

rows=[dict(name=r["name"],setter=r["setter"],liberofor=r["liberofor"],front=r["front"],back=r["back"],
  rec=[list(x) for x in r["rec"]],ar=[list(x) for x in r["ar"]],serve=[r["serve"][0],r["serve"][1]],note=r["note"]) for r in ROWS]
data=dict(rows=rows,attackLine=ATTACK_LINE,sets=[list(s) for s in SETS],setterX=SETTER_X)
t=open(ROOT/'src'/'template.html').read()
t=t.replace('__DATA__',json.dumps(data))
t=t.replace('__PDF_SCHEMA__',base64.b64encode(open(OUT/'KSV_5-1_rotation_schema.pdf','rb').read()).decode())
t=t.replace('__PDF_SETS__',base64.b64encode(open(OUT/'KSV_front_row_sets.pdf','rb').read()).decode())
open(ROOT/'index.html','w').write(t)
print(len(t))
