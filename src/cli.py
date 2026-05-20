"""Click-based CLI for AstraNotes.

Commands : add, get, list, update, delete
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

Refs: [BL B-19, B-23, B-32, B-36, B-37, B-39, B-52] [REQ R1, R2] [US-1, US-2]
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import click
from cryptography.exceptions import InvalidTag

from src.core.blob_codec import BlobCodec
from src.core.notes import DatabaseStore, Note
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

        store.add(note)
        registry.call_hook("on_add", note)
        click.echo(note.id)

    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
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

    try:
        _, local_notes = store.list()
    except PermissionError as exc:
        click.echo(f"Error: permission denied — {exc}", err=True)
        sys.exit(1)
    except OSError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

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


if __name__ == "__main__":  # pragma: no cover
    cli()
