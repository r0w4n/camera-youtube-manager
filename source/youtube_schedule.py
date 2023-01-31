import datetime


def schedule_broadcast(youtube, title, description):
    content = {
        "snippet": {
            "title": title,
            "description": description,
            "scheduledStartTime": datetime.datetime.now().isoformat() + "Z",
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

    return response["id"]


def get_default_stream_id(youtube):
    streams = youtube.liveStreams().list(part="id", mine=True).execute()
    return streams["items"][0]["id"]


def has_scheduled_broadcast(youtube):
    response = youtube.liveBroadcasts().list(part="status", mine=True).execute()

    if [x for x in response["items"] if x["status"]["lifeCycleStatus"] != "complete"]:
        return True

    return False


def has_inactive_broadcast(youtube):
    response = youtube.liveBroadcasts().list(part="status", mine=True).execute()

    if [x for x in response["items"] if x["status"]["lifeCycleStatus"] == "ready"]:
        return True

    return False


def get_scheduled_broadcast_id(youtube):
    response = youtube.liveBroadcasts().list(part="status", mine=True).execute()
    live_stream = [
        x for x in response["items"] if x["status"]["lifeCycleStatus"] != "complete"
    ]
    return live_stream[0]["id"]


def do_schedule(youtube, camera):
    # Schedules a broadcast
    broadcast_id = schedule_broadcast(youtube, camera["title"], camera["description"])

    # Binds the new broadcast to default stream (this assumes that only one stream per account)
    youtube.liveBroadcasts().bind(
        part="id,contentDetails",
        id=broadcast_id,
        streamId=get_default_stream_id(youtube),
    ).execute()


def end_schedule(youtube):
    youtube.liveBroadcasts().transition(
        broadcastStatus="complete", id=get_scheduled_broadcast_id(youtube), part="id,snippet,status"
    ).execute()
