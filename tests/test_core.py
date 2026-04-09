"""
Tests for AstraNote Core Modules
"""

import json
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

    def test_add_encrypted_note_requires_key_manager(self, tmp_path):
        store = NoteStore(path=str(tmp_path / "notes.json"), key_manager=None)

        with pytest.raises(ValueError):
            store.add(Note(id="1", title="Secret", content="Content", encrypted=True))

    def test_load_encrypted_note_without_key_hides_title_and_content(self, tmp_path):
        path = tmp_path / "notes.json"
        writer = NoteStore(path=str(path), key_manager=KeyManager("correctpass"))
        writer.add(Note(id="1", title="Secret", content="Content", encrypted=True))

        reader = NoteStore(path=str(path), key_manager=None)
        note = reader.get("1")

        assert note is not None
        assert note.encrypted is True
        assert note.title == "[Encrypted Note]"
        assert note.content != "Content"
        assert note.encrypted_title is not None

    def test_load_encrypted_note_with_wrong_key_hides_title_and_content(self, tmp_path):
        path = tmp_path / "notes.json"
        writer = NoteStore(path=str(path), key_manager=KeyManager("correctpass"))
        writer.add(Note(id="1", title="Secret", content="Content", encrypted=True))

        reader = NoteStore(path=str(path), key_manager=KeyManager("wrongpass"))
        note = reader.get("1")

        assert note is not None
        assert note.title == "[Encrypted Note]"
        assert note.content != "Content"

    def test_load_encrypted_note_with_correct_key_decrypts(self, tmp_path):
        path = tmp_path / "notes.json"
        writer = NoteStore(path=str(path), key_manager=KeyManager("correctpass"))
        writer.add(Note(id="1", title="Secret", content="Content", encrypted=True))

        reader = NoteStore(path=str(path), key_manager=KeyManager("correctpass"))
        note = reader.get("1")

        assert note is not None
        assert note.title == "Secret"
        assert note.content == "Content"

    def test_delete_unencrypted_note_preserves_other_encrypted_records(self, tmp_path):
        path = tmp_path / "notes.json"
        writer = NoteStore(path=str(path), key_manager=KeyManager("correctpass"))
        writer.add(Note(id="1", title="Plain", content="Visible", encrypted=False))
        writer.add(Note(id="2", title="Secret", content="Hidden", encrypted=True))

        reader = NoteStore(path=str(path), key_manager=None)
        reader.delete("1")

        reloaded = NoteStore(path=str(path), key_manager=KeyManager("correctpass"))
        note = reloaded.get("2")
        assert note is not None
        assert note.title == "Secret"
        assert note.content == "Hidden"


@pytest.mark.stress
def test_store_handles_1001_adds_and_deletes_safely(tmp_path):
    path = tmp_path / "notes.json"
    store = NoteStore(path=str(path))

    for index in range(1001):
        note_id = str(index + 1)
        store.add(Note(id=note_id, title=f"Note {note_id}", content=f"Content {note_id}"))

    assert len(store.list()) == 1001

    reloaded = NoteStore(path=str(path))
    assert len(reloaded.list()) == 1001

    for index in range(1001):
        reloaded.delete(str(index + 1))

    assert reloaded.list() == []
    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert persisted == {}