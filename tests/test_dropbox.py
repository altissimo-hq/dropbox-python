"""Unit tests for Dropbox clients and settings."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from altissimo.dropbox import (
    DropboxAppSettings,
    DropboxAuthClient,
    DropboxClient,
    DropboxSecretClient,
    DropboxSecretSettings,
    DropboxSettings,
)


def test_dropbox_app_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test app settings loading, validation, and fallbacks."""
    monkeypatch.delenv("DROPBOX_APP_KEY", raising=False)
    monkeypatch.delenv("DROPBOX_APP_SECRET", raising=False)
    monkeypatch.delenv("DROPBOX_LMM_APP_KEY", raising=False)
    monkeypatch.delenv("DROPBOX_LMM_APP_SECRET", raising=False)

    with pytest.raises(ValueError, match="Neither DROPBOX_APP_KEY nor DROPBOX_LMM_APP_KEY is set"):
        DropboxAppSettings.from_env()

    # Test legacy fallback
    monkeypatch.setenv("DROPBOX_LMM_APP_KEY", "legacy-key")
    monkeypatch.setenv("DROPBOX_LMM_APP_SECRET", "legacy-secret")
    settings = DropboxAppSettings.from_env()
    assert settings.app_key == "legacy-key"
    assert settings.app_secret == "legacy-secret"

    # Test modern settings take preference
    monkeypatch.setenv("DROPBOX_APP_KEY", "modern-key")
    monkeypatch.setenv("DROPBOX_APP_SECRET", "modern-secret")
    settings = DropboxAppSettings.from_env()
    assert settings.app_key == "modern-key"
    assert settings.app_secret == "modern-secret"


def test_dropbox_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test client settings loading, validation, and fallbacks."""
    monkeypatch.setenv("DROPBOX_APP_KEY", "key")
    monkeypatch.setenv("DROPBOX_APP_SECRET", "secret")
    monkeypatch.delenv("DROPBOX_REFRESH_TOKEN", raising=False)
    monkeypatch.delenv("DROPBOX_LMM_APP_REFRESH_TOKEN", raising=False)

    with pytest.raises(ValueError, match="Neither DROPBOX_REFRESH_TOKEN nor DROPBOX_LMM_APP_REFRESH_TOKEN is set"):
        DropboxSettings.from_env()

    # Test legacy fallback
    monkeypatch.setenv("DROPBOX_LMM_APP_REFRESH_TOKEN", "legacy-token")
    settings = DropboxSettings.from_env()
    assert settings.refresh_token == "legacy-token"

    # Test modern takes preference
    monkeypatch.setenv("DROPBOX_REFRESH_TOKEN", "modern-token")
    settings = DropboxSettings.from_env()
    assert settings.refresh_token == "modern-token"


def test_dropbox_secret_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test Secret Manager settings loading, validation, and fallbacks."""
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GCP_PROJECT", raising=False)
    monkeypatch.delenv("PROJECT_ID", raising=False)
    monkeypatch.delenv("DROPBOX_REFRESH_TOKEN_SECRET_ID", raising=False)
    monkeypatch.delenv("DROPBOX_LMM_REFRESH_TOKEN_SECRET_ID", raising=False)

    with pytest.raises(ValueError, match=r"GOOGLE_CLOUD_PROJECT .* is not set"):
        DropboxSecretSettings.from_env()

    # Resolve project ID from env
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "project-123")
    settings = DropboxSecretSettings.from_env()
    assert settings.project_id == "project-123"
    assert settings.secret_id == "dropbox-app-refresh-token"  # default

    # Verify custom secret ID overrides
    monkeypatch.setenv("DROPBOX_LMM_REFRESH_TOKEN_SECRET_ID", "legacy-secret-id")
    settings = DropboxSecretSettings.from_env()
    assert settings.secret_id == "legacy-secret-id"

    monkeypatch.setenv("DROPBOX_REFRESH_TOKEN_SECRET_ID", "modern-secret-id")
    settings = DropboxSecretSettings.from_env()
    assert settings.secret_id == "modern-secret-id"


def test_dropbox_client_lazy_loading() -> None:
    """Test DropboxClient lazy loading RuntimeError when dependency is missing."""
    settings = DropboxSettings(app_key="key", app_secret="secret", refresh_token="token")
    client = DropboxClient(settings)

    with (
        patch("builtins.__import__", side_effect=ModuleNotFoundError("No module named 'dropbox'")),
        pytest.raises(RuntimeError, match="Dropbox dependency not installed"),
    ):
        client._get_client()


