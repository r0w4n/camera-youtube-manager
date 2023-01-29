from __future__ import print_function

import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import datetime
import json


def get_settings():
    with open(os.path.dirname(os.path.abspath(__file__)) + "/../settings.json", "r") as f:
        return json.load(f)


def schedule_broadcast(youtube, title, description):
    content = {
        "snippet": {
            "title": title,
            "description": description,
            "scheduledStartTime": datetime.datetime.now().isoformat() + "Z",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
        "contentDetails": {
            "enableEmbed": True,
            "enableDvr": True,
            "recordFromStart": True,
            "enableClosedCaptions": False,
            "latencyPreference": "normal",
            "enableAutoStart": True,
            "enableAutoStop": False,
        },
    }

    response = (
        youtube.liveBroadcasts()
        .insert(
            part="snippet, status, contentDetails",
            body=content,
        )
        .execute()
    )

    return response["id"]


def get_default_stream_id(youtube):
    streams = youtube.liveStreams().list(part="id", mine=True).execute()
    return streams["items"][0]["id"]


def has_scheduled_broadcast(youtube):
    response = youtube.liveBroadcasts().list(part="status", mine=True).execute()

    if [x for x in response["items"] if x["status"]["lifeCycleStatus"] != "complete"]:
        return True

    return False


SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


def handle_auth(camera_name):
    credentials = None
    token_file_path = os.path.dirname(os.path.abspath(__file__)) + "/../tokens/" + camera_name + "_token.json"

    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(token_file_path):
        credentials = Credentials.from_authorized_user_file(token_file_path, SCOPES)

    # If there are no (valid) credentials available, let the user log in.
    if not credentials or not credentials.valid:
        print("requesting auth for " + camera_name)
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                os.path.dirname(os.path.abspath(__file__)) + "/../client_secret.json", SCOPES
            )
            credentials = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(token_file_path, "w") as token:
            token.write(credentials.to_json())

    return credentials


def main():
    try:
        settings = get_settings()

        for camera in settings["cameras"]:
            if not camera["enabled"]:
                continue

            # Build the YouTube service object and builds the credential object
            youtube = build("youtube", "v3", credentials=handle_auth(camera["name"]))

            # Checks to see whether there are any scheduled broadcasts and skips if there are
            if has_scheduled_broadcast(youtube):
                continue

            print("no scheduled broadcasts found for " + camera["name"])

            # Schedules a broadcast
            broadcast_id = schedule_broadcast(
                youtube, camera["title"], camera["description"]
            )

            # Binds the new broadcast to default stream (this assumes that only one stream per account)
            youtube.liveBroadcasts().bind(
                part="id,contentDetails",
                id=broadcast_id,
                streamId=get_default_stream_id(youtube),
            ).execute()
    except HttpError as err:
        print(err)


if __name__ == "__main__":
    main()
