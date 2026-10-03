"""Rotation data and set calls for the KSV 5-1 trainer; the single source of truth.

Coordinates: x 0 = left sideline, 1 = right sideline; y 0 = net, 1 = end line.
The 3 m line sits at y = 0.42 (as drawn in the KSV guide). Reception and
after-reception positions are measured from KSV_M3.pdf pages 4-9.
"""

from typing import Literal, TypedDict

ATTACK_LINE = 0.42
# The front middle opens for the quick here, in front of the 3 m line: the back-row hitter's lane stays clear.
QUICK_START_Y = 0.26

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
    """One rotation: lineup, reception, after-reception and serve positions.

    `move` holds one Learn caption per player for each phase (serve, rec,
    ar), written to that player, 78 characters at most.
    """

    name: str
    setter: int
    liberofor: str
    front: list[str]
    back: list[str]
    rec: list[tuple[str, float, float]]
    ar: list[tuple[str, float, float, str | None]]
    serve: tuple[list[str], list[str]]
    note: str
    move: dict[str, dict[str, str]]


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
            ("MB1", 0.50, QUICK_START_Y, "front"),
            ("OH1", 0.90, 0.44, "front"),
            ("L", 0.18, 0.66, None),
            ("OH2", 0.50, 0.86, None),
            ("S", 0.69, 0.10, "set"),
        ],
        serve=(["OH1", "MB1", "OP"], ["L", "OH2", "S"]),
        note="Setter in 1: the opposite plays left, outside hitter 1 plays right.",
        move={
            "serve": {
                "OH1": "Cross to zone 4: outside hitters block and attack on the left.",
                "MB1": "Stay in zone 3, in the middle of the net, ready to block.",
                "OP": "Cross to zone 2: the opposite blocks and attacks on the right.",
                "L": "Move to zone 5 and defend deep on the left.",
                "OH2": "Move to zone 6 and defend deep in the middle.",
                "S": "Serve from behind the end line, then defend zone 1 until we dig.",
            },
            "rec": {
                "MB1": "Stand at the net in the middle, out of the receivers' way.",
                "OP": "Stand at the left sideline on the 3 m line: here the opposite plays left.",
                "OH2": "Receive on the left of the passing line.",
                "L": "Receive in the middle of the passing line.",
                "OH1": "Receive on the right: here outside hitter 1 plays right.",
                "S": "Hide behind OH1 in zone 1, out of the passing lanes.",
            },
            "ar": {
                "S": "Leave zone 1 for the setting spot as soon as the serve is hit.",
                "OP": "Stay at the left sideline on the 3 m line, then attack in zone 4.",
                "MB1": "Step off the net to the middle of the front zone to open for the quick.",
                "OH1": "Move up to the 3 m line at the right and attack in zone 2.",
                "L": "Run on to cover OP close behind, then defend zone 5.",
                "OH2": "Run on to cover deep in the middle, then defend zone 6.",
            },
        },
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
            ("MB1", 0.50, QUICK_START_Y, "front"),
            ("OP", 0.93, 0.44, "front"),
            ("L", 0.20, 0.72, None),
            ("OH1", 0.50, 0.87, None),
            ("S", 0.70, 0.11, "set"),
        ],
        serve=(["OH2", "MB1", "OP"], ["L", "OH1", "S"]),
        note="The front-row middle may start near the middle or farther right, but must be ready to attack.",
        move={
            "serve": {
                "OH2": "Stay in zone 4, ready to block and attack on the left.",
                "MB1": "Move to zone 3, in the middle of the net, ready to block.",
                "OP": "Move to zone 2: the opposite blocks and attacks on the right.",
                "L": "Stay in zone 5 and defend deep on the left.",
                "OH1": "Serve from behind the end line, then run to zone 6 and defend deep.",
                "S": "Move to zone 1 and defend there until we dig.",
            },
            "rec": {
                "OP": "Stand at the net just right of the middle, in front of the setter.",
                "S": "Hide behind OP near the net, ready to run to the setting spot.",
                "MB1": "Start near the middle or farther right, ready to attack.",
                "OH2": "Receive on the left of the passing line.",
                "L": "Receive in the middle of the passing line.",
                "OH1": "Receive on the right of the passing line.",
            },
            "ar": {
                "S": "Step up to the setting spot, right of the middle.",
                "OH2": "Move up to the 3 m line at the left and attack in zone 4.",
                "MB1": "Get to the middle of the front zone to open for the quick.",
                "OP": "Leave the net for the 3 m line at the right and attack in zone 2.",
                "L": "Run on to cover OH2 close behind, then defend zone 5.",
                "OH1": "Run on to cover deep in the middle, then defend zone 6.",
            },
        },
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
            ("MB2", 0.50, QUICK_START_Y, "front"),
            ("OP", 0.93, 0.44, "front"),
            ("L", 0.15, 0.74, None),
            ("OH1", 0.52, 0.76, None),
            ("S", 0.66, 0.09, "set"),
        ],
        serve=(["OH2", "MB2", "OP"], ["MB1", "OH1", "S"]),
        note="Front-row outside hitter 2 stands slightly ahead of back-row outside hitter 1.",
        move={
            "serve": {
                "OH2": "Move to zone 4, ready to block and attack on the left.",
                "MB2": "Move to zone 3, in the middle of the net, ready to block.",
                "OP": "Stay in zone 2: the opposite blocks and attacks on the right.",
                "OH1": "Move to zone 6 and defend deep in the middle.",
                "MB1": "Serve from behind the end line, then run to zone 5, the libero's spot.",
                "S": "Move to zone 1 and defend there until we dig.",
            },
            "rec": {
                "MB2": "Stand at the left, in front of the setter, out of the receivers' way.",
                "S": "Stand just behind the 3 m line, left of the middle, out of the lanes.",
                "OP": "Stand at the right sideline near the 3 m line, ready to attack.",
                "OH2": "Receive on the left, slightly ahead of OH1.",
                "OH1": "Receive in the middle, slightly behind OH2.",
                "L": "Receive on the right of the passing line.",
            },
            "ar": {
                "S": "Run forward to the setting spot, right of the middle.",
                "OH2": "Move up to the 3 m line at the left and attack in zone 4.",
                "MB2": "Cut across to the middle of the front zone to open for the quick.",
                "OP": "Stay at the right sideline on the 3 m line, then attack in zone 2.",
                "L": "Run round behind OH1 to cover OH2 close behind, then defend zone 5.",
                "OH1": "Stay in the middle to cover deep, then defend zone 6.",
            },
        },
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
            ("MB2", 0.48, QUICK_START_Y, "front"),
            ("OP", 0.93, 0.70, "back"),
            ("L", 0.13, 0.77, None),
            ("OH1", 0.50, 0.73, None),
            ("S", 0.69, 0.10, "set"),
        ],
        serve=(["OH2", "MB2", "S"], ["L", "OH1", "OP"]),
        note="Setter runs along the net from zone 4. Opposite goes straight to zone 1 for the back-row attack.",
        move={
            "serve": {
                "OH2": "Cross to zone 4: outside hitters block and attack on the left.",
                "MB2": "Stay in zone 3, in the middle of the net, ready to block.",
                "S": "Cross to zone 2: the setter blocks on the right and sets from there.",
                "L": "Move to zone 5 and defend deep on the left.",
                "OH1": "Move to zone 6 and defend deep in the middle.",
                "OP": "Serve from behind the end line, then defend zone 1.",
            },
            "rec": {
                "S": "Stand at the net in the left corner, out of the receivers' way.",
                "MB2": "Stand left, just behind the setter, out of the receivers' way.",
                "OH2": "Receive on the left of the passing line.",
                "OH1": "Receive in the middle of the passing line.",
                "L": "Receive on the right of the passing line.",
                "OP": "Stand deep in the right corner, out of the passing lanes.",
            },
            "ar": {
                "S": "Run along the net from zone 4 to the setting spot.",
                "OH2": "Move up to the 3 m line at the left and attack in zone 4.",
                "MB2": "Step off the net to the middle of the front zone to open for the quick.",
                "OP": "Come in to cover deep, right of the middle: the set goes to zone 4.",
                "L": "Run round behind OH1 to cover OH2 close behind, then defend zone 5.",
                "OH1": "Stay in the middle to cover deep, then defend zone 6.",
            },
        },
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
            ("MB2", 0.50, QUICK_START_Y, "front"),
            ("OP", 0.93, 0.69, "back"),
            ("L", 0.20, 0.72, None),
            ("OH2", 0.50, 0.87, None),
            ("S", 0.58, 0.10, "set"),
        ],
        serve=(["OH1", "MB2", "S"], ["L", "OH2", "OP"]),
        note="The libero stands slightly behind front-row outside hitter 1.",
        move={
            "serve": {
                "OH1": "Stay in zone 4, ready to block and attack on the left.",
                "MB2": "Move to zone 3, in the middle of the net, ready to block.",
                "S": "Move to zone 2: the setter blocks on the right and sets from there.",
                "L": "Stay in zone 5 and defend deep on the left.",
                "OH2": "Serve from behind the end line, then run to zone 6 and defend deep.",
                "OP": "Move to zone 1 and defend deep on the right.",
            },
            "rec": {
                "S": "Stand at the net, just right of the middle, ready to set.",
                "MB2": "Stand on the right, off the net, out of the receivers' way.",
                "OH1": "Receive on the left, slightly ahead of the libero.",
                "L": "Receive in the middle, slightly behind OH1.",
                "OH2": "Receive on the right of the passing line.",
                "OP": "Stand deep behind the receivers, out of the passing lanes.",
            },
            "ar": {
                "S": "Stay at the net: you are already at the setting spot.",
                "OH1": "Move up to the 3 m line at the left and attack in zone 4.",
                "MB2": "Cut in to the middle of the front zone to open for the quick.",
                "OP": "Come in to cover deep, right of the middle: the set goes to zone 4.",
                "L": "Run on to cover OH1 close behind, then defend zone 5.",
                "OH2": "Run on to cover deep in the middle, then defend zone 6.",
            },
        },
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
            ("MB1", 0.48, QUICK_START_Y, "front"),
            ("OP", 0.93, 0.78, "back"),
            ("L", 0.16, 0.74, None),
            ("OH2", 0.52, 0.76, None),
            ("S", 0.75, 0.12, "set"),
        ],
        serve=(["OH1", "MB1", "S"], ["MB2", "OH2", "OP"]),
        note="Front-row outside hitter 1 stands slightly ahead of back-row outside hitter 2.",
        move={
            "serve": {
                "OH1": "Move to zone 4, ready to block and attack on the left.",
                "MB1": "Move to zone 3, in the middle of the net, ready to block.",
                "S": "Stay in zone 2: the setter blocks on the right and sets from there.",
                "OH2": "Move to zone 6 and defend deep in the middle.",
                "MB2": "Serve from behind the end line, then run to zone 5, the libero's spot.",
                "OP": "Move to zone 1 and defend deep on the right.",
            },
            "rec": {
                "MB1": "Stand at the net in the left corner, out of the receivers' way.",
                "S": "Stand at the net on the right, ready to set.",
                "OH1": "Receive on the left, slightly ahead of OH2.",
                "OH2": "Receive in the middle, slightly behind OH1.",
                "L": "Receive on the right of the passing line.",
                "OP": "Stand deep behind the receivers, out of the passing lanes.",
            },
            "ar": {
                "S": "Stay at the net: you are already at the setting spot.",
                "OH1": "Move up to the 3 m line at the left and attack in zone 4.",
                "MB1": "Step off the net to the middle of the front zone to open for the quick.",
                "OP": "Come in to cover deep, right of the middle: the set goes to zone 4.",
                "L": "Run round behind OH2 to cover OH1 close behind, then defend zone 5.",
                "OH2": "Stay in the middle to cover deep, then defend zone 6.",
            },
        },
    ),
]

