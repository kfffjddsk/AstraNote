Feature: Listing Notes
  As a user
  I want to list my notes
  So that I can see what notes I have

  Scenario: List all notes with mixed encryption
    Given I have added several notes some encrypted some not
    When I run the list command
    Then I should see all unencrypted notes with full details
    And encrypted notes should show only titles with encryption indicator
    And I should not be prompted for a passphrase

  Scenario: List notes when no notes exist
    Given I have no notes stored
    When I run the list command
    Then I should see a message indicating no notes found