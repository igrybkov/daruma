#pragma once

// Every state a persona can be asked to show, as a typed id. The list is
// generated at build time from the registry (daruma/registry.py: the
// core's states plus each included module's) into the DARUMA_STATE_LIST
// macro in defines.h. Strings remain only for logs and HA selects.
//
// Each entry is X(ID, "name", KIND, fallback index or -1, duration ms,
// celebrates): `celebrates` is true when the fallback chain passes through
// `celebrate`, which ends with a double wink.

#include <cstdint>
#include <cstring>

#ifndef DARUMA_STATE_LIST
#include "esphome/core/defines.h"
#endif

#ifndef DARUMA_STATE_LIST
// Only for editors and tools that read this header without a build.
#define DARUMA_STATE_LIST X(NEUTRAL, "neutral", MOOD, -1, 0, false)
#endif

namespace Daruma {

enum class StateKind : uint8_t { MOOD, ACTIVITY, REACTION };

enum class StateId : uint8_t {
#define X(id, name, kind, fallback, ms, celebrates) id,
  DARUMA_STATE_LIST
#undef X
};

struct StateInfo {
  const char *name;
  StateKind kind;
  int8_t fallback;
  uint16_t duration_ms;
  bool celebrates;
};

inline const StateInfo &state_info(StateId id) {
  static const StateInfo INFO[] = {
#define X(id, name, kind, fallback, ms, celebrates) {name, StateKind::kind, fallback, ms, celebrates},
      DARUMA_STATE_LIST
#undef X
  };
  return INFO[static_cast<uint8_t>(id)];
}

inline constexpr int state_count() {
  return 0
#define X(id, name, kind, fallback, ms, celebrates) +1
      DARUMA_STATE_LIST
#undef X
      ;
}

inline const char *state_name(StateId id) { return state_info(id).name; }

// The state with this name, any case. False when there is none.
inline bool state_by_name(const char *name, StateId *out) {
  for (int i = 0; i < state_count(); i++) {
    const char *candidate = state_info(static_cast<StateId>(i)).name;
    size_t k = 0;
    for (; candidate[k] != '\0' && name[k] != '\0'; k++) {
      char c = name[k];
      if (c >= 'A' && c <= 'Z')
        c = (char) (c - 'A' + 'a');
      if (c != candidate[k])
        break;
    }
    if (candidate[k] == '\0' && name[k] == '\0') {
      *out = static_cast<StateId>(i);
      return true;
    }
  }
  return false;
}

}  // namespace Daruma