# Front row sets (KSV guide p.10) and the club's back-row sets A, B, C (not in the guide).
# x: 0 = left antenna, 1 = right antenna, seen from our side. peak: relative height.
SETTER_X = 0.64
SETS: list[tuple[str, float, float, str, str]] = [
    ("1", 0.02, 1.00, "left", "High ball to the left antenna (zone 4). Most time for the attacker."),
    ("0", 0.02, 0.52, "left", "Lower, faster ball to the left antenna."),
    ("2", 0.18, 0.46, "left", "Medium-fast ball landing about 1.5 m inside the left antenna."),
    ("Shoot", 0.36, 0.30, "mid", "Flat, fast ball between zone 4 and the middle."),
    ("4", 0.56, 0.16, "mid", "The middle's quick: short, low ball just in front of the setter, close to the net."),
    ("7", 0.97, 0.50, "right", "Lower, faster back set to the right antenna."),
    ("6", 0.97, 0.92, "right", "High back set to the right antenna (zone 2)."),
    ("A", 0.83, 0.62, "back", "Back-row attack from zone 1 (right back), behind the 3 m line."),
    ("B", 0.50, 0.66, "back", "Back-row attack from zone 6 (middle back, the pipe), behind the 3 m line."),
    ("C", 0.17, 0.62, "back", "Back-row attack from zone 5 (left back), behind the 3 m line."),
]

