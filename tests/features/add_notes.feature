Feature: Adding Notes
  As a user
  I want to add notes with optional encryption
  So that I can store my information securely or simply

  Scenario: Add an unencrypted note
    When I run the add command without encryption
    Then the note should be added successfully
    And I should see a confirmation message
    And I should not be prompted for a passphrase

  Scenario: Add an encrypted note
    When I run the add command with encryption
    Then the note should be added successfully
    And I should see a confirmation message
    And I should be prompted for a passphrase

  Scenario: Add note with invalid input
    When I run the add command with invalid data
    Then I should see an error message
    And no note should be stored