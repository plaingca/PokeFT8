"""Simulated RF session; datagrams pass through the real binary parser."""

import datetime as dt

import protocol as wire


def real_sequence():
    """15-second alternating slots; decodes arrive near the receive-slot end."""
    end = dt.datetime.now(dt.timezone.utc)
    return [
        (0, wire.status("CQ N0CALL CN79", True)),
        (13.2, wire.status("", False)),
        (27, wire.status("", False, True)),
        (27.2, wire.reception("N0CALL W1AW FN31", -19, 1)),
        (27.5, wire.reception("N0CALL JA1ABC PM95", -5, 1)),
        (27.7, wire.reception("N0CALL VK2XYZ QF56", -12, 1)),
        (28.5, wire.status()),
        (30, wire.status("JA1ABC N0CALL -05", True, target="JA1ABC")),
        (43.2, wire.status()),
        (57, wire.status("", False, True)),
        (57.5, wire.reception("N0CALL JA1ABC R-07", -6, 3)),
        (57.6, wire.reception("N0CALL JA1ABC R-07", -6, 3)),
        (58.5, wire.status()),
        (60, wire.status("JA1ABC N0CALL -05", True, target="JA1ABC")),
        (73.2, wire.status()),
        (87, wire.status("", False, True)),
        (87.5, wire.reception("N0CALL JA1ABC R-07", -8, 5)),
        (88.5, wire.status()),
        (90, wire.status("JA1ABC N0CALL RR73", True, target="JA1ABC")),
        (103.2, wire.status()),
        (117, wire.status("", False, True)),
        (117.5, wire.reception("N0CALL JA1ABC 73", -7, 7)),
        (118.5, wire.status()),
        (119, wire.logged("JA1ABC", end)),
        (119.1, wire.logged("JA1ABC", end)),
    ]


def sequence():
    end = dt.datetime.now(dt.timezone.utc)
    return [
        (0, wire.status("CQ N0CALL CN79", True)),
        (4, wire.status("CQ N0CALL CN79", False, True)),
        (4.2, wire.reception("N0CALL W1AW FN31", -19, 1)),
        (4.5, wire.reception("N0CALL JA1ABC PM95", -5, 1)),
        (4.7, wire.reception("N0CALL VK2XYZ QF56", -12, 1)),
        (5, wire.status("", False, False)),
        (15, wire.status("JA1ABC N0CALL -05", True, target="JA1ABC")),
        (18, wire.reception("N0CALL JA1ABC R-07", -6, 3)),
        (18.1, wire.reception("N0CALL JA1ABC R-07", -6, 3)),  # duplicate ignored
        (25, wire.reception("N0CALL JA1ABC R-07", -6, 5)),  # actual retry: one attack
        (26, wire.status("", False)),
        (31, wire.status("JA1ABC N0CALL RR73", True, target="JA1ABC")),
        (34, wire.reception("N0CALL JA1ABC 73", -7, 7)),
        (42, wire.logged("JA1ABC", end)),
        (42.1, wire.logged("JA1ABC", end)),
    ]
