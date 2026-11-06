"""dropbox-python client."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .client import (
    DropboxAppSettings,
    DropboxAuthClient,
    DropboxClient,
    DropboxSecretClient,
    DropboxSecretSettings,
    DropboxSettings,
)
from .exceptions import (
    DropboxAPIError,
    DropboxConfigurationError,
    DropboxError,
    DropboxFileNotFoundError,
)

try:
    __version__ = version("dropbox-python")
except PackageNotFoundError:  # pragma: no cover — editable install without metadata
    __version__ = "0.1.0"

__all__ = [
    "DropboxAPIError",
    "DropboxAppSettings",
    "DropboxAuthClient",
    "DropboxClient",
    "DropboxConfigurationError",
    "DropboxError",
    "DropboxFileNotFoundError",
    "DropboxSecretClient",
    "DropboxSecretSettings",
    "DropboxSettings",
    "__version__",
]
