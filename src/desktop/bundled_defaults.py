"""Build-time patchable credential defaults.

These fields are empty in the source repository.  At build time (for example
when packaging with PyInstaller) patch this file to embed your Google OAuth
credentials so users do not need to configure them manually.

Override order (highest priority first):
  1. ``config.json``  ``google_client_id`` / ``google_client_secret``
  2. Environment variables ``ASTRANOTES_GOOGLE_CLIENT_ID`` / ``ASTRANOTES_GOOGLE_CLIENT_SECRET``
  3. These bundled defaults (set at build time)
"""

GOOGLE_CLIENT_ID: str = ""
GOOGLE_CLIENT_SECRET: str = ""
