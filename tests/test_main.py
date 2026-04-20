import importlib
import sys
import types
from pathlib import Path
from unittest.mock import Mock

import pytest


SOURCE_DIR = Path(__file__).resolve().parents[1] / "source"


@pytest.fixture
def main_module(monkeypatch):
    monkeypatch.syspath_prepend(str(SOURCE_DIR))

    fake_youtube_auth = types.ModuleType("youtube_auth")
    fake_youtube_schedule = types.ModuleType("youtube_schedule")
    fake_youtube_streamer = types.ModuleType("youtube_streamer")
    fake_settings = types.ModuleType("settings")

    fake_googleapiclient = types.ModuleType("googleapiclient")
    fake_discovery = types.ModuleType("googleapiclient.discovery")
    fake_errors = types.ModuleType("googleapiclient.errors")

    class FakeHttpError(Exception):
        pass

    fake_discovery.build = Mock(name="build")
    fake_errors.HttpError = FakeHttpError

    modules = {
        "youtube_auth": fake_youtube_auth,
        "youtube_schedule": fake_youtube_schedule,
        "youtube_streamer": fake_youtube_streamer,
        "settings": fake_settings,
        "googleapiclient": fake_googleapiclient,
        "googleapiclient.discovery": fake_discovery,
        "googleapiclient.errors": fake_errors,
    }

    for module_name, module in modules.items():
        monkeypatch.setitem(sys.modules, module_name, module)

    sys.modules.pop("main", None)
    main = importlib.import_module("main")

    yield {
        "main": main,
        "youtube_auth": fake_youtube_auth,
        "youtube_schedule": fake_youtube_schedule,
        "youtube_streamer": fake_youtube_streamer,
        "settings": fake_settings,
        "discovery": fake_discovery,
    }

    sys.modules.pop("main", None)


def test_main_skips_later_checks_after_creating_schedule(main_module):
    """Verify that creating a schedule exits the loop before later checks run."""
    main = main_module["main"]
    youtube = object()
    camera = {"name": "cam1", "enabled": True}

    main_module["settings"].get_settings = Mock(return_value={"cameras": [camera]})
    main_module["youtube_auth"].handle_auth = Mock(return_value="credentials")
    main.build = Mock(return_value=youtube)
    main.is_recycle_time = Mock(return_value=False)
    main.manage_schedule = Mock()
    main.manage_unhealthy_stream = Mock()
    main.manage_inactive_broadcast = Mock()

    main_module["youtube_schedule"].has_scheduled_broadcast = Mock(return_value=False)
    main_module["youtube_streamer"].is_live_stream_healthy = Mock()
    main_module["youtube_schedule"].has_inactive_broadcast = Mock()

    main.main()

    main.manage_schedule.assert_called_once_with(camera, youtube)
    main_module["youtube_streamer"].is_live_stream_healthy.assert_not_called()
    main_module["youtube_schedule"].has_inactive_broadcast.assert_not_called()
    main.manage_unhealthy_stream.assert_not_called()
    main.manage_inactive_broadcast.assert_not_called()


def test_main_skips_inactive_check_after_restarting_unhealthy_stream(main_module):
    """Verify that an unhealthy stream restart skips the inactive broadcast check."""
    main = main_module["main"]
    youtube = object()
    camera = {"name": "cam1", "enabled": True}

    main_module["settings"].get_settings = Mock(return_value={"cameras": [camera]})
    main_module["youtube_auth"].handle_auth = Mock(return_value="credentials")
    main.build = Mock(return_value=youtube)
    main.is_recycle_time = Mock(return_value=False)
    main.manage_schedule = Mock()
    main.manage_unhealthy_stream = Mock()
    main.manage_inactive_broadcast = Mock()

    main_module["youtube_schedule"].has_scheduled_broadcast = Mock(return_value=True)
    main_module["youtube_streamer"].is_live_stream_healthy = Mock(return_value=False)
    main_module["youtube_schedule"].has_inactive_broadcast = Mock()

    main.main()

    main.manage_unhealthy_stream.assert_called_once_with(camera)
    main_module["youtube_schedule"].has_inactive_broadcast.assert_not_called()
    main.manage_inactive_broadcast.assert_not_called()


def test_main_checks_inactive_broadcast_when_stream_is_healthy(main_module):
    """Verify that healthy streams still reach the inactive broadcast branch."""
    main = main_module["main"]
    youtube = object()
    camera = {"name": "cam1", "enabled": True}

    main_module["settings"].get_settings = Mock(return_value={"cameras": [camera]})
    main_module["youtube_auth"].handle_auth = Mock(return_value="credentials")
    main.build = Mock(return_value=youtube)
    main.is_recycle_time = Mock(return_value=False)
    main.manage_schedule = Mock()
    main.manage_unhealthy_stream = Mock()
    main.manage_inactive_broadcast = Mock()

    main_module["youtube_schedule"].has_scheduled_broadcast = Mock(return_value=True)
    main_module["youtube_streamer"].is_live_stream_healthy = Mock(return_value=True)
    main_module["youtube_schedule"].has_inactive_broadcast = Mock(return_value=True)

    main.main()

    main.manage_schedule.assert_not_called()
    main.manage_unhealthy_stream.assert_not_called()
    main.manage_inactive_broadcast.assert_called_once_with(camera)


def test_manage_schedule_creates_broadcast_and_starts_stream(main_module):
    """Verify that schedule creation also starts the local stream immediately."""
    main = main_module["main"]
    youtube = object()
    camera = {"name": "cam1", "enabled": True}

    main_module["youtube_streamer"].is_streaming = Mock(return_value=False)
    main_module["youtube_streamer"].start_stream = Mock()
    main_module["youtube_schedule"].do_schedule = Mock()

    main.manage_schedule(camera, youtube)

    main_module["youtube_schedule"].do_schedule.assert_called_once_with(youtube, camera)
    main_module["youtube_streamer"].start_stream.assert_called_once_with(camera)


def test_main_continues_to_next_camera_after_http_error(main_module):
    """Verify that one camera's YouTube API failure does not stop later cameras."""
    main = main_module["main"]
    camera1 = {"name": "cam1", "enabled": True}
    camera2 = {"name": "cam2", "enabled": True}
    youtube2 = object()

    main_module["settings"].get_settings = Mock(
        return_value={"cameras": [camera1, camera2]}
    )
    main_module["youtube_auth"].handle_auth = Mock(side_effect=["cred1", "cred2"])
    main.build = Mock(side_effect=[main.HttpError("boom"), youtube2])
    main.is_recycle_time = Mock(return_value=False)
    main.logger.exception = Mock()

    main_module["youtube_schedule"].has_scheduled_broadcast = Mock(return_value=True)
    main_module["youtube_streamer"].is_live_stream_healthy = Mock(return_value=True)
    main_module["youtube_schedule"].has_inactive_broadcast = Mock(return_value=False)

    main.main()

    assert main.build.call_count == 2
    main_module["youtube_schedule"].has_scheduled_broadcast.assert_called_once_with(
        youtube2
    )
    main_module["youtube_streamer"].is_live_stream_healthy.assert_called_once_with(
        camera2, youtube2
    )
    main_module["youtube_schedule"].has_inactive_broadcast.assert_called_once_with(
        youtube2
    )
    main.logger.exception.assert_called_once()
