package com.sanjuthomas.policypilot.routing;

import java.util.Optional;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Slot parsing only — extract a covering desk LOB from free text (parity with Python {@code
 * lob_filter_from_question}).
 */
public final class LobFilterParser {

  private static final Pattern LOB_FILTER =
      Pattern.compile(
          "\\b(?:lob\\s+|desk\\s+lob\\s+|for\\s+|payments?\\s+for\\s+)?"
              + "(FICC|FX|DESK_[A-Z][A-Z0-9_]*)\\b",
          Pattern.CASE_INSENSITIVE);

  private LobFilterParser() {}

  public static Optional<String> extract(String question) {
    if (question == null || question.isBlank()) {
      return Optional.empty();
    }
    Matcher match = LOB_FILTER.matcher(question);
    if (!match.find()) {
      return Optional.empty();
    }
    return Optional.of(match.group(1).toUpperCase());
  }
}
