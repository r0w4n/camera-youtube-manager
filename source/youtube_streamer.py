import os
import subprocess
import logging


HEALTHY_STREAM_STATUSES = {"good", "ok"}
logger = logging.getLogger(__name__)


def kill_stream(camera):
    screen_name = f"""youtube_{camera["name"]}"""
    logger.info("%s - stopping screen session %s", camera["name"], screen_name)
    exit_status = os.system(f"""screen -X -S {screen_name} quit""")
    if exit_status != 0:
        logger.warning(
            "%s - screen quit command for %s exited with status %s",
            camera["name"],
            screen_name,
            exit_status,
        )


def start_stream(camera):
    logger.info("%s - starting ffmpeg stream", camera["name"])
    exit_status = os.system(
        f"""screen -dS youtube_{camera["name"]}  -m ffmpeg -f lavfi -i anullsrc -rtsp_transport tcp -i rtsp://{camera["url"]} -vcodec libx264 -pix_fmt + -c:v copy -f flv rtmp://a.rtmp.youtube.com/live2/{camera["key"]}"""
    )
    if exit_status != 0:
        logger.warning(
            "%s - ffmpeg launch command exited with status %s",
            camera["name"],
            exit_status,
        )


def is_live_stream_healthy(camera, youtube):
    response = youtube.liveStreams().list(part="status", mine=True).execute()
    statuses = [
        item.get("status", {}).get("healthStatus", {}).get("status")
        for item in response.get("items", [])
    ]
    is_healthy = any(status in HEALTHY_STREAM_STATUSES for status in statuses)

    if not is_healthy:
        logger.warning(
            "%s - no healthy YouTube live streams detected; statuses=%s",
            camera["name"],
            statuses,
        )

    return is_healthy


def is_streaming(camera):
    try:
        subprocess.check_output(
            [f'screen -list | grep -q "{camera["name"]}" ;'], shell=True
        )
        return True
    except subprocess.CalledProcessError:
        return False
