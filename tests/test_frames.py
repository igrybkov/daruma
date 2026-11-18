"""Host tests of animation frames stored as keyframes and patches.

    uv run pytest tests/test_frames.py

- The encoder (src/esphome/components/daruma/sprite_codec.py) round trips through
  its own Python decoder, on small made-up frames.
- The device's decoder (frame_chain.h, sprite.h), built with the host's
  c++ (cpp_build.py), decodes every frame of every pixel persona to exactly its source
  picture, in full color, gray4 and mono, on its own and played in order
  (test_frames.cpp). This builds the personas: some seconds. Set
  DARUMA_SKIP_PERSONAS=1 to check only the made-up frames.

The decoder program is kept in the temp folder, named by a hash of what
goes into it, so later runs and other workers skip its build.

Skipped without Pillow, and the C++ part without a c++ compiler.
"""

import hashlib
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import cpp_build

_HERE = Path(__file__).resolve().parent

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None

if Image is not None:
    import frames_fixture

    codec = frames_fixture.codec


def _picture(rows: list[str], colors: dict[str, tuple]) -> "Image.Image":
    img = Image.new("RGBA", (len(rows[0]), len(rows)))
    img.putdata([colors[ch] for row in rows for ch in row])
    return img


COLORS = {".": (0, 0, 0, 0), "r": (255, 0, 0, 255), "g": (0, 255, 0, 255), "b": (0, 0, 255, 255)}


@unittest.skipIf(Image is None, "needs Pillow")
class EncoderTest(unittest.TestCase):
    def roundtrip(self, images, sequences, mode="full"):
        fs = codec.encode_set(images, sequences, mode)
        decoded = codec.decode_set(fs)
        for i, img in enumerate(images):
            self.assertEqual(decoded[fs.index[i]], codec.screen_pixels(img, mode), f"picture {i}")
        return fs

    def test_patch_keeps_clears_and_paints(self):
        a = _picture(["rrrr", "r..r", "rrrr"], COLORS)
        b = _picture(["rrrr", "r.gr", "rr.r"], COLORS)  # One pixel painted, one cleared.
        fs = self.roundtrip([a, b], [[0, 1]])
        patch = fs.frames[1]
        self.assertEqual(patch.base, 0)
        self.assertEqual((patch.x, patch.y, patch.w, patch.h), (2, 1, 1, 2))

    def test_same_pictures_are_one_frame(self):
        a = _picture(["rg", "gr"], COLORS)
        b = _picture(["rg", "gr"], COLORS)
        fs = self.roundtrip([a, b, a], [[0, 1, 2]])
        self.assertEqual(len(fs.frames), 1)
        self.assertEqual(fs.index, [0, 0, 0])

    def test_depth_is_capped(self):
        # A dot moving one pixel per frame: every frame wants the one before.
        frames = [_picture(["".join("r" if x == i else "." for x in range(30))], COLORS) for i in range(30)]
        fs = self.roundtrip(frames, [list(range(30))])
        self.assertLessEqual(max(f.depth for f in fs.frames), codec.MAX_DEPTH)

    def test_first_frames_stay_shallow(self):
        frames = [_picture(["".join("r" if x <= i else "b" for x in range(16))] * 4, COLORS) for i in range(16)]
        # Each animation starts at a different frame.
        seqs = [list(range(k, 16)) + list(range(0, k)) for k in range(0, 16, 3)]
        fs = self.roundtrip(frames, seqs)
        for seq in seqs:
            self.assertLessEqual(fs.frames[fs.index[seq[0]]].depth, codec.FIRST_DEPTH)

    def test_prefers_the_frame_before(self):
        a = _picture(["rrrrrrrr"] * 4, COLORS)
        b = _picture(["rrrrrrrg"] + ["rrrrrrrr"] * 3, COLORS)
        c = _picture(["rrrrrrgg"] + ["rrrrrrrr"] * 3, COLORS)
        fs = self.roundtrip([a, b, c], [[0, 1, 2]])
        self.assertEqual(fs.frames[2].base, 1)

    def test_gray_modes(self):
        a = _picture(["rgb.", "bgr."], COLORS)
        b = _picture(["rgb.", "bgg."], COLORS)
        for mode in ("gray4", "mono"):
            self.roundtrip([a, b], [[0, 1]], mode)

    def test_sizes_must_match(self):
        with self.assertRaises(ValueError):
            codec.encode_set([_picture(["r"], COLORS), _picture(["rr"], COLORS)])


