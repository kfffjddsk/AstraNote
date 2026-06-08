"""Sync-related desktop UI: background worker, merge dialog, account dialog.

Public API re-exported for convenient imports:

    from src.desktop.sync import SyncWorker, MergeWindow, SyncLoginDialog
"""
from src.desktop.sync.worker import SyncWorker  # noqa: F401
from src.desktop.sync.merge_window import MergeWindow  # noqa: F401
from src.desktop.sync.account_dialog import (  # noqa: F401
    SyncLoginDialog,
    _OAuthCallbackHandler,
    _OAuthCallbackServer,
    _GOOGLE_AUTH_URL,
    _GOOGLE_SCOPE,
)
