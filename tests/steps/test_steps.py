from pytest_bdd import given, when, then, parsers, scenario
import pytest
import re


def _store_note_id(title, output):
    match = re.search(r"Note '.*' added with ID (\d+)", output)
    if match:
        if not hasattr(pytest, 'shared_note_ids'):
            pytest.shared_note_ids = {}
        pytest.shared_note_ids[title] = match.group(1)


def _resolve_note_ref(title_or_id):
    if hasattr(pytest, 'shared_note_ids') and title_or_id in pytest.shared_note_ids:
        return pytest.shared_note_ids[title_or_id]
    return title_or_id


# ---------------------------------------------------------------------------
# Scenarios – Add
# ---------------------------------------------------------------------------
@scenario('../features/add_notes.feature', 'Add an unencrypted note')
def test_add_unencrypted_note():
    pass

@scenario('../features/add_notes.feature', 'Add an encrypted note')
def test_add_encrypted_note():
    pass

@scenario('../features/add_notes.feature', 'Add note with invalid input')
def test_add_invalid_note():
    pass

# ---------------------------------------------------------------------------
# Scenarios – List
# ---------------------------------------------------------------------------
@scenario('../features/list_notes.feature', 'List all notes with mixed encryption')
def test_list_mixed_notes():
    pass

@scenario('../features/list_notes.feature', 'List notes when no notes exist')
def test_list_empty():
    pass

# ---------------------------------------------------------------------------
# Scenarios – Get
# ---------------------------------------------------------------------------
@scenario('../features/get_notes.feature', 'Get an unencrypted note')
def test_get_unencrypted():
    pass

@scenario('../features/get_notes.feature', 'Get an encrypted note with correct passphrase')
def test_get_encrypted_correct():
    pass

@scenario('../features/get_notes.feature', 'Get an encrypted note with wrong passphrase')
def test_get_encrypted_wrong():
    pass

@scenario('../features/get_notes.feature', 'Get a non-existent note')
def test_get_nonexistent():
    pass

# ---------------------------------------------------------------------------
# Scenarios – Update
# ---------------------------------------------------------------------------
@scenario('../features/update_notes.feature', 'Update an unencrypted note')
def test_update_unencrypted():
    pass

@scenario('../features/update_notes.feature', 'Update an encrypted note')
def test_update_encrypted():
    pass

@scenario('../features/update_notes.feature', 'Update an encrypted note with wrong passphrase')
def test_update_encrypted_wrong():
    pass

@scenario('../features/update_notes.feature', 'Update a non-existent note')
def test_update_nonexistent():
    pass

# ---------------------------------------------------------------------------
# Scenarios – Delete
# ---------------------------------------------------------------------------
@scenario('../features/delete_notes.feature', 'Delete an unencrypted note')
def test_delete_unencrypted():
    pass

@scenario('../features/delete_notes.feature', 'Delete an encrypted note with correct passphrase')
def test_delete_encrypted_correct():
    pass

@scenario('../features/delete_notes.feature', 'Delete an encrypted note with wrong passphrase')
def test_delete_encrypted_wrong():
    pass

@scenario('../features/delete_notes.feature', 'Delete a non-existent note')
def test_delete_nonexistent():
    pass


# ===================================================================
# Given steps
# ===================================================================
@given(parsers.parse('I have a note with title "{title}" and content "{content}"'))
def note_data(title, content):
    return {"title": title, "content": content}


@given(parsers.parse('I have an unencrypted note with title "{title}"'))
def existing_unencrypted_note(cli_app, title):
    result = cli_app(['add', '--title', title, '--content', 'Test content', '--encrypt', 'no'])
    assert result.exit_code == 0
    _store_note_id(title, result.output)


@given(parsers.parse('I have an encrypted note with title "{title}"'))
def existing_encrypted_note(cli_app, title):
    result = cli_app(['add', '--title', title, '--content', 'Secret content', '--encrypt', 'yes'], input='correctpass\ncorrectpass\n')
    assert result.exit_code == 0
    _store_note_id(title, result.output)


@given('I have added several notes some encrypted some not')
def multiple_notes(cli_app):
    result1 = cli_app(['add', '--title', 'Note1', '--content', 'Content1', '--encrypt', 'no'])
    assert result1.exit_code == 0
    _store_note_id('Note1', result1.output)
    result2 = cli_app(['add', '--title', 'Note2', '--content', 'Content2', '--encrypt', 'yes'], input='pass\npass\n')
    assert result2.exit_code == 0
    _store_note_id('Note2', result2.output)


@given('I have no notes stored')
def no_notes(cli_app):
    pass


@given(parsers.parse('I have no note with title "{title}"'))
def no_such_note(title):
    pass


@given('I have invalid note data')
def invalid_data():
    return {"title": "", "content": ""}


# ===================================================================
# When steps
# ===================================================================
@when('I run the add command without encryption')
def add_unencrypted(cli_app):
    result = cli_app(['add', '--title', 'Test Note', '--content', 'This is a test', '--encrypt', 'no'])
    pytest.shared_result = result


