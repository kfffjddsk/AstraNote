Feature: Update notes in the store
  As a user I want to update notes so that I can keep my information current.

  Scenario: Update an unencrypted note
    Given an empty note store
    And a plain note exists with title "Old Title" and content "Old Body"
    When I update the note with title "New Title" and content "New Body"
    Then the updated note has title "New Title"
    And the updated note has content "New Body"

  Scenario: Update a non-existent note raises KeyError
    Given an empty note store
    When I try to update a note with ID "ghost-id"
    Then a KeyError is raised

  Scenario: Unencrypted update does not corrupt a co-stored encrypted note
    Given an empty note store
    And a plain note exists with title "Plain" and content "Readable"
    And an encrypted note exists with title "Secret" content "Private" passphrase "SecretPass1"
    When I update the plain note with title "Updated" and content "Updated body"
    Then the encrypted note blob is unchanged
    And the plain note has title "Updated"

  Scenario: Update encrypted note replaces blob
    Given an empty note store
    And an encrypted note exists with title "Secret" content "Original text" passphrase "SecretPass1"
    When I re-encrypt the note with content "Updated text" using passphrase "SecretPass1"
    Then the encrypted note can be decrypted to "Updated text" with passphrase "SecretPass1"
