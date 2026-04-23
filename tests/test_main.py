import importlib
import sys
import types
import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest


SOURCE_DIR = Path(__file__).resolve().parents[1] / "source"
sys.path.insert(0, str(SOURCE_DIR))

from camera_config import AppSettings, CameraConfig


def make_camera(name="cam1", enabled=True):
    return CameraConfig(name=name, enabled=enabled)


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
    camera = make_camera()

    main_module["settings"].get_settings = Mock(return_value=AppSettings(cameras=[camera]))
    main_module["youtube_auth"].handle_auth = Mock(return_value="credentials")
    main.build = Mock(return_value=youtube)
    main.get_recycle_window_start = Mock(return_value=None)
    main.manage_schedule = Mock()
    main.manage_unhealthy_stream = Mock()
    main.manage_inactive_broadcast = Mock()

    main_module["youtube_schedule"].has_scheduled_broadcast = Mock(return_value=False)
    main_module["youtube_schedule"].ensure_active_broadcast_bound_to_stream = Mock()
    main_module["youtube_streamer"].is_live_stream_healthy = Mock()
    main_module["youtube_schedule"].has_inactive_broadcast = Mock()

    main.main()

    main.manage_schedule.assert_called_once_with(camera, youtube)
    main_module["youtube_streamer"].is_live_stream_healthy.assert_not_called()
    main_module["youtube_schedule"].has_inactive_broadcast.assert_not_called()
    main_module["youtube_schedule"].ensure_active_broadcast_bound_to_stream.assert_not_called()
    main.manage_unhealthy_stream.assert_not_called()
    main.manage_inactive_broadcast.assert_not_called()


def test_main_skips_disabled_camera(main_module):
    """Verify that disabled cameras are skipped before any camera processing starts."""
    main = main_module["main"]
    camera = make_camera(enabled=False)

    main_module["settings"].get_settings = Mock(return_value=AppSettings(cameras=[camera]))
    main.process_camera = Mock()

    main.main()

    main.process_camera.assert_not_called()


def test_main_checks_only_selected_camera(main_module):
    """Verify that the check action can target a single configured camera."""
    main = main_module["main"]
    camera1 = make_camera(name="cam1")
    camera2 = make_camera(name="cam2")

    main_module["settings"].get_settings = Mock(
        return_value=AppSettings(cameras=[camera1, camera2])
    )
    main.process_camera_action = Mock()

    main.main(["check", "--camera", "cam2"])

    main.process_camera_action.assert_called_once_with(camera2, "check")


def test_manual_action_requires_camera_name(main_module):
    """Verify that manual stream actions require an explicit camera target."""
    main = main_module["main"]
    camera = make_camera()

    main_module["settings"].get_settings = Mock(return_value=AppSettings(cameras=[camera]))

    with pytest.raises(SystemExit, match="kill requires --camera"):
        main.main(["kill"])


def test_main_exits_when_selected_camera_is_unknown(main_module):
    """Verify that unknown camera names fail before an action runs."""
    main = main_module["main"]
    camera = make_camera(name="cam1")

    main_module["settings"].get_settings = Mock(return_value=AppSettings(cameras=[camera]))
    main.process_camera_action = Mock()

    with pytest.raises(SystemExit, match="Unknown camera 'cam2'"):
        main.main(["check", "--camera", "cam2"])

    main.process_camera_action.assert_not_called()


def test_kill_action_stops_selected_camera_even_when_disabled(main_module):
    """Verify that manual kill can stop a configured camera that automatic checks skip."""
    main = main_module["main"]
    camera = make_camera(enabled=False)

    main_module["settings"].get_settings = Mock(return_value=AppSettings(cameras=[camera]))
    main.stop_stream_if_running = Mock()

    main.main(["kill", "--camera", camera.name])

    main.stop_stream_if_running.assert_called_once_with(camera)


