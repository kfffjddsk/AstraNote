"""Click-based CLI for AstraNotes.

Commands : add, get, list, update, delete, reencrypt
           search, export
           register, login, logout, delete-account
           config set/get/list/reset
           audit
Global   : --data-dir (validated: must exist or be creatable, must be writable)
           ASTRANOTES_DATA_DIR env var as fallback; default is ~/.astranotes

Design notes:
- All string inputs are checked for null bytes and control characters at this
  boundary before reaching any lower layer.  [BL B-52]
- Non-zero exit codes (sys.exit(1)) on every error path.  [BL B-23]
- Passphrase is prompted with hide_input + confirmation on encrypt.  [BL B-32]
- --data-dir is validated for existence, type, and write permission.  [BL B-36]
- File-system / permission errors produce friendly messages.  [BL B-39]
- Plugin auto-discovery runs at startup from the ``plugins/`` directory.  [BL B-37]
- Plugin override policy: red warning + CONFIRM OVERRIDE required.  [BL B-24]
- Plugin allowlist: only plugins in config allowed_plugins list loaded.  [BL B-69]
- Plugin CLI commands wired into main CLI after discovery.  [BL B-28]
- Auth credentials NEVER accepted as positional CLI arguments; always prompted
  interactively with hide_input=True.  [BL B-57] [REQ R13.1]
- DATABASE_URL is never stored in any config file; only from os.environ.
  [BL B-64] [REQ R9.6]
- ANSI escape sequences and control codes stripped from note output.  [BL B-54]
- Output file paths normalized to prevent path traversal.  [BL B-55]
- AuditLogger integrated into all security-relevant operations.  [BL B-25, B-71]
- Passphrase held in memory as Python str; not zeroizable (documented
  limitation).  [BL B-73] [REQ R2.15]
- Encrypted-note alias stored unencrypted — info message shown.  [BL B-79]

Refs: [BL B-19, B-23, B-24, B-25, B-28, B-29, B-30, B-32, B-36, B-37, B-39,
       B-41, B-46, B-52, B-54, B-55, B-57, B-59, B-61, B-62, B-69, B-71,
       B-73, B-76, B-78, B-79]
      [REQ R1, R2, R7, R8, R9, R10, R13, R15] [US-1, US-2, US-4-11, US-13]
"""
from __future__ import annotations

import json
import logging
import re
import shutil
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import click
from cryptography.exceptions import InvalidTag

from src.core.audit import AuditLogger
from src.core.auth import (
    AccountStore,
    AuthError,
    RateLimitError,
    SessionManager,
    validate_username,
)
from src.core.blob_codec import BlobCodec
from src.core.config import ConfigStore
from src.core.notes import DatabaseStore, DiskFullError, Note
from src.core.plugin_base import PluginBase, PluginRegistry, discover_plugins
from src.core.security import KeyManager

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ANSI / control-code stripping  [BL B-54] [REQ R15.5]
# ---------------------------------------------------------------------------

_ANSI_ESC_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b[^\x1b]")


def _strip_ansi(text: str) -> str:
    """Strip ANSI escape codes and remaining non-printable control codes.

    Keeps horizontal tab, line feed, and carriage return.
    [BL B-54] [REQ R15.5]
    """
    text = _ANSI_ESC_RE.sub("", text)
    return "".join(ch for ch in text if ord(ch) >= 0x20 or ch in "\t\n\r")


# ---------------------------------------------------------------------------
# File-permission helper  [BL B-78] [REQ R10.7]
# ---------------------------------------------------------------------------


def _set_file_permissions(path: Path) -> None:
    """Restrict *path* to owner read/write only (0o600).

    Best-effort: Windows NTFS silently ignores POSIX chmod bits.
    [BL B-78] [REQ R10.7]
    """
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass

# ---------------------------------------------------------------------------
# Input-validation helpers  [BL B-52]
# ---------------------------------------------------------------------------

# Control characters forbidden in all fields: 0x00–0x1F + 0x7F (DEL).
# Content additionally permits \t (0x09), \n (0x0A), \r (0x0D) for multi-line notes.
_FORBIDDEN_ALL: frozenset[int] = frozenset(range(0x00, 0x20)) | {0x7F}
_ALLOWED_IN_CONTENT: frozenset[int] = {0x09, 0x0A, 0x0D}   # tab, LF, CR
_FORBIDDEN_CONTENT: frozenset[int] = _FORBIDDEN_ALL - _ALLOWED_IN_CONTENT


def _check_title(value: str, field: str = "title") -> None:
    """Raise :exc:`click.UsageError` if *value* contains forbidden characters."""
    for ch in value:
        cp = ord(ch)
        if cp in _FORBIDDEN_ALL:
            raise click.UsageError(
                f"{field!r} must not contain null bytes or control characters "
                f"(found U+{cp:04X})."
            )


