from __future__ import annotations

import os
from pathlib import Path


APP_DIR_NAME = "MiniaturedWorld"


def default_data_root() -> Path:
    override = os.environ.get("MINIATURED_WORLD_DATA_DIR")
    if override:
        return Path(override).expanduser()

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / APP_DIR_NAME

    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home) / APP_DIR_NAME

    return Path.home() / ".miniatured_world"