# Sets the guide does not confirm: left out of match questions and marked on the Sets tab.
UNCONFIRMED_SETS: list[str] = []

RulesMode = Literal["simple", "official"]
RULES_MODES: tuple[RulesMode, ...] = ("simple", "official")
ZONE_ORDER = [4, 3, 2, 5, 6, 1]
MIDDLES = ("MB1", "MB2")
# Simplified R3 and R6: the middle on court in zone 4 while MB serves from zone 1.
OTHER_MIDDLE = "OM"


def rotation_zones(row: Row) -> dict[int, str]:
    """Maps each zone to the player standing there at the Rotation step."""
    return dict(zip(ZONE_ORDER, row["front"] + row["back"], strict=True))


def middle_pair(ri: int) -> tuple[int, int]:
    """Returns the zones of the front-row middle slot and the back-row middle slot in reception.

    The back slot is where the libero stands for the back-row middle. In
    Simplified KSV, MB always takes the front slot and L the back slot.
    """
    zones = rotation_zones(ROWS[ri])
    front = next(z for z in (4, 3, 2) if zones[z] in MIDDLES)
    back = next(z for z in (5, 6, 1) if zones[z] == "L")
    return front, back


def server(ri: int, mode: RulesMode) -> str:
    """Returns who serves from zone 1: the libero may not, so the middle in zone 1 does (MB in Simplified)."""
    player = ROWS[ri]["back"][2]
    if player != "L":
        return player
    return ROWS[ri]["liberofor"] if mode == "official" else "MB"


