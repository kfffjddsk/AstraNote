Feature: Search notes
  As a user I want to search notes by title and content
  so that I can quickly find the information I need.

  Refs: [BL B-29] [REQ R10.1–R10.3]

  Background:
    Given an empty note store

  Scenario: Search finds a plain note by content
    Given a plain note exists with title "Meeting Notes" and content "Discuss project timeline"
    When I search for "timeline"
    Then 1 search result is returned
    And the first search result has title "Meeting Notes"

  Scenario: Search finds a plain note by title
    Given a plain note exists with title "Shopping List" and content "Apples and Oranges"
    When I search for "Shopping"
    Then 1 search result is returned
    And the first search result has title "Shopping List"

  Scenario: Search is case-insensitive
    Given a plain note exists with title "Random Thought" and content "The sky is Blue today"
    When I search for "blue"
    Then 1 search result is returned

  Scenario: Search with no matches returns empty
    Given a plain note exists with title "Hello World" and content "Some content here"
    When I search for "xyz_absolutely_not_present"
    Then 0 search results are returned

  Scenario: Encrypted notes excluded from default search
    Given an encrypted note exists with title "[Encrypted Note]" content "Hidden secret" passphrase "Pass1234!"
    When I search for "Hidden"
    Then 0 search results are returned

  Scenario: Encrypted note alias is always searchable without a passphrase
    Given an encrypted note exists with alias "Budget Meeting" title "Real Confidential Title" content "Private figures" passphrase "Pass1234!"
    When I search for "Budget"
    Then 1 search result is returned
    And the first search result has title "Budget Meeting"

  Scenario: Alias shown in results, not the real encrypted title
    Given an encrypted note exists with alias "Q3 Planning" title "Hidden Real Title" content "Private content" passphrase "Pass1234!"
    When I search for "Q3"
    Then 1 search result is returned
    And the first search result has title "Q3 Planning"
