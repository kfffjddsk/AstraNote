Feature: Audit log
  As a user I want an append-only audit trail of security operations
  so that I can review what happened to my notes.

  Refs: [BL B-25, B-71] [REQ R8]

  Scenario: Audit log records an operation
    Given a fresh audit logger
    When I log a "login" operation with outcome "success"
    Then the audit log has 1 entry
    And the audit entry has operation "login"
    And the audit entry has outcome "success"

  Scenario: Audit log can be filtered by operation
    Given a fresh audit logger
    When I log a "login" operation with outcome "success"
    And I log a "encrypt" operation with outcome "success"
    And I log a "login" operation with outcome "failure"
    Then reading the audit log filtered by "login" returns 2 entries

  Scenario: Audit log missing file returns empty list
    Given a fresh audit logger
    Then reading the audit log returns 0 entries

  Scenario: Audit log limit returns last N entries
    Given a fresh audit logger
    When I log a "login" operation with outcome "success"
    And I log a "encrypt" operation with outcome "success"
    And I log a "decrypt" operation with outcome "success"
    Then reading the audit log with limit 2 returns 2 entries
    And the first limited entry has operation "encrypt"
