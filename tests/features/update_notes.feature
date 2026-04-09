Feature: Updating Notes
  As a user
  I want to update existing notes
  So that I can modify my stored information

  Scenario: Update an unencrypted note
    Given I have an unencrypted note with title "Old Note"
    When I run the update command for "Old Note" with new content
    Then the note should be updated successfully
    And I should not be prompted for a passphrase
    And the note "Old Note" should contain "Updated content"

  Scenario: Update an encrypted note
    Given I have an encrypted note with title "Secret Note"
    When I run the update command for "Secret Note" with passphrase "correctpass"
    Then the note should be updated successfully
    And I should be prompted for a passphrase
    And the note "Secret Note" should contain "Updated content" with passphrase "correctpass"

  Scenario: Update an encrypted note with wrong passphrase
    Given I have an encrypted note with title "Locked"
    When I run the update command for "Locked" with passphrase "wrongpass"
    Then I should see an error message about incorrect key
    And the note "Locked" should contain "Secret content" with passphrase "correctpass"

  Scenario: Update a non-existent note
    Given I have no note with title "Ghost"
    When I run the update command for "Ghost" with new content
    Then I should see an error message