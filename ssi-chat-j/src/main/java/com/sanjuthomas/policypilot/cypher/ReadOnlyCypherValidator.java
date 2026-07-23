package com.sanjuthomas.policypilot.cypher;

import com.sanjuthomas.policypilot.cypher.GraphPlanModels.ValidateResult;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Multi-layer read-only Cypher guard (parity with Python {@code validate_read_only_cypher} /
 * {@code normalize_read_only_cypher}).
 */
public final class ReadOnlyCypherValidator {

  private static final int MAX_CYPHER_LEN = 4096;
  private static final Pattern LINE_COMMENT = Pattern.compile("//[^\\n]*", Pattern.MULTILINE);
  private static final Pattern BLOCK_COMMENT = Pattern.compile("/\\*.*?\\*/", Pattern.DOTALL);
  private static final Pattern STRING_LITERAL =
      Pattern.compile("'(?:[^'\\\\]|\\\\.)*'|\"(?:[^\"\\\\]|\\\\.)*\"");
  private static final Pattern WRITE_KEYWORD =
      Pattern.compile(
          "\\b(CREATE|MERGE|SET|DELETE|REMOVE|DROP|DETACH|FOREACH|LOAD)\\b",
          Pattern.CASE_INSENSITIVE);
  private static final Pattern WRITE_PROCEDURE =
      Pattern.compile(
          "\\bCALL\\s+(db\\.\\w+|apoc\\.create\\.|apoc\\.periodic\\.|apoc\\.merge\\.|apoc\\.refactor\\.)",
          Pattern.CASE_INSENSITIVE);
  private static final Pattern READ_START =
      Pattern.compile(
          "^\\s*(MATCH|OPTIONAL\\s+MATCH|WITH|RETURN|UNWIND)\\b", Pattern.CASE_INSENSITIVE);
  private static final Pattern LIMIT_CLAUSE =
      Pattern.compile("\\bLIMIT\\s+\\d+\\b", Pattern.CASE_INSENSITIVE);
  private static final Pattern AGGREGATE_RETURN =
      Pattern.compile(
          "\\bRETURN\\b[\\s\\S]*\\b(count|sum|avg|min|max|collect)\\s*\\(",
          Pattern.CASE_INSENSITIVE);

  private ReadOnlyCypherValidator() {}

  public static ValidateResult validate(String cypher) {
    try {
      validateOrThrow(cypher);
      return ValidateResult.ok(normalize(cypher));
    } catch (IllegalArgumentException ex) {
      return ValidateResult.fail(ex.getMessage());
    }
  }

  static void validateOrThrow(String cypher) {
    String stripped = cypher == null ? "" : cypher.strip();
    if (stripped.isEmpty()) {
      throw new IllegalArgumentException("Cypher validation failed: empty query");
    }
    if (stripped.length() > MAX_CYPHER_LEN) {
      throw new IllegalArgumentException(
          "Cypher validation failed: query exceeds " + MAX_CYPHER_LEN + " characters");
    }
    String withoutTrailing = stripped.replaceAll(";+\\s*$", "");
    if (withoutTrailing.contains(";")) {
      throw new IllegalArgumentException(
          "Cypher validation failed: multiple statements are not allowed");
    }
    String noStrings = stripLiterals(stripped);
    if (!READ_START.matcher(noStrings).find()) {
      throw new IllegalArgumentException(
          "Cypher validation failed: query must begin with "
              + "MATCH, OPTIONAL MATCH, WITH, RETURN, or UNWIND");
    }
    Matcher write = WRITE_KEYWORD.matcher(noStrings);
    if (write.find()) {
      throw new IllegalArgumentException(
          "Cypher validation failed: disallowed write keyword '"
              + write.group(0).toUpperCase()
              + "'");
    }
    if (WRITE_PROCEDURE.matcher(noStrings).find()) {
      throw new IllegalArgumentException(
          "Cypher validation failed: CALL to a write-capable procedure is not allowed");
    }
    if (!LIMIT_CLAUSE.matcher(noStrings).find()) {
      throw new IllegalArgumentException(
          "Cypher validation failed: query must include a LIMIT clause");
    }
  }

  static String normalize(String cypher) {
    String stripped = cypher == null ? "" : cypher.strip();
    if (stripped.isEmpty()) {
      return stripped;
    }
    String noStrings = stripLiterals(stripped);
    if (LIMIT_CLAUSE.matcher(noStrings).find()) {
      return stripped;
    }
    if (AGGREGATE_RETURN.matcher(noStrings).find()) {
      return stripped.replaceAll(";+\\s*$", "") + "\nLIMIT 1";
    }
    return stripped;
  }

  private static String stripLiterals(String cypher) {
    String normalized = LINE_COMMENT.matcher(cypher).replaceAll("");
    normalized = BLOCK_COMMENT.matcher(normalized).replaceAll("");
    return STRING_LITERAL.matcher(normalized).replaceAll("''");
  }
}