def _check_content(value: str) -> None:
    """Raise :exc:`click.UsageError` if *value* contains forbidden characters."""
    for ch in value:
        cp = ord(ch)
        if cp in _FORBIDDEN_CONTENT:
            raise click.UsageError(
                f"content must not contain null bytes or control characters "
                f"(found U+{cp:04X})."
            )


# ---------------------------------------------------------------------------
# --data-dir validation callback  [BL B-36]
# ---------------------------------------------------------------------------


def _validate_data_dir(
    ctx: click.Context,
    param: click.Parameter,
    value: Optional[str],
) -> Path:
    """Resolve the data directory, create it if necessary, and verify write access."""
    resolved = Path(value).resolve() if value else Path.home() / ".astranotes"

    # Attempt to create the directory (parents allowed).
    try:
        resolved.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        raise click.BadParameter(
            f"cannot create {str(resolved)!r}: permission denied."
        )
    except OSError as exc:
        raise click.BadParameter(f"cannot create {str(resolved)!r}: {exc}.")

    if not resolved.is_dir():
        raise click.BadParameter(
            f"{str(resolved)!r} exists but is not a directory."
        )

    # Write-access probe — create and immediately remove a temporary marker.
    probe = resolved / ".write_probe"
    try:
        probe.touch()
        probe.unlink()
    except PermissionError:
        raise click.BadParameter(
            f"directory {str(resolved)!r} is not writable."
        )

    return resolved


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------


@click.group()
@click.option(
    "--data-dir",
    default=None,
    envvar="ASTRANOTES_DATA_DIR",
    callback=_validate_data_dir,
    is_eager=True,
    expose_value=True,
    help="Directory for notes.db.  Defaults to ~/.astranotes.",
)
@click.pass_context
def cli(ctx: click.Context, data_dir: Path) -> None:
    """AstraNotes — encrypted personal note manager."""
    ctx.ensure_object(dict)
    ctx.obj["data_dir"] = data_dir
    ctx.obj["store"] = DatabaseStore(data_dir)

    # Audit logger available to all commands.  [BL B-25, B-71]
    audit = AuditLogger(data_dir)
    ctx.obj["audit"] = audit

    # Config (global OS-standard path).  [BL B-26] [REQ R9.1]
    config = ConfigStore()
    ctx.obj["config"] = config

    # Plugin discovery with override policy and allowlist.  [BL B-24, B-69]
    registry = PluginRegistry()
    plugin_dir = Path(__file__).parent.parent / "plugins"

    allowed_list = config.get("allowed_plugins") or []
    allowed_set: Optional[frozenset] = (
        frozenset(allowed_list) if allowed_list else None
    )

    def _override_check(plugin: PluginBase) -> bool:
        """Prompt for CONFIRM OVERRIDE before allowing an overriding plugin.

        [BL B-24] [REQ R7]
        """
        click.echo(
            click.style(
                f"\nWarning: plugin {plugin.name!r} declares overrides:"
                f" {plugin.overrides}",
                fg="red",
                bold=True,
            ),
            err=True,
        )
        click.echo(
            click.style(
                "Further action may damage notes or app "
                "— ensure you know what you are doing.",
                fg="red",
            ),
            err=True,
        )
        confirmation = click.prompt(
            "Type CONFIRM OVERRIDE to proceed (anything else cancels)"
        )
        approved = confirmation == "CONFIRM OVERRIDE"
        audit.log(
            "override",
            outcome="success" if approved else "failure",
            detail=f"plugin={plugin.name!r}, overrides={plugin.overrides!r}",
        )
        return approved

    discovered = discover_plugins(
        plugin_dir,
        registry,
        allowed_plugins=allowed_set,
        override_check_fn=_override_check,
    )

    # Wire plugin CLI commands into the main group.  [BL B-28] [REQ R4.4]
    for plugin in discovered:
        for cmd_name, cmd in plugin.get_commands().items():
            try:
                cli.add_command(cmd, cmd_name)
            except Exception:
                logger.warning(
                    "Failed to add command %r from plugin %r.",
                    cmd_name,
                    plugin.name,
                )
        audit.log(
            "plugin_load",
            outcome="success",
            detail=f"plugin={plugin.name!r}",
        )

    ctx.obj["registry"] = registry


# ---------------------------------------------------------------------------
# add  [BL B-19, B-32, B-52]
# ---------------------------------------------------------------------------


