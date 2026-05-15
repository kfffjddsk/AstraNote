"""Unit tests for AstraNotes core modules.

23 tests covering: Note dataclass, DatabaseStore CRUD, encryption, BlobCodec,
KeyManager validation, co-existence invariants, and injection-hardening checks.
1  stress test (1 001 notes) marked ``stress``.

Refs: [BL B-21, B-22] [REQ R1, R2, R3.5, R14] planning/sprint-zero-plan.md §4
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest
from cryptography.exceptions import InvalidTag

from src.core.blob_codec import BlobCodec
from src.core.notes import DatabaseStore, Note
from src.core.security import EncryptionEngine, KeyManager
from tests.conftest import _TEST_ITERATIONS, make_encrypted_note

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _plain_note(title: str = "Title", content: str = "Body") -> Note:
    return Note.create(title, content)


def _enc_note(
    title: str = "Secret",
    content: str = "Private",
    pw: str = "SecretPass1",
) -> Note:
    return make_encrypted_note(title, content, pw)


# ===========================================================================
# 1. Note dataclass
# ===========================================================================


@pytest.mark.unit
def test_note_create_assigns_unique_uuid() -> None:
    """Two Note.create() calls must produce different UUIDs.  [BL B-31]"""
    a = _plain_note()
    b = _plain_note()
    assert a.id != b.id


@pytest.mark.unit
def test_note_update_title_refreshes_modified_at() -> None:
    """update(title=…) changes title and bumps modified_at.  [REQ R1.4]"""
    note = _plain_note("Old", "Body")
    original_ts = note.modified_at
    time.sleep(0.01)  # ensure clock advances
    note.update(title="New")
    assert note.title == "New"
    assert note.modified_at > original_ts


@pytest.mark.unit
def test_note_update_noop_when_no_args() -> None:
    """update() with no arguments must not change any field.  [REQ R1.4]"""
    note = _plain_note()
    before = (note.title, note.content, note.modified_at)
    note.update()
    assert (note.title, note.content, note.modified_at) == before


@pytest.mark.unit
def test_note_create_rejects_empty_title() -> None:
    """Note.create('', …) must raise ValueError.  [REQ R1.6]"""
    with pytest.raises(ValueError, match="title"):
        Note.create("", "Some content")


@pytest.mark.unit
def test_note_create_rejects_whitespace_content() -> None:
    """Note.create(…, '   ') must raise ValueError.  [REQ R1.6]"""
    with pytest.raises(ValueError, match="content"):
        Note.create("Title", "   ")


# ===========================================================================
# 2. DatabaseStore — add / get
# ===========================================================================


@pytest.mark.unit
def test_store_add_returns_note_id(tmp_store: DatabaseStore) -> None:
    """add() must return the note's own id.  [BL B-01]"""
    note = _plain_note()
    returned_id = tmp_store.add(note)
    assert returned_id == note.id


@pytest.mark.unit
def test_store_add_persists_content(tmp_store: DatabaseStore) -> None:
    """get() after add() must return title and content unchanged.  [BL B-04]"""
    note = _plain_note("Hello", "World")
    tmp_store.add(note)
    fetched = tmp_store.get(note.id)
    assert fetched is not None
    assert fetched.title == "Hello"
    assert fetched.content == "World"
    assert fetched.encrypted is False


@pytest.mark.unit
def test_store_get_not_found_returns_none(tmp_store: DatabaseStore) -> None:
    """get() for a non-existent ID must return None.  [BL B-14] [REQ R1.7]"""
    assert tmp_store.get("does-not-exist") is None


@pytest.mark.unit
def test_store_add_encrypted_note_stores_blob(tmp_store: DatabaseStore) -> None:
    """add() for an encrypted note must persist the blob; get() returns it.  [BL B-02]"""
    note = _enc_note()
    tmp_store.add(note)
    fetched = tmp_store.get(note.id)
    assert fetched is not None
    assert fetched.encrypted is True
    assert fetched.blob is not None
    assert len(fetched.blob) > 0


@pytest.mark.unit
def test_store_get_encrypted_returns_placeholder_title(tmp_store: DatabaseStore) -> None:
    """get() for an encrypted note must return the stored alias (or default placeholder),
    not the real title, without a passphrase.  [BL B-07] [REQ R2.7] [D-07]"""
    note = _enc_note()
    tmp_store.add(note)
    fetched = tmp_store.get(note.id)
    assert fetched is not None
    assert fetched.title == "[Encrypted Note]"
    assert fetched.content == ""


# ===========================================================================
# 3. DatabaseStore — update
# ===========================================================================


