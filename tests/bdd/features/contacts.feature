Feature: Contact management
  The artist manages gallery contacts and tracks outreach history.

  Scenario: Contact list is empty
    Given there are no contacts in the system
    When the artist lists contacts
    Then the output contains "No contacts found"

  Scenario: Contact list shows name, city, and type
    Given a gallery contact exists
    When the artist lists contacts
    Then the output contains "Galerie Stern"
    And the output contains "Augsburg"
    And the output contains "gallery"

  Scenario: Viewing an unknown contact
    Given there are no contacts in the system
    When the artist views contact 99
    Then the output contains "not found"

  Scenario: Viewing a contact shows full record with no history
    Given a gallery contact exists
    When the artist views contact 1
    Then the output contains "Galerie Stern"
    And the output contains "No interactions yet"
