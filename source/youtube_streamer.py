import logging
import re
import subprocess

from camera_config import CameraConfig


HEALTHY_STREAM_STATUSES = {"good", "ok"}
logger = logging.getLogger(__name__)


def get_screen_name(camera: CameraConfig):
    return f"youtube_{camera.name}"


def kill_stream(camera: CameraConfig):
    screen_name = get_screen_name(camera)
    logger.info("%s - stopping screen session %s", camera.name, screen_name)
    result = subprocess.run(
        ["screen", "-X", "-S", screen_name, "quit"],
        check=False,
    )
    exit_status = result.returncode
    if exit_status != 0:
        logger.warning(
            "%s - screen quit command for %s exited with status %s",
            camera.name,
            screen_name,
            exit_status,
        )


def build_stream_command(camera: CameraConfig):
    return [
        "screen",
        "-dS",
        get_screen_name(camera),
        "-m",
        "ffmpeg",
        "-f",
        "lavfi",
        "-i",
        "anullsrc",
        "-rtsp_transport",
        "tcp",
        "-i",
        f"rtsp://{camera.url}",
        "-vcodec",
        "libx264",
        "-pix_fmt",
        "+",
        "-c:v",
        "copy",
        "-f",
        "flv",
        f"rtmp://a.rtmp.youtube.com/live2/{camera.key}",
    ]


def start_stream(camera: CameraConfig):
    logger.info("%s - starting ffmpeg stream", camera.name)
    result = subprocess.run(build_stream_command(camera), check=False)
    exit_status = result.returncode
    if exit_status != 0:
        logger.warning(
            "%s - ffmpeg launch command exited with status %s",
            camera.name,
            exit_status,
        )


def is_live_stream_healthy(camera: CameraConfig, youtube):
    response = youtube.liveStreams().list(part="status", mine=True).execute()
    statuses = [
        item.get("status", {}).get("healthStatus", {}).get("status")
        for item in response.get("items", [])
    ]
    is_healthy = any(status in HEALTHY_STREAM_STATUSES for status in statuses)

    if not is_healthy:
        logger.warning(
            "%s - no healthy YouTube live streams detected; statuses=%s",
            camera.name,
            statuses,
        )

    return is_healthy


def is_streaming(camera: CameraConfig):
    screen_name = get_screen_name(camera)
    result = subprocess.run(
        ["screen", "-list"],
        capture_output=True,
        text=True,
        check=False,
    )
    pattern = rf"\d+\.{re.escape(screen_name)}(?:\t|\s)"
    return re.search(pattern, result.stdout or "") is not None
