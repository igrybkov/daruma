"""Host test: the edge strips that extend a pixel-art room (daruma_sprites/extend.py).

    uv run pytest tests/test_extend.py

test_screens.py checks the strips of a real room. These pin the rules on
small made-up grids: the period most lines share, a line that repeats
with a shorter period, a line that borrows a strip, and where the
extended room switches from strip to room.
"""

from __future__ import annotations

import esphome_components  # noqa: F401
from esphome.components.daruma_sprites import extend


def lines(*texts: str) -> list[list[str]]:
    return [list(t) for t in texts]


def test_period_is_the_one_most_lines_share():
    assert extend._period(lines("abcabcabc", "abcabcabc", "abababab")) == (3, [True, True, False])


def test_period_ties_go_to_the_shortest():
    # "aaaa" repeats every 1 and every 2: the first, 1, wins.
    assert extend._period(lines("aaaa")) == (1, [True])


def test_period_needs_a_window_of_two_periods_and_at_least_four():
    assert extend._period(lines("abab")) == (2, [True])
    assert extend._period(lines("abcabc")) == (3, [True])
    # Too short to tell: no period fits, every line fails.
    assert extend._period(lines("ab")) == (1, [False])
    assert extend._period(lines("abca")) == (1, [False])
    assert extend._period([]) == (1, [])


def test_period_stops_at_max_period():
    texts = ["abcdeabcde"] * 2
    assert extend._period(lines(*texts), max_period=5) == (5, [True, True])
    assert extend._period(lines(*texts), max_period=4)[0] == 1


def test_repeats_checks_the_window_only():
    assert extend._repeats(list("abababX"), 2)
    assert not extend._repeats(list("abaX"), 2)
    assert not extend._repeats(list("aba"), 1)
    assert extend._repeats(list("aaaa"), 1)
    assert not extend._repeats(list("abcab"), 3)


def test_a_line_may_repeat_with_a_period_that_divides_the_strip():
    # The period is 3; "aaaaxyzwv" repeats only every pixel, so its strip is "aaa".
    strips = extend._strip(lines("abcabcabc", "abcabcabc", "aaaaxyzwv", "abcabcabc"))
    assert strips == lines("abc", "abc", "aaa", "abc")


def test_a_line_that_does_not_repeat_borrows_the_nearest_with_its_edge_pixel():
    # Line 0 starts with x: it borrows line 3, not the nearer line 1.
    # Line 4 also starts with x: line 3 is the nearest such.
    strips = extend._strip(lines("xbcabcabc", "abcabcabc", "abcabcabc", "xbcxbcxbc", "xqrstuvwy"))
    assert strips == lines("xbc", "abc", "abc", "xbc", "xbc")


def test_ties_between_borrowed_lines_go_to_the_upper_one():
    strips = extend._strip(lines("abcabcabc", "qrstuvwxy", "defdefdef"))
    assert strips == lines("abc", "abc", "def")


def test_with_no_repeating_line_each_keeps_its_own_start():
    assert extend._strip(lines("abcd", "efgh")) == lines("a", "e")


ROOM = [[5, 6, 7, 8, 9], [1, 2, 1, 2, 1], [3, 4, 3, 4, 3], [1, 2, 1, 2, 1], [3, 4, 3, 4, 3]]


def test_strips_of_a_room_with_a_top_row_that_does_not_repeat():
    assert extend.left_strip(ROOM) == [[1, 2], [1, 2], [3, 4], [1, 2], [3, 4]]
    assert extend.right_strip(ROOM) == [[2, 1], [2, 1], [4, 3], [2, 1], [4, 3]]
    assert extend.top_strip(ROOM) == [[5, 6, 7, 8, 9]]
    assert extend.top_strip([]) == []


def test_extended_room_switches_to_the_strips_at_its_edges():
    out = extend.extended(ROOM, 2, 3, 2)
    assert out == [
        [1, 2, 5, 6, 7, 8, 9, 2, 1, 2],
        [1, 2, 5, 6, 7, 8, 9, 2, 1, 2],
        [1, 2, 5, 6, 7, 8, 9, 2, 1, 2],
        [1, 2, 1, 2, 1, 2, 1, 2, 1, 2],
        [3, 4, 3, 4, 3, 4, 3, 4, 3, 4],
        [1, 2, 1, 2, 1, 2, 1, 2, 1, 2],
        [3, 4, 3, 4, 3, 4, 3, 4, 3, 4],
    ]
    # The room itself is untouched.
    assert [row[2:7] for row in out[2:]] == ROOM


def test_a_shorter_period_must_divide_the_strip_and_fill_its_own_window():
    # The period is 4. "abcabcXY" repeats every 3, but 3 does not divide 4:
    # it borrows. "ababXYZW" repeats every 2 over a window of 4: its strip
    # is "abab".
    strips = extend._strip(lines("abcabcXY", "abcdabcd", "abcdabcd", "ababXYZW"))
    assert strips == lines("abcd", "abcd", "abcd", "abab")


def test_a_line_borrows_the_nearest_line_not_the_first():
    strips = extend._strip(lines("abcabcabc", "qqqqqqqqq", "aXYZWVUTS", "adeadeade"))
    assert strips[2] == list("ade")


def test_extended_right_edge_counts_from_the_room_edge():
    # Width 8 with a right strip of 3: column 8 + k is strip column k mod 3.
    rows = [list("abcabcab")] * 2
    assert extend.right_strip(rows) == [list("cab")] * 2
    assert extend.extended(rows, 0, 4, 0)[0] == list("abcabcab" + "cabc")
    assert extend.extended(rows, 0, 4, 1)[0] == list("abcabcab" + "cabc")


def test_extended_top_edge_starts_above_the_room():
    # Column 2 does not repeat: its top strip is column 1's, so row 0 of the
    # room differs from row 0 of the strip there.
    rows = [[1, 3, 5], [2, 4, 6], [1, 3, 7], [2, 4, 8]]
    assert extend.top_strip(rows) == [[1, 3, 3], [2, 4, 4]]
    out = extend.extended(rows, 0, 0, 2)
    assert out[:2] == [[1, 3, 3], [2, 4, 4]]
    assert out[2:] == rows


def test_strip_passes_its_max_period_on():
    assert extend._strip(lines("abcdeabcde"), max_period=4) == lines("a")