@when('I run the add command with encryption')
def add_encrypted(cli_app):
    result = cli_app(['add', '--title', 'Secret Note', '--content', 'This is secret', '--encrypt', 'yes'], input='mypassword\nmypassword\n')
    pytest.shared_result = result


@when('I run the add command with invalid data')
def add_note_invalid(cli_app):
    result = cli_app(['add', '--title', '', '--content', ''])
    pytest.shared_result = result


@when('I run the list command')
def list_notes(cli_app):
    result = cli_app(['list'])
    pytest.shared_result = result


@when(parsers.parse('I run the get command for "{title}"'))
def get_note(cli_app, title):
    note_id = _resolve_note_ref(title)
    result = cli_app(['get', note_id])
    pytest.shared_result = result


@when(parsers.parse('I run the get command for "{title}" with passphrase "{password}"'))
def get_note_with_passphrase(cli_app, title, password):
    note_id = _resolve_note_ref(title)
    result = cli_app(['get', note_id], input=f'{password}\n')
    pytest.shared_result = result


@when(parsers.parse('I run the update command for "{title}" with new content'))
def update_note(cli_app, title):
    note_id = _resolve_note_ref(title)
    result = cli_app(['update', note_id, '--content', 'Updated content'])
    pytest.shared_result = result


@when(parsers.parse('I run the update command for "{title}" with passphrase "{password}"'))
def update_note_with_passphrase(cli_app, title, password):
    note_id = _resolve_note_ref(title)
    result = cli_app(['update', note_id, '--content', 'Updated content'], input=f'{password}\n')
    pytest.shared_result = result


@when(parsers.parse('I run the delete command for "{title}"'))
def delete_note(cli_app, title):
    note_id = _resolve_note_ref(title)
    result = cli_app(['delete', note_id])
    pytest.shared_result = result


@when(parsers.parse('I run the delete command for "{title}" with passphrase "{password}"'))
def delete_note_with_passphrase(cli_app, title, password):
    note_id = _resolve_note_ref(title)
    result = cli_app(['delete', note_id], input=f'{password}\n')
    pytest.shared_result = result


# ===================================================================
# Then steps
# ===================================================================
@then('the note should be added successfully')
def note_added():
    assert pytest.shared_result.exit_code == 0


@then('I should see a confirmation message')
def confirmation_message():
    assert 'added with id' in pytest.shared_result.output.lower()


@then('I should see an error message')
def error_message():
    assert pytest.shared_result.exit_code != 0 or 'error' in pytest.shared_result.output.lower()


@then('I should not be prompted for a passphrase')
def no_passphrase_prompt():
    assert 'Encryption passphrase:' not in pytest.shared_result.output


@then('I should be prompted for a passphrase')
def passphrase_prompt():
    assert 'Encryption passphrase:' in pytest.shared_result.output


@then('no note should be stored')
def no_note_stored(cli_app):
    list_result = cli_app(['list'])
    assert 'No notes found' in list_result.output


@then('I should see all unencrypted notes with full details')
def unencrypted_notes_visible():
    output = pytest.shared_result.output
    assert 'Note1' in output
    assert '1:' in output


@then('encrypted notes should show only titles with encryption indicator')
def encrypted_notes_hidden():
    output = pytest.shared_result.output
    assert '2: [Encrypted Note]' in output


@then('I should see a message indicating no notes found')
def no_notes_message():
    assert 'no notes' in pytest.shared_result.output.lower()


@then('I should see the full content of the note')
def full_content_visible():
    assert 'Test content' in pytest.shared_result.output


@then('I should see the decrypted content')
def decrypted_content():
    assert 'Secret content' in pytest.shared_result.output


@then('I should see an error message about incorrect key')
def wrong_key_error():
    assert pytest.shared_result.exit_code != 0
    assert 'incorrect' in pytest.shared_result.output.lower()


@then('I should see an error message about note not found')
def note_not_found():
    assert 'not found' in pytest.shared_result.output.lower()


@then('the note should be updated successfully')
def note_updated():
    assert pytest.shared_result.exit_code == 0
    assert 'updated' in pytest.shared_result.output.lower()


@then('the note should be deleted successfully')
def note_deleted():
    assert pytest.shared_result.exit_code == 0
    assert 'deleted' in pytest.shared_result.output.lower()


@then('no notes should remain')
def no_notes_remain(cli_app):
    list_result = cli_app(['list'])
    assert 'No notes found' in list_result.output


@then('the note should still exist')
def note_still_exists(cli_app):
    list_result = cli_app(['list'])
    assert '[Encrypted Note]' in list_result.output


@then(parsers.parse('the note "{title}" should contain "{expected_content}"'))
def note_content_check(cli_app, title, expected_content):
    note_id = _resolve_note_ref(title)
    result = cli_app(['get', note_id])
    assert result.exit_code == 0
    assert expected_content in result.output


@then(parsers.parse('the note "{title}" should contain "{expected_content}" with passphrase "{password}"'))
def note_content_check_encrypted(cli_app, title, expected_content, password):
    note_id = _resolve_note_ref(title)
    result = cli_app(['get', note_id], input=f'{password}\n')
    assert result.exit_code == 0
    assert expected_content in result.output