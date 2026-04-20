import os
import subprocess


HEALTHY_STREAM_STATUSES = {"good", "ok"}


def kill_stream(camera):
    os.system(f"""screen -X -S youtube_{camera["name"]} quit""")


def start_stream(camera):
    os.system(
        f"""screen -dS youtube_{camera["name"]}  -m ffmpeg -f lavfi -i anullsrc -rtsp_transport tcp -i rtsp://{camera["url"]} -vcodec libx264 -pix_fmt + -c:v copy -f flv rtmp://a.rtmp.youtube.com/live2/{camera["key"]}"""
    )


def is_live_stream_healthy(youtube):
    response = youtube.liveStreams().list(part="status", mine=True).execute()
    return any(
        item.get("status", {}).get("healthStatus", {}).get("status")
        in HEALTHY_STREAM_STATUSES
        for item in response.get("items", [])
    )


def is_streaming(camera):
    try:
        subprocess.check_output(
            [f'screen -list | grep -q "{camera["name"]}" ;'], shell=True
        )
        return True
    except subprocess.CalledProcessError:
        return False
