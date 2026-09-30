"""Rotation data and set calls for the KSV 5-1 trainer; the single source of truth.

Coordinates: x 0 = left sideline, 1 = right sideline; y 0 = net, 1 = end line.
The 3 m line sits at y = 0.42 (as drawn in the KSV guide). Reception and
after-reception positions are measured from KSV_M3.pdf pages 4-9.
"""

from typing import Literal, TypedDict

ATTACK_LINE = 0.42

# Base defence when we serve, taken before the serve (not in the guide): zone -> (x, y, kind).
BASE_DEF: dict[int, tuple[float, float, str | None]] = {
    4: (0.15, 0.21, "zone"),
    3: (0.50, 0.21, "zone"),
    2: (0.85, 0.21, "zone"),
    5: (0.12, 0.66, None),
    6: (0.50, 0.86, None),
    1: (0.88, 0.66, None),
}


class Row(TypedDict):
    """One rotation: lineup, reception, after-reception and serve positions."""

    name: str
    setter: int
    liberofor: str
    front: list[str]
    back: list[str]
    rec: list[tuple[str, float, float]]
    ar: list[tuple[str, float, float, str | None]]
    serve: tuple[list[str], list[str]]
    note: str


ROWS: list[Row] = [
    Row(
        name="R1",
        setter=1,
        liberofor="MB2",
        front=["OP", "MB1", "OH1"],
        back=["OH2", "L", "S"],
        rec=[
            ("MB1", 0.50, 0.18),
            ("OP", 0.07, 0.42),
            ("OH2", 0.20, 0.73),
            ("L", 0.50, 0.73),
            ("OH1", 0.80, 0.73),
            ("S", 0.90, 0.84),
        ],
        ar=[
            ("OP", 0.07, 0.44, "front"),
            ("MB1", 0.50, 0.44, "front"),
            ("OH1", 0.90, 0.44, "front"),
            ("L", 0.18, 0.66, None),
            ("OH2", 0.50, 0.86, None),
            ("S", 0.69, 0.10, "set"),
        ],
        serve=(["OH1", "MB1", "OP"], ["L", "OH2", "S"]),
        note="Setter in 1: the opposite plays left, outside hitter 1 plays right.",
    ),
    Row(
        name="R2",
        setter=6,
        liberofor="MB2",
        front=["OH2", "OP", "MB1"],
        back=["L", "S", "OH1"],
        rec=[
            ("OP", 0.58, 0.10),
            ("S", 0.58, 0.31),
            ("MB1", 0.76, 0.32),
            ("OH2", 0.17, 0.70),
            ("L", 0.50, 0.72),
            ("OH1", 0.84, 0.72),
        ],
        ar=[
            ("OH2", 0.07, 0.44, "front"),
            ("MB1", 0.50, 0.44, "front"),
            ("OP", 0.93, 0.44, "front"),
            ("L", 0.20, 0.72, None),
            ("OH1", 0.50, 0.87, None),
            ("S", 0.70, 0.11, "set"),
        ],
        serve=(["OH2", "MB1", "OP"], ["L", "OH1", "S"]),
        note="The front-row middle may start near the middle or farther right, but must be ready to attack.",
    ),
    Row(
        name="R3",
        setter=5,
        liberofor="MB1",
        front=["MB2", "OH2", "OP"],
        back=["S", "OH1", "L"],
        rec=[
            ("MB2", 0.10, 0.31),
            ("S", 0.36, 0.47),
            ("OP", 0.93, 0.40),
            ("OH2", 0.25, 0.72),
            ("OH1", 0.52, 0.76),
            ("L", 0.82, 0.76),
        ],
        ar=[
            ("OH2", 0.07, 0.44, "front"),
            ("MB2", 0.50, 0.44, "front"),
            ("OP", 0.93, 0.44, "front"),
            ("L", 0.15, 0.74, None),
            ("OH1", 0.52, 0.76, None),
            ("S", 0.66, 0.09, "set"),
        ],
        serve=(["OH2", "MB2", "OP"], ["OH1", "MB1", "S"]),
        note="Front-row outside hitter 2 stands slightly ahead of back-row outside hitter 1.",
    ),
    Row(
        name="R4",
        setter=4,
        liberofor="MB1",
        front=["S", "MB2", "OH2"],
        back=["OH1", "L", "OP"],
        rec=[
            ("S", 0.08, 0.09),
            ("MB2", 0.15, 0.24),
            ("OH2", 0.25, 0.73),
            ("OH1", 0.50, 0.73),
            ("L", 0.76, 0.73),
            ("OP", 0.92, 0.92),
        ],
        ar=[
            ("OH2", 0.07, 0.44, "front"),
            ("MB2", 0.48, 0.44, "front"),
            ("OP", 0.93, 0.70, "back"),
            ("L", 0.13, 0.77, None),
            ("OH1", 0.50, 0.73, None),
            ("S", 0.69, 0.10, "set"),
        ],
        serve=(["OH2", "MB2", "S"], ["L", "OH1", "OP"]),
        note="Setter runs along the net from zone 4. Opposite goes straight to zone 1 for the back-row attack.",
    ),
    Row(
        name="R5",
        setter=3,
        liberofor="MB1",
        front=["OH1", "S", "MB2"],
        back=["L", "OP", "OH2"],
        rec=[
            ("S", 0.58, 0.10),
            ("MB2", 0.81, 0.28),
            ("OH1", 0.18, 0.71),
            ("L", 0.50, 0.76),
            ("OH2", 0.81, 0.69),
            ("OP", 0.66, 0.92),
        ],
        ar=[
            ("OH1", 0.07, 0.44, "front"),
            ("MB2", 0.50, 0.44, "front"),
            ("OP", 0.93, 0.69, "back"),
            ("L", 0.20, 0.72, None),
            ("OH2", 0.50, 0.87, None),
            ("S", 0.58, 0.10, "set"),
        ],
        serve=(["OH1", "MB2", "S"], ["L", "OH2", "OP"]),
        note="The libero stands slightly behind front-row outside hitter 1.",
    ),
    Row(
        name="R6",
        setter=2,
        liberofor="MB2",
        front=["MB1", "OH1", "S"],
        back=["OP", "OH2", "L"],
        rec=[
            ("MB1", 0.07, 0.10),
            ("S", 0.75, 0.12),
            ("OH1", 0.23, 0.70),
            ("OH2", 0.52, 0.76),
            ("L", 0.83, 0.74),
            ("OP", 0.40, 0.92),
        ],
        ar=[
            ("OH1", 0.07, 0.44, "front"),
            ("MB1", 0.48, 0.44, "front"),
            ("OP", 0.93, 0.78, "back"),
            ("L", 0.16, 0.74, None),
            ("OH2", 0.52, 0.76, None),
            ("S", 0.75, 0.12, "set"),
        ],
        serve=(["OH1", "MB1", "S"], ["OH2", "MB2", "OP"]),
        note="Front-row outside hitter 1 stands slightly ahead of back-row outside hitter 2.",
    ),
]

