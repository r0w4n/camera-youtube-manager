import json
from pathlib import Path

from camera_config import AppSettings


def get_settings_file_path():
    return Path(__file__).resolve().parent.parent / "settings.json"


def get_settings():
    with get_settings_file_path().open() as settings_file:
        return AppSettings.from_dict(json.load(settings_file))
