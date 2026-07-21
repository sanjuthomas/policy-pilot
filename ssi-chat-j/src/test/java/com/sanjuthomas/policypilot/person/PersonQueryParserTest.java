package com.sanjuthomas.policypilot.person;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

import org.junit.jupiter.api.Test;

class PersonQueryParserTest {

  @Test
  void extractsDisplayName() {
    assertEquals(
        "Kowalski, Anna",
        PersonQueryParser.extract("Can you list the permissions of Kowalski, Anna?"));
  }

  @Test
  void extractsUserId() {
    assertEquals("pay-203", PersonQueryParser.extract("Summarize permissions for pay-203"));
  }

  @Test
  void extractsWhatCanDo() {
    assertEquals("Kowalski, Anna", PersonQueryParser.extract("What can Kowalski, Anna do?"));
  }

  @Test
  void skipsWhoListQuestions() {
    assertNull(
        PersonQueryParser.extract("Who has permission to approve payments for LOB FICC?"));
  }
}
