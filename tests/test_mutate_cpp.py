"""mutate_cpp.py: which C++ tests it runs, and how a test gets its fixture."""

from __future__ import annotations

from pathlib import Path

import mutate_cpp


def test_every_cpp_test_counts_test_frames_too():
    assert "test_frames" in mutate_cpp.tests()


def test_test_frames_reads_its_fixture_from_next_to_the_work_folders():
    exe = Path("/work/0/test_frames")
    assert mutate_cpp.run_command("test_frames", exe) == [str(exe), "/work/test_frames-fixture.txt"]
    assert mutate_cpp.run_command("test_layout", Path("/work/0/test_layout")) == ["/work/0/test_layout"]


def test_the_decoder_headers_are_mutated_through_test_frames():
    headers = mutate_cpp.headers_by_test()["test_frames"]
    assert "src/esphome/components/daruma/frame_chain.h" in headers
    assert "src/esphome/components/daruma/sprite.h" in headers