def test_main_skips_inactive_check_after_restarting_unhealthy_stream(main_module):
    """Verify that an unhealthy stream restart skips the inactive broadcast check."""
    main = main_module["main"]
    youtube = object()
    camera = make_camera()

    main_module["settings"].get_settings = Mock(return_value=AppSettings(cameras=[camera]))
    main_module["youtube_auth"].handle_auth = Mock(return_value="credentials")
    main.build = Mock(return_value=youtube)
    main.get_recycle_window_start = Mock(return_value=None)
    main.manage_schedule = Mock()
    main.manage_unhealthy_stream = Mock()
    main.manage_inactive_broadcast = Mock()

    main_module["youtube_schedule"].has_scheduled_broadcast = Mock(return_value=True)
    main_module["youtube_schedule"].ensure_active_broadcast_bound_to_stream = Mock(
        return_value="stream-123"
    )
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
    camera = make_camera()

    main_module["settings"].get_settings = Mock(return_value=AppSettings(cameras=[camera]))
    main_module["youtube_auth"].handle_auth = Mock(return_value="credentials")
    main.build = Mock(return_value=youtube)
    main.get_recycle_window_start = Mock(return_value=None)
    main.manage_schedule = Mock()
    main.manage_unhealthy_stream = Mock()
    main.manage_inactive_broadcast = Mock()

    main_module["youtube_schedule"].has_scheduled_broadcast = Mock(return_value=True)
    main_module["youtube_schedule"].ensure_active_broadcast_bound_to_stream = Mock(
        return_value="stream-123"
    )
    main_module["youtube_streamer"].is_live_stream_healthy = Mock(return_value=True)
    main_module["youtube_schedule"].has_inactive_broadcast = Mock(return_value=True)

    main.main()

    main.manage_schedule.assert_not_called()
    main.manage_unhealthy_stream.assert_not_called()
    main.manage_inactive_broadcast.assert_called_once_with(camera, youtube)


def test_main_recycles_scheduled_broadcast_before_other_checks(main_module):
    """Verify that the recycle path runs when the recycle window is reached."""
    main = main_module["main"]
    youtube = object()
    camera = make_camera()
    recycle_window_start = object()

    main_module["settings"].get_settings = Mock(return_value=AppSettings(cameras=[camera]))
    main_module["youtube_auth"].handle_auth = Mock(return_value="credentials")
    main.build = Mock(return_value=youtube)
    main.get_recycle_window_start = Mock(return_value=recycle_window_start)
    main.manage_ending_broadcast = Mock()
    main.manage_schedule = Mock()
    main.logger.info = Mock()

    main_module["youtube_schedule"].get_recycle_decision = Mock(
        return_value=types.SimpleNamespace(
            should_recycle=True,
            reason="older_than_recycle_window",
            broadcast_id="broadcast-123",
            scheduled_start_time="2026-04-21 06:30:00+00:00",
        )
    )
    main_module["youtube_schedule"].has_scheduled_broadcast = Mock(return_value=True)
    main_module["youtube_schedule"].ensure_active_broadcast_bound_to_stream = Mock(
        return_value="stream-123"
    )
    main_module["youtube_streamer"].is_live_stream_healthy = Mock(return_value=True)
    main_module["youtube_schedule"].has_inactive_broadcast = Mock(return_value=False)

    main.main()

    main_module["youtube_schedule"].get_recycle_decision.assert_called_once_with(
        youtube, recycle_window_start
    )
    main.manage_ending_broadcast.assert_called_once_with(camera, youtube)
    main.manage_schedule.assert_not_called()
    main.logger.info.assert_any_call(
        "%s - recycle hour active; broadcast %s was scheduled at %s, recycling",
        camera.name,
        "broadcast-123",
        "2026-04-21 06:30:00+00:00",
    )


def test_manage_schedule_creates_broadcast_and_starts_stream(main_module):
    """Verify that schedule creation also starts the local stream immediately."""
    main = main_module["main"]
    youtube = object()
    camera = make_camera()

    main_module["youtube_streamer"].is_streaming = Mock(return_value=False)
    main_module["youtube_streamer"].start_stream = Mock()
    main_module["youtube_schedule"].do_schedule = Mock()

    main.manage_schedule(camera, youtube)

    main_module["youtube_schedule"].do_schedule.assert_called_once_with(youtube, camera)
    main_module["youtube_streamer"].start_stream.assert_called_once_with(camera)


def test_restart_stream_stops_before_starting(main_module):
    """Verify that manual restart replaces the local stream process."""
    main = main_module["main"]
    camera = make_camera()
    call_order = []

    main.stop_stream_if_running = Mock(side_effect=lambda cam: call_order.append(("stop", cam)))
    main_module["youtube_streamer"].start_stream = Mock(
        side_effect=lambda cam: call_order.append(("start", cam))
    )

    main.restart_stream(camera)

    assert call_order == [
        ("stop", camera),
        ("start", camera),
    ]


