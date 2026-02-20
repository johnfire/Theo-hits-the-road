Feature: Outreach follow-up
  The artist identifies contacts needing attention and reviews AI recommendations.

  Scenario: No contacts are overdue
    Given there are no overdue contacts
    When the artist checks overdue contacts
    Then the output contains "all caught up"

  Scenario: Overdue contacts are listed
    Given a gallery contact has an overdue follow-up
    When the artist checks overdue contacts
    Then the output contains "Galerie Stern"

  Scenario: No contacts are dormant
    Given there are no dormant contacts
    When the artist checks dormant contacts
    Then the output contains "No dormant contacts"

  Scenario: AI daily brief is displayed
    Given the AI returns a brief recommendation
    When the artist requests the daily brief
    Then the output contains "Contact Galerie Stern this week"
