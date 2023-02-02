import youtube_auth
import youtube_schedule
import youtube_streamer
import settings
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import time
import datetime


def main():
    try:
        camera_settings = settings.get_settings()

        for camera in camera_settings["cameras"]:
            if not camera["enabled"]:
                print(f"""{camera["name"]} is disabled""")
                continue

            # Build the YouTube service object and builds the credential object
            youtube = build(
                "youtube", "v3", credentials=youtube_auth.handle_auth(camera["name"])
            )

            # Check to see if it time to recycle and if it is kill the current schedule
            if is_recycle_time() and youtube_schedule.has_scheduled_broadcast(youtube):
                manage_ending_broadcast(camera, youtube)

            # Checks to see whether there are any scheduled broadcasts and if there isn't creates a schedule
            if not youtube_schedule.has_scheduled_broadcast(youtube):
                manage_schedule(camera, youtube)

            # checks to see whether there are any unhealthy streams and if there are kill them
            if not youtube_streamer.is_live_stream_healthy(youtube):
                manage_unhealthy_stream(camera)

            # checks to see whether a scheduled broadcast is inactive
            if youtube_schedule.has_inactive_broadcast(youtube):
                manage_inactive_broadcast(camera)

    except HttpError as err:
        print(err)


def is_recycle_time():
    now = datetime.datetime.now()

    if (now.hour == 8 or now.hour == 20 or now.hour == 2) and now.minute == 0:
        return True
    return False


def manage_ending_broadcast(camera, youtube):
    print(f"""It's recycle time and {camera["name"]} has scheduled stream on youtube""")
    print(f"""Ending {camera["name"]} scheduled stream on youtube""")
    youtube_schedule.end_schedule(youtube)
    if youtube_streamer.is_streaming(camera):
        print(f"""killing screen session for {camera["name"]}""")
        youtube_streamer.kill_stream(camera)
        time.sleep(5)


def manage_schedule(camera, youtube):
    print(f"""{camera["name"]} has no scheduled stream on youtube""")
    if youtube_streamer.is_streaming(camera):
        print(f"""killing screen session for {camera["name"]}""")
        youtube_streamer.kill_stream(camera)
    print(f"""creating schedule for {camera["name"]} on youtube""")
    youtube_schedule.do_schedule(youtube, camera)


def manage_unhealthy_stream(camera):
    print(f"""{camera["name"]} stream on youtube is unhealthy""")
    if youtube_streamer.is_streaming(camera):
        print(f"""killing screen session for {camera["name"]}""")
        youtube_streamer.kill_stream(camera)
        time.sleep(5)
    print(f"""starting stream for {camera["name"]}""")
    youtube_streamer.start_stream(camera)


def manage_inactive_broadcast(camera):
    print(f"""{camera["name"]} has a scheduled broadcast that hasn't been started""")
    if youtube_streamer.is_streaming(camera):
        print(f"""killing screen session for {camera["name"]}""")
        youtube_streamer.kill_stream(camera)
        time.sleep(5)
    print(f"""starting stream for {camera["name"]}""")
    youtube_streamer.start_stream(camera)


if __name__ == "__main__":
    main()
