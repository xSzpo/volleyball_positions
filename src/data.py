# Coordinates: x 0 = left sideline, 1 = right sideline; y 0 = net, 1 = end line.
# 3 m line sits at y = 0.42 (as drawn in the KSV guide).
# Reception and after-reception positions measured from KSV_M3.pdf pages 4-9.
ATTACK_LINE = 0.42

ROWS = [
    dict(name="R1", setter=1, liberofor="MB2",
         front=["OP", "MB1", "OH1"], back=["OH2", "L", "S"],
         rec=[("MB1", .50, .18), ("OP", .07, .42), ("OH2", .20, .73), ("L", .50, .73), ("OH1", .80, .73), ("S", .90, .84)],
         ar=[("OP", .07, .44, "front"), ("MB1", .50, .44, "front"), ("OH1", .90, .44, "front"),
             ("L", .18, .66, None), ("OH2", .50, .86, None), ("S", .69, .10, "set")],
         serve=(["OH1", "MB1", "OP"], ["L", "OH2", "S"]),
         note="Setter in 1: the opposite plays left, outside hitter 1 plays right."),
    dict(name="R2", setter=6, liberofor="MB2",
         front=["OH2", "OP", "MB1"], back=["L", "S", "OH1"],
         rec=[("OP", .58, .10), ("S", .58, .31), ("MB1", .76, .32), ("OH2", .17, .70), ("L", .50, .72), ("OH1", .84, .72)],
         ar=[("OH2", .07, .44, "front"), ("MB1", .50, .44, "front"), ("OP", .93, .44, "front"),
             ("L", .20, .72, None), ("OH1", .50, .87, None), ("S", .70, .11, "set")],
         serve=(["OH2", "MB1", "OP"], ["L", "OH1", "S"]),
         note="The front-row middle may start near the middle or farther right, but must be ready to attack."),
    dict(name="R3", setter=5, liberofor="MB1",
         front=["MB2", "OH2", "OP"], back=["S", "OH1", "L"],
         rec=[("MB2", .10, .31), ("S", .36, .47), ("OP", .93, .40), ("OH2", .25, .72), ("OH1", .52, .76), ("L", .82, .76)],
         ar=[("OH2", .07, .44, "front"), ("MB2", .50, .44, "front"), ("OP", .93, .44, "front"),
             ("L", .15, .74, None), ("OH1", .52, .76, None), ("S", .66, .09, "set")],
         serve=(["OH2", "MB2", "OP"], ["OH1", "MB1", "S"]),
         note="Front-row outside hitter 2 stands slightly ahead of back-row outside hitter 1."),
    dict(name="R4", setter=4, liberofor="MB1",
         front=["S", "MB2", "OH2"], back=["OH1", "L", "OP"],
         rec=[("S", .08, .09), ("MB2", .15, .24), ("OH2", .25, .73), ("OH1", .50, .73), ("L", .76, .73), ("OP", .92, .92)],
         ar=[("OH2", .07, .44, "front"), ("MB2", .48, .44, "front"), ("OP", .93, .70, "back"),
             ("L", .13, .77, None), ("OH1", .50, .73, None), ("S", .69, .10, "set")],
         serve=(["OH2", "MB2", "S"], ["L", "OH1", "OP"]),
         note="Setter runs along the net from zone 4. Opposite goes straight to zone 1 for the back-row attack."),
    dict(name="R5", setter=3, liberofor="MB1",
         front=["OH1", "S", "MB2"], back=["L", "OP", "OH2"],
         rec=[("S", .58, .10), ("MB2", .81, .28), ("OH1", .18, .71), ("L", .50, .76), ("OH2", .81, .69), ("OP", .66, .92)],
         ar=[("OH1", .07, .44, "front"), ("MB2", .50, .44, "front"), ("OP", .93, .69, "back"),
             ("L", .20, .72, None), ("OH2", .50, .87, None), ("S", .58, .10, "set")],
         serve=(["OH1", "MB2", "S"], ["L", "OH2", "OP"]),
         note="The libero stands slightly behind front-row outside hitter 1."),
    dict(name="R6", setter=2, liberofor="MB2",
         front=["MB1", "OH1", "S"], back=["OP", "OH2", "L"],
         rec=[("MB1", .07, .10), ("S", .75, .12), ("OH1", .23, .70), ("OH2", .52, .76), ("L", .83, .74), ("OP", .40, .92)],
         ar=[("OH1", .07, .44, "front"), ("MB1", .48, .44, "front"), ("OP", .93, .78, "back"),
             ("L", .16, .74, None), ("OH2", .52, .76, None), ("S", .75, .12, "set")],
         serve=(["OH1", "MB1", "S"], ["OH2", "MB2", "OP"]),
         note="Front-row outside hitter 1 stands slightly ahead of back-row outside hitter 2."),
]

# Front row sets (KSV guide p.10). x: 0 = left antenna, 1 = right antenna. peak: relative height.
SETTER_X = 0.64
SETS = [
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