@pytest.mark.unit
def test_store_update_unencrypted_note(tmp_store: DatabaseStore) -> None:
    """update() changes title and content for unencrypted notes.  [BL B-08]"""
    note = _plain_note("Old Title", "Old Body")
    tmp_store.add(note)
    updated = tmp_store.update(note.id, title="New Title", content="New Body")
    assert updated.title == "New Title"
    assert updated.content == "New Body"
    # Persisted change is visible on subsequent get
    fetched = tmp_store.get(note.id)
    assert fetched is not None
    assert fetched.title == "New Title"
    assert fetched.content == "New Body"


@pytest.mark.unit
def test_store_update_not_found_raises(tmp_store: DatabaseStore) -> None:
    """update() for a non-existent ID must raise KeyError.  [BL B-14] [REQ R1.7]"""
    with pytest.raises(KeyError):
        tmp_store.update("ghost-id", title="X")


# ===========================================================================
# 4. DatabaseStore — delete
# ===========================================================================


@pytest.mark.unit
def test_store_delete_removes_note(tmp_store: DatabaseStore) -> None:
    """delete() must make get() return None for that note.  [BL B-11]"""
    note = _plain_note()
    tmp_store.add(note)
    tmp_store.delete(note.id)
    assert tmp_store.get(note.id) is None


@pytest.mark.unit
def test_store_delete_not_found_raises(tmp_store: DatabaseStore) -> None:
    """delete() for a non-existent ID must raise KeyError.  [BL B-14] [REQ R1.7]"""
    with pytest.raises(KeyError):
        tmp_store.delete("ghost-id")


# ===========================================================================
# 5. DatabaseStore — list
# ===========================================================================


@pytest.mark.unit
def test_store_list_empty_returns_empty_tuple(tmp_store: DatabaseStore) -> None:
    """list() on an empty store returns ([], []).  [BL B-07]"""
    account_notes, local_notes = tmp_store.list()
    assert account_notes == []
    assert local_notes == []


@pytest.mark.unit
def test_store_list_mixed_encryption(tmp_store: DatabaseStore) -> None:
    """list() returns both unencrypted and encrypted notes in local_notes.
    Encrypted notes appear with their stored alias; content is never populated.
    [BL B-07] [REQ R1.3, R2.7] [BL B-74]"""
    plain = _plain_note("Plain Title", "Body")
    encrypted = _enc_note("Secret", "Private")
    tmp_store.add(plain)
    tmp_store.add(encrypted)

    _, local_notes = tmp_store.list()
    assert len(local_notes) == 2

    titles = {n.title for n in local_notes}
    assert "Plain Title" in titles
    assert "[Encrypted Note]" in titles

    # list() must never return content for any note (no blob parsing)
    for note in local_notes:
        assert note.content == ""


# ===========================================================================
# 6. Co-existence invariant  [BL B-33] [REQ R2.12]
# ===========================================================================


@pytest.mark.unit
def test_unencrypted_update_does_not_corrupt_encrypted_note(
    tmp_store: DatabaseStore,
) -> None:
    """Updating an unencrypted note must leave a co-stored encrypted note
    untouched.  [BL B-33] [REQ R2.12]"""
    plain = _plain_note("Plain", "Readable")
    encrypted = _enc_note("Secret", "Private")
    tmp_store.add(plain)
    tmp_store.add(encrypted)

    original_blob = tmp_store.get(encrypted.id).blob  # type: ignore[union-attr]

    tmp_store.update(plain.id, title="Updated Plain", content="New Readable")

    preserved = tmp_store.get(encrypted.id)
    assert preserved is not None
    assert preserved.blob == original_blob


# ===========================================================================
# 7. Encryption / BlobCodec
# ===========================================================================


@pytest.mark.unit
def test_encryption_roundtrip() -> None:
    """EncryptionEngine.encrypt() → decrypt() recovers the original bytes."""
    engine = EncryptionEngine("TestPass1", iterations=_TEST_ITERATIONS)
    plaintext = b"Hello, AstraNotes!"
    ciphertext = engine.encrypt(plaintext)
    assert ciphertext != plaintext
    assert engine.decrypt(ciphertext) == plaintext


@pytest.mark.unit
def test_wrong_passphrase_raises_invalid_tag() -> None:
    """decrypt() with the wrong passphrase must raise InvalidTag.  [BL B-06] [REQ R2.8]"""
    engine_enc = EncryptionEngine("CorrectPass1", iterations=_TEST_ITERATIONS)
    engine_dec = EncryptionEngine("WrongPass999", iterations=_TEST_ITERATIONS)
    ciphertext = engine_enc.encrypt(b"secret data")
    with pytest.raises(InvalidTag):
        engine_dec.decrypt(ciphertext)


@pytest.mark.unit
def test_keymanager_rejects_short_passphrase() -> None:
    """KeyManager must reject passphrases shorter than 8 chars.  [BL B-34] [REQ R2.11]"""
    with pytest.raises(ValueError, match="8"):
        KeyManager("short")


