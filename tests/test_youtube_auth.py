import sys
from pathlib import Path


SOURCE_DIR = Path(__file__).resolve().parents[1] / "source"
sys.path.insert(0, str(SOURCE_DIR))

import youtube_auth


class FakeCredentials:
    def __init__(self, valid, expired, refresh_token):
        self.valid = valid
        self.expired = expired
        self.refresh_token = refresh_token
        self.refreshed_with = None

    def refresh(self, request):
        self.refreshed_with = request
        self.valid = True

    def to_json(self):
        return '{"token": "value"}'


class FakeFlow:
    def __init__(self, credentials):
        self.credentials = credentials
        self.port = None

    def run_local_server(self, port):
        self.port = port
        return self.credentials


def test_handle_auth_refreshes_existing_credentials(monkeypatch, tmp_path):
    """Verify that expired credentials are refreshed and saved back to disk."""
    tokens_dir = tmp_path / "tokens"
    token_file = tokens_dir / "cam1_token.json"
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text("{}")

    credentials = FakeCredentials(valid=False, expired=True, refresh_token="refresh")

    monkeypatch.setattr(youtube_auth, "TOKENS_DIR", tokens_dir)
    monkeypatch.setattr(
        youtube_auth.Credentials,
        "from_authorized_user_file",
        lambda path, scopes: credentials,
    )
    monkeypatch.setattr(youtube_auth, "Request", lambda: "request")

    returned_credentials = youtube_auth.handle_auth("cam1")

    assert returned_credentials is credentials
    assert credentials.refreshed_with == "request"
    assert token_file.read_text() == '{"token": "value"}'


def test_handle_auth_requests_and_saves_new_credentials(monkeypatch, tmp_path):
    """Verify that missing credentials trigger a new OAuth flow and create the token file."""
    tokens_dir = tmp_path / "tokens"
    client_secret_path = tmp_path / "client_secret.json"
    client_secret_path.write_text("{}")

    credentials = FakeCredentials(valid=True, expired=False, refresh_token=None)
    fake_flow = FakeFlow(credentials)
    captured = {}

    def fake_from_client_secrets_file(path, scopes):
        captured["path"] = path
        captured["scopes"] = scopes
        return fake_flow

    monkeypatch.setattr(youtube_auth, "TOKENS_DIR", tokens_dir)
    monkeypatch.setattr(youtube_auth, "CLIENT_SECRET_PATH", client_secret_path)
    monkeypatch.setattr(
        youtube_auth.InstalledAppFlow,
        "from_client_secrets_file",
        fake_from_client_secrets_file,
    )

    returned_credentials = youtube_auth.handle_auth("cam1")

    assert returned_credentials is credentials
    assert fake_flow.port == 0
    assert captured["path"] == str(client_secret_path)
    assert captured["scopes"] == youtube_auth.SCOPES
    assert (tokens_dir / "cam1_token.json").read_text() == '{"token": "value"}'
