"""Builds the host C++ programs: tests/conftest.py, test_frames.py and
mutate_cpp.py use it.

The compiler is $CXX, else c++. CI sets CXX="ccache c++". ccache caches a
compile (-c) but not a compile and link in one call, so a build is two
steps: the object, then the program.
"""

import os
import shlex
import shutil
import subprocess
from pathlib import Path


def compiler() -> list[str]:
    """The compiler command: $CXX split into words, else c++."""
    return shlex.split(os.environ.get("CXX") or "c++")


def available() -> bool:
    """Whether every program in the compiler command is on the PATH."""
    return all(shutil.which(word) for word in compiler() if not word.startswith("-"))


def build(args: list[str], out: Path, link_flags: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Compiles to `out`.o, then links `out`. Returns the step that failed,
    or the link. `args` holds the flags and the source. `link_flags` holds
    the flags the link needs too (--coverage)."""
    cxx = compiler()
    obj = Path(f"{out}.o")
    done = subprocess.run([*cxx, *args, "-c", "-o", str(obj)], cwd=cwd, capture_output=True, text=True, check=False)
    if done.returncode:
        return done
    link = [*cxx, *link_flags, str(obj), "-o", str(out)]
    return subprocess.run(link, cwd=cwd, capture_output=True, text=True, check=False)
