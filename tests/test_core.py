"""
Tests for AstraNote Core Modules
"""

import pytest
import tempfile
from pathlib import Path
from src.core.notes import Note, NoteStore
from src.core.security import EncryptionEngine, KeyManager


class TestNote:
    def test_note_creation(self):
        note = Note(id="1", title="Test", content="Content")
        assert note.id == "1"
        assert note.title == "Test"
        assert note.content == "Content"
        assert "created_at" in note.__dict__

    def test_note_update(self):
        note = Note(id="1", title="Old", content="Old")
        original_modified = note.modified_at
        note.update(title="New", content="New")
        assert note.title == "New"
        assert note.content == "New"
        assert note.modified_at >= original_modified  # Modified at least as recent


class TestEncryptionEngine:
    def test_encrypt_decrypt(self):
        engine = EncryptionEngine("test_passphrase")
        plaintext = b"Hello, World!"
        ciphertext = engine.encrypt(plaintext)
        decrypted = engine.decrypt(ciphertext)
        assert decrypted == plaintext

    def test_wrong_passphrase_fails(self):
        engine1 = EncryptionEngine("pass1")
        engine2 = EncryptionEngine("pass2")
        plaintext = b"Secret"
        ciphertext = engine1.encrypt(plaintext)
        with pytest.raises(Exception):  # InvalidTag or similar
            engine2.decrypt(ciphertext)


class TestKeyManager:
    def test_get_engine(self):
        km = KeyManager("pass")
        engine = km.get_engine()
        assert isinstance(engine, EncryptionEngine)


class TestNoteStore:
    def test_add_get_note(self, tmp_path):
        store = NoteStore(path=str(tmp_path / "notes.json"))
        note = Note(id="1", title="Test", content="Content")
        store.add(note)
        retrieved = store.get("1")
        assert retrieved.title == "Test"
        assert retrieved.content == "Content"

    def test_update_note(self, tmp_path):
        store = NoteStore(path=str(tmp_path / "notes.json"))
        note = Note(id="1", title="Old", content="Old")
        store.add(note)
        store.update("1", title="New")
        updated = store.get("1")
        assert updated.title == "New"

    def test_delete_note(self, tmp_path):
        store = NoteStore(path=str(tmp_path / "notes.json"))
        note = Note(id="1", title="Test", content="Content")
        store.add(note)
        store.delete("1")
        assert store.get("1") is None

    def test_list_notes(self, tmp_path):
        store = NoteStore(path=str(tmp_path / "notes.json"))
        store.add(Note(id="1", title="Note1", content="C1"))
        store.add(Note(id="2", title="Note2", content="C2"))
        notes = store.list()
        assert len(notes) == 2

    def test_duplicate_add_raises(self, tmp_path):
        store = NoteStore(path=str(tmp_path / "notes.json"))
        note = Note(id="1", title="Test", content="Content")
        store.add(note)
        with pytest.raises(ValueError):
            store.add(note)