def test_main_continues_to_next_camera_after_http_error(main_module):
    """Verify that one camera's YouTube API failure does not stop later cameras."""
    main = main_module["main"]
    camera1 = make_camera(name="cam1")
    camera2 = make_camera(name="cam2")
    youtube2 = object()

    main_module["settings"].get_settings = Mock(
        return_value=AppSettings(cameras=[camera1, camera2])
    )
    main_module["youtube_auth"].handle_auth = Mock(side_effect=["cred1", "cred2"])
    main.build = Mock(side_effect=[main.HttpError("boom"), youtube2])
    main.get_recycle_window_start = Mock(return_value=None)
    main.logger.exception = Mock()

    main_module["youtube_schedule"].has_scheduled_broadcast = Mock(return_value=True)
    main_module["youtube_schedule"].ensure_active_broadcast_bound_to_stream = Mock(
        return_value="stream-123"
    )
    main_module["youtube_streamer"].is_live_stream_healthy = Mock(return_value=True)
    main_module["youtube_schedule"].has_inactive_broadcast = Mock(return_value=False)

    main.main()

    assert main.build.call_count == 2
    main_module["youtube_schedule"].has_scheduled_broadcast.assert_called_once_with(
        youtube2
    )
    main_module["youtube_schedule"].ensure_active_broadcast_bound_to_stream.assert_called_once_with(
        youtube2, camera2
    )
    main_module["youtube_streamer"].is_live_stream_healthy.assert_called_once_with(
        camera2, youtube2, "stream-123"
    )
    main_module["youtube_schedule"].has_inactive_broadcast.assert_called_once_with(
        youtube2
    )
    main.logger.exception.assert_called_once()


def test_main_continues_to_next_camera_after_unexpected_error(main_module):
    """Verify that one camera's unexpected failure does not stop later cameras."""
    main = main_module["main"]
    camera1 = make_camera(name="cam1")
    camera2 = make_camera(name="cam2")
    youtube2 = object()

    main_module["settings"].get_settings = Mock(
        return_value=AppSettings(cameras=[camera1, camera2])
    )
    main_module["youtube_auth"].handle_auth = Mock(side_effect=["cred1", "cred2"])
    main.build = Mock(side_effect=[RuntimeError("boom"), youtube2])
    main.get_recycle_window_start = Mock(return_value=None)
    main.logger.exception = Mock()

    main_module["youtube_schedule"].has_scheduled_broadcast = Mock(return_value=True)
    main_module["youtube_schedule"].ensure_active_broadcast_bound_to_stream = Mock(
        return_value="stream-123"
    )
    main_module["youtube_streamer"].is_live_stream_healthy = Mock(return_value=True)
    main_module["youtube_schedule"].has_inactive_broadcast = Mock(return_value=False)

    main.main()

    assert main.build.call_count == 2
    main_module["youtube_schedule"].has_scheduled_broadcast.assert_called_once_with(
        youtube2
    )
    main_module["youtube_schedule"].ensure_active_broadcast_bound_to_stream.assert_called_once_with(
        youtube2, camera2
    )
    main_module["youtube_streamer"].is_live_stream_healthy.assert_called_once_with(
        camera2, youtube2, "stream-123"
    )
    main_module["youtube_schedule"].has_inactive_broadcast.assert_called_once_with(
        youtube2
    )
    main.logger.exception.assert_called_once()


def test_stop_stream_if_running_kills_stream_and_waits(main_module):
    """Verify that stopping a running stream also waits before continuing."""
    main = main_module["main"]
    camera = make_camera()

    main_module["youtube_streamer"].is_streaming = Mock(return_value=True)
    main_module["youtube_streamer"].kill_stream = Mock()
    main.time.sleep = Mock()

    main.stop_stream_if_running(camera)

    main_module["youtube_streamer"].kill_stream.assert_called_once_with(camera)
    main.time.sleep.assert_called_once_with(5)


def test_get_recycle_window_start_returns_hour_start_during_recycle_hour(main_module):
    """Verify that recycle windows stay open for the full recycle hour."""
    main = main_module["main"]
    now = datetime.datetime(
        2026, 4, 21, 8, 37, 12, tzinfo=datetime.timezone(datetime.timedelta(hours=1))
    )

    assert main.get_recycle_window_start(now) == datetime.datetime(
        2026, 4, 21, 8, 0, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=1))
    )


def test_get_recycle_window_start_returns_none_outside_recycle_hours(main_module):
    """Verify that non-recycle hours do not trigger recycle logic."""
    main = main_module["main"]
    now = datetime.datetime(
        2026, 4, 21, 9, 5, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=1))
    )

    assert main.get_recycle_window_start(now) is None