def test_dropbox_client_operations() -> None:
    """Test file operations wrapper methods on DropboxClient."""
    mock_sdk = MagicMock()
    settings = DropboxSettings(app_key="key", app_secret="secret", refresh_token="token")
    client = DropboxClient(settings, client=mock_sdk)

    # 1. get_raw_client
    assert client.get_raw_client() is mock_sdk

    # 2. get_current_account
    mock_sdk.users_get_current_account.return_value = {"email": "test@example.com"}
    assert client.get_current_account() == {"email": "test@example.com"}
    mock_sdk.users_get_current_account.assert_called_once()

    # 3. download_file
    mock_sdk.files_download.return_value = ("metadata-val", "file-content-val")
    meta, content = client.download_file("/path/to/file.txt")
    assert meta == "metadata-val"
    assert content == "file-content-val"
    mock_sdk.files_download.assert_called_once_with("/path/to/file.txt")

    # 4. list_files
    mock_sdk.files_list_folder.return_value = {"entries": []}
    assert client.list_files("/folder") == {"entries": []}
    mock_sdk.files_list_folder.assert_called_once_with("/folder")

    # 5. list_files_continue
    mock_sdk.files_list_folder_continue.return_value = {"entries": []}
    assert client.list_files_continue("cursor123") == {"entries": []}
    mock_sdk.files_list_folder_continue.assert_called_once_with("cursor123")

    # 6. upload_file
    mock_sdk.files_upload.return_value = {"name": "uploaded.txt"}
    assert client.upload_file(b"data", "/path/uploaded.txt") == {"name": "uploaded.txt"}
    mock_sdk.files_upload.assert_called_once_with(b"data", path="/path/uploaded.txt")


def test_dropbox_auth_client_lazy_loading() -> None:
    """Test DropboxAuthClient lazy loading RuntimeError when dependency is missing."""
    settings = DropboxAppSettings(app_key="key", app_secret="secret")
    auth_client = DropboxAuthClient(settings)

    with (
        patch("builtins.__import__", side_effect=ModuleNotFoundError("No module named 'dropbox'")),
        pytest.raises(RuntimeError, match="Dropbox dependency not installed"),
    ):
        auth_client.start_oauth_flow()


@patch("dropbox.DropboxOAuth2FlowNoRedirect")
def test_dropbox_auth_client_flow(mock_flow_cls: MagicMock) -> None:
    """Test DropboxAuthClient OAuth flow initialization and code exchanging."""
    mock_flow = MagicMock()
    mock_flow.start.return_value = "https://authorize-url.com"
    mock_flow_cls.return_value = mock_flow

    settings = DropboxAppSettings(app_key="key", app_secret="secret")
    auth_client = DropboxAuthClient(settings)

    flow, url = auth_client.start_oauth_flow()
    assert flow is mock_flow
    assert url == "https://authorize-url.com"
    mock_flow_cls.assert_called_once_with(
        "key",
        "secret",
        scope=list(DropboxAuthClient.DEFAULT_SCOPES),
        token_access_type="offline",
    )

    # Test exchange_auth_code
    mock_oauth_result = MagicMock()
    mock_oauth_result.refresh_token = "new-refresh-token"
    mock_flow.finish.return_value = mock_oauth_result

    token = DropboxAuthClient.exchange_auth_code(mock_flow, "auth-code-123")
    assert token == "new-refresh-token"
    mock_flow.finish.assert_called_once_with("auth-code-123")

    # Test exchange_auth_code handles missing refresh token
    mock_oauth_result.refresh_token = None
    with pytest.raises(ValueError, match="Dropbox did not return a refresh token"):
        DropboxAuthClient.exchange_auth_code(mock_flow, "auth-code-123")


def test_dropbox_secret_client_lazy_loading() -> None:
    """Test DropboxSecretClient lazy loading RuntimeError when dependency is missing."""
    settings = DropboxSecretSettings(project_id="proj", secret_id="sec")
    secret_client = DropboxSecretClient(settings)

    with (
        patch("builtins.__import__", side_effect=ModuleNotFoundError("No module named 'google'")),
        pytest.raises(RuntimeError, match="Google Secret Manager dependency not installed"),
    ):
        secret_client._get_client()


def test_dropbox_secret_client_operations() -> None:
    """Test Secret Manager access and version adding methods on DropboxSecretClient."""
    mock_sm = MagicMock()
    settings = DropboxSecretSettings(project_id="project-id", secret_id="secret-id")
    secret_client = DropboxSecretClient(settings, client=mock_sm)

    # 1. get_refresh_token success
    mock_response = MagicMock()
    mock_response.payload.data = b"my-refreshed-token"
    mock_sm.access_secret_version.return_value = mock_response

    token = secret_client.get_refresh_token()
    assert token == "my-refreshed-token"
    mock_sm.access_secret_version.assert_called_once_with(
        request={"name": "projects/project-id/secrets/secret-id/versions/latest"}
    )

    # 2. get_refresh_token exception handled gracefully
    mock_sm.access_secret_version.side_effect = Exception("API Error")
    assert secret_client.get_refresh_token() is None

    # 3. add_refresh_token_version
    mock_sm.access_secret_version.side_effect = None
    mock_add_response = MagicMock()
    mock_add_response.name = "projects/project-id/secrets/secret-id/versions/5"
    mock_sm.add_secret_version.return_value = mock_add_response

    version_name = secret_client.add_refresh_token_version("new-token")
    assert version_name == "projects/project-id/secrets/secret-id/versions/5"
    mock_sm.add_secret_version.assert_called_once_with(
        request={
            "parent": "projects/project-id/secrets/secret-id",
            "payload": {"data": b"new-token"},
        }
    )
