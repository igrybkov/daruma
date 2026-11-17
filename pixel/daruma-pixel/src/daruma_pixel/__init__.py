"""Daruma's pixel drawing layer: what every pixel persona is drawn with, at build time.

    personas   build(name) -> Persona: every layer and frame the device needs;
               Spec says what a persona is; discover() finds them all
    scene      the Scene interface, spots, and Grower (a progress prop)
    effects    hearts, zzz, sweat, tears, dots and sparkles round any actor
    pixelkit   shapes on a low-res canvas, outlines and shading

Two namespace packages build on it, one workspace member per part:

    daruma_shapes.pets     the sitting-pet rig, dogs and cats
    daruma_shapes.rooms    the cozy room, the living room and its couch, the studio
    daruma_shapes.plants   pothos, spider plant, cat grass, bonsai
    daruma_shapes.office   the desk, the chair and the person at them
    daruma_personas.<name> one persona each: corgi, jack_russell, tabby_cat,
                           the_boss, daruma

Firmware builds load them from the Daruma checkout. Elsewhere, install this
layer: pip install "git+https://github.com/igrybkov/daruma#subdirectory=pixel/daruma-pixel".
"""
