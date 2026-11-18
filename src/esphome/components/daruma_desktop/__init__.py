"""Daruma on a computer: demo input, a frame recorder and sound capture.

Host builds only (`host:` platform with an `sdl` display). It drives the
device the way a person would, so scripted demos go through the real touch
and button paths:

- touch: taps, holds, swipes and strokes move the SDL display's mouse, which
  the `sdl` touchscreen reads;
- buttons: named binary sensors are pressed and released;
- screen: the hub draws into `canvas()`, a copy of the screen in RAM.
  `frame()` sends the rectangle that changed to the window in one call.
  The sdl display is slow when it gets one pixel at a time;
- frames: each drawn frame is saved as a BMP named by its time, while a
  recording runs. The display lambda calls `frame()` after the hub renders;
- sounds: each sound the device plays is rendered by the synth to a WAV file
  named by its time, next to the frames.

Files go to the directory given to `record_start()`. A recording holds only
what the screen showed, without the window or the mouse pointer.

    daruma_desktop:
      id: desktop
      display: desktop_lcd
      buttons:
        home: home_button
        top: left_top_button
"""

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import binary_sensor
from esphome.components.daruma import CONF_DARUMA_ID, Hub, daruma_ns
from esphome.components.sdl.display import Sdl
from esphome.const import CONF_DISPLAY, CONF_ID, PLATFORM_HOST

DEPENDENCIES = ["daruma", "display"]
AUTO_LOAD = ["json"]

CONF_BUTTONS = "buttons"

Desktop = daruma_ns.class_("Desktop", cg.Component)

CONFIG_SCHEMA = cv.All(
    cv.Schema(
        {
            cv.GenerateID(): cv.declare_id(Desktop),
            cv.GenerateID(CONF_DARUMA_ID): cv.use_id(Hub),
            cv.Required(CONF_DISPLAY): cv.use_id(Sdl),
            cv.Optional(CONF_BUTTONS, default={}): cv.Schema({cv.string_strict: cv.use_id(binary_sensor.BinarySensor)}),
        }
    ).extend(cv.COMPONENT_SCHEMA),
    cv.only_on(PLATFORM_HOST),
)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_display(await cg.get_variable(config[CONF_DISPLAY])))
    cg.add(var.set_hub(await cg.get_variable(config[CONF_DARUMA_ID])))
    for name, sensor_id in config[CONF_BUTTONS].items():
        cg.add(var.add_button(name, await cg.get_variable(sensor_id)))
