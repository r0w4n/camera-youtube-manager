import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock


import pytest


SOURCE_DIR = Path(__file__).resolve().parents[1] / "source"
sys.path.insert(0, str(SOURCE_DIR))

from camera_config import CameraConfig

import youtube_streamer


def make_camera(name="cam1", url="", key=""):
    return CameraConfig(name=name, url=url, key=key)


class FakeRequest:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class FakeLiveStreams:
    def __init__(self, payload):
        self.payload = payload

    def list(self, **kwargs):
        return FakeRequest(self.payload)


class FakeYoutube:
    def __init__(self, payload):
        self.payload = payload

    def liveStreams(self):
        return FakeLiveStreams(self.payload)


def test_is_live_stream_healthy_returns_false_for_bad_status():
    """Verify that a bad YouTube health status is treated as unhealthy."""
    camera = make_camera()
    youtube = FakeYoutube(
        {"items": [{"status": {"healthStatus": {"status": "bad"}}}]}
    )

    assert youtube_streamer.is_live_stream_healthy(camera, youtube) is False


def test_is_live_stream_healthy_returns_true_for_good_status():
    """Verify that a good YouTube health status is treated as healthy."""
    camera = make_camera()
    youtube = FakeYoutube(
        {"items": [{"status": {"healthStatus": {"status": "good"}}}]}
    )

    assert youtube_streamer.is_live_stream_healthy(camera, youtube) is True


def test_start_stream_passes_special_characters_without_shell_parsing(monkeypatch):
    """Verify that stream startup uses a subprocess argument list, not a shell string."""
    camera = make_camera(
        url="user:p@ss!word@camera.local/stream?foo=1&bar=2",
        key="abcd-efgh-ijkl?test=1&mode=live",
    )
    run_mock = Mock(return_value=SimpleNamespace(returncode=0))
    monkeypatch.setattr(youtube_streamer.subprocess, "run", run_mock)

    youtube_streamer.start_stream(camera)

    run_mock.assert_called_once_with(
        [
            "screen",
            "-dS",
            "youtube_cam1",
            "-m",
            "ffmpeg",
            "-f",
            "lavfi",
            "-i",
            "anullsrc",
            "-rtsp_transport",
            "tcp",
            "-i",
            "rtsp://user:p@ss!word@camera.local/stream?foo=1&bar=2",
            "-vcodec",
            "libx264",
            "-pix_fmt",
            "+",
            "-c:v",
            "copy",
            "-f",
            "flv",
            "rtmp://a.rtmp.youtube.com/live2/abcd-efgh-ijkl?test=1&mode=live",
        ],
        check=False,
    )


def test_kill_stream_uses_argument_list(monkeypatch):
    """Verify that stopping a stream uses subprocess arguments instead of a shell string."""
    camera = make_camera()
    run_mock = Mock(return_value=SimpleNamespace(returncode=0))
    monkeypatch.setattr(youtube_streamer.subprocess, "run", run_mock)

    youtube_streamer.kill_stream(camera)

    run_mock.assert_called_once_with(
        ["screen", "-X", "-S", "youtube_cam1", "quit"], check=False
    )


def test_is_streaming_matches_exact_screen_session_name(monkeypatch):
    """Verify that cam1 does not accidentally match a cam10 screen session."""
    camera = make_camera()
    run_mock = Mock(
        return_value=SimpleNamespace(
            returncode=0,
            stdout="\t1234.youtube_cam10\t(Detached)\n",
        )
    )
    monkeypatch.setattr(youtube_streamer.subprocess, "run", run_mock)

    assert youtube_streamer.is_streaming(camera) is False
