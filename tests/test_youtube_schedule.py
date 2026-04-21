import datetime
import sys
from pathlib import Path


import pytest


SOURCE_DIR = Path(__file__).resolve().parents[1] / "source"
sys.path.insert(0, str(SOURCE_DIR))

from camera_config import CameraConfig

import youtube_schedule


def make_camera():
    return CameraConfig(
        name="cam1",
        title="Back Garden",
        description="Live camera",
    )


class FixedDatetime(datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        assert tz == datetime.timezone.utc
        return cls(2026, 4, 20, 12, 34, 56, tzinfo=datetime.timezone.utc)


class FakeRequest:
    def __init__(self, response):
        self.response = response

    def execute(self):
        return self.response


class FakeBroadcasts:
    def __init__(self):
        self.insert_kwargs = None

    def insert(self, **kwargs):
        self.insert_kwargs = kwargs
        return FakeRequest({"id": "broadcast-123"})


class FakeYoutube:
    def __init__(self):
        self.broadcasts = FakeBroadcasts()

    def liveBroadcasts(self):
        return self.broadcasts


def test_get_scheduled_start_time_uses_utc(monkeypatch):
    """Verify that scheduled start times are generated as real UTC timestamps."""
    monkeypatch.setattr(youtube_schedule.datetime, "datetime", FixedDatetime)

    assert youtube_schedule.get_scheduled_start_time() == "2026-04-20T12:34:56Z"


def test_schedule_broadcast_writes_utc_start_time(monkeypatch):
    """Verify that broadcast scheduling sends the UTC timestamp in the request body."""
    monkeypatch.setattr(youtube_schedule.datetime, "datetime", FixedDatetime)
    youtube = FakeYoutube()
    camera = make_camera()

    youtube_schedule.schedule_broadcast(youtube, camera)

    assert (
        youtube.broadcasts.insert_kwargs["body"]["snippet"]["scheduledStartTime"]
        == "2026-04-20T12:34:56Z"
    )