@cli.command("add")
@click.option("--title", "-t", required=True, help="Note title.")
@click.option(
    "--content", "-c", default=None,
    help="Note content.  Omit to read from stdin.",
)
@click.option(
    "--encrypt", "-e", is_flag=True, default=False,
    help="Encrypt the note with a passphrase.",
)
@click.option(
    "--alias", default=None,
    help=(
        "Plaintext alias for an encrypted note (stored unencrypted, visible "
        "without passphrase).  [BL B-79] [REQ R2.16]"
    ),
)
@click.pass_context
def add_cmd(
    ctx: click.Context,
    title: str,
    content: Optional[str],
    encrypt: bool,
    alias: Optional[str],
) -> None:
    """Add a new note to the store."""
    store: DatabaseStore = ctx.obj["store"]
    registry: PluginRegistry = ctx.obj["registry"]
    audit: AuditLogger = ctx.obj["audit"]

    # Input validation at CLI boundary.  [BL B-52]
    try:
        _check_title(title)
    except click.UsageError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if content is None:
        content = click.get_text_stream("stdin").read()

    try:
        _check_content(content)
    except click.UsageError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if alias is not None:
        try:
            _check_title(alias, field="alias")
        except click.UsageError as exc:
            click.echo(f"Error: {exc}", err=True)
            sys.exit(1)

    try:
        if encrypt:
            # Alias info: alias stored unencrypted.  [BL B-79] [REQ R2.16]
            if alias:
                click.echo(
                    "Note: alias is stored unencrypted and visible"
                    " without passphrase."
                )
                stored_title = alias
            else:
                stored_title = "[Encrypted Note]"

            # Prompt with confirmation so typos don't silently lock the note.  [BL B-32]
            # Passphrase held in memory as Python str; not zeroizable.  [BL B-73]
            passphrase = click.prompt(
                "Passphrase", hide_input=True, confirmation_prompt=True
            )
            km = KeyManager(passphrase)
            engine = km.get_engine()
            header = {"title": title, "format": "text/plain"}
            raw_blob = BlobCodec.encode(header, content.encode("utf-8"))
            encrypted_blob = BlobCodec.encrypt(raw_blob, engine)
            note = Note.create(
                stored_title, content, encrypted=True, blob=encrypted_blob
            )
            audit.log("encrypt", note_id=note.id, outcome="success")
        else:
            note = Note.create(title, content)

        # Associate with the active account if a valid session exists.  [BL B-47]
        data_dir: Path = ctx.obj["data_dir"]
        session_data = SessionManager.load(data_dir)
        account_id = session_data["account_id"] if session_data else None

        store.add(note, account_id=account_id)
        registry.call_hook("on_add", note)
        click.echo(note.id)

    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    except DiskFullError as exc:
        click.echo(f"Error: disk full — {exc}", err=True)
        sys.exit(1)
    except PermissionError as exc:
        click.echo(f"Error: permission denied — {exc}", err=True)
        sys.exit(1)
    except OSError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


@cli.command("get")
@click.argument("note_id")
@click.option(
    "--decrypt", "-d", is_flag=True, default=False,
    help="Decrypt and display the note's plaintext content.",
)
@click.pass_context
def get_cmd(ctx: click.Context, note_id: str, decrypt: bool) -> None:
    """Retrieve a note by ID."""
    store: DatabaseStore = ctx.obj["store"]
    audit: AuditLogger = ctx.obj["audit"]

    try:
        note = store.get(note_id)
    except PermissionError as exc:
        click.echo(f"Error: permission denied — {exc}", err=True)
        sys.exit(1)
    except OSError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if note is None:
        click.echo(f"Error: note {note_id!r} not found.", err=True)
        sys.exit(1)

    if note.encrypted and decrypt:
        passphrase = click.prompt("Passphrase", hide_input=True)
        try:
            engine = KeyManager(passphrase).get_engine()
            raw_blob = BlobCodec.decrypt(note.blob, engine)
            _, payload = BlobCodec.decode(raw_blob)
            click.echo(_strip_ansi(payload.decode("utf-8")))
            audit.log("decrypt", note_id=note_id, outcome="success")
        except InvalidTag:
            click.echo("Error: wrong passphrase or corrupted data.", err=True)
            audit.log("passphrase_attempt", note_id=note_id, outcome="failure")
            sys.exit(1)
        except ValueError as exc:
            click.echo(f"Error: {exc}", err=True)
            sys.exit(1)
    else:
        click.echo(f"ID:      {note.id}")
        click.echo(f"Title:   {_strip_ansi(note.title)}")
        click.echo(f"Content: {_strip_ansi(note.content or '[encrypted]')}")
        click.echo(f"Created: {note.created_at}")


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


