"""
AstraNote Core Notes Module

Handles note data model and storage.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional
from .security import KeyManager


@dataclass
class Note:
    """
    Represents a single note.
    """
    id: str
    title: str
    content: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat() + "Z")
    modified_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat() + "Z")
    metadata: Dict[str, str] = field(default_factory=dict)

    def update(self, title: Optional[str] = None, content: Optional[str] = None):
        """Update note fields and timestamp."""
        updated = False
        if title is not None:
            self.title = title
            updated = True
        if content is not None:
            self.content = content
            updated = True
        if updated:
            self.modified_at = datetime.now(timezone.utc).isoformat() + "Z"


class NoteStore:
    """
    Manages note persistence with encryption.
    """

    def __init__(self, path: str = "data/notes.json", key_manager: Optional[KeyManager] = None):
        self.path = Path(path)
        self.key_manager = key_manager or KeyManager("default_passphrase")  # For demo
        self._notes: Dict[str, Note] = {}
        self.load()

    def load(self):
        """Load and decrypt notes from storage."""
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            engine = self.key_manager.get_engine()
            for nid, nd in data.items():
                # Decrypt content if encrypted
                if "encrypted_content" in nd:
                    nd["content"] = engine.decrypt(nd["encrypted_content"]).decode()
                    del nd["encrypted_content"]
                self._notes[nid] = Note(**nd)

    def save(self):
        """Encrypt and save notes to storage."""
        engine = self.key_manager.get_engine()
        data = {}
        for nid, note in self._notes.items():
            nd = note.__dict__.copy()
            # Encrypt content
            nd["encrypted_content"] = engine.encrypt(note.content.encode())
            del nd["content"]
            data[nid] = nd
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def add(self, note: Note):
        """Add a new note."""
        if note.id in self._notes:
            raise ValueError(f"Note with id {note.id} already exists")
        self._notes[note.id] = note
        self.save()

    def get(self, note_id: str) -> Optional[Note]:
        """Retrieve a note by ID."""
        return self._notes.get(note_id)

    def update(self, note_id: str, title: Optional[str] = None, content: Optional[str] = None):
        """Update an existing note."""
        note = self.get(note_id)
        if note is None:
            raise KeyError(f"Note {note_id} not found")
        note.update(title=title, content=content)
        self.save()
        return note

    def delete(self, note_id: str):
        """Delete a note."""
        if note_id in self._notes:
            del self._notes[note_id]
            self.save()
        else:
            raise KeyError(f"Note {note_id} not found")

    def list(self) -> List[Note]:
        """List all notes."""
        return list(self._notes.values())