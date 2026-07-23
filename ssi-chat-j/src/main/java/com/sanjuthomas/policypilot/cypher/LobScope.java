package com.sanjuthomas.policypilot.cypher;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Subject + question LOB constraints for planned Cypher ({@code alias.owning_lob}), parity with
 * Python {@code cypher_builder.lob_scope.owning_lob_and_clause}.
 */
public final class LobScope {

  private static final Pattern ALIAS = Pattern.compile("^[A-Za-z_][A-Za-z0-9_]*$");
  private static final Pattern LOB_NAME = Pattern.compile("^[A-Z][A-Z0-9_]*$");
  private static final Pattern NAMED_LOB =
      Pattern.compile(
          "\\b(?:lob\\s+|desk\\s+lob\\s+|for\\s+|payments?\\s+for\\s+)?"
              + "(FICC|FX|DESK_[A-Z][A-Z0-9_]*)\\b",
          Pattern.CASE_INSENSITIVE);

  private LobScope() {}

  /**
   * @param allowedLobs {@code null} = unscoped (compliance); empty = deny; non-empty = FO/MO
   */
  public static String owningLobAndClause(String alias, String question, Set<String> allowedLobs) {
    if (!ALIAS.matcher(alias).matches()) {
      throw new IllegalArgumentException("invalid Cypher alias for LOB scope: " + alias);
    }
    String named = namedLobFromQuestion(question);
    if (named != null && !LOB_NAME.matcher(named).matches()) {
      return " AND false";
    }

    if (allowedLobs == null) {
      if (named != null) {
        return " AND " + alias + ".owning_lob = '" + escape(named) + "'";
      }
      return "";
    }

    if (allowedLobs.isEmpty()) {
      return " AND false";
    }

    if (named != null) {
      if (!allowedLobs.contains(named)) {
        return " AND false";
      }
      return " AND " + alias + ".owning_lob = '" + escape(named) + "'";
    }

    List<String> ordered = new ArrayList<>();
    for (String lob : allowedLobs) {
      if (lob != null) {
        String upper = lob.strip().toUpperCase(Locale.ROOT);
        if (LOB_NAME.matcher(upper).matches()) {
          ordered.add(upper);
        }
      }
    }
    ordered.sort(String::compareTo);
    if (ordered.isEmpty()) {
      return " AND false";
    }
    if (ordered.size() == 1) {
      return " AND " + alias + ".owning_lob = '" + escape(ordered.get(0)) + "'";
    }
    StringBuilder listed = new StringBuilder();
    for (int i = 0; i < ordered.size(); i++) {
      if (i > 0) {
        listed.append(", ");
      }
      listed.append('\'').append(escape(ordered.get(i))).append('\'');
    }
    return " AND " + alias + ".owning_lob IN [" + listed + "]";
  }

  static String namedLobFromQuestion(String question) {
    if (question == null || question.isBlank()) {
      return null;
    }
    Matcher match = NAMED_LOB.matcher(question);
    return match.find() ? match.group(1).toUpperCase(Locale.ROOT) : null;
  }

  static String escape(String value) {
    return value.replace("\\", "\\\\").replace("'", "\\'");
  }
}
