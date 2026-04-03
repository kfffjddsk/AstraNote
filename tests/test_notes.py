import os
import tempfile
from src.notes import Note, NoteStore


def test_note_lifecycle(tmp_path):
    data_path = tmp_path / "notes.json"
    store = NoteStore(path=str(data_path))

    note = Note(id="1", title="Hello", content="World")
    store.add(note)
    assert store.get("1") is not None
    assert store.get("1").title == "Hello"

    updated = store.update("1", title="Hi")
    assert updated.title == "Hi"

    store.delete("1")
    assert store.get("1") is None


def test_duplicate_add_raises(tmp_path):
    data_path = tmp_path / "notes.json"
    store = NoteStore(path=str(data_path))

    note = Note(id="2", title="Two", content="Two content")
    store.add(note)

    try:
        store.add(note)
        assert False, "Expected ValueError on duplicate note" 
    except ValueError:
        pass
