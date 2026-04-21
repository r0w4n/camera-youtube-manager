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

from camera_config import CameraConfig


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

    camera_settings = settings.get_settings()
    logger.info("Loaded %s camera configuration(s)", len(camera_settings.cameras))

    for camera in camera_settings.cameras:
        if not camera.enabled:
            logger.info("%s - camera disabled; skipping", camera.name)
            continue

        process_camera(camera)


def process_camera(camera: CameraConfig):
    logger.info("%s - checking camera", camera.name)

    try:
        youtube = build(
            "youtube",
            "v3",
            credentials=youtube_auth.handle_auth(camera.name),
            cache_discovery=False,
        )

        if is_recycle_time() and youtube_schedule.has_scheduled_broadcast(youtube):
            manage_ending_broadcast(camera, youtube)

        if not youtube_schedule.has_scheduled_broadcast(youtube):
            manage_schedule(camera, youtube)
            return

        if not youtube_streamer.is_live_stream_healthy(camera, youtube):
            manage_unhealthy_stream(camera)
            return

        if youtube_schedule.has_inactive_broadcast(youtube):
            manage_inactive_broadcast(camera)
            return

        logger.info("%s - healthy; no action needed", camera.name)

    except HttpError as err:
        logger.exception("%s - YouTube API request failed: %s", camera.name, err)
    except Exception as err:
        logger.exception("%s - camera check failed: %s", camera.name, err)


def is_recycle_time():
    now = datetime.datetime.now()

    if (now.hour == 8 or now.hour == 20 or now.hour == 2) and now.minute == 0:
        return True
    return False


def stop_stream_if_running(camera: CameraConfig):
    if youtube_streamer.is_streaming(camera):
        logger.info("%s - killing screen session", camera.name)
        youtube_streamer.kill_stream(camera)
        time.sleep(5)


def manage_ending_broadcast(camera: CameraConfig, youtube):
    logger.info(
        "%s - recycle window reached with a scheduled stream on YouTube",
        camera.name,
    )
    logger.info("%s - ending scheduled broadcast", camera.name)
    youtube_schedule.end_schedule(youtube, camera)
    stop_stream_if_running(camera)


def manage_schedule(camera: CameraConfig, youtube):
    logger.info("%s - no scheduled stream on YouTube", camera.name)
    stop_stream_if_running(camera)
    logger.info("%s - creating scheduled broadcast", camera.name)
    youtube_schedule.do_schedule(youtube, camera)
    logger.info("%s - starting stream", camera.name)
    youtube_streamer.start_stream(camera)


def manage_unhealthy_stream(camera: CameraConfig):
    logger.warning("%s - stream on YouTube is unhealthy", camera.name)
    stop_stream_if_running(camera)
    logger.info("%s - starting stream", camera.name)
    youtube_streamer.start_stream(camera)


def manage_inactive_broadcast(camera: CameraConfig):
    logger.warning("%s - scheduled broadcast has not started", camera.name)
    if youtube_streamer.is_streaming(camera):
        logger.info(
            "%s - local stream is already running; waiting for YouTube broadcast to activate",
            camera.name,
        )
        return
    logger.info("%s - starting stream", camera.name)
    youtube_streamer.start_stream(camera)


if __name__ == "__main__":
    main()
