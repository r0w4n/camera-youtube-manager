import json
import sys
from pathlib import Path

import pytest


SOURCE_DIR = Path(__file__).resolve().parents[1] / "source"
sys.path.insert(0, str(SOURCE_DIR))

from camera_config import AppSettings, CameraConfig
import settings


def test_app_settings_from_dict_builds_typed_camera_configs():
    """Verify that valid config data is converted into typed camera settings."""
    app_settings = AppSettings.from_dict(
        {
            "cameras": [
                {
                    "name": "cam1",
                    "title": "Garden Camera",
                    "description": "Live stream",
                    "enabled": True,
                    "url": "user:pass@camera.local/stream",
                    "key": "stream-key",
                }
            ]
        }
    )

    assert app_settings == AppSettings(
        cameras=[
            CameraConfig(
                name="cam1",
                title="Garden Camera",
                description="Live stream",
                enabled=True,
                url="user:pass@camera.local/stream",
                key="stream-key",
            )
        ]
    )


def test_app_settings_from_dict_defaults_to_empty_camera_list():
    """Verify that missing camera config defaults to an empty settings list."""
    assert AppSettings.from_dict({}) == AppSettings(cameras=[])


def test_app_settings_from_dict_rejects_missing_required_camera_fields():
    """Verify that incomplete camera config fails clearly during settings load."""
    with pytest.raises(ValueError, match="required field\\(s\\): key"):
        AppSettings.from_dict(
            {
                "cameras": [
                    {
                        "name": "cam1",
                        "title": "Garden Camera",
                        "url": "user:pass@camera.local/stream",
                    }
                ]
            }
        )


def test_app_settings_from_dict_rejects_non_list_cameras():
    """Verify that the top-level cameras value must be a list."""
    with pytest.raises(ValueError, match="must be a list"):
        AppSettings.from_dict({"cameras": {}})


def test_get_settings_loads_settings_json(monkeypatch, tmp_path):
    """Verify that get_settings reads the configured settings file path."""
    settings_file_path = tmp_path / "settings.json"
    settings_file_path.write_text(
        json.dumps(
            {
                "cameras": [
                    {
                        "name": "cam1",
                        "title": "Garden Camera",
                        "description": "Live stream",
                        "enabled": True,
                        "url": "user:pass@camera.local/stream",
                        "key": "stream-key",
                    }
                ]
            }
        )
    )
    monkeypatch.setattr(settings, "get_settings_file_path", lambda: settings_file_path)

    loaded_settings = settings.get_settings()

    assert loaded_settings.cameras[0].name == "cam1"
    assert loaded_settings.cameras[0].title == "Garden Camera"
