Feature: Delete notes from the store
  As a user I want to delete notes so that I can remove information I no longer need.

  Scenario: Delete an unencrypted note
    Given an empty note store
    And a plain note exists with title "My Note" and content "Body"
    When I delete the note
    Then the note no longer exists in the store

  Scenario: Delete a non-existent note raises KeyError
    Given an empty note store
    When I try to delete a note with ID "ghost-id"
    Then a KeyError is raised

  Scenario: Delete an encrypted note
    Given an empty note store
    And an encrypted note exists with title "Secret" content "Private" passphrase "SecretPass1"
    When I delete the note
    Then the note no longer exists in the store

  Scenario: Deleting a plain note preserves a co-stored encrypted note
    Given an empty note store
    And a plain note exists with title "Plain" and content "Hello"
    And an encrypted note exists with title "Secret" content "Private" passphrase "SecretPass1"
    When I delete the plain note
    Then the encrypted note still exists in the store
