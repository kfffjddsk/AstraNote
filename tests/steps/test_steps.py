"""BDD step definitions for AstraNotes.

All 17 scenarios from 5 feature files are registered here.  State is shared
between steps via the ``context`` fixture (a plain dict) defined in conftest.py.

Refs: [BL B-20] planning/sprint-zero-plan.md §4, docs/bdd-testing.md
"""
from __future__ import annotations

import pytest
from cryptography.exceptions import InvalidTag
from pytest_bdd import given, parsers, scenarios, then, when

from src.core.blob_codec import BlobCodec
from src.core.notes import DatabaseStore, Note
from src.core.security import KeyManager
from tests.conftest import _TEST_ITERATIONS, make_encrypted_note

# ---------------------------------------------------------------------------
# Register all feature files
# ---------------------------------------------------------------------------

scenarios("../features/add_notes.feature")
scenarios("../features/get_notes.feature")
scenarios("../features/list_notes.feature")
scenarios("../features/update_notes.feature")
scenarios("../features/delete_notes.feature")


# ===========================================================================
# Given — preconditions
# ===========================================================================


@given("an empty note store")
def empty_note_store(context: dict) -> None:
    context["store"] = DatabaseStore(context["tmp_path"])
    context["notes"] = {}   # keyed by role: "plain", "encrypted"
    context["result"] = None
    context["error"] = None
    context["decrypted_content"] = None
    context["list_result"] = None


@given(parsers.parse('a plain note exists with title "{title}" and content "{content}"'))
def plain_note_exists(context: dict, title: str, content: str) -> None:
    note = Note.create(title, content)
    context["store"].add(note)
    context["notes"]["plain"] = note


@given(
    parsers.parse(
        'an encrypted note exists with title "{title}" content "{content}" passphrase "{passphrase}"'
    )
)
def encrypted_note_exists(context: dict, title: str, content: str, passphrase: str) -> None:
    note = make_encrypted_note(title, content, passphrase)
    context["store"].add(note)
    context["notes"]["encrypted"] = note


# ===========================================================================
# When — actions
# ===========================================================================


@when(parsers.parse('I add a note with title "{title}" and content "{content}"'))
def add_plain_note(context: dict, title: str, content: str) -> None:
    note = Note.create(title, content)
    context["store"].add(note)
    context["notes"]["plain"] = note


@when(
    parsers.parse(
        'I add an encrypted note titled "{title}" with content "{content}" and passphrase "{passphrase}"'
    )
)
def add_encrypted_note(context: dict, title: str, content: str, passphrase: str) -> None:
    note = make_encrypted_note(title, content, passphrase)
    context["store"].add(note)
    context["notes"]["encrypted"] = note


@when(parsers.re(r'I try to create a note with title "(?P<title>[^"]*)" and content "(?P<content>[^"]*)"'))
def try_create_note(context: dict, title: str, content: str) -> None:
    try:
        Note.create(title, content)
    except ValueError as exc:
        context["error"] = exc


@when("I retrieve the note by its ID")
def retrieve_note_by_id(context: dict) -> None:
    note = context["notes"].get("plain") or context["notes"].get("encrypted")
    assert note is not None, "No note in context to retrieve."
    context["result"] = context["store"].get(note.id)


@when(parsers.parse('I retrieve a note with ID "{note_id}"'))
def retrieve_note_by_literal_id(context: dict, note_id: str) -> None:
    context["result"] = context["store"].get(note_id)


@when(parsers.parse('I decrypt the blob with passphrase "{passphrase}"'))
def decrypt_blob(context: dict, passphrase: str) -> None:
    fetched: Note = context["result"]
    assert fetched is not None and fetched.blob is not None
    engine = KeyManager(passphrase, iterations=_TEST_ITERATIONS).get_engine()
    raw_blob = BlobCodec.decrypt(fetched.blob, engine)
    _, payload = BlobCodec.decode(raw_blob)
    context["decrypted_content"] = payload.decode("utf-8")


