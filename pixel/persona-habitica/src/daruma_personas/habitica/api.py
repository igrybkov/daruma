"""The look from Habitica's API, read once per build.

    GET https://habitica.com/api/v3/user?userFields=preferences,items.gear,...

with the user id and the API token from the options, and the `x-client`
header Habitica asks third-party tools to send (`<user id>-daruma`). The
part of the reply that makes the look (preferences, items, stats) is saved
as the last look in the builder's data folder. When Habitica can't be
reached, the build uses that last look, with a warning.

The token and the user id are used for the request only. They are never
logged, saved or returned.
"""

from __future__ import annotations

import json
import logging
import urllib.request
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from .sources import CACHE_FOLDER, TIMEOUT

log = logging.getLogger(__name__)

USER_URL = "https://habitica.com/api/v3/user"
USER_FIELDS = "preferences,items.gear,items.currentPet,items.currentMount,stats.class"
LAST_LOOK = "last_look.json"
LOOK_KEYS = ("preferences", "items", "stats")  # What of the user object makes the look.


class LookUnavailable(RuntimeError):
    """No look: Habitica can't be reached and no last look is saved."""


def http_get(url: str, headers: Mapping[str, str]) -> bytes:
    """The body at `url`. Raises OSError (urllib's errors among them) when it fails."""
    request = urllib.request.Request(url, headers=dict(headers))
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310 - a fixed https URL
        return response.read()


def fetch_user(user_id: str, token: str, get: Callable[[str, Mapping[str, str]], bytes]) -> dict[str, Any]:
    """The look part of the user object, from one GET."""
    headers = {"x-api-user": user_id, "x-api-key": token, "x-client": f"{user_id}-daruma"}
    reply = json.loads(get(f"{USER_URL}?userFields={USER_FIELDS}", headers))
    if not isinstance(reply, dict) or not reply.get("success") or not isinstance(reply.get("data"), dict):
        raise ValueError("Habitica's reply holds no user")
    return {key: reply["data"][key] for key in LOOK_KEYS if key in reply["data"]}


def last_look_path(data_dir: Path) -> Path:
    return Path(data_dir) / CACHE_FOLDER / LAST_LOOK


def save_last_look(data_dir: Path | None, user: Mapping[str, Any]) -> None:
    if data_dir is None:
        return
    path = last_look_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")  # pragma: no mutate (any spare name works)
    tmp.write_text(json.dumps(user, sort_keys=True, indent=1))
    tmp.replace(path)


def read_last_look(data_dir: Path | None) -> dict[str, Any] | None:
    if data_dir is None or not last_look_path(data_dir).is_file():
        return None
    return json.loads(last_look_path(data_dir).read_text())


def user_from_api(user_id: str, token: str, data_dir: Path | None) -> dict[str, Any]:
    """The user's look from Habitica, saved as the last look; offline, the last look."""
    try:
        user = fetch_user(user_id, token, http_get)
    except (OSError, ValueError) as err:  # Offline, refused, or an odd reply.
        last = read_last_look(data_dir)
        if last is None:
            raise LookUnavailable(
                f"habitica: could not read the look ({type(err).__name__}), and no last look is saved"
            ) from None
        log.warning("habitica: could not read the look (%s); using the last look", type(err).__name__)
        return last
    save_last_look(data_dir, user)
    return user
