"""Host test: the sprite byte format in Python (sprite_codec.py).

    uv run pytest tests/test_sprite_codec.py

test_frames.py checks the encoder against the device's decoder. These
check the parts it can't see: the exact colors, the run bytes at each
index width, and whole pictures (encode_image).
"""

from __future__ import annotations

import random

import esphome_components  # noqa: F401
import pytest
from esphome.components.daruma import sprite_codec as codec

Image = pytest.importorskip("PIL.Image")


def picture(w: int, h: int, color) -> Image.Image:
    img = Image.new("RGBA", (w, h))
    img.putdata([color(x, y) for y in range(h) for x in range(w)])
    return img


def keyframe(w: int, h: int, bits: int, clear: int, palette: list[int], data: list[int]) -> codec.SetFrame:
    return codec.SetFrame(-1, 0, 0, w, h, bits, clear, palette, data, 0)


def test_rgb565_keeps_the_top_bits_of_each_channel():
    assert codec.rgb565(255, 255, 255) == 0xFFFF
    assert codec.rgb565(0b10101111, 0, 0) == 0b10101 << 11
    assert codec.rgb565(0, 0b10101111, 0) == 0b101011 << 5
    assert codec.rgb565(0, 0, 0b10101111) == 0b10101


@pytest.mark.parametrize(
    ("mode", "rgb", "gray"),
    [
        ("mono", (128, 128, 128), 255),
        ("mono", (127, 127, 127), 0),
        ("mono", (255, 0, 0), 0),  # Luminance 76.
        ("mono", (0, 255, 0), 255),  # Luminance 149.
        ("mono", (0, 0, 255), 0),  # Luminance 29.
        ("gray4", (42, 42, 42), 0),
        ("gray4", (43, 43, 43), 85),
        ("gray4", (127, 127, 127), 85),
        ("gray4", (128, 128, 128), 170),
        ("gray4", (212, 212, 212), 170),
        ("gray4", (213, 213, 213), 255),
        ("gray4", (0, 0, 255), 0),
        ("gray4", (255, 0, 0), 85),
        ("gray4", (0, 255, 0), 170),
    ],
)
def test_gray_for_matches_quantize_gray(mode, rgb, gray):
    assert codec.gray_for(mode, *rgb) == gray


def test_screen_pixels_clears_alpha_below_128_and_grays_the_rest():
    img = picture(4, 1, lambda x, y: [(255, 0, 0, 127), (255, 0, 0, 128), (0, 255, 0, 255), (9, 9, 9, 0)][x])
    assert codec.screen_pixels(img) == [codec.CLEAR, 0xF800, 0x07E0, codec.CLEAR]
    gray = codec.rgb565(170, 170, 170)
    assert codec.screen_pixels(img, "gray4") == [codec.CLEAR, codec.rgb565(85, 85, 85), gray, codec.CLEAR]
    assert codec.screen_pixels(img, "mono") == [codec.CLEAR, 0, 0xFFFF, codec.CLEAR]


def test_reduce_colors_grays_only_what_is_seen():
    img = picture(2, 1, lambda x, y: [(0, 255, 0, 255), (0, 255, 0, 100)][x])
    assert codec.reduce_colors(img, "full") is img
    assert list(codec.reduce_colors(img, "gray4").getdata()) == [(170, 170, 170, 255), (0, 255, 0, 100)]
    assert list(codec.reduce_colors(img, "mono").getdata()) == [(255, 255, 255, 255), (0, 255, 0, 100)]


@pytest.mark.parametrize(("codes", "bits"), [(1, 1), (2, 1), (3, 2), (4, 2), (5, 3), (129, 8), (256, 8)])
def test_bits_fit_the_codes(codes, bits):
    assert codec._bits(codes) == bits


def test_runs_at_three_bits_use_a_long_byte_after_31():
    # Three bits leave five for the length: 31 at most in one byte.
    assert codec._runs([2] * 31, 31, 1, 7, 3) == [2 << 5 | 31]
    assert codec._runs([2] * 32, 32, 1, 7, 3) == [2 << 5, 0]
    assert codec._runs([2] * 300, 300, 1, 7, 3) == [2 << 5, 255, 2 << 5 | 13]


def test_runs_at_eight_bits_are_two_bytes_of_at_most_256():
    assert codec._runs([5] * 300, 300, 1, 200, 8) == [5, 255, 5, 43]