@when(parsers.parse('I try to decrypt the blob with passphrase "{passphrase}"'))
def try_decrypt_blob(context: dict, passphrase: str) -> None:
    fetched: Note = context["result"]
    assert fetched is not None and fetched.blob is not None
    try:
        engine = KeyManager(passphrase, iterations=_TEST_ITERATIONS).get_engine()
        BlobCodec.decrypt(fetched.blob, engine)
    except InvalidTag as exc:
        context["error"] = exc


@when("I list all notes")
def list_all_notes(context: dict) -> None:
    context["list_result"] = context["store"].list()


@when(parsers.parse('I update the note with title "{title}" and content "{content}"'))
def update_plain_note(context: dict, title: str, content: str) -> None:
    note = context["notes"]["plain"]
    context["result"] = context["store"].update(note.id, title=title, content=content)


@when(parsers.parse('I try to update a note with ID "{note_id}"'))
def try_update_nonexistent(context: dict, note_id: str) -> None:
    try:
        context["store"].update(note_id, title="X")
    except KeyError as exc:
        context["error"] = exc


@when(parsers.parse('I update the plain note with title "{title}" and content "{content}"'))
def update_plain_note_coexistence(context: dict, title: str, content: str) -> None:
    note = context["notes"]["plain"]
    context["result"] = context["store"].update(note.id, title=title, content=content)


@when(
    parsers.parse(
        'I re-encrypt the note with content "{content}" using passphrase "{passphrase}"'
    )
)
def reencrypt_note(context: dict, content: str, passphrase: str) -> None:
    note = context["notes"]["encrypted"]
    engine = KeyManager(passphrase, iterations=_TEST_ITERATIONS).get_engine()
    header = {"title": note.title, "format": "text/plain"}
    raw_blob = BlobCodec.encode(header, content.encode("utf-8"))
    new_blob = BlobCodec.encrypt(raw_blob, engine)
    context["store"].update(note.id, blob=new_blob)
    context["notes"]["encrypted"] = context["store"].get(note.id)


@when("I delete the note")
def delete_note(context: dict) -> None:
    note = context["notes"].get("plain") or context["notes"].get("encrypted")
    assert note is not None
    context["store"].delete(note.id)
    context["deleted_note_id"] = note.id


@when(parsers.parse('I try to delete a note with ID "{note_id}"'))
def try_delete_nonexistent(context: dict, note_id: str) -> None:
    try:
        context["store"].delete(note_id)
    except KeyError as exc:
        context["error"] = exc


@when("I delete the plain note")
def delete_plain_note(context: dict) -> None:
    note = context["notes"]["plain"]
    context["store"].delete(note.id)
    context["deleted_note_id"] = note.id


# ===========================================================================
# Then — assertions
# ===========================================================================


@then(parsers.parse('the note with title "{title}" exists in the store'))
def note_title_exists(context: dict, title: str) -> None:
    note = context["notes"]["plain"]
    fetched = context["store"].get(note.id)
    assert fetched is not None
    assert fetched.title == title


@then(parsers.parse('the stored content is "{content}"'))
def stored_content_matches(context: dict, content: str) -> None:
    note = context["notes"]["plain"]
    fetched = context["store"].get(note.id)
    assert fetched is not None
    assert fetched.content == content


@then(parsers.parse('an encrypted note with alias "{alias}" exists in the store'))
def encrypted_note_alias_exists(context: dict, alias: str) -> None:
    note = context["notes"]["encrypted"]
    fetched = context["store"].get(note.id)
    assert fetched is not None
    assert fetched.encrypted is True
    assert fetched.title == alias


@then("the encrypted note has a non-empty blob")
def encrypted_note_has_blob(context: dict) -> None:
    note = context["notes"]["encrypted"]
    fetched = context["store"].get(note.id)
    assert fetched is not None
    assert fetched.blob is not None and len(fetched.blob) > 0


