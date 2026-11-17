"""Daruma's pixel-art library: the rooms, personas and engines its pixel
personas are drawn with, at build time.

    personas   build(name) -> Persona: every layer and frame the device needs;
               Spec says what a persona is; discover() finds them all
    scene      the Scene interface: what is behind a persona
    effects    hearts, zzz, sweat, tears, dots and sparkles round any actor
    pixelkit   shapes on a low-res canvas, outlines and shading
    pet        a sitting pet in a room (room.py, living_room.py, studio.py);
               dog.py, corgi.py, jack_russell.py, cat.py and tabby_cat.py
               are on it
    desk_boss  a person behind a desk; the_boss.py is a look on it
    daruma     the daruma doll and its tatami room (bonsai.py)

Firmware builds load it from the Daruma checkout. Elsewhere, install it:
pip install "git+https://github.com/igrybkov/daruma".
"""
