Feature: Show management
  The artist tracks the exhibition pipeline and upcoming shows.

  Scenario: No shows exist
    Given there are no shows scheduled
    When the artist lists shows
    Then the output contains "No shows found"

  Scenario: Upcoming shows are displayed
    Given a confirmed show exists in München
    When the artist lists upcoming shows
    Then the output contains "Frühjahrsausstellung"
    And the output contains "confirmed"