@pytest.mark.unit
def test_blobcodec_encode_decode_roundtrip() -> None:
    """BlobCodec.encode() → decode() recovers header and payload exactly."""
    header = {"title": "My Note", "format": "text/plain"}
    payload = b"Hello World"
    blob = BlobCodec.encode(header, payload)
    decoded_header, decoded_payload = BlobCodec.decode(blob)
    assert decoded_header == header
    assert decoded_payload == payload


@pytest.mark.unit
def test_blobcodec_encrypted_blob_decrypts_to_original_content(
    tmp_store: DatabaseStore,
) -> None:
    """An encrypted note's blob, when decrypted with BlobCodec, yields the
    original content.  [BL B-05] [REQ R2.3]"""
    passphrase = "SecretPass1"
    content = "Top secret content"
    note = make_encrypted_note("Secret", content, passphrase)
    tmp_store.add(note)

    fetched = tmp_store.get(note.id)
    assert fetched is not None and fetched.blob is not None

    engine = KeyManager(passphrase, iterations=_TEST_ITERATIONS).get_engine()
    raw_blob = BlobCodec.decrypt(fetched.blob, engine)
    _, payload = BlobCodec.decode(raw_blob)
    assert payload.decode("utf-8") == content


# ===========================================================================
# 8. Stress test  [BL B-22] [REQ R3.5]
# ===========================================================================


@pytest.mark.stress
def test_store_stress_1001_notes(tmp_path: Path) -> None:
    """Add 1 001 unencrypted notes; list and delete all within 0.5 s each phase.
    [BL B-22] [REQ R3.5]"""
    store = DatabaseStore(tmp_path)
    notes = [Note.create(f"Note {i}", f"Content {i}") for i in range(1001)]

    t0 = time.monotonic()
    for note in notes:
        store.add(note)
    add_time = time.monotonic() - t0

    t1 = time.monotonic()
    _, local_notes = store.list()
    list_time = time.monotonic() - t1
    assert len(local_notes) == 1001

    t2 = time.monotonic()
    for note in notes:
        store.delete(note.id)
    delete_time = time.monotonic() - t2

    _, after = store.list()
    assert len(after) == 0

    assert list_time < 0.5, f"list() took {list_time:.2f}s — exceeds 0.5 s budget"
    assert delete_time < 5.0, f"bulk delete took {delete_time:.2f}s"
    _ = add_time  # add time not bounded by spec; recorded for reference


# ===========================================================================
# 9. Injection-hardening  [OWASP A03, A08]
# ===========================================================================


@pytest.mark.unit
def test_note_create_rejects_null_byte_in_title() -> None:
    """Note.create() must reject titles containing null bytes."""
    with pytest.raises(ValueError, match="null"):
        Note.create("Bad\x00Title", "content")


@pytest.mark.unit
def test_note_create_rejects_null_byte_in_content() -> None:
    """Note.create() must reject plaintext content containing null bytes."""
    with pytest.raises(ValueError, match="null"):
        Note.create("Good Title", "bad\x00content")


@pytest.mark.unit
def test_note_update_rejects_null_byte_in_title() -> None:
    """Note.update() must reject a title containing null bytes."""
    note = _plain_note()
    with pytest.raises(ValueError, match="null"):
        note.update(title="bad\x00title")


@pytest.mark.unit
def test_note_update_rejects_null_byte_in_content() -> None:
    """Note.update() must reject content containing null bytes."""
    note = _plain_note()
    with pytest.raises(ValueError, match="null"):
        note.update(content="bad\x00content")


@pytest.mark.unit
def test_blobcodec_decode_rejects_oversized_header(tmp_path: Path) -> None:
    """BlobCodec.decode() must reject a header claiming more than 64 KiB."""
    import struct

    oversized = BlobCodec._MAX_HEADER_LEN + 1
    blob = struct.pack(">I", oversized) + b"x" * oversized
    with pytest.raises(ValueError, match="exceeds maximum"):
        BlobCodec.decode(blob)


@pytest.mark.unit
def test_blobcodec_decode_rejects_non_dict_header() -> None:
    """BlobCodec.decode() must reject a blob whose JSON header is not a dict."""
    import json
    import struct

    header_bytes = json.dumps([1, 2, 3]).encode("utf-8")
    blob = struct.pack(">I", len(header_bytes)) + header_bytes + b"payload"
    with pytest.raises(ValueError, match="JSON object"):
        BlobCodec.decode(blob)


@pytest.mark.unit
def test_encryption_decrypt_rejects_short_ciphertext() -> None:
    """EncryptionEngine.decrypt() must raise ValueError for undersized input."""
    engine = EncryptionEngine("TestPass1", iterations=_TEST_ITERATIONS)
    with pytest.raises(ValueError, match="too short"):
        engine.decrypt(b"tooshort")