# Front row sets (KSV guide p.10). x: 0 = left antenna, 1 = right antenna. peak: relative height.
SETTER_X = 0.64
SETS: list[tuple[str, float, float, str, str]] = [
    ("1", 0.02, 1.00, "left", "High ball to the left antenna (zone 4). Most time for the attacker."),
    ("0", 0.02, 0.52, "left", "Lower, faster ball to the left antenna."),
    ("2", 0.18, 0.46, "left", "Medium-fast ball landing about 1.5 m inside the left antenna."),
    ("Shoot", 0.36, 0.30, "mid", "Flat, fast ball between zone 4 and the middle."),
    ("4", 0.56, 0.72, "mid", "Higher ball just in front of the setter. More time for the middle."),
    ("Po", 0.56, 0.30, "mid", "Low quick just in front of the setter."),
    ("Til", 0.75, 0.22, "right", "Short quick just behind the setter."),
    ("7", 0.97, 0.50, "right", "Lower, faster back set to the right antenna."),
    ("6", 0.97, 0.92, "right", "High back set to the right antenna (zone 2)."),
]

# Inferred from the guide's drawings only; left out of match questions until the coach confirms them.
UNCONFIRMED_SETS: list[str] = ["Po", "4"]

RulesMode = Literal["simple", "official"]
RULES_MODES: tuple[RulesMode, ...] = ("simple", "official")
ZONE_ORDER = [4, 3, 2, 5, 6, 1]
MIDDLES = ("MB1", "MB2")


def rotation_zones(row: Row) -> dict[int, str]:
    """Maps each zone to the player standing there at the Rotation step."""
    return dict(zip(ZONE_ORDER, row["front"] + row["back"], strict=True))


def middle_pair(ri: int) -> tuple[int, int]:
    """Returns the zones of the front-row middle slot and the back-row middle slot.

    The back slot is where the libero stands for the back-row middle. In
    Simplified KSV, MB always takes the front slot and L the back slot.
    """
    zones = rotation_zones(ROWS[ri])
    front = next(z for z in (4, 3, 2) if zones[z] in MIDDLES)
    back = next(z for z in (5, 6, 1) if zones[z] == "L")
    return front, back


def server(ri: int, mode: RulesMode) -> str:
    """Returns who serves from zone 1: the libero may not, so a middle (Official) or SUB (Simplified) does."""
    player = ROWS[ri]["back"][2]
    if player != "L":
        return player
    return ROWS[ri]["liberofor"] if mode == "official" else "SUB"


def lineup(ri: int, mode: RulesMode) -> Row:
    """Returns rotation ri under a rule set, derived from the official data.

    Simplified renames the front-row middle to MB and the back-row middle,
    who is on court only at our serve in R3 and R6, to SUB.
    """
    row = ROWS[ri]
    if mode == "official":
        return row
    front_zone, _ = middle_pair(ri)
    rename = {rotation_zones(row)[front_zone]: "MB", row["liberofor"]: "SUB"}

    def name(player: str) -> str:
        return rename.get(player, player)

    return Row(
        name=row["name"],
        setter=row["setter"],
        liberofor="SUB" if server(ri, mode) == "SUB" else "",
        front=[name(p) for p in row["front"]],
        back=[name(p) for p in row["back"]],
        rec=[(name(p), x, y) for p, x, y in row["rec"]],
        ar=[(name(p), x, y, kind) for p, x, y, kind in row["ar"]],
        serve=([name(p) for p in row["serve"][0]], [name(p) for p in row["serve"][1]]),
        note=row["note"],
    )
