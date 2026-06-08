"""Dropbox domain exceptions."""

from __future__ import annotations


class DropboxError(Exception):
    """Base exception for dropbox module."""


class DropboxConfigurationError(DropboxError):
    """Raised when Dropbox client configuration is missing or invalid."""


class DropboxAPIError(DropboxError):
    """Raised when Dropbox API request fails."""


class DropboxFileNotFoundError(DropboxError):
    """Raised when a Dropbox file is not found."""