def lineup(ri: int, mode: RulesMode) -> Row:
    """Returns rotation ri under a rule set, derived from the official data.

    Simplified renames the front-row middle to MB. In R3 and R6, where a
    middle serves, MB takes the serving middle's place at our serve and the
    front-row middle becomes the other middle (OTHER_MIDDLE); the rotation
    and reception lineups keep MB in the front-row middle slot.
    """
    row = ROWS[ri]
    if mode == "official":
        return row
    front_zone, _ = middle_pair(ri)
    front_middle = rotation_zones(row)[front_zone]
    rename = {front_middle: "MB"}
    at_serve = rename
    if row["back"][2] == "L":
        at_serve = {row["liberofor"]: "MB", front_middle: OTHER_MIDDLE}

    def name(player: str, names: dict[str, str] = rename) -> str:
        return names.get(player, player)

    def phase_names(phase: str) -> dict[str, str]:
        return at_serve if phase == "serve" else rename

    return Row(
        name=row["name"],
        setter=row["setter"],
        liberofor="",
        front=[name(p) for p in row["front"]],
        back=[name(p) for p in row["back"]],
        rec=[(name(p), x, y) for p, x, y in row["rec"]],
        ar=[(name(p), x, y, kind) for p, x, y, kind in row["ar"]],
        serve=([name(p, at_serve) for p in row["serve"][0]], [name(p, at_serve) for p in row["serve"][1]]),
        note=row["note"],
        move={
            phase: {name(p, phase_names(phase)): text for p, text in notes.items()}
            for phase, notes in row["move"].items()
        },
    )


def rotation_lineup(ri: int, mode: RulesMode) -> list[str]:
    """Returns who stands where at the Rotation step, zones 4 3 2 5 6 1.

    When the libero would be in zone 1, the middle who serves is on and L is
    off; in Simplified that is MB, and the other middle plays zone 4.
    """
    r = lineup(ri, mode)
    if r["back"][2] != "L":
        return r["front"] + r["back"]
    serving = server(ri, mode)
    front = [OTHER_MIDDLE if p == serving else p for p in r["front"]]
    return front + [serving if p == "L" else p for p in r["back"]]
