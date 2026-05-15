Feature: List notes from the store
  As a user I want to list notes so that I can see my saved information without
  being prompted for a passphrase.

  Scenario: List notes with mixed encryption
    Given an empty note store
    And a plain note exists with title "Plain Note" and content "Readable"
    And an encrypted note exists with title "Secret" content "Private" passphrase "SecretPass1"
    When I list all notes
    Then there are 2 notes in the local list
    And one note has title "Plain Note"
    And one note has title "[Encrypted Note]"
    And no note in the list has non-empty content

  Scenario: List an empty store
    Given an empty note store
    When I list all notes
    Then there are 0 notes in the local list
