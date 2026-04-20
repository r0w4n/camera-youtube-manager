import sys
from pathlib import Path


import pytest


SOURCE_DIR = Path(__file__).resolve().parents[1] / "source"
sys.path.insert(0, str(SOURCE_DIR))

import youtube_streamer


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
    camera = {"name": "cam1"}
    youtube = FakeYoutube(
        {"items": [{"status": {"healthStatus": {"status": "bad"}}}]}
    )

    assert youtube_streamer.is_live_stream_healthy(camera, youtube) is False


def test_is_live_stream_healthy_returns_true_for_good_status():
    """Verify that a good YouTube health status is treated as healthy."""
    camera = {"name": "cam1"}
    youtube = FakeYoutube(
        {"items": [{"status": {"healthStatus": {"status": "good"}}}]}
    )

    assert youtube_streamer.is_live_stream_healthy(camera, youtube) is True
