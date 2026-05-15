Feature: Retrieve notes from the store
  As a user I want to retrieve notes by ID so that I can read my saved information.

  Scenario: Get an unencrypted note by ID
    Given an empty note store
    And a plain note exists with title "My Note" and content "Hello"
    When I retrieve the note by its ID
    Then the retrieved title is "My Note"
    And the retrieved content is "Hello"

  Scenario: Get an encrypted note with the correct passphrase
    Given an empty note store
    And an encrypted note exists with title "Secret" content "Private data" passphrase "SecretPass1"
    When I retrieve the note by its ID
    And I decrypt the blob with passphrase "SecretPass1"
    Then the decrypted content is "Private data"

  Scenario: Wrong passphrase raises InvalidTag
    Given an empty note store
    And an encrypted note exists with title "Secret" content "Private data" passphrase "SecretPass1"
    When I retrieve the note by its ID
    And I try to decrypt the blob with passphrase "WrongPass999"
    Then an InvalidTag error is raised

  Scenario: Get a non-existent note returns None
    Given an empty note store
    When I retrieve a note with ID "does-not-exist"
    Then the result is None
