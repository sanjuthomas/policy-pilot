package com.sanjuthomas.policypilot.person;

import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.springframework.util.StringUtils;

/**
 * Slot fallback for {@code person_permissions} when the router omits {@code personQuery}.
 * Prefer the LLM {@code personQuery} slot; this extractor is resilience-only (not path NLU).
 */
public final class PersonQueryParser {

  private static final Pattern WHO_LIST =
      Pattern.compile("\\b(who|which\\s+users?)\\b", Pattern.CASE_INSENSITIVE);

  private static final Pattern PERSON_QUERY =
      Pattern.compile(
          "(?:"
              + "(?:list|show|summarize|summary|tell\\s+me|what\\s+are)\\s+(?:the\\s+)?"
              + "permissions?\\s+(?:of|for)\\s+"
              + "|"
              + "permissions?\\s+(?:of|for)\\s+"
              + "|"
              + "what\\s+can\\s+"
              + ")"
              + "(.+?)"
              + "(?:\\s+do\\b)?\\s*[?.!]?\\s*$",
          Pattern.CASE_INSENSITIVE);

  private static final Pattern TRAILING_NOISE =
      Pattern.compile("\\b(can\\s+you|please|could\\s+you)\\b", Pattern.CASE_INSENSITIVE);

  private static final Pattern LEADING_PLEASE =
      Pattern.compile("^(?:can\\s+you|please|could\\s+you)\\s+", Pattern.CASE_INSENSITIVE);

  private static final Pattern POLICY_NOISE =
      Pattern.compile(
          "\\b(policy|approval|funding|payment|instruction)\\b", Pattern.CASE_INSENSITIVE);

  private PersonQueryParser() {}

  public static String extract(String message) {
    if (!StringUtils.hasText(message)) {
      return null;
    }
    String text = message.strip().replaceAll("\\s+", " ");
    if (WHO_LIST.matcher(text).find()) {
      return null;
    }
    Matcher match = PERSON_QUERY.matcher(text);
    if (!match.find()) {
      return null;
    }
    String person = match.group(1).strip().replaceAll("^[ \\t\"'`]+|[ \\t\"'`]+$", "");
    person = TRAILING_NOISE.matcher(person).replaceAll("").strip().replaceAll("^[,\\s]+|[,\\s]+$", "");
    person = LEADING_PLEASE.matcher(person).replaceFirst("").strip().replaceAll("^[,\\s]+|[,\\s]+$", "");
    if (person.length() < 2) {
      return null;
    }
    if (POLICY_NOISE.matcher(person).find()) {
      return null;
    }
    return person;
  }
}
