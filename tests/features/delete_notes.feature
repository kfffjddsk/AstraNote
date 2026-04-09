Feature: Deleting Notes
  As a user
  I want to delete notes I no longer need
  So that I can clean up my storage

  Scenario: Delete an unencrypted note
    Given I have an unencrypted note with title "To Delete"
    When I run the delete command for "To Delete"
    Then the note should be deleted successfully
    And I should not be prompted for a passphrase
    And no notes should remain

  Scenario: Delete an encrypted note with correct passphrase
    Given I have an encrypted note with title "Secret Delete"
    When I run the delete command for "Secret Delete" with passphrase "correctpass"
    Then the note should be deleted successfully
    And I should be prompted for a passphrase
    And no notes should remain

  Scenario: Delete an encrypted note with wrong passphrase
    Given I have an encrypted note with title "Secret Keep"
    When I run the delete command for "Secret Keep" with passphrase "wrongpass"
    Then I should see an error message about incorrect key
    And the note should still exist

  Scenario: Delete a non-existent note
    Given I have no note with title "Not There"
    When I run the delete command for "Not There"
    Then I should see an error message