def test_runs_copy_the_row_above_when_that_is_longer():
    codes = [1, 2, 3, 4] + [1, 2, 3, 0]
    assert codec._runs(codes, 4, 2, 7, 3) == [1 << 5 | 1, 2 << 5 | 1, 3 << 5 | 1, 4 << 5 | 1, 7 << 5 | 3, 0 << 5 | 1]


def test_encode_image_decodes_to_its_pixels():
    # Two colors, see-through pixels and long rows: a 2-bit picture.
    img = picture(70, 3, lambda x, y: (255, 0, 0, 255) if x % 35 < 20 else (0, 0, 0, 0))
    w, h, bits, clear, palette, data = codec.encode_image(img, "test")
    assert (w, h, bits) == (70, 3, 2)
    assert palette[clear] == 0
    frame = keyframe(w, h, bits, clear, palette, data)
    assert codec.decode_set(codec.FrameSet(w, h, [frame], [0]))[0] == codec.screen_pixels(img)


def test_encode_image_takes_at_most_255_colors():
    # 256 colors, all different at RGB565.
    many = picture(256, 1, lambda x, y: (x // 32 * 8, x % 32 * 8, 0, 255))
    with pytest.raises(ValueError, match="at most 255"):
        codec.encode_image(many, "many")
    fine = picture(255, 1, lambda x, y: (x // 32 * 8, x % 32 * 8, 0, 255))
    assert codec.encode_image(fine, "fine")[2] == 8


def test_eight_bit_sets_roundtrip():
    """More than 127 colors need 8-bit indexes: two bytes a run."""

    def shade(v):
        return v // 32 * 8, v % 32 * 8, 0, 255

    frames = [picture(300, 3, lambda x, y, k=k: shade((x // 2 + y + k) % 200)) for k in range(3)]
    fs = codec.encode_set(frames, [[0, 1, 2]])
    assert fs.frames[0].bits == 8
    decoded = codec.decode_set(fs)
    for i, img in enumerate(frames):
        assert decoded[fs.index[i]] == codec.screen_pixels(img)


def test_long_runs_roundtrip_at_low_bits():
    flat = picture(600, 2, lambda x, y: (0, 0, 255, 255) if x < 400 else (255, 0, 0, 255))
    dot = picture(600, 2, lambda x, y: (0, 255, 0, 255) if (x, y) == (599, 1) else flat.getpixel((x, y)))
    fs = codec.encode_set([flat, dot], [[0, 1]])
    assert fs.frames[0].bits < 8
    assert codec.decode_set(fs) == [codec.screen_pixels(flat), codec.screen_pixels(dot)]


def test_frame_sizes_count_data_palette_and_fields():
    frame = keyframe(1, 1, 1, -1, [1, 2, 3], [9, 9])
    assert frame.size() == 2 + 2 * 3 + 16
    assert codec.FrameSet(1, 1, [frame, frame], [0, 1]).size() == 2 * frame.size()
    assert frame.key
    assert not codec.SetFrame(0, 0, 0, 1, 1, 1, -1, [], [], 1).key


def test_a_patch_covers_only_the_changed_box():
    base = picture(8, 6, lambda x, y: (0, 0, 255, 255))
    moved = picture(8, 6, lambda x, y: (255, 0, 0, 255) if (x, y) in {(2, 1), (5, 3)} else (0, 0, 255, 255))
    fs = codec.encode_set([base, moved], [[0, 1]])
    patch = fs.frames[1]
    assert (patch.base, patch.x, patch.y, patch.w, patch.h, patch.depth) == (0, 2, 1, 4, 3, 1)
    assert patch.palette == [0xF800]


@pytest.mark.parametrize(
    ("rgb", "gray"),
    [
        # Each sits next to a mono threshold: one more in any weight crosses it.
        ((6, 215, 0), 0),
        ((0, 180, 195), 0),
        ((0, 175, 220), 0),
    ],
)
def test_gray_for_weights_are_exact(rgb, gray):
    assert codec.gray_for("mono", *rgb) == gray


def test_reduce_colors_and_screen_pixels_take_any_picture_mode():
    rgb = Image.new("RGB", (2, 1), (0, 255, 0))
    assert list(codec.reduce_colors(rgb, "mono").getdata()) == [(255, 255, 255, 255)] * 2
    assert codec.screen_pixels(rgb) == [0x07E0, 0x07E0]


def test_reduce_colors_grays_from_alpha_128():
    img = picture(2, 1, lambda x, y: [(0, 255, 0, 127), (0, 255, 0, 128)][x])
    assert list(codec.reduce_colors(img, "mono").getdata()) == [(0, 255, 0, 127), (255, 255, 255, 255)]


def test_palette_is_by_count_most_first():
    palette, at = codec._palette([7, 5, 5, 9, 9, 9])
    assert palette == [9, 5, 7]
    assert at == {9: 0, 5: 1, 7: 2}


def test_lanes_put_the_first_pixel_lowest():
    assert codec._lanes([1, 2]) == 1 | 2 << 32
    assert codec._lanes([]) == 0


@pytest.mark.parametrize("bit", range(32))
def test_differing_lanes_counts_a_lane_with_any_one_bit(bit):
    # The lane sits between two empty ones, so a bit that spills over shows.
    value = (1 << bit) - (1 << 32 if bit == 31 else 0)  # As a signed 32-bit int.
    ones = codec._lanes([1, 1, 1])
    assert codec._differing_lanes(codec._lanes([0, value, 0]), ones, 32) == 1
    assert codec._differing_lanes(codec._lanes([value, 0, -1]), ones, 32) == 2
    assert codec._differing_lanes(codec._lanes([0, 0, value]), ones, 32) == 1


@pytest.mark.parametrize("bit", range(8))
def test_differing_lanes_counts_a_byte_lane_with_any_one_bit(bit):
    ones = int.from_bytes(b"\x01\x01\x01", "little")
    lane = (1 << bit) << 8  # The middle of three byte lanes.
    assert codec._differing_lanes(lane, ones, 8) == 1
    assert codec._differing_lanes(lane | 0xFF << 16, ones, 8) == 2


def test_set_lanes_give_a_small_set_a_byte_per_pixel_by_color_order():
    lanes, ones, width = codec._set_lanes([[700, 5, codec.CLEAR], [5, 5, 700]])
    # The colors in order: CLEAR (-1) is 0, 5 is 1, 700 is 2.
    assert width == 8
    assert lanes == [int.from_bytes(bytes([2, 1, 0]), "little"), int.from_bytes(bytes([1, 1, 2]), "little")]
    assert ones == int.from_bytes(b"\x01\x01\x01", "little")


def test_set_lanes_keep_32_bits_past_256_colors():
    for colors, width in ((256, 8), (257, 32)):
        a = list(range(colors))
        b = a[1:] + a[:1]
        lanes, ones, got = codec._set_lanes([a, b])
        assert got == width
        assert codec._differing_lanes(lanes[0] ^ lanes[1], ones, got) == colors
        assert codec._differing_lanes(lanes[0] ^ lanes[0], ones, got) == 0
    lanes, ones, _ = codec._set_lanes([list(range(257))])
    assert lanes == [codec._lanes(list(range(257)))]
    assert ones == codec._lanes([1] * 257)


def test_encode_image_without_see_through_has_no_clear_index():
    img = picture(3, 1, lambda x, y: (255, 0, 0, 255))
    assert codec.encode_image(img, "red")[3] == -1


def test_encode_image_reduces_colors_by_mode():
    img = picture(2, 1, lambda x, y: [(0, 255, 0, 255), (0, 250, 0, 255)][x])
    assert codec.encode_image(img, "green", "mono")[4] == [0xFFFF]
    assert len(codec.encode_image(img, "green")[4]) == 2


def test_frames_mark_see_through_with_a_zero_entry():
    seen = picture(4, 1, lambda x, y: (255, 0, 0, 255))
    holes = picture(4, 1, lambda x, y: (0, 0, 0, 0) if x == 1 else (255, 0, 0, 255))
    fs = codec.encode_set([seen, holes, holes], [[0, 1]])
    key, patch = fs.frames
    assert (key.base, key.x, key.y, key.clear, key.palette) == (-1, 0, 0, -1, [0xF800])
    assert patch.base == 0
    assert patch.palette[patch.clear] == 0
    red = picture(4, 1, lambda x, y: (255, 0, 0, 255) if x == 1 else (0, 0, 255, 255))
    solid = codec.encode_set([red, seen], [[0, 1]]).frames[1]
    assert (solid.base, solid.clear) == (0, -1)
    alone = codec.encode_set([holes])
    assert alone.frames[0].palette[alone.frames[0].clear] == 0


def test_index_bits_leave_room_for_the_codes():
    # Three colors and "same as above": 2 bits. A patch adds "keep".
    three = picture(3, 2, lambda x, y: [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255)][x])
    fs = codec.encode_set([three])
    assert fs.frames[0].bits == 2
    two = picture(3, 2, lambda x, y: (9, 9, 9, 255) if (x, y) == (0, 0) else three.getpixel((x, y)))
    two = picture(3, 2, lambda x, y: (200, 200, 200, 255) if y == 1 and x < 2 else two.getpixel((x, y)))
    patch = codec.encode_set([three, two], [[0, 1]]).frames[1]
    assert (patch.base, len(patch.palette), patch.bits) == (0, 2, 2)


def _shades(n: int, k: int = 0):
    """n colors, all different at RGB565."""
    return [((v + k) // 32 * 8, (v + k) % 32 * 8, 0, 255) for v in range(n)]


def test_a_keyframe_takes_at_most_255_colors():
    assert codec.encode_set([picture(255, 1, lambda x, y: _shades(255)[x])]).frames[0].bits == 8
    with pytest.raises(ValueError, match="at most 255"):
        codec.encode_set([picture(256, 1, lambda x, y: _shades(256)[x])])


def test_a_patch_takes_at_most_254_colors():
    # Every pixel changes, so the patch has all the frame's colors.
    def pair(n):
        base = picture(n, 1, lambda x, y: (255, 255, 255, 255))
        return [base, picture(n, 1, lambda x, y: _shades(n)[x])]

    assert codec.encode_set(pair(254), [[0, 1]]).frames[1].base == 0
    with pytest.raises(ValueError, match="at most 254"):
        codec.encode_set(pair(255), [[0, 1]])


def test_one_picture_is_one_keyframe():
    fs = codec.encode_set([picture(2, 2, lambda x, y: (1, 2, 3, 255))])
    assert [f.key for f in fs.frames] == [True]


def _walk(n: int, width: int = 40):
    return [picture(width, 4, lambda x, y, i=i: (255, 0, 0, 255) if x == i else (0, 0, 255, 255)) for i in range(n)]


def test_patches_stack_up_to_max_depth():
    fs = codec.encode_set(_walk(12), [list(range(12))])
    assert max(f.depth for f in fs.frames) == codec.MAX_DEPTH


def test_first_frames_patch_only_up_to_first_depth():
    # Every frame starts an animation of its own.
    fs = codec.encode_set(_walk(6), [[i] for i in range(6)])
    assert max(f.depth for f in fs.frames) == codec.FIRST_DEPTH
    # Frames no sequence names count as first frames too.
    fs = codec.encode_set(_walk(6))
    assert max(f.depth for f in fs.frames) == codec.FIRST_DEPTH


def _dots(*xs):
    return picture(40, 4, lambda x, y: (255, 0, 0, 255) if x in xs else (0, 0, 255, 255))


def test_a_frame_patches_the_closest_frame():
    # The last frame is the first with one more dot; the four between are
    # farther from both, so only counting changed pixels finds the first.
    far = [_dots(*range(10, 10 + k)) for k in (20, 22, 24, 26)]
    fs = codec.encode_set([_dots(1), *far, _dots(1, 2)])
    assert fs.frames[5].base == 0


def test_the_closest_frame_wins_wherever_it_sits():
    # The close frame comes after more far ones than CANDIDATES, so only
    # the changed-pixel count, not the order, puts it among the bases tried.
    far = [_dots(*range(10, 10 + k)) for k in (20, 22, 24, 26, 28)]
    fs = codec.encode_set([*far, _dots(1), _dots(1, 2)])
    assert len(far) > codec.CANDIDATES
    assert fs.frames[6].base == 5


def test_a_frame_may_patch_its_animations_first_frame():
    # The last frame is the first with a compact block. The six between
    # differ from it in fewer pixels, spread wide: patches on them cost more.
    w, h = 64, 16
    block = {(x, y) for x in range(20, 30) for y in range(4, 12)}

    def last(x, y):
        return (255, 0, 0, 255) if (x, y) in block else (0, 0, 255, 255)

    def between(k):
        rnd = random.Random(k)
        spots = {(rnd.randrange(w), rnd.randrange(h)) for _ in range(30)}
        return picture(w, h, lambda x, y: (k * 40 % 256, k * 20, 0, 255) if (x, y) in spots else last(x, y))

    images = [picture(w, h, lambda x, y: (0, 0, 255, 255)), *map(between, range(1, 7)), picture(w, h, last)]
    fs = codec.encode_set(images, [list(range(8))])
    assert fs.frames[7].base == 0
