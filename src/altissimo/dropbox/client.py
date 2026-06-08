"""Dropbox API client."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DropboxAppSettings:
    """Dropbox app settings."""

    app_key: str
    app_secret: str

    @classmethod
    def from_env(cls) -> DropboxAppSettings:
        """Build Dropbox app settings from environment."""
        app_key = os.environ.get("DROPBOX_APP_KEY") or os.environ.get("DROPBOX_LMM_APP_KEY", "")
        app_secret = os.environ.get("DROPBOX_APP_SECRET") or os.environ.get("DROPBOX_LMM_APP_SECRET", "")

        if not app_key:
            raise ValueError("Neither DROPBOX_APP_KEY nor DROPBOX_LMM_APP_KEY is set")
        if not app_secret:
            raise ValueError("Neither DROPBOX_APP_SECRET nor DROPBOX_LMM_APP_SECRET is set")
        return cls(app_key=app_key, app_secret=app_secret)


@dataclass(frozen=True)
class DropboxSettings:
    """Dropbox client settings."""

    app_key: str
    app_secret: str
    refresh_token: str

    @classmethod
    def from_env(cls) -> DropboxSettings:
        """Build Dropbox settings from environment."""
        app = DropboxAppSettings.from_env()
        refresh_token = os.environ.get("DROPBOX_REFRESH_TOKEN") or os.environ.get("DROPBOX_LMM_APP_REFRESH_TOKEN", "")
        if not refresh_token:
            raise ValueError("Neither DROPBOX_REFRESH_TOKEN nor DROPBOX_LMM_APP_REFRESH_TOKEN is set")
        return cls(
            app_key=app.app_key,
            app_secret=app.app_secret,
            refresh_token=refresh_token,
        )


class DropboxClient:
    """Thin Dropbox API wrapper."""

    def __init__(self, settings: DropboxSettings, client: Any = None) -> None:
        """Initialize the DropboxClient."""
        self._settings = settings
        self._client = client

    @classmethod
    def from_env(cls) -> DropboxClient:
        """Create Dropbox client from environment."""
        return cls(DropboxSettings.from_env())

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                import dropbox  # type: ignore[import-untyped]
            except ModuleNotFoundError as exc:
                raise RuntimeError(
                    "Dropbox dependency not installed. Install with `pip install dropbox-python[dropbox]`."
                ) from exc

            self._client = dropbox.Dropbox(
                app_key=self._settings.app_key,
                app_secret=self._settings.app_secret,
                oauth2_refresh_token=self._settings.refresh_token,
            )
        return self._client

    def get_raw_client(self) -> Any:
        """Expose raw Dropbox SDK client for compatibility paths."""
        return self._get_client()

    def get_current_account(self) -> Any:
        """Fetch current Dropbox account."""
        return self._get_client().users_get_current_account()

    def download_file(self, path: str) -> tuple[Any, Any]:
        """Download file from Dropbox path."""
        res = self._get_client().files_download(path)
        return res[0], res[1]

    def list_files(self, path: str) -> Any:
        """List file entries at Dropbox path."""
        return self._get_client().files_list_folder(path)

    def list_files_continue(self, cursor: str) -> Any:
        """Continue Dropbox listing with cursor."""
        return self._get_client().files_list_folder_continue(cursor)

    def upload_file(self, data: bytes, path: str) -> Any:
        """Upload file content to Dropbox path."""
        return self._get_client().files_upload(data, path=path)


class DropboxAuthClient:
    """Dropbox OAuth helper client."""

    DEFAULT_SCOPES = (
        "account_info.read",
        "files.content.read",
        "files.content.write",
    )

    def __init__(self, settings: DropboxAppSettings) -> None:
        """Initialize the DropboxAuthClient."""
        self._settings = settings

    @classmethod
    def from_env(cls) -> DropboxAuthClient:
        """Create auth client from environment."""
        return cls(DropboxAppSettings.from_env())

    def start_oauth_flow(self, scopes: list[str] | None = None) -> tuple[Any, str]:
        """Create OAuth no-redirect flow and return authorize URL."""
        try:
            from dropbox import DropboxOAuth2FlowNoRedirect
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Dropbox dependency not installed. Install with `pip install dropbox-python[dropbox]`."
            ) from exc

        flow = DropboxOAuth2FlowNoRedirect(
            self._settings.app_key,
            self._settings.app_secret,
            scope=scopes or list(self.DEFAULT_SCOPES),
            token_access_type="offline",  # noqa: S106
        )
        return flow, str(flow.start())

    @staticmethod
    def exchange_auth_code(flow: Any, auth_code: str) -> str:
        """Exchange authorization code for refresh token."""
        oauth_result = flow.finish(auth_code.strip())
        refresh_token = getattr(oauth_result, "refresh_token", None)
        if not refresh_token:
            raise ValueError("Dropbox did not return a refresh token")
        return str(refresh_token)


@dataclass(frozen=True)
class DropboxSecretSettings:
    """Secret Manager settings for Dropbox refresh token."""

    project_id: str
    secret_id: str = "dropbox-app-refresh-token"  # noqa: S105

    @classmethod
    def from_env(
        cls,
        *,
        project_id: str | None = None,
        secret_id: str | None = None,
    ) -> DropboxSecretSettings:
        """Build DropboxSecretSettings from environment variables."""
        resolved_project_id = (
            project_id
            or os.environ.get("GOOGLE_CLOUD_PROJECT")
            or os.environ.get("GCP_PROJECT")
            or os.environ.get("PROJECT_ID")
            or ""
        )
        if not resolved_project_id:
            raise ValueError("GOOGLE_CLOUD_PROJECT (or GCP_PROJECT/PROJECT_ID) is not set")

        resolved_secret_id = (
            secret_id
            or os.environ.get("DROPBOX_REFRESH_TOKEN_SECRET_ID")
            or os.environ.get("DROPBOX_LMM_REFRESH_TOKEN_SECRET_ID")
            or "dropbox-app-refresh-token"
        )

        return cls(project_id=resolved_project_id, secret_id=resolved_secret_id)


class DropboxSecretClient:
    """Secret Manager client for Dropbox refresh token."""

    def __init__(self, settings: DropboxSecretSettings, client: Any = None) -> None:
        """Initialize the DropboxSecretClient."""
        self._settings = settings
        self._client = client

    @classmethod
    def from_env(
        cls,
        *,
        project_id: str | None = None,
        secret_id: str | None = None,
    ) -> DropboxSecretClient:
        """Create Secret Manager client from environment."""
        return cls(
            DropboxSecretSettings.from_env(
                project_id=project_id,
                secret_id=secret_id,
            )
        )

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from google.cloud import secretmanager
            except ModuleNotFoundError as exc:
                raise RuntimeError(
                    "Google Secret Manager dependency not installed. Install with `pip install dropbox-python[gcp]`."
                ) from exc
            self._client = secretmanager.SecretManagerServiceClient()
        return self._client

    def _version_path(self, version: str = "latest") -> str:
        return f"projects/{self._settings.project_id}/secrets/{self._settings.secret_id}/versions/{version}"

    def _secret_parent(self) -> str:
        return f"projects/{self._settings.project_id}/secrets/{self._settings.secret_id}"

    def get_refresh_token(self) -> str | None:
        """Get latest refresh token value from Secret Manager."""
        try:
            response = self._get_client().access_secret_version(request={"name": self._version_path()})
        except Exception:
            return None
        return str(response.payload.data.decode("utf-8"))

    def add_refresh_token_version(self, refresh_token: str) -> str:
        """Store a new refresh token version and return version resource name."""
        response = self._get_client().add_secret_version(
            request={
                "parent": self._secret_parent(),
                "payload": {"data": refresh_token.encode("utf-8")},
            }
        )
        return str(response.name)
