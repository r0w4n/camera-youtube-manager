from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import logging
from pathlib import Path

SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]
BASE_DIR = Path(__file__).resolve().parent.parent
CLIENT_SECRET_PATH = BASE_DIR / "client_secret.json"
TOKENS_DIR = BASE_DIR / "tokens"
logger = logging.getLogger(__name__)


def get_token_file_path(camera_name):
    return TOKENS_DIR / f"{camera_name}_token.json"


def load_credentials(camera_name):
    token_file_path = get_token_file_path(camera_name)
    if token_file_path.exists():
        return Credentials.from_authorized_user_file(str(token_file_path), SCOPES)
    return None


def refresh_credentials(camera_name, credentials):
    logger.info("%s - refreshing YouTube credentials", camera_name)
    credentials.refresh(Request())
    return credentials


def request_credentials(camera_name):
    logger.info("%s - requesting new YouTube credentials", camera_name)
    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_PATH), SCOPES)
    return flow.run_local_server(port=0)


def save_credentials(camera_name, credentials):
    token_file_path = get_token_file_path(camera_name)
    token_file_path.parent.mkdir(parents=True, exist_ok=True)
    token_file_path.write_text(credentials.to_json())
    logger.info("%s - saved YouTube credentials", camera_name)


def handle_auth(camera_name):
    credentials = load_credentials(camera_name)

    if credentials and credentials.valid:
        return credentials

    if credentials and credentials.expired and credentials.refresh_token:
        credentials = refresh_credentials(camera_name, credentials)
    else:
        credentials = request_credentials(camera_name)

    save_credentials(camera_name, credentials)
    return credentials
