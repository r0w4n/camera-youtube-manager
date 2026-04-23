import datetime
import sys
from pathlib import Path

import pytest


SOURCE_DIR = Path(__file__).resolve().parents[1] / "source"
sys.path.insert(0, str(SOURCE_DIR))

from camera_config import CameraConfig

import youtube_schedule


def make_camera(key="stream-key"):
    return CameraConfig(
        name="cam1",
        title="Back Garden",
        description="Live camera",
        key=key,
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


class FakeLiveStreams:
    def __init__(self, response):
        self.response = response
        self.list_kwargs = None

    def list(self, **kwargs):
        self.list_kwargs = kwargs
        return FakeRequest(self.response)


class FakeBroadcasts:
    def __init__(self, list_response=None, insert_response=None):
        self.list_response = list_response or {"items": []}
        self.insert_response = insert_response or {"id": "broadcast-123"}
        self.list_kwargs = None
        self.insert_kwargs = None
        self.bind_kwargs = None
        self.transition_kwargs = None
        self.delete_kwargs = None

    def list(self, **kwargs):
        self.list_kwargs = kwargs
        return FakeRequest(self.list_response)

    def insert(self, **kwargs):
        self.insert_kwargs = kwargs
        return FakeRequest(self.insert_response)

    def bind(self, **kwargs):
        self.bind_kwargs = kwargs
        return FakeRequest({"status": "ok"})

    def transition(self, **kwargs):
        self.transition_kwargs = kwargs
        return FakeRequest({"status": "ok"})

    def delete(self, **kwargs):
        self.delete_kwargs = kwargs
        return FakeRequest({"status": "ok"})


class FakeYoutube:
    def __init__(self, broadcast_items=None, stream_items=None, insert_response=None):
        self.broadcasts = FakeBroadcasts(
            list_response={"items": broadcast_items or []},
            insert_response=insert_response,
        )
        self.streams = FakeLiveStreams({"items": stream_items or []})

    def liveBroadcasts(self):
        return self.broadcasts

    def liveStreams(self):
        return self.streams


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


def test_schedule_broadcast_disables_monitor_stream_for_autostart(monkeypatch):
    """Verify that auto-start broadcasts disable monitor stream mode."""
    monkeypatch.setattr(youtube_schedule.datetime, "datetime", FixedDatetime)
    youtube = FakeYoutube()
    camera = make_camera()

    youtube_schedule.schedule_broadcast(youtube, camera)

    assert (
        youtube.broadcasts.insert_kwargs["body"]["contentDetails"]["monitorStream"][
            "enableMonitorStream"
        ]
        is False
    )


def test_get_stream_id_for_key_returns_matching_stream_id():
    """Verify that the stream lookup matches the configured ingest key."""
    youtube = FakeYoutube(
        stream_items=[
            {
                "id": "stream-123",
                "cdn": {"ingestionInfo": {"streamName": "stream-key-123"}},
            }
        ]
    )

    assert (
        youtube_schedule.get_stream_id_for_key(youtube, "stream-key-123")
        == "stream-123"
    )
    assert youtube.streams.list_kwargs == {"part": "id,cdn", "mine": True}


def test_get_stream_id_for_key_raises_when_key_is_unknown():
    """Verify that unknown stream keys fail clearly instead of binding the wrong stream."""
    youtube = FakeYoutube(
        stream_items=[
            {
                "id": "stream-123",
                "cdn": {"ingestionInfo": {"streamName": "stream-key-123"}},
            }
        ]
    )

    with pytest.raises(ValueError, match="does not match any reusable live stream"):
        youtube_schedule.get_stream_id_for_key(youtube, "different-key")


def test_has_scheduled_broadcast_returns_true_for_non_complete_broadcast():
    """Verify that any non-complete broadcast counts as scheduled."""
    youtube = FakeYoutube(
        broadcast_items=[
            {"id": "broadcast-1", "status": {"lifeCycleStatus": "complete"}},
            {"id": "broadcast-2", "status": {"lifeCycleStatus": "ready"}},
        ]
    )

    assert youtube_schedule.has_scheduled_broadcast(youtube) is True
    assert youtube.broadcasts.list_kwargs == {"part": "status", "mine": True}


def test_has_scheduled_broadcast_returns_false_when_all_are_complete():
    """Verify that only complete broadcasts count as having no schedule."""
    youtube = FakeYoutube(
        broadcast_items=[
            {"id": "broadcast-1", "status": {"lifeCycleStatus": "complete"}},
        ]
    )

    assert youtube_schedule.has_scheduled_broadcast(youtube) is False


def test_has_inactive_broadcast_returns_true_for_ready_broadcast():
    """Verify that a ready broadcast is treated as inactive."""
    youtube = FakeYoutube(
        broadcast_items=[
            {"id": "broadcast-1", "status": {"lifeCycleStatus": "live"}},
            {"id": "broadcast-2", "status": {"lifeCycleStatus": "ready"}},
        ]
    )

    assert youtube_schedule.has_inactive_broadcast(youtube) is True


def test_has_inactive_broadcast_returns_false_without_ready_broadcast():
    """Verify that non-ready broadcasts do not count as inactive."""
    youtube = FakeYoutube(
        broadcast_items=[
            {"id": "broadcast-1", "status": {"lifeCycleStatus": "live"}},
        ]
    )

    assert youtube_schedule.has_inactive_broadcast(youtube) is False


def test_get_scheduled_broadcast_id_returns_first_non_complete_broadcast():
    """Verify that the first non-complete broadcast id is selected."""
    youtube = FakeYoutube(
        broadcast_items=[
            {"id": "broadcast-1", "status": {"lifeCycleStatus": "complete"}},
            {"id": "broadcast-2", "status": {"lifeCycleStatus": "ready"}},
            {"id": "broadcast-3", "status": {"lifeCycleStatus": "live"}},
        ]
    )

    assert youtube_schedule.get_scheduled_broadcast_id(youtube) == "broadcast-2"


def test_should_recycle_broadcast_returns_true_for_broadcast_created_before_window():
    """Verify that older broadcasts recycle when the recycle hour arrives."""
    youtube = FakeYoutube(
        broadcast_items=[
            {
                "id": "broadcast-1",
                "status": {"lifeCycleStatus": "ready"},
                "snippet": {"scheduledStartTime": "2026-04-21T06:30:00Z"},
            }
        ]
    )
    recycle_window_start = datetime.datetime(
        2026, 4, 21, 8, 0, 0, tzinfo=datetime.timezone.utc
    )

    assert (
        youtube_schedule.should_recycle_broadcast(youtube, recycle_window_start) is True
    )
    assert youtube.broadcasts.list_kwargs == {"part": "snippet,status", "mine": True}


def test_should_recycle_broadcast_returns_false_after_recycling_this_hour():
    """Verify that a broadcast created this recycle hour is not recycled again."""
    youtube = FakeYoutube(
        broadcast_items=[
            {
                "id": "broadcast-1",
                "status": {"lifeCycleStatus": "ready"},
                "snippet": {"scheduledStartTime": "2026-04-21T08:05:00Z"},
            }
        ]
    )
    recycle_window_start = datetime.datetime(
        2026, 4, 21, 8, 0, 0, tzinfo=datetime.timezone.utc
    )

    assert (
        youtube_schedule.should_recycle_broadcast(youtube, recycle_window_start)
        is False
    )


def test_should_recycle_broadcast_returns_false_without_active_broadcast():
    """Verify that recycle logic stays off when there is no active broadcast."""
    youtube = FakeYoutube(
        broadcast_items=[
            {"id": "broadcast-1", "status": {"lifeCycleStatus": "complete"}},
        ]
    )
    recycle_window_start = datetime.datetime(
        2026, 4, 21, 8, 0, 0, tzinfo=datetime.timezone.utc
    )

    assert (
        youtube_schedule.should_recycle_broadcast(youtube, recycle_window_start)
        is False
    )


def test_do_schedule_binds_created_broadcast_to_configured_stream(monkeypatch):
    """Verify that scheduling binds the new broadcast to the configured stream key."""
    monkeypatch.setattr(youtube_schedule.datetime, "datetime", FixedDatetime)
    youtube = FakeYoutube(
        stream_items=[
            {
                "id": "stream-123",
                "cdn": {"ingestionInfo": {"streamName": "stream-key"}},
            }
        ],
        insert_response={"id": "broadcast-123"},
    )

    youtube_schedule.do_schedule(youtube, make_camera())

    assert youtube.broadcasts.bind_kwargs == {
        "part": "id,contentDetails",
        "id": "broadcast-123",
        "streamId": "stream-123",
    }


def test_ensure_active_broadcast_bound_to_stream_rebinds_ready_broadcast():
    """Verify that ready broadcasts are rebound when the configured key maps to a different stream."""
    youtube = FakeYoutube(
        broadcast_items=[
            {
                "id": "broadcast-123",
                "status": {"lifeCycleStatus": "ready"},
                "contentDetails": {"boundStreamId": "stream-old"},
            }
        ],
        stream_items=[
            {
                "id": "stream-new",
                "cdn": {"ingestionInfo": {"streamName": "stream-key"}},
            }
        ],
    )

    stream_id = youtube_schedule.ensure_active_broadcast_bound_to_stream(
        youtube, make_camera(key="stream-key")
    )

    assert stream_id == "stream-new"
    assert youtube.broadcasts.bind_kwargs == {
        "part": "id,contentDetails",
        "id": "broadcast-123",
        "streamId": "stream-new",
    }


def test_end_schedule_deletes_ready_broadcast():
    """Verify that ready broadcasts are deleted instead of transitioned to complete."""
    youtube = FakeYoutube(
        broadcast_items=[
            {"id": "broadcast-123", "status": {"lifeCycleStatus": "ready"}},
        ]
    )

    youtube_schedule.end_schedule(youtube, make_camera())

    assert youtube.broadcasts.transition_kwargs is None
    assert youtube.broadcasts.delete_kwargs == {"id": "broadcast-123"}


def test_end_schedule_transitions_live_broadcast_to_complete():
    """Verify that live broadcasts are transitioned to complete."""
    youtube = FakeYoutube(
        broadcast_items=[
            {"id": "broadcast-123", "status": {"lifeCycleStatus": "live"}},
        ]
    )

    youtube_schedule.end_schedule(youtube, make_camera())

    assert youtube.broadcasts.transition_kwargs == {
        "broadcastStatus": "complete",
        "id": "broadcast-123",
        "part": "id,snippet,status",
    }
    assert youtube.broadcasts.delete_kwargs is None
