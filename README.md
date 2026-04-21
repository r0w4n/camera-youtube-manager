# Camera YouTube Manager

Camera YouTube Manager is a small Python service for keeping IP camera streams live on YouTube with as little manual intervention as possible.

It does two jobs together:

1. It manages the YouTube side by creating and ending scheduled broadcasts.
2. It manages the local streaming side by launching and supervising `ffmpeg` inside `screen` sessions.

This is useful when you want a Raspberry Pi or other small Linux machine to keep one or more camera feeds online without having to constantly recreate broadcasts, restart stuck streams, or log into YouTube by hand.

## What Value It Adds

Without this kind of manager, a camera-to-YouTube setup usually needs manual attention when:

- a scheduled broadcast does not exist
- a stream becomes unhealthy
- a machine reboot stops the local `ffmpeg` process
- a broadcast needs recycling
- credentials expire and need refreshing

This project automates those repetitive tasks so the box running the stream can act more like a watchdog than a one-shot script.

## What It Does

For each enabled camera, the manager:

- loads the camera configuration from `settings.json`
- authenticates to the camera's YouTube account
- checks whether a scheduled broadcast already exists
- creates and binds a new broadcast if one is missing
- starts the local camera stream when a schedule is created
- checks the YouTube live stream health
- restarts the stream if the YouTube stream is unhealthy
- starts the stream if the broadcast exists but has not started yet
- recycles broadcasts at fixed times of day
- logs the main actions so you can see what happened

## How It Works

The local machine streams to YouTube by launching `ffmpeg` in a dedicated `screen` session per camera.

Session naming convention:

- `youtube_<camera_name>`

That makes it possible to:

- leave streams running in the background
- stop and restart them cleanly
- check whether a given camera process is already active

## Dependencies

This project has both Python dependencies and system/runtime dependencies.

### System Dependencies

These must be installed on the machine running the service:

- Linux or another Unix-like environment
- Python 3
- `pip`
- [FFmpeg](https://ffmpeg.org/)
- [GNU Screen](https://www.gnu.org/software/screen/)
- network access to each IP camera over RTSP
- network access to YouTube / Google APIs

Typical Raspberry Pi package installation:

```bash
sudo apt update
sudo apt install -y python3 python3-pip ffmpeg screen
```

### Python Dependencies

Installed from `requirements.txt`:

- `google-api-python-client`
- `google-auth`
- `google-auth-oauthlib`
- `pytest` for local testing

Install them with:

```bash
pip3 install -r requirements.txt
```

## External Setup Requirements

Before the service can run successfully, you also need:

- a Google Cloud project
- YouTube Data API access for that project
- an OAuth client downloaded as `client_secret.json`
- one YouTube account per camera
- a valid YouTube stream key for each camera/account

Place `client_secret.json` in the project root.

## Project Files You Need

At runtime, these files/directories matter:

- `client_secret.json`
- `settings.json`
- `tokens/`

The `tokens/` directory stores the per-camera OAuth token files generated after authentication.

Create it before first run:

```bash
mkdir -p tokens
```

## Configuration

Create a `settings.json` file in the project root.

Example:

```json
{
  "cameras": [
    {
      "name": "cam1",
      "title": "Back Garden Live",
      "description": "Live stream from the back garden camera",
      "enabled": true,
      "url": "user:password@192.168.1.1/ISAPI/Streaming/Channels/101/picture",
      "key": "xxxx-xxxx-xxxx-xxxx-xxxx"
    }
  ]
}
```

### Settings Notes

- `name`
  Used for logging and for the local `screen` session name.
- `title`
  Used as the YouTube broadcast title.
- `description`
  Used as the YouTube broadcast description.
- `enabled`
  If `false`, the camera is skipped.
- `url`
  The RTSP target without the leading `rtsp://` because the code adds that prefix.
- `key`
  The YouTube stream key for that camera's account.

## First Run

On the first run for each camera, the application will open the OAuth flow and ask you to authorise the relevant YouTube account.

Once completed, it stores the token in:

- `tokens/<camera_name>_token.json`

After that, future runs will reuse or refresh the saved credentials automatically.

## Running the Manager

Run it directly with:

```bash
python3 source/main.py
```

## Logging

The application logs the main operational events, for example:

- camera checks
- schedule creation
- stream starts
- stream stops
- unhealthy stream recovery
- YouTube API failures

By default logging runs at `INFO`.

To change the log level:

```bash
LOG_LEVEL=WARNING python3 source/main.py
```

## Testing

Run the test suite locally with:

```bash
pytest -q
```

## Operational Notes

Current behaviour worth knowing:

- broadcasts are recycled at `02:00`, `08:00`, and `20:00`
- the script is designed to be run repeatedly, for example from cron or a service/timer
- each camera should use its own YouTube account

## Suggested Raspberry Pi Deployment

This project is a good fit for a Raspberry Pi that:

- stays powered on continuously
- has a stable network connection
- can reach both the cameras and YouTube
- runs this script on a schedule

Typical deployment pattern:

1. Install system packages.
2. Install Python dependencies.
3. Add `client_secret.json`.
4. Create `settings.json`.
5. Create the `tokens/` directory.
6. Run the script once interactively to complete OAuth.
7. Run it repeatedly using cron, systemd, or another scheduler.

## Summary

Camera YouTube Manager acts as the glue between your IP cameras, local streaming process, and YouTube Live.

Its main benefit is operational reliability:

- it reduces manual setup
- it recovers from common streaming problems
- it keeps the YouTube broadcast state aligned with the local stream state
- it gives you enough logging to understand what it is doing