MODES = ("full", "gray4", "mono")
_DECODER = _HERE.parent / "src" / "esphome" / "components" / "daruma"
_BUILDS = Path(tempfile.gettempdir()) / "daruma-test-frames"


def _build_key(args: list[str]) -> str:
    """A hash of the compiler and its arguments, the compiler's version, the
    test and the decoder's headers."""
    key = hashlib.sha256("\0".join([*cpp_build.compiler(), *args]).encode())
    key.update(subprocess.run([*cpp_build.compiler(), "--version"], capture_output=True, check=True).stdout)
    for source in [_HERE / "test_frames.cpp", *sorted(_DECODER.glob("*.h"))]:
        key.update(source.name.encode() + b"\0" + source.read_bytes())
    return key.hexdigest()[:16]


def _build(args: list[str], binary: Path) -> None:
    done = cpp_build.build(args, binary, os.environ.get("CXXFLAGS", "").split())
    if done.returncode:
        raise RuntimeError(f"building test_frames.cpp failed:\n{done.stdout}{done.stderr}")


@unittest.skipIf(Image is None or not cpp_build.available(), "needs Pillow and a c++ compiler")
class DeviceDecoderTest(unittest.TestCase):
    """One test per frame set, so pytest-xdist can spread the personas."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        args = [
            "-std=c++17",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-O1",
            *os.environ.get("CXXFLAGS", "").split(),
            f"-I{_DECODER}",
            str(_HERE / "test_frames.cpp"),
        ]
        # For coverage, as tests/conftest.py: CXXFLAGS above, and a folder
        # that keeps the program and its data. One program per worker,
        # named by the worker, so ccache finds the object at the same path
        # in every run.
        if os.environ.get("DARUMA_CPP_OUT"):
            worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
            cls.binary = Path(os.environ["DARUMA_CPP_OUT"]) / f"test_frames-{worker}"
            cls.binary.parent.mkdir(parents=True, exist_ok=True)
            _build(args, cls.binary)
            return
        # Otherwise one program for every worker and run, named by what
        # went into it. A worker that finds it skips the build.
        cls.binary = _BUILDS / f"test_frames-{_build_key(args)}"
        if not cls.binary.exists():
            _BUILDS.mkdir(parents=True, exist_ok=True)
            built = Path(cls._tmp.name) / "test_frames"
            _build(args, built)
            os.replace(built, cls.binary)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def decode(self, sets):
        fixture = Path(self._tmp.name) / f"frames-{self.id()}.txt"
        frames_fixture.write(fixture, sets, MODES)
        run = subprocess.run([str(self.binary), str(fixture)], capture_output=True, text=True)
        print(run.stdout.strip().splitlines()[-1] if run.stdout.strip() else run.stderr)
        self.assertEqual(run.returncode, 0, run.stdout[-2000:])

    def test_device_decodes_made_up_frames(self):
        self.decode(frames_fixture.synthetic())


def _persona_test(label: str):
    @unittest.skipIf(os.environ.get("DARUMA_SKIP_PERSONAS"), "DARUMA_SKIP_PERSONAS is set")
    def test(self):
        build = dict(frames_fixture.persona_builds())[label]
        found = frames_fixture.persona_set(label, build)
        if found is None:
            self.skipTest(f"{label}: its art lives elsewhere")
        self.decode([found])

    return test


# The device decodes every frame of each pixel persona.
if Image is not None:
    for _label, _ in frames_fixture.persona_builds():
        setattr(DeviceDecoderTest, f"test_device_decodes_{_label}", _persona_test(_label))


if __name__ == "__main__":
    unittest.main()
