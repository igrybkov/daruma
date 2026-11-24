#pragma once

// Whether a sound may play past the Sounds switch. Plain C++, host-tested
// (tests/test_quiet.cpp).

namespace Daruma {

// Sounds on: every sound plays. Sounds off by the person: none. Sounds off
// because a module holds it (Do not disturb): only urgent sounds.
inline bool sound_passes(bool sounds_on, bool held, bool urgent) { return sounds_on || (held && urgent); }

}  // namespace Daruma
