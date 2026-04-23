import youtube_auth
import youtube_schedule
import youtube_streamer
import settings
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import argparse
import time
import datetime
import logging
import os
import sys

from camera_config import CameraConfig


logger = logging.getLogger(__name__)
RECYCLE_HOURS = {2, 8, 20}
MANUAL_ACTIONS = {"kill", "recycle", "restart"}


def configure_logging():
    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Manage camera streams and their YouTube broadcasts."
    )
    parser.add_argument(
        "action",
        nargs="?",
        default="check",
        choices=("check", "kill", "recycle", "restart"),
        help=(
            "Action to run. 'check' is the normal watchdog action used by cron. "
            "'kill' stops a camera stream, 'restart' restarts a camera stream, "
            "and 'recycle' recreates a camera broadcast and stream."
        ),
    )
    parser.add_argument(
        "--camera",
        help="Camera name from settings.json. Required for kill, recycle, and restart.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    configure_logging()
    if argv is None:
        argv = []
    args = parse_args(argv)
    if args.action in MANUAL_ACTIONS and not args.camera:
        raise SystemExit(f"{args.action} requires --camera <camera_name>")

    camera_settings = settings.get_settings()
    logger.info("Loaded %s camera configuration(s)", len(camera_settings.cameras))

    cameras = get_selected_cameras(camera_settings.cameras, args.camera)

    for camera in cameras:
        if args.action == "check" and not camera.enabled:
            logger.info("%s - camera disabled; skipping", camera.name)
            continue

        process_camera_action(camera, args.action)


def get_selected_cameras(cameras, camera_name=None):
    if camera_name is None:
        return cameras

    selected_camera = next(
        (camera for camera in cameras if camera.name == camera_name),
        None,
    )
    if selected_camera is None:
        available_cameras = ", ".join(camera.name for camera in cameras) or "none"
        raise SystemExit(
            f"Unknown camera '{camera_name}'. Available cameras: {available_cameras}"
        )

    return [selected_camera]


def process_camera_action(camera: CameraConfig, action: str):
    if action == "check":
        process_camera(camera)
    elif action == "kill":
        stop_stream_if_running(camera)
    elif action == "restart":
        restart_stream(camera)
    elif action == "recycle":
        recycle_camera(camera)
    else:
        raise ValueError(f"Unsupported action: {action}")


def build_youtube_client(camera: CameraConfig):
    return build(
        "youtube",
        "v3",
        credentials=youtube_auth.handle_auth(camera.name),
        cache_discovery=False,
    )


def process_camera(camera: CameraConfig):
    logger.info("%s - checking camera", camera.name)

    try:
        youtube = build_youtube_client(camera)

        recycle_window_start = get_recycle_window_start()
        if recycle_window_start:
            recycle_decision = youtube_schedule.get_recycle_decision(
                youtube, recycle_window_start
            )
            if recycle_decision.should_recycle:
                if recycle_decision.reason == "missing_scheduled_start_time":
                    logger.info(
                        "%s - recycle hour active; broadcast %s has no scheduled start time, recycling",
                        camera.name,
                        recycle_decision.broadcast_id,
                    )
                else:
                    logger.info(
                        "%s - recycle hour active; broadcast %s was scheduled at %s, recycling",
                        camera.name,
                        recycle_decision.broadcast_id,
                        recycle_decision.scheduled_start_time,
                    )
                manage_ending_broadcast(camera, youtube)
            elif recycle_decision.reason == "already_recycled_this_hour":
                logger.info(
                    "%s - recycle hour active; broadcast %s was scheduled at %s, skipping recycle",
                    camera.name,
                    recycle_decision.broadcast_id,
                    recycle_decision.scheduled_start_time,
                )

        if not youtube_schedule.has_scheduled_broadcast(youtube):
            manage_schedule(camera, youtube)
            return

        stream_id = youtube_schedule.ensure_active_broadcast_bound_to_stream(
            youtube, camera
        )

        if not youtube_streamer.is_live_stream_healthy(camera, youtube, stream_id):
            manage_unhealthy_stream(camera)
            return

        if youtube_schedule.has_inactive_broadcast(youtube):
            manage_inactive_broadcast(camera, youtube)
            return

        logger.info("%s - healthy; no action needed", camera.name)

    except HttpError as err:
        logger.exception("%s - YouTube API request failed: %s", camera.name, err)
    except Exception as err:
        logger.exception("%s - camera check failed: %s", camera.name, err)


def get_recycle_window_start(now=None):
    if now is None:
        now = datetime.datetime.now().astimezone()
    elif now.tzinfo is None:
        now = now.astimezone()

    if now.hour not in RECYCLE_HOURS:
        return None

    return now.replace(minute=0, second=0, microsecond=0)


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
    stop_stream_if_running(camera)
    youtube_schedule.end_schedule(youtube, camera)


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


def restart_stream(camera: CameraConfig):
    stop_stream_if_running(camera)
    logger.info("%s - starting stream", camera.name)
    youtube_streamer.start_stream(camera)


def recycle_camera(camera: CameraConfig):
    logger.info("%s - manually recycling broadcast and stream", camera.name)
    youtube = build_youtube_client(camera)
    manage_ending_broadcast(camera, youtube)
    logger.info("%s - creating scheduled broadcast", camera.name)
    youtube_schedule.do_schedule(youtube, camera)
    logger.info("%s - starting stream", camera.name)
    youtube_streamer.start_stream(camera)


def manage_inactive_broadcast(camera: CameraConfig, youtube):
    logger.warning("%s - scheduled broadcast has not started", camera.name)
    if youtube_streamer.is_streaming(camera):
        logger.warning(
            "%s - local stream is already running but the YouTube broadcast is still inactive; recreating the scheduled broadcast",
            camera.name,
        )
        stop_stream_if_running(camera)
        youtube_schedule.end_schedule(youtube, camera)
        logger.info("%s - creating scheduled broadcast", camera.name)
        youtube_schedule.do_schedule(youtube, camera)
        logger.info("%s - starting stream", camera.name)
        youtube_streamer.start_stream(camera)
        return
    logger.info("%s - starting stream", camera.name)
    youtube_streamer.start_stream(camera)


if __name__ == "__main__":
    main(sys.argv[1:])
