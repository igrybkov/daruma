"""Sound effects made on the device: chiptune sounds rendered on first use.

Sounds come from the current persona (its `sounds:`, else the built-in ones in
daruma/synth.cpp) and are kept as WAV in PSRAM, within `cache_size`.
When a new sound does not fit, the least recently played ones are freed;
the two most recent stay, as one may still be playing. Keep cache_size at
three times the longest sound (96 kB per second) or more: below that, the
cache can go over by a sound, and the log says so.

    daruma_sounds:
      cache_size: 384kB
"""

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import audio
from esphome.components.daruma import daruma_ns

DEPENDENCIES = ["daruma", "audio", "psram"]

CONF_CACHE_SIZE = "cache_size"

Sounds = daruma_ns.class_("Sounds")

CONFIG_SCHEMA = cv.Schema(
    {
        cv.Optional(CONF_CACHE_SIZE, default="384kB"): cv.All(
            cv.validate_bytes, cv.int_range(min=64 * 1024, max=4 * 1024 * 1024)
        ),
    }
)


async def to_code(config):
    audio.request_wav_support()
    cg.add(cg.RawStatement(f"Daruma::Sounds::set_cache_size({config[CONF_CACHE_SIZE]});"))
