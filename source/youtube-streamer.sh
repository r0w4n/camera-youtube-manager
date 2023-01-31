#!/bin/bash

main() {
    source "${BASH_SOURCE%/*}/settings.cfg"

    for camera in "${!cameras[@]}"
    do
        screen -X -S youtube_$camera quit
        sleep 5
        doYoutube
    done
}

function doYoutube() {
    screen -dS youtube_$camera  -m \
    ffmpeg -f lavfi -i anullsrc -rtsp_transport tcp \
    -i rtsp://"${cameras[$camera]}" \
    -vcodec libx264 -pix_fmt + -c:v copy \
    -f flv rtmp://a.rtmp.youtube.com/live2/"${youtube_key[$camera]}"
}

main "$@"
