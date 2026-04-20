import youtube_auth
import youtube_schedule
import youtube_streamer
import settings
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import time
import datetime
import logging
import os


logger = logging.getLogger(__name__)


def configure_logging():
    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def main():
    configure_logging()

    try:
        camera_settings = settings.get_settings()
        logger.info("Loaded %s camera configuration(s)", len(camera_settings["cameras"]))

        for camera in camera_settings["cameras"]:
            if not camera["enabled"]:
                logger.info("%s - camera disabled; skipping", camera["name"])
                continue

            logger.info("%s - checking camera", camera["name"])

            # Build the YouTube service object and builds the credential object
            youtube = build(
                "youtube",
                "v3",
                credentials=youtube_auth.handle_auth(camera["name"]),
                cache_discovery=False,
            )

            # Check to see if it time to recycle and if it is kill the current schedule
            if is_recycle_time() and youtube_schedule.has_scheduled_broadcast(youtube):
                manage_ending_broadcast(camera, youtube)

            # Checks to see whether there are any scheduled broadcasts and if there isn't creates a schedule
            if not youtube_schedule.has_scheduled_broadcast(youtube):
                manage_schedule(camera, youtube)
                continue

            # checks to see whether there are any unhealthy streams and if there are kill them
            if not youtube_streamer.is_live_stream_healthy(camera, youtube):
                manage_unhealthy_stream(camera)
                continue

            # checks to see whether a scheduled broadcast is inactive
            if youtube_schedule.has_inactive_broadcast(youtube):
                manage_inactive_broadcast(camera)
                continue

            logger.info("%s - healthy; no action needed", camera["name"])

    except HttpError as err:
        logger.exception("YouTube API request failed: %s", err)


def is_recycle_time():
    now = datetime.datetime.now()

    if (now.hour == 8 or now.hour == 20 or now.hour == 2) and now.minute == 0:
        return True
    return False


def manage_ending_broadcast(camera, youtube):
    logger.info(
        "%s - recycle window reached with a scheduled stream on YouTube",
        camera["name"],
    )
    logger.info("%s - ending scheduled broadcast", camera["name"])
    youtube_schedule.end_schedule(youtube, camera)
    if youtube_streamer.is_streaming(camera):
        logger.info("%s - killing screen session", camera["name"])
        youtube_streamer.kill_stream(camera)
        time.sleep(5)


def manage_schedule(camera, youtube):
    logger.info("%s - no scheduled stream on YouTube", camera["name"])
    if youtube_streamer.is_streaming(camera):
        logger.info("%s - killing existing screen session", camera["name"])
        youtube_streamer.kill_stream(camera)
        time.sleep(5)
    logger.info("%s - creating scheduled broadcast", camera["name"])
    youtube_schedule.do_schedule(youtube, camera)
    logger.info("%s - starting stream", camera["name"])
    youtube_streamer.start_stream(camera)


def manage_unhealthy_stream(camera):
    logger.warning("%s - stream on YouTube is unhealthy", camera["name"])
    if youtube_streamer.is_streaming(camera):
        logger.info("%s - killing screen session", camera["name"])
        youtube_streamer.kill_stream(camera)
        time.sleep(5)
    logger.info("%s - starting stream", camera["name"])
    youtube_streamer.start_stream(camera)


def manage_inactive_broadcast(camera):
    logger.warning("%s - scheduled broadcast has not started", camera["name"])
    if youtube_streamer.is_streaming(camera):
        logger.info("%s - killing screen session", camera["name"])
        youtube_streamer.kill_stream(camera)
        time.sleep(5)
    logger.info("%s - starting stream", camera["name"])
    youtube_streamer.start_stream(camera)


if __name__ == "__main__":
    main()
