Feature: Getting Notes
  As a user
  I want to retrieve specific notes
  So that I can read my stored information

  Scenario: Get an unencrypted note
    Given I have an unencrypted note with title "My Note"
    When I run the get command for "My Note"
    Then I should see the full content of the note
    And I should not be prompted for a passphrase

  Scenario: Get an encrypted note with correct passphrase
    Given I have an encrypted note with title "Secret"
    When I run the get command for "Secret" with passphrase "correctpass"
    Then I should see the decrypted content
    And I should be prompted for a passphrase

  Scenario: Get an encrypted note with wrong passphrase
    Given I have an encrypted note with title "Secret"
    When I run the get command for "Secret" with passphrase "wrongpass"
    Then I should see an error message about incorrect key

  Scenario: Get a non-existent note
    Given I have no note with title "Missing"
    When I run the get command for "Missing"
    Then I should see an error message about note not found