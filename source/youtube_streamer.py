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


def is_live_stream_healthy(camera: CameraConfig, youtube, stream_id):
    if not stream_id:
        logger.warning("%s - scheduled broadcast has no bound YouTube stream", camera.name)
        return False

    response = youtube.liveStreams().list(part="id,status", id=stream_id).execute()
    stream = next(
        (item for item in response.get("items", []) if item.get("id") == stream_id),
        None,
    )
    if stream is None:
        logger.warning(
            "%s - could not find YouTube live stream %s bound to the scheduled broadcast",
            camera.name,
            stream_id,
        )
        return False

    status = stream.get("status", {})
    stream_status = status.get("streamStatus")
    health_status = status.get("healthStatus", {}).get("status")
    is_healthy = (
        stream_status == "active" and health_status in HEALTHY_STREAM_STATUSES
    )

    if not is_healthy:
        logger.warning(
            "%s - bound YouTube live stream %s is not healthy; streamStatus=%s healthStatus=%s",
            camera.name,
            stream_id,
            stream_status,
            health_status,
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
