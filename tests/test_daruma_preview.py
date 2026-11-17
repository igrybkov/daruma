"""daruma_preview.py sizes the daruma's frames with the firmware's own encoder."""

from __future__ import annotations

from pathlib import Path

import esphome_components  # noqa: F401
import pytest
from esphome.components.daruma import sprite_codec

pytest.importorskip("PIL")


def test_the_preview_loads_the_firmware_encoder() -> None:
    from daruma_pixel import daruma_preview

    encoder = daruma_preview._encoder()
    assert Path(encoder.__file__).resolve() == Path(sprite_codec.__file__).resolve()
    assert callable(encoder.encode_image)
