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
sudo apt install -y git python3 python3-pip ffmpeg screen logrotate
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
- a YouTube channel enabled for live streaming
- remember that one YouTube channel can only run one live stream at a time
- one YouTube account/channel per camera if you want simultaneous camera streams
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
  The YouTube stream key for that camera's account. It must match the reusable
  YouTube live stream that you want broadcasts to bind to.

## First Run

On the first run for each camera, the application will open the OAuth flow and ask you to authorise the relevant YouTube account.

In practice, that means:

- run `python3 source/main.py` manually before enabling cron
- the script starts Google's installed-app OAuth flow on the local machine
- a browser window should open, or you will be given a local Google authorisation URL to open yourself
- sign in to the YouTube account/channel for that camera
- click `Allow` when Google asks for permission
- once Google redirects back to the local callback, the script saves the token file automatically

Once completed, it stores the token in:

- `tokens/<camera_name>_token.json`

After that, future runs will reuse or refresh the saved credentials automatically.

If the Pi is headless, do this first run from a session where you can complete the browser sign-in on the Pi.

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

To see line coverage locally:

```bash
pytest -q --cov=source --cov-report=term-missing
```

## Operational Notes

Current behaviour worth knowing:

- broadcasts are recycled once during the `02:00`, `08:00`, and `20:00` hours
- the script is designed to be run repeatedly, for example from cron or a service/timer
- each camera should use its own YouTube account

## Suggested Raspberry Pi Deployment

This project is a good fit for a Raspberry Pi that:

- stays powered on continuously
- has a stable network connection
- can reach both the cameras and YouTube
- runs this script on a schedule

The steps below assume the service will run as your normal Pi user and that the repository lives at `~/camera-youtube-manager`. That keeps the cron entry simple and makes it obvious where `settings.json`, `client_secret.json`, and the saved OAuth tokens live.

### 1. Install the dependencies

Install the system packages first:

```bash
sudo apt update
sudo apt install -y git python3 python3-pip ffmpeg screen logrotate
```

Then install the Python packages used by this project:

```bash
cd ~
git clone https://github.com/r0w4n/camera-youtube-manager.git
cd ~/camera-youtube-manager
pip3 install -r requirements.txt
mkdir -p ~/camera-youtube-manager/tokens
```

If you already have the repository on the Pi and just want to update it:

```bash
cd ~/camera-youtube-manager
git pull
pip3 install -r requirements.txt
```

### 2. Put the script in the correct directory

The cron example later in this guide expects the code to be in:

```text
~/camera-youtube-manager
```

That means the main script path will be:

```text
~/camera-youtube-manager/source/main.py
```

If you install it somewhere else, update the cron command and any notes below to match your chosen location.

### 3. Add `client_secret.json`

Copy the OAuth client downloaded from Google Cloud into the project root:

```text
~/camera-youtube-manager/client_secret.json
```

### 4. Configure `settings.json`

Create `~/camera-youtube-manager/settings.json` using the example earlier in this README.

Important points when filling it in:

- `name` should be short and unique because it is used in log messages and in the `screen` session name
- `url` must not include the leading `rtsp://` because the code adds that part itself
- `key` must be the YouTube stream key for the channel that camera should stream to
- `enabled` lets you temporarily disable a camera without deleting its configuration

### 5. Set up the YouTube side

Before you automate the Pi, make sure the YouTube side is ready:

- enable live streaming on the YouTube channel
- create or retrieve the correct stream key for each camera
- remember that a single YouTube channel can only have one live stream at a time
- if you want multiple cameras live at the same time, give each one its own YouTube account/channel and its own stream key

This project already assumes separate YouTube credentials per camera by saving tokens as:

```text
tokens/<camera_name>_token.json
```

### 6. Run the script once manually

Do one interactive run before setting up cron so the OAuth flow can complete and create the token files:

```bash
cd ~/camera-youtube-manager
python3 source/main.py
```

During this run, approve the Google/YouTube access request in the browser for each camera account as prompted.

When approval succeeds, the script writes the saved credentials to:

```text
~/camera-youtube-manager/tokens/<camera_name>_token.json
```

### 7. Prepare the log file

If you want to use the home-directory log file from the cron example below, create it once:

```bash
touch ~/youtube-camera.log
```

### 8. Add the cron entry

Open your user crontab:

```bash
crontab -e
```

Add this line:

```cron
*/5 * * * * python3 ~/camera-youtube-manager/source/main.py >> ~/youtube-camera.log 2>&1
```

That runs the manager every five minutes, which fits the way this project is designed to keep checking schedules, stream health, and inactive broadcasts.

### 9. Discard the log daily with logrotate

Create `/etc/logrotate.d/camera-youtube-manager` with contents like this:

```conf
/home/pi/youtube-camera.log {
    daily
    rotate 0
    missingok
    notifempty
    copytruncate
}
```

Replace `/home/pi/youtube-camera.log` with the real home-directory path for the user running the cron job.

Because the cron job appends to the file as your normal user, `copytruncate` keeps rotation simple without needing root to recreate the file with specific ownership.

`rotate 0` means old log files are not kept. The current log is discarded each day rather than keeping dated archives.

### 10. Turn on the Raspberry Pi overlay filesystem last

Do this only after:

- the repository is in place
- `settings.json` is correct
- `client_secret.json` is present
- the first OAuth run has completed successfully

Then enable the overlay filesystem from `raspi-config`:

```bash
sudo raspi-config
```

In the menu, go to `Advanced Options` and then `Overlay File System`, enable it, and reboot when prompted.

Reasons to do this:

- it reduces SD card wear on a Pi that is writing logs and temporary data regularly
- it makes the box more resilient to sudden power loss
- it helps the Pi behave more like a small appliance once the setup is stable

Important trade-off:

- when the overlay filesystem is enabled, changes made to the root filesystem do not persist across reboot unless you disable the overlay first
- that means future `git pull` updates, package installs, changes to `settings.json`, and re-authorisation work should be done with the overlay temporarily turned off

## Summary

Camera YouTube Manager acts as the glue between your IP cameras, local streaming process, and YouTube Live.

Its main benefit is operational reliability:

- it reduces manual setup
- it recovers from common streaming problems
- it keeps the YouTube broadcast state aligned with the local stream state
- it gives you enough logging to understand what it is doing