@cli.command("list")
@click.pass_context
def list_cmd(ctx: click.Context) -> None:
    """List all notes (titles only)."""
    store: DatabaseStore = ctx.obj["store"]
    data_dir: Path = ctx.obj["data_dir"]

    # Load session to determine whether to show account sections.  [BL B-47]
    session_data = SessionManager.load(data_dir)
    account_id = session_data["account_id"] if session_data else None

    try:
        account_notes, local_notes = store.list(account_id)
    except PermissionError as exc:
        click.echo(f"Error: permission denied — {exc}", err=True)
        sys.exit(1)
    except OSError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if account_id:
        # Logged in: show two labelled sections.  [REQ R1.3] [BL B-47]
        if account_notes:
            click.echo("Your Notes:")
            for note in account_notes:
                enc_marker = " [enc]" if note.encrypted else ""
                click.echo(f"  {note.id}  {_strip_ansi(note.title)}{enc_marker}")
        else:
            click.echo("Your Notes: (none)")

        if local_notes:
            click.echo("Local Open Notes:")
            for note in local_notes:
                enc_marker = " [enc]" if note.encrypted else ""
                click.echo(f"  {note.id}  {_strip_ansi(note.title)}{enc_marker}")
        else:
            click.echo("Local Open Notes: (none)")
    else:
        # Logged out: flat list (backward-compatible).
        if not local_notes:
            click.echo("No notes found.")
            return
        for note in local_notes:
            enc_marker = " [enc]" if note.encrypted else ""
            click.echo(f"{note.id}  {_strip_ansi(note.title)}{enc_marker}")


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


@cli.command("update")
@click.argument("note_id")
@click.option("--title", "-t", default=None, help="New title.")
@click.option("--content", "-c", default=None, help="New content.")
@click.pass_context
def update_cmd(
    ctx: click.Context,
    note_id: str,
    title: Optional[str],
    content: Optional[str],
) -> None:
    """Update a note's title and/or content."""
    store: DatabaseStore = ctx.obj["store"]

    if title is None and content is None:
        click.echo("Error: supply at least --title or --content.", err=True)
        sys.exit(1)

    try:
        if title is not None:
            _check_title(title)
        if content is not None:
            _check_content(content)
    except click.UsageError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    # Fetch note first to determine whether it is encrypted.  [REQ R2.4]
    try:
        note = store.get(note_id)
    except PermissionError as exc:
        click.echo(f"Error: permission denied — {exc}", err=True)
        sys.exit(1)
    except OSError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if note is None:
        click.echo(f"Error: note {note_id!r} not found.", err=True)
        sys.exit(1)

    blob: Optional[bytes] = None
    store_content: Optional[str] = content

    if note.encrypted and content is not None:
        # Re-encrypt with new content; passphrase required.  [REQ R2.4]
        passphrase = click.prompt("Passphrase", hide_input=True)
        try:
            engine = KeyManager(passphrase).get_engine()
            BlobCodec.decrypt(note.blob, engine)  # verify passphrase
            stored_title = title if title is not None else note.title
            header = {"title": stored_title, "format": "text/plain"}
            raw_blob = BlobCodec.encode(header, content.encode("utf-8"))
            blob = BlobCodec.encrypt(raw_blob, engine)
        except InvalidTag:
            click.echo("Error: wrong passphrase or corrupted data.", err=True)
            sys.exit(1)
        except ValueError as exc:
            click.echo(f"Error: {exc}", err=True)
            sys.exit(1)
        store_content = None  # content is inside the new blob

    try:
        updated = store.update(note_id, title=title, content=store_content, blob=blob)
        click.echo(f"Updated: {updated.id}")
    except KeyError:
        click.echo(f"Error: note {note_id!r} not found.", err=True)
        sys.exit(1)
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    except DiskFullError as exc:
        click.echo(f"Error: disk full — {exc}", err=True)
        sys.exit(1)
    except PermissionError as exc:
        click.echo(f"Error: permission denied — {exc}", err=True)
        sys.exit(1)
    except OSError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


@cli.command("delete")
@click.argument("note_id")
@click.pass_context
def delete_cmd(ctx: click.Context, note_id: str) -> None:
    """Delete a note by ID."""
    store: DatabaseStore = ctx.obj["store"]

    # Fetch first to check encryption status before prompting.  [REQ R2.5]
    try:
        note = store.get(note_id)
    except PermissionError as exc:
        click.echo(f"Error: permission denied — {exc}", err=True)
        sys.exit(1)
    except OSError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if note is None:
        click.echo(f"Error: note {note_id!r} not found.", err=True)
        sys.exit(1)

    if note.encrypted:
        passphrase = click.prompt("Passphrase", hide_input=True)
        try:
            engine = KeyManager(passphrase).get_engine()
            BlobCodec.decrypt(note.blob, engine)
        except InvalidTag:
            click.echo("Error: wrong passphrase or corrupted data.", err=True)
            sys.exit(1)
        except ValueError as exc:
            click.echo(f"Error: {exc}", err=True)
            sys.exit(1)

    try:
        store.delete(note_id)
        click.echo(f"Deleted: {note_id}")
    except KeyError:
        click.echo(f"Error: note {note_id!r} not found.", err=True)
        sys.exit(1)
    except PermissionError as exc:
        click.echo(f"Error: permission denied — {exc}", err=True)
        sys.exit(1)
    except OSError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# register  [BL B-45, B-57, B-60] [REQ R13.1–R13.4]
