Feature: Add notes to the store
  As a user I want to add notes so that I can save information.

  Background:
    Given an empty note store

  Scenario: Add an unencrypted note
    When I add a note with title "My Note" and content "Hello World"
    Then the note with title "My Note" exists in the store
    And the stored content is "Hello World"

  Scenario: Add an encrypted note
    When I add an encrypted note titled "Secret" with content "Top secret" and passphrase "SecretPass1"
    Then an encrypted note with alias "[Encrypted Note]" exists in the store
    And the encrypted note has a non-empty blob

  Scenario: Reject a note with an empty title
    When I try to create a note with title "" and content "Some content"
    Then a ValueError is raised
