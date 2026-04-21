import datetime
import logging


logger = logging.getLogger(__name__)


def get_scheduled_start_time():
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def schedule_broadcast(youtube, camera):
    logger.info(
        '%s - creating YouTube broadcast with title "%s"',
        camera["name"],
        camera["title"],
    )
    content = {
        "snippet": {
            "title": camera["title"],
            "description": camera["description"],
            "scheduledStartTime": get_scheduled_start_time(),
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
        "contentDetails": {
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

    logger.info("%s - created YouTube broadcast %s", camera["name"], response["id"])
    return response["id"]


def get_default_stream_id(youtube):
    streams = youtube.liveStreams().list(part="id", mine=True).execute()
    return streams["items"][0]["id"]


def get_broadcasts(youtube):
    response = youtube.liveBroadcasts().list(part="status", mine=True).execute()
    return response["items"]


def has_scheduled_broadcast(youtube):
    return any(
        broadcast["status"]["lifeCycleStatus"] != "complete"
        for broadcast in get_broadcasts(youtube)
    )


def has_inactive_broadcast(youtube):
    return any(
        broadcast["status"]["lifeCycleStatus"] == "ready"
        for broadcast in get_broadcasts(youtube)
    )


def get_scheduled_broadcast_id(youtube):
    live_stream = [
        x for x in get_broadcasts(youtube) if x["status"]["lifeCycleStatus"] != "complete"
    ]
    return live_stream[0]["id"]


def do_schedule(youtube, camera):
    # Schedules a broadcast
    broadcast_id = schedule_broadcast(youtube, camera)
    logger.info("%s - binding broadcast %s to stream", camera["name"], broadcast_id)

    # Binds the new broadcast to default stream (this assumes that only one stream per account)
    youtube.liveBroadcasts().bind(
        part="id,contentDetails",
        id=broadcast_id,
        streamId=get_default_stream_id(youtube),
    ).execute()


def end_schedule(youtube, camera):
    broadcast_id = get_scheduled_broadcast_id(youtube)
    logger.info("%s - ending YouTube broadcast %s", camera["name"], broadcast_id)
    youtube.liveBroadcasts().transition(
        broadcastStatus="complete", id=broadcast_id, part="id,snippet,status"
    ).execute()
