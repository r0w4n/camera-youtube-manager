from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import logging
import os.path

SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]
logger = logging.getLogger(__name__)

def handle_auth(camera_name):
    credentials = None
    token_file_path = (
        os.path.dirname(os.path.abspath(__file__))
        + "/../tokens/"
        + camera_name
        + "_token.json"
    )

    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(token_file_path):
        credentials = Credentials.from_authorized_user_file(token_file_path, SCOPES)

    # If there are no (valid) credentials available, let the user log in.
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            logger.info("%s - refreshing YouTube credentials", camera_name)
            credentials.refresh(Request())
        else:
            logger.info("%s - requesting new YouTube credentials", camera_name)
            flow = InstalledAppFlow.from_client_secrets_file(
                os.path.dirname(os.path.abspath(__file__)) + "/../client_secret.json",
                SCOPES,
            )
            credentials = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(token_file_path, "w") as token:
            token.write(credentials.to_json())
        logger.info("%s - saved YouTube credentials", camera_name)

    return credentials