@then("a ValueError is raised")
def value_error_raised(context: dict) -> None:
    assert isinstance(context.get("error"), ValueError), (
        f"Expected ValueError, got {context.get('error')!r}"
    )


@then("an InvalidTag error is raised")
def invalid_tag_raised(context: dict) -> None:
    assert isinstance(context.get("error"), InvalidTag), (
        f"Expected InvalidTag, got {context.get('error')!r}"
    )


@then("a KeyError is raised")
def key_error_raised(context: dict) -> None:
    assert isinstance(context.get("error"), KeyError), (
        f"Expected KeyError, got {context.get('error')!r}"
    )


@then(parsers.parse('the retrieved title is "{title}"'))
def retrieved_title_matches(context: dict, title: str) -> None:
    assert context["result"] is not None
    assert context["result"].title == title


@then(parsers.parse('the retrieved content is "{content}"'))
def retrieved_content_matches(context: dict, content: str) -> None:
    assert context["result"] is not None
    assert context["result"].content == content


@then(parsers.parse('the decrypted content is "{content}"'))
def decrypted_content_matches(context: dict, content: str) -> None:
    assert context["decrypted_content"] == content


@then("the result is None")
def result_is_none(context: dict) -> None:
    assert context["result"] is None


@then(parsers.parse("there are {count:d} notes in the local list"))
def local_list_count(context: dict, count: int) -> None:
    _, local_notes = context["list_result"]
    assert len(local_notes) == count


@then(parsers.parse('one note has title "{title}"'))
def one_note_has_title(context: dict, title: str) -> None:
    _, local_notes = context["list_result"]
    assert any(n.title == title for n in local_notes), (
        f"No note with title {title!r}. Titles: {[n.title for n in local_notes]}"
    )


@then("no note in the list has non-empty content")
def no_note_has_content(context: dict) -> None:
    _, local_notes = context["list_result"]
    for note in local_notes:
        assert note.content == "", f"Note {note.id!r} unexpectedly has content: {note.content!r}"


@then(parsers.parse('the updated note has title "{title}"'))
def updated_note_title(context: dict, title: str) -> None:
    assert context["result"] is not None
    assert context["result"].title == title


@then(parsers.parse('the updated note has content "{content}"'))
def updated_note_content(context: dict, content: str) -> None:
    assert context["result"] is not None
    assert context["result"].content == content


@then("the encrypted note blob is unchanged")
def encrypted_blob_unchanged(context: dict) -> None:
    enc_note = context["notes"]["encrypted"]
    original_blob = enc_note.blob
    fetched = context["store"].get(enc_note.id)
    assert fetched is not None
    assert fetched.blob == original_blob


@then(parsers.parse('the plain note has title "{title}"'))
def plain_note_has_title(context: dict, title: str) -> None:
    plain_note = context["notes"]["plain"]
    fetched = context["store"].get(plain_note.id)
    assert fetched is not None
    assert fetched.title == title


@then(
    parsers.parse(
        'the encrypted note can be decrypted to "{content}" with passphrase "{passphrase}"'
    )
)
def encrypted_note_decrypts_to(context: dict, content: str, passphrase: str) -> None:
    enc_note = context["notes"]["encrypted"]
    fetched = context["store"].get(enc_note.id)
    assert fetched is not None and fetched.blob is not None
    engine = KeyManager(passphrase, iterations=_TEST_ITERATIONS).get_engine()
    raw_blob = BlobCodec.decrypt(fetched.blob, engine)
    _, payload = BlobCodec.decode(raw_blob)
    assert payload.decode("utf-8") == content


@then("the note no longer exists in the store")
def note_no_longer_exists(context: dict) -> None:
    note_id = context["deleted_note_id"]
    assert context["store"].get(note_id) is None


@then("the encrypted note still exists in the store")
def encrypted_note_still_exists(context: dict) -> None:
    enc_note = context["notes"]["encrypted"]
    fetched = context["store"].get(enc_note.id)
    assert fetched is not None
    assert fetched.encrypted is True
