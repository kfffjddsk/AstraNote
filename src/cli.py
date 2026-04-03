"""
AstraNote CLI Entry Point

Provides command-line interface for note management.
"""

import click
from pathlib import Path
from .core.notes import Note, NoteStore
from .core.security import KeyManager


def ensure_store(ctx, data_dir):
    """Ensure store is initialized in context."""
    if 'store' not in ctx.obj:
        passphrase = click.prompt('Encryption passphrase', hide_input=True)
        key_manager = KeyManager(passphrase)
        store_path = Path(data_dir) / "notes.json"
        ctx.obj['store'] = NoteStore(path=str(store_path), key_manager=key_manager)


@click.group()
@click.option('--data-dir', default='data', help='Directory for note storage')
@click.pass_context
def cli(ctx, data_dir):
    """AstraNote: Secure, modular note-taking app."""
    ctx.ensure_object(dict)
    ctx.obj['data_dir'] = data_dir  # Store data_dir for later use


@cli.command()
@click.option('--title', prompt='Title', help='Note title')
@click.option('--content', prompt='Content', help='Note content')
@click.pass_context
def add(ctx, title, content):
    """Add a new note."""
    ensure_store(ctx, ctx.obj['data_dir'])
    store = ctx.obj['store']
    note_id = str(len(store.list()) + 1)  # Simple ID generation
    note = Note(id=note_id, title=title, content=content)
    store.add(note)
    click.echo(f"Note '{title}' added with ID {note_id}")


@cli.command()
@click.argument('note_id')
@click.pass_context
def get(ctx, note_id):
    """Retrieve and display a note."""
    ensure_store(ctx, ctx.obj['data_dir'])
    store = ctx.obj['store']
    note = store.get(note_id)
    if note:
        click.echo(f"ID: {note.id}")
        click.echo(f"Title: {note.title}")
        click.echo(f"Content: {note.content}")
        click.echo(f"Created: {note.created_at}")
        click.echo(f"Modified: {note.modified_at}")
    else:
        click.echo(f"Note {note_id} not found")


@cli.command()
@click.pass_context
def list(ctx):
    """List all notes."""
    ensure_store(ctx, ctx.obj['data_dir'])
    store = ctx.obj['store']
    notes = store.list()
    if notes:
        for note in notes:
            click.echo(f"{note.id}: {note.title} ({note.created_at})")
    else:
        click.echo("No notes found")


@cli.command()
@click.argument('note_id')
@click.option('--title', help='New title')
@click.option('--content', help='New content')
@click.pass_context
def update(ctx, note_id, title, content):
    """Update an existing note."""
    ensure_store(ctx, ctx.obj['data_dir'])
    store = ctx.obj['store']
    try:
        store.update(note_id, title=title, content=content)
        click.echo(f"Note {note_id} updated")
    except KeyError:
        click.echo(f"Note {note_id} not found")


@cli.command()
@click.argument('note_id')
@click.pass_context
def delete(ctx, note_id):
    """Delete a note."""
    ensure_store(ctx, ctx.obj['data_dir'])
    store = ctx.obj['store']
    try:
        store.delete(note_id)
        click.echo(f"Note {note_id} deleted")
    except KeyError:
        click.echo(f"Note {note_id} not found")


if __name__ == '__main__':
    cli()