# ---------------------------------------------------------------------------


@cli.command("register")
@click.pass_context
def register_cmd(ctx: click.Context) -> None:
    """Create a new local account (optional — app works without one)."""
    data_dir: Path = ctx.obj["data_dir"]
    audit: AuditLogger = ctx.obj["audit"]
    account_store = AccountStore(data_dir)

    # Credentials always prompted interactively; NEVER accepted as args.  [BL B-57]
    username = click.prompt("Username")
    try:
        validate_username(username)
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    password = click.prompt("Password", hide_input=True, confirmation_prompt=True)

    try:
        account_id = account_store.register(username, password)
        click.echo(f"Account created: {username} ({account_id})")
        audit.log("register", outcome="success", detail=f"username={username!r}")
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        audit.log("register", outcome="failure", detail=f"username={username!r}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# login  [BL B-46, B-57, B-58, B-59] [REQ R13.5–R13.8]
# ---------------------------------------------------------------------------


@cli.command("login")
@click.pass_context
def login_cmd(ctx: click.Context) -> None:
    """Log in to a local account and create a session token (24 h)."""
    data_dir: Path = ctx.obj["data_dir"]
    store: DatabaseStore = ctx.obj["store"]
    audit: AuditLogger = ctx.obj["audit"]
    account_store = AccountStore(data_dir)

    username = click.prompt("Username")
    password = click.prompt("Password", hide_input=True)  # [BL B-57]

    try:
        account = account_store.authenticate(username, password)
    except RateLimitError as exc:
        click.echo(f"Error: {exc}", err=True)
        audit.log("login", outcome="failure",
                  detail=f"username={username!r}, reason=rate_limited")
        sys.exit(1)
    except AuthError as exc:
        click.echo(f"Error: {exc}", err=True)
        audit.log("login", outcome="failure",
                  detail=f"username={username!r}, reason=auth_error")
        sys.exit(1)

    SessionManager.create(data_dir, account["account_id"], account["username"])
    click.echo(f"Logged in as {account['username']}.")
    audit.log("login", outcome="success",
              detail=f"username={account['username']!r}")

    # --- First-login anonymous note association prompt  [BL B-41] [REQ R12.3] ---
    _, anon_notes = store.list(account_id=None)
    if anon_notes:
        click.echo(
            f"\nYou have {len(anon_notes)} local note(s) with no account.\n"
            "Associate them with your account?"
        )
        choice = click.prompt(
            "[yes / no / ask]",
            default="no",
            type=click.Choice(["yes", "no", "ask"], case_sensitive=False),
        )

        if choice == "yes":
            count = store.associate_anonymous_notes(account["account_id"])
            click.echo(f"Associated {count} note(s) with your account.")
        elif choice == "ask":
            associated = 0
            for note in anon_notes:
                enc_marker = " [enc]" if note.encrypted else ""
                if click.confirm(f"  Associate '{note.title}{enc_marker}'?", default=False):
                    store.set_note_account_id(note.id, account["account_id"])
                    associated += 1
            click.echo(f"Associated {associated} note(s) with your account.")
        else:
            click.echo("Local notes left unchanged.")


# ---------------------------------------------------------------------------
# logout  [BL B-46] [REQ R13.9]
# ---------------------------------------------------------------------------


@cli.command("logout")
@click.pass_context
def logout_cmd(ctx: click.Context) -> None:
    """End the current session (local notes remain accessible)."""
    data_dir: Path = ctx.obj["data_dir"]
    audit: AuditLogger = ctx.obj["audit"]
    removed = SessionManager.delete(data_dir)
    if removed:
        click.echo("Logged out.")
        audit.log("logout", outcome="success")
    else:
        click.echo("No active session.")


# ---------------------------------------------------------------------------
# delete-account  [BL B-61, B-81] [REQ R13.12]
# ---------------------------------------------------------------------------


@cli.command("delete-account")
@click.pass_context
def delete_account_cmd(ctx: click.Context) -> None:
    """Permanently delete account; local notes kept but disassociated."""
    data_dir: Path = ctx.obj["data_dir"]
    store: DatabaseStore = ctx.obj["store"]

    session_data = SessionManager.load(data_dir)
    if not session_data:
        click.echo("Error: not logged in.", err=True)
        sys.exit(1)

    account_id = session_data["account_id"]
    username = session_data["username"]

    click.echo(
        f"This will permanently delete account '{username}'.\n"
        "Local notes will be kept but disassociated from your account.\n"
        "Any cloud copies will also be deleted."
    )

    # Require password + typed confirmation.  [REQ R13.12]
    password = click.prompt("Confirm your password", hide_input=True)
    account_store = AccountStore(data_dir)
    try:
        account_store.authenticate(username, password)
    except (AuthError, RateLimitError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    confirmation = click.prompt('Type "CONFIRM DELETE ACCOUNT" to proceed')
    if confirmation != "CONFIRM DELETE ACCOUNT":
        click.echo("Aborted — confirmation text did not match.")
        sys.exit(1)

    # Detach all notes from this account.  [REQ R13.12]
    affected = store.disassociate_account(account_id)

    # Delete account record.
    account_store.delete(account_id)

    # Delete session file.
    SessionManager.delete(data_dir)

    # Delete per-user audit log if it exists.  [BL B-81]
    audit_log = data_dir / "audit.log"
    if audit_log.exists():
        audit_log.unlink()

    click.echo(
        f"Account '{username}' deleted. "
        f"{affected} note(s) are now anonymous local notes."
    )


# ---------------------------------------------------------------------------
# reencrypt  [BL B-62] [REQ R2.14]
# ---------------------------------------------------------------------------


@cli.command("reencrypt")
@click.argument("note_id")
@click.pass_context
def reencrypt_cmd(ctx: click.Context, note_id: str) -> None:
    """Re-encrypt a note with a new passphrase.  [BL B-62] [REQ R2.14]

    Passphrase held in memory as Python str; not zeroizable.  [BL B-73]
    """
    store: DatabaseStore = ctx.obj["store"]
    audit: AuditLogger = ctx.obj["audit"]

    try:
        note = store.get(note_id)
    except (PermissionError, OSError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if note is None:
        click.echo(f"Error: note {note_id!r} not found.", err=True)
        sys.exit(1)

    if not note.encrypted:
        click.echo("Error: note is not encrypted.", err=True)
        sys.exit(1)

    if note.blob is None:
        click.echo("Error: encrypted note has no content.", err=True)
        sys.exit(1)

    # Verify old passphrase.
    old_passphrase = click.prompt("Current passphrase", hide_input=True)
    try:
        old_engine = KeyManager(old_passphrase).get_engine()
        raw_blob = BlobCodec.decrypt(note.blob, old_engine)
    except InvalidTag:
        click.echo("Error: wrong passphrase or corrupted data.", err=True)
        audit.log("passphrase_attempt", note_id=note_id, outcome="failure",
                  detail="reencrypt")
        sys.exit(1)
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    audit.log("passphrase_attempt", note_id=note_id, outcome="success",
              detail="reencrypt-verify")

    # Get new passphrase (confirmed).
    try:
        new_passphrase = click.prompt(
            "New passphrase", hide_input=True, confirmation_prompt=True
        )
        new_engine = KeyManager(new_passphrase).get_engine()
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    new_blob = BlobCodec.encrypt(raw_blob, new_engine)

    try:
        store.update(note_id, blob=new_blob)
        click.echo(f"Re-encrypted: {note_id}")
        audit.log("reencrypt", note_id=note_id, outcome="success")
    except KeyError:
        click.echo(f"Error: note {note_id!r} not found.", err=True)
        sys.exit(1)
    except DiskFullError as exc:
        click.echo(f"Error: disk full — {exc}", err=True)
        sys.exit(1)
    except (PermissionError, OSError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# search  [BL B-29] [REQ R10.1–R10.3]
# ---------------------------------------------------------------------------


@cli.command("search")
@click.argument("query")
@click.pass_context
def search_cmd(ctx: click.Context, query: str) -> None:
    """Search notes by title and content.  [BL B-29] [REQ R10.1, R10.2]

    Plain notes are matched by title and content.
    Encrypted notes are matched by alias title only; content is never exposed.
    """
    store: DatabaseStore = ctx.obj["store"]
    audit: AuditLogger = ctx.obj["audit"]
    data_dir: Path = ctx.obj["data_dir"]

    try:
        _check_title(query, field="query")
    except click.UsageError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    session_data = SessionManager.load(data_dir)
    account_id = session_data["account_id"] if session_data else None

    results = store.search(query, account_id=account_id)

    if not results:
        click.echo("No notes found.")
        return

    audit.log("search", outcome="success", detail=f"query={query!r}")

    for note in results:
        click.echo(f"{note.id}  {_strip_ansi(note.title)}")
        if not note.encrypted:
            preview = _strip_ansi(note.content or "")[:80]
            if preview:
                click.echo(f"    {preview}")


# ---------------------------------------------------------------------------
# export  [BL B-30, B-76, B-78] [REQ R10.4–R10.7]
# ---------------------------------------------------------------------------


@cli.command("export")
@click.option(
    "--format", "fmt",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format: text (default) or json.",
)
@click.option(
    "--output", "-o", default=None,
    help="Output file path.  Default: <data-dir>/export.<format>.",
)
@click.option(
    "--encrypted", "-e", is_flag=True, default=False,
    help="Decrypt all encrypted notes for export (prompts passphrase once).",
)
@click.option(
    "--cleanup", is_flag=True, default=False,
    help="Purge the exports directory (<data-dir>/exports/) then exit.",
)
@click.pass_context
def export_cmd(
    ctx: click.Context,
    fmt: str,
    output: Optional[str],
    encrypted: bool,
    cleanup: bool,
) -> None:
    """Export notes to text or JSON.  [BL B-30, B-76, B-78] [REQ R10.4–R10.7]"""
    data_dir: Path = ctx.obj["data_dir"]
    audit: AuditLogger = ctx.obj["audit"]
    store: DatabaseStore = ctx.obj["store"]

    # --cleanup: purge exports directory.  [REQ R10.7]
    if cleanup:
        exports_dir = data_dir / "exports"
        if exports_dir.exists():
            shutil.rmtree(exports_dir)
        click.echo("Exports directory purged.")
        return

    # Resolve output path.  [BL B-55]
    if output is not None:
        if "\x00" in output:
            click.echo("Error: output path contains null bytes.", err=True)
            sys.exit(1)
        out_path = Path(output).resolve()
    else:
        out_path = data_dir / f"export.{fmt}"

    passphrase: Optional[str] = None
    if encrypted:
        passphrase = click.prompt(
            "Passphrase for encrypted notes", hide_input=True
        )
        click.echo(
            "Warning: decrypted data written to disk "
            "— run `export --cleanup` when done."
        )

    session_data = SessionManager.load(data_dir)
    account_id = session_data["account_id"] if session_data else None
    account_notes, local_notes = store.list(account_id)
    all_notes = account_notes + local_notes

    if not all_notes:
        click.echo("No notes to export.")
        return

    exports_dir = data_dir / "exports"
    export_rows: list[dict] = []

    for note in all_notes:
        if note.encrypted:
            full_note = store.get(note.id)
            if passphrase and full_note and full_note.blob:
                try:
                    engine = KeyManager(passphrase).get_engine()
                    raw_blob = BlobCodec.decrypt(full_note.blob, engine)
                    header, payload = BlobCodec.decode(raw_blob)
                    try:
                        text_content = payload.decode("utf-8")
                        export_rows.append({
                            "id": note.id,
                            "title": header.get("title", note.title),
                            "content": _strip_ansi(text_content),
                            "created_at": note.created_at,
                            "modified_at": note.modified_at,
                            "format": header.get("format", "text/plain"),
                        })
                        audit.log("decrypt", note_id=note.id, outcome="success",
                                  detail="export")
                    except UnicodeDecodeError:
                        # Binary payload — write to exports dir.  [BL B-76]
                        exports_dir.mkdir(exist_ok=True)
                        fname = Path(
                            header.get("original_filename", f"{note.id}.bin")
                        ).name
                        payload_path = exports_dir / fname
                        payload_path.write_bytes(payload)
                        _set_file_permissions(payload_path)
                        export_rows.append({
                            "id": note.id,
                            "title": header.get("title", note.title),
                            "content": f"[binary payload: {payload_path}]",
                            "created_at": note.created_at,
                            "modified_at": note.modified_at,
                        })
                except (InvalidTag, ValueError):
                    export_rows.append({
                        "id": note.id,
                        "title": note.title,
                        "content": "[Encrypted Note]",
                        "created_at": note.created_at,
                        "modified_at": note.modified_at,
                    })
            else:
                export_rows.append({
                    "id": note.id,
                    "title": note.title,
                    "content": "[Encrypted Note]",
                    "created_at": note.created_at,
                    "modified_at": note.modified_at,
                })
        else:
            full_note = store.get(note.id)
            plain_content = _strip_ansi(
                (full_note.content if full_note and full_note.content else note.content) or ""
            )
            export_rows.append({
                "id": note.id,
                "title": note.title,
                "content": plain_content,
                "created_at": note.created_at,
                "modified_at": note.modified_at,
                "format": "text/plain",
            })

    try:
        if fmt == "json":
            out_path.write_text(
                json.dumps(export_rows, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        else:
            lines: list[str] = []
            for row in export_rows:
                lines.append(f"Note ID: {row['id']}")
                lines.append(f"Title: {row['title']}")
                lines.append(f"Content: {row['content']}")
                lines.append(f"Created: {row.get('created_at', '')}")
                lines.append(f"Modified: {row.get('modified_at', '')}")
                lines.append("---")
            out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        # Restrict permissions to owner only.  [BL B-78] [REQ R10.7]
        _set_file_permissions(out_path)

        click.echo(f"Exported {len(export_rows)} note(s) to {out_path}.")
        audit.log(
            "export",
            outcome="success",
            detail=f"format={fmt!r}, count={len(export_rows)}",
        )

    except PermissionError as exc:
        click.echo(f"Error: permission denied — {exc}", err=True)
        sys.exit(1)
    except OSError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# config group  [BL B-26] [REQ R9]
# ---------------------------------------------------------------------------


@cli.group("config")
def config_grp() -> None:
    """Manage AstraNotes settings.  [BL B-26] [REQ R9]"""


@config_grp.command("set")
@click.argument("key")
@click.argument("value")
def config_set_cmd(key: str, value: str) -> None:
    """Set a configuration key to value."""
    store = ConfigStore()
    try:
        store.set(key, value)
        click.echo(f"Set {key} = {store.get(key)!r}")
    except (KeyError, ValueError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


@config_grp.command("get")
@click.argument("key")
def config_get_cmd(key: str) -> None:
    """Print the current value of a configuration key."""
    store = ConfigStore()
    try:
        value = store.get(key)
        click.echo(f"{key} = {value!r}")
    except KeyError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


@config_grp.command("list")
def config_list_cmd() -> None:
    """List all configuration keys and their current values."""
    store = ConfigStore()
    for k, v in store.list_all().items():
        click.echo(f"{k} = {v!r}")


@config_grp.command("reset")
@click.argument("key")
def config_reset_cmd(key: str) -> None:
    """Reset a configuration key to its default value."""
    store = ConfigStore()
    try:
        store.reset(key)
        default = store.get(key)
        click.echo(f"Reset {key} to default ({default!r}).")
    except KeyError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# audit  [BL B-25, B-71] [REQ R8.5]
# ---------------------------------------------------------------------------


@cli.command("audit")
@click.option(
    "--limit", "-n", type=int, default=None,
    help="Show only the last N entries.",
)
@click.option(
    "--operation", "-o", default=None,
    help="Filter by operation type (e.g. login, encrypt, export).",
)
@click.option(
    "--since", "-s", default=None,
    help="Show entries from this date/time onward (ISO 8601, e.g. 2026-05-01).",
)
@click.pass_context
def audit_cmd(
    ctx: click.Context,
    limit: Optional[int],
    operation: Optional[str],
    since: Optional[str],
) -> None:
    """Show audit log entries.  [BL B-25, B-71] [REQ R8.5]"""
    data_dir: Path = ctx.obj["data_dir"]
    audit_logger = AuditLogger(data_dir)

    since_dt: Optional[datetime] = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
            if since_dt.tzinfo is None:
                since_dt = since_dt.replace(tzinfo=timezone.utc)
        except ValueError:
            click.echo(
                f"Error: invalid date format {since!r}. "
                "Use ISO 8601 (e.g. 2026-05-01 or 2026-05-01T12:00:00).",
                err=True,
            )
            sys.exit(1)

    entries = audit_logger.read(limit=limit, operation=operation, since=since_dt)

    if not entries:
        click.echo("No audit entries found.")
        return

    for entry in entries:
        ts = entry.get("timestamp", "")
        op = entry.get("operation", "")
        outcome = entry.get("outcome", "")
        note_id = entry.get("note_id") or ""
        detail = entry.get("detail") or ""
        parts = [f"[{ts}]", op, outcome]
        if note_id:
            parts.append(f"note={note_id}")
        if detail:
            parts.append(detail)
        click.echo("  ".join(parts))


# ---------------------------------------------------------------------------
# gui  [BL B-84] [REQ R11] [US-9]
# ---------------------------------------------------------------------------


@cli.command("gui")
@click.pass_context
def gui_cmd(ctx: click.Context) -> None:
    """Launch the AstraNotes desktop GUI.  [BL B-84]"""
    from src.desktop.app_controller import AppController

    data_dir = None
    if ctx.obj and ctx.obj.get("store"):
        # Reuse the data_dir resolved during CLI startup
        store = ctx.obj["store"]
        if hasattr(store, "_data_dir"):
            data_dir = store._data_dir

    controller = AppController(data_dir=data_dir)
    exit_code = controller.run()
    if exit_code != 0:
        raise SystemExit(exit_code)


if __name__ == "__main__":  # pragma: no cover
    cli()
