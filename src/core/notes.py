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
    encrypted: bool = False  # New: flag for encryption
    encrypted_title: Optional[str] = None

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
        self.key_manager = key_manager
        self._notes: Dict[str, Note] = {}
        self.load()

    def load(self):
        """Load notes from storage. Handle both old and new JSON formats."""
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            for nid, nd in data.items():
                # Handle old format (encrypted_content) and new format (content + encrypted)
                if "encrypted_content" in nd:
                    # Old format: always encrypted
                    content = nd["encrypted_content"]
                    encrypted = True
                    title = nd.get("encrypted_title", nd.get("title", "Untitled"))
                else:
                    # New format
                    content = nd["content"]
                    encrypted = nd.get("encrypted", False)
                    if encrypted:
                        title = nd.get("encrypted_title", "Untitled")
                    else:
                        title = nd["title"]
                
                note = Note(
                    id=nd["id"],
                    title=title,
                    content=content,
                    created_at=nd["created_at"],
                    modified_at=nd["modified_at"],
                    metadata=nd.get("metadata", {}),
                    encrypted=encrypted,
                    encrypted_title=nd.get("encrypted_title")
                )
                
                # If encrypted and we have key, try to decrypt
                if note.encrypted and self.key_manager:
                    try:
                        engine = self.key_manager.get_engine()
                        note.content = engine.decrypt(note.content).decode()
                        # Decrypt title if it was encrypted
                        if encrypted and "encrypted_title" in nd:
                            note.title = engine.decrypt(nd["encrypted_title"]).decode()
                        elif "encrypted_title" in nd:  # for old format
                            note.title = engine.decrypt(nd["encrypted_title"]).decode()
                    except Exception:
                        # Leave encrypted if key wrong or missing
                        note.title = "[Encrypted Note]"  # Hide title for encrypted notes without key
                        pass
                
                if note.encrypted and not self.key_manager:
                    note.title = "[Encrypted Note]"
                
                self._notes[nid] = note

    def save(self):
        """Encrypt and save notes to storage."""
        data = {}
        for nid, note in self._notes.items():
            nd = note.__dict__.copy()
            if note.encrypted:
                if self.key_manager:
                    engine = self.key_manager.get_engine()
                    nd["content"] = engine.encrypt(note.content.encode())
                    nd["encrypted_title"] = engine.encrypt(note.title.encode())
                    del nd["title"]
                else:
                    if not note.encrypted_title:
                        raise ValueError("Encrypted note requires a key manager to be saved")
                    nd["content"] = note.content
                    nd["encrypted_title"] = note.encrypted_title
                    del nd["title"]
            data[nid] = nd
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def add(self, note: Note):
        """Add a new note."""
        if note.id in self._notes:
            raise ValueError(f"Note with id {note.id} already exists")
        if note.encrypted and not self.key_manager:
            raise ValueError("Encrypted note requires a key manager")
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