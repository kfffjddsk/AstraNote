"""Click-based CLI for AstraNotes.

Commands : add, get, list, update, delete
           register, login, logout, delete-account
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
- Auth credentials NEVER accepted as positional CLI arguments; always prompted
  interactively with hide_input=True.  [BL B-57] [REQ R13.1]
- DATABASE_URL is never stored in any config file; only from os.environ.
  [BL B-64] [REQ R9.6]

Refs: [BL B-19, B-23, B-32, B-36, B-37, B-39, B-41, B-46, B-52, B-57, B-59, B-61]
      [REQ R1, R2, R13] [US-1, US-2, US-11]
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import click
from cryptography.exceptions import InvalidTag

from src.core.auth import AccountStore, AuthError, RateLimitError, SessionManager, validate_username
from src.core.blob_codec import BlobCodec
from src.core.notes import DatabaseStore, DiskFullError, Note
from src.core.plugin_base import PluginRegistry, discover_plugins
from src.core.security import KeyManager

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
    # Auto-discover and register plugins from the top-level plugins/ directory.
    registry = PluginRegistry()
    plugin_dir = Path(__file__).parent.parent / "plugins"
    discover_plugins(plugin_dir, registry)
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
@click.pass_context
def add_cmd(
    ctx: click.Context,
    title: str,
    content: Optional[str],
    encrypt: bool,
) -> None:
    """Add a new note to the store."""
    store: DatabaseStore = ctx.obj["store"]
    registry: PluginRegistry = ctx.obj["registry"]

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

    try:
        if encrypt:
            # Prompt with confirmation so typos don't silently lock the note.  [BL B-32]
            passphrase = click.prompt(
                "Passphrase", hide_input=True, confirmation_prompt=True
            )
            km = KeyManager(passphrase)
            engine = km.get_engine()
            header = {"title": title, "format": "text/plain"}
            raw_blob = BlobCodec.encode(header, content.encode("utf-8"))
            encrypted_blob = BlobCodec.encrypt(raw_blob, engine)
            note = Note.create(
                "[Encrypted Note]", content, encrypted=True, blob=encrypted_blob
            )
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
            click.echo(payload.decode("utf-8"))
        except InvalidTag:
            click.echo("Error: wrong passphrase or corrupted data.", err=True)
            sys.exit(1)
        except ValueError as exc:
            click.echo(f"Error: {exc}", err=True)
            sys.exit(1)
    else:
        click.echo(f"ID:      {note.id}")
        click.echo(f"Title:   {note.title}")
        click.echo(f"Content: {note.content or '[encrypted]'}")
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
                click.echo(f"  {note.id}  {note.title}{enc_marker}")
        else:
            click.echo("Your Notes: (none)")

        if local_notes:
            click.echo("Local Open Notes:")
            for note in local_notes:
                enc_marker = " [enc]" if note.encrypted else ""
                click.echo(f"  {note.id}  {note.title}{enc_marker}")
        else:
            click.echo("Local Open Notes: (none)")
    else:
        # Logged out: flat list (backward-compatible).
        if not local_notes:
            click.echo("No notes found.")
            return
        for note in local_notes:
            enc_marker = " [enc]" if note.encrypted else ""
            click.echo(f"{note.id}  {note.title}{enc_marker}")


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
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
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
    account_store = AccountStore(data_dir)

    username = click.prompt("Username")
    password = click.prompt("Password", hide_input=True)  # [BL B-57]

    try:
        account = account_store.authenticate(username, password)
    except RateLimitError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    except AuthError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    SessionManager.create(data_dir, account["account_id"], account["username"])
    click.echo(f"Logged in as {account['username']}.")

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
    removed = SessionManager.delete(data_dir)
    if removed:
        click.echo("Logged out.")
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


if __name__ == "__main__":  # pragma: no cover
    cli()
