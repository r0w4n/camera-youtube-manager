import datetime
import logging
from dataclasses import dataclass
from typing import Optional

from camera_config import CameraConfig


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RecycleDecision:
    should_recycle: bool
    reason: str
    broadcast_id: Optional[str] = None
    scheduled_start_time: Optional[datetime.datetime] = None


def get_scheduled_start_time():
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def schedule_broadcast(youtube, camera: CameraConfig):
    logger.info(
        '%s - creating YouTube broadcast with title "%s"',
        camera.name,
        camera.title,
    )
    content = {
        "snippet": {
            "title": camera.title,
            "description": camera.description,
            "scheduledStartTime": get_scheduled_start_time(),
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
        "contentDetails": {
            "monitorStream": {
                "enableMonitorStream": False,
            },
            "enableEmbed": True,
            "enableDvr": True,
            "recordFromStart": True,
            "enableClosedCaptions": False,
            "latencyPreference": "normal",
            "enableAutoStart": True,
            "enableAutoStop": False,
        },
    }

    response = (
        youtube.liveBroadcasts()
        .insert(
            part="snippet, status, contentDetails",
            body=content,
        )
        .execute()
    )

    logger.info("%s - created YouTube broadcast %s", camera.name, response["id"])
    return response["id"]


def get_stream_id_for_key(youtube, stream_key):
    normalized_stream_key = stream_key.strip()
    streams = youtube.liveStreams().list(part="id,cdn", mine=True).execute()

    for stream in streams["items"]:
        candidate_key = (
            stream.get("cdn", {}).get("ingestionInfo", {}).get("streamName", "").strip()
        )
        if candidate_key == normalized_stream_key:
            return stream["id"]

    raise ValueError(
        "Configured YouTube stream key does not match any reusable live stream"
    )


def parse_youtube_datetime(datetime_text):
    return datetime.datetime.fromisoformat(datetime_text.replace("Z", "+00:00"))


def get_broadcasts(youtube, part="status"):
    response = youtube.liveBroadcasts().list(part=part, mine=True).execute()
    return response["items"]


def get_active_broadcast(youtube, part="status"):
    for broadcast in get_broadcasts(youtube, part=part):
        if broadcast["status"]["lifeCycleStatus"] != "complete":
            return broadcast
    return None


def has_scheduled_broadcast(youtube):
    return get_active_broadcast(youtube) is not None


def has_inactive_broadcast(youtube):
    return any(
        broadcast["status"]["lifeCycleStatus"] == "ready"
        for broadcast in get_broadcasts(youtube)
    )


def get_scheduled_broadcast_id(youtube):
    broadcast = get_active_broadcast(youtube)
    return broadcast["id"]


def get_recycle_decision(youtube, recycle_window_start):
    if recycle_window_start.tzinfo is None:
        recycle_window_start = recycle_window_start.astimezone()

    broadcast = get_active_broadcast(youtube, part="snippet,status")
    if broadcast is None:
        return RecycleDecision(should_recycle=False, reason="no_active_broadcast")

    broadcast_id = broadcast["id"]

    scheduled_start_time_text = broadcast.get("snippet", {}).get("scheduledStartTime")
    if not scheduled_start_time_text:
        return RecycleDecision(
            should_recycle=True,
            reason="missing_scheduled_start_time",
            broadcast_id=broadcast_id,
        )

    scheduled_start_time = parse_youtube_datetime(scheduled_start_time_text)
    if scheduled_start_time < recycle_window_start:
        return RecycleDecision(
            should_recycle=True,
            reason="older_than_recycle_window",
            broadcast_id=broadcast_id,
            scheduled_start_time=scheduled_start_time,
        )

    return RecycleDecision(
        should_recycle=False,
        reason="already_recycled_this_hour",
        broadcast_id=broadcast_id,
        scheduled_start_time=scheduled_start_time,
    )


def should_recycle_broadcast(youtube, recycle_window_start):
    return get_recycle_decision(youtube, recycle_window_start).should_recycle


def do_schedule(youtube, camera: CameraConfig):
    # Schedules a broadcast
    broadcast_id = schedule_broadcast(youtube, camera)
    logger.info("%s - binding broadcast %s to stream", camera.name, broadcast_id)

    # Bind the broadcast to the reusable stream whose ingest key matches the camera config.
    youtube.liveBroadcasts().bind(
        part="id,contentDetails",
        id=broadcast_id,
        streamId=get_stream_id_for_key(youtube, camera.key),
    ).execute()


def ensure_active_broadcast_bound_to_stream(youtube, camera: CameraConfig):
    broadcast = get_active_broadcast(youtube, part="id,status,contentDetails")
    if broadcast is None:
        return None

    expected_stream_id = get_stream_id_for_key(youtube, camera.key)
    current_stream_id = broadcast.get("contentDetails", {}).get("boundStreamId")
    if current_stream_id == expected_stream_id:
        return expected_stream_id

    life_cycle_status = broadcast.get("status", {}).get("lifeCycleStatus")
    if life_cycle_status not in {"created", "ready"}:
        logger.warning(
            "%s - broadcast %s is bound to stream %s but configured key maps to %s; cannot rebind automatically while status is %s",
            camera.name,
            broadcast["id"],
            current_stream_id,
            expected_stream_id,
            life_cycle_status,
        )
        return current_stream_id

    logger.warning(
        "%s - rebinding broadcast %s from stream %s to configured stream %s",
        camera.name,
        broadcast["id"],
        current_stream_id,
        expected_stream_id,
    )
    youtube.liveBroadcasts().bind(
        part="id,contentDetails",
        id=broadcast["id"],
        streamId=expected_stream_id,
    ).execute()
    return expected_stream_id


def end_schedule(youtube, camera: CameraConfig):
    broadcast = get_active_broadcast(youtube, part="id,status")
    if broadcast is None:
        logger.info("%s - no active YouTube broadcast to end", camera.name)
        return

    broadcast_id = broadcast["id"]
    life_cycle_status = broadcast.get("status", {}).get("lifeCycleStatus")
    logger.info(
        "%s - ending YouTube broadcast %s from %s state",
        camera.name,
        broadcast_id,
        life_cycle_status,
    )

    if life_cycle_status in {"testing", "live"}:
        youtube.liveBroadcasts().transition(
            broadcastStatus="complete", id=broadcast_id, part="id,snippet,status"
        ).execute()
        return

    if life_cycle_status in {"created", "ready", "testStarting", "liveStarting"}:
        logger.info(
            "%s - deleting YouTube broadcast %s because %s cannot transition directly to complete",
            camera.name,
            broadcast_id,
            life_cycle_status,
        )
        youtube.liveBroadcasts().delete(id=broadcast_id).execute()
        return

    logger.warning(
        "%s - leaving YouTube broadcast %s unchanged because lifecycle status %s is not supported for recycle cleanup",
        camera.name,
        broadcast_id,
        life_cycle_status,
    )
