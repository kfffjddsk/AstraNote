Feature: Re-encrypt a note
  As a user I want to change the passphrase on an encrypted note
  so that I can rotate credentials without losing data.

  Refs: [BL B-62] [REQ R2.14]

  Background:
    Given an empty note store

  Scenario: Re-encrypt an encrypted note with a new passphrase
    Given an encrypted note exists with title "[Encrypted Note]" content "Top secret data" passphrase "OldPass123!"
    When I re-encrypt the note from passphrase "OldPass123!" to passphrase "NewPass456!"
    Then decrypting the note with passphrase "NewPass456!" succeeds
    And decrypting the note with passphrase "OldPass123!" fails

  Scenario: Re-encrypting preserves the original content
    Given an encrypted note exists with title "[Encrypted Note]" content "Preserved content" passphrase "FirstPass1!"
    When I re-encrypt the note from passphrase "FirstPass1!" to passphrase "SecondPass2!"
    Then the decrypted content after re-encryption with "SecondPass2!" equals "Preserved content"