def test_main_logs_when_recycle_is_skipped_for_current_hour(main_module):
    """Verify that recycle-hour skips are logged when the broadcast is already current."""
    main = main_module["main"]
    youtube = object()
    camera = make_camera()
    recycle_window_start = object()

    main_module["settings"].get_settings = Mock(return_value=AppSettings(cameras=[camera]))
    main_module["youtube_auth"].handle_auth = Mock(return_value="credentials")
    main.build = Mock(return_value=youtube)
    main.get_recycle_window_start = Mock(return_value=recycle_window_start)
    main.manage_ending_broadcast = Mock()
    main.logger.info = Mock()

    main_module["youtube_schedule"].get_recycle_decision = Mock(
        return_value=types.SimpleNamespace(
            should_recycle=False,
            reason="already_recycled_this_hour",
            broadcast_id="broadcast-123",
            scheduled_start_time="2026-04-21 08:05:00+00:00",
        )
    )
    main_module["youtube_schedule"].has_scheduled_broadcast = Mock(return_value=True)
    main_module["youtube_schedule"].ensure_active_broadcast_bound_to_stream = Mock(
        return_value="stream-123"
    )
    main_module["youtube_streamer"].is_live_stream_healthy = Mock(return_value=True)
    main_module["youtube_schedule"].has_inactive_broadcast = Mock(return_value=False)

    main.main()

    main.manage_ending_broadcast.assert_not_called()
    main.logger.info.assert_any_call(
        "%s - recycle hour active; broadcast %s was scheduled at %s, skipping recycle",
        camera.name,
        "broadcast-123",
        "2026-04-21 08:05:00+00:00",
    )


def test_manage_inactive_broadcast_recreates_running_stuck_broadcast(main_module):
    """Verify that a stuck ready broadcast is recreated when the local stream is already running."""
    main = main_module["main"]
    camera = make_camera()
    youtube = object()

    main_module["youtube_streamer"].is_streaming = Mock(return_value=True)
    main.stop_stream_if_running = Mock()
    main_module["youtube_schedule"].end_schedule = Mock()
    main_module["youtube_schedule"].do_schedule = Mock()
    main_module["youtube_streamer"].start_stream = Mock()

    main.manage_inactive_broadcast(camera, youtube)

    main.stop_stream_if_running.assert_called_once_with(camera)
    main_module["youtube_schedule"].end_schedule.assert_called_once_with(youtube, camera)
    main_module["youtube_schedule"].do_schedule.assert_called_once_with(youtube, camera)
    main_module["youtube_streamer"].start_stream.assert_called_once_with(camera)


def test_manage_inactive_broadcast_starts_stream_when_not_running(main_module):
    """Verify that an inactive broadcast starts the local stream when needed."""
    main = main_module["main"]
    camera = make_camera()
    youtube = object()

    main_module["youtube_streamer"].is_streaming = Mock(return_value=False)
    main_module["youtube_streamer"].start_stream = Mock()

    main.manage_inactive_broadcast(camera, youtube)

    main_module["youtube_streamer"].start_stream.assert_called_once_with(camera)


def test_manage_ending_broadcast_stops_stream_before_ending_schedule(main_module):
    """Verify that recycle shutdown stops the local stream before ending the broadcast."""
    main = main_module["main"]
    camera = make_camera()
    youtube = object()
    call_order = []

    main.stop_stream_if_running = Mock(side_effect=lambda arg: call_order.append(("stop", arg)))
    main_module["youtube_schedule"].end_schedule = Mock(
        side_effect=lambda yt, cam: call_order.append(("end", yt, cam))
    )

    main.manage_ending_broadcast(camera, youtube)

    assert call_order == [
        ("stop", camera),
        ("end", youtube, camera),
    ]


def test_recycle_camera_ends_broadcast_creates_schedule_and_starts_stream(main_module):
    """Verify that manual recycle recreates the YouTube broadcast and local stream."""
    main = main_module["main"]
    camera = make_camera()
    youtube = object()
    call_order = []

    main.build_youtube_client = Mock(return_value=youtube)
    main.manage_ending_broadcast = Mock(
        side_effect=lambda cam, yt: call_order.append(("end", cam, yt))
    )
    main_module["youtube_schedule"].do_schedule = Mock(
        side_effect=lambda yt, cam: call_order.append(("schedule", yt, cam))
    )
    main_module["youtube_streamer"].start_stream = Mock(
        side_effect=lambda cam: call_order.append(("start", cam))
    )

    main.recycle_camera(camera)

    assert call_order == [
        ("end", camera, youtube),
        ("schedule", youtube, camera),
        ("start", camera),
    ]
