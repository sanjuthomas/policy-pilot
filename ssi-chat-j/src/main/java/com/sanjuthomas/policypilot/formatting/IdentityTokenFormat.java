package com.sanjuthomas.policypilot.formatting;

import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.springframework.stereotype.Component;

/**
 * Backtick SCREAMING_SNAKE identity tokens (roles / groups / clubs) for markdown-safe display —
 * parity with Python {@code format_identity_token*} helpers.
 */
@Component
public class IdentityTokenFormat {

  private static final Pattern IDENTITY_TOKEN =
      Pattern.compile("\\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\\b");
  private static final Pattern CODE_SPAN = Pattern.compile("`[^`]+`");
  private static final String CODE_SLOT_PREFIX = "\0IDCODE";
  private static final String CODE_SLOT_SUFFIX = "\0";

  public String formatToken(String name) {
    String token = name == null ? "" : name.strip();
    if (token.isEmpty()) {
      return token;
    }
    if (token.startsWith("`") && token.endsWith("`") && token.chars().filter(c -> c == '`').count() == 2) {
      return token;
    }
    if (IDENTITY_TOKEN.matcher(token).matches()) {
      return "`" + token + "`";
    }
    return token;
  }

  /** Join identity tokens with markdown-safe backticks (comma-separated). */
  public String formatTokenList(List<String> names) {
    return formatTokenList(names, "—");
  }

  public String formatTokenList(List<String> names, String empty) {
    if (names == null || names.isEmpty()) {
      return empty;
    }
    List<String> parts = new ArrayList<>();
    for (String name : names) {
      if (name == null || name.isBlank()) {
        continue;
      }
      parts.add(formatToken(name));
    }
    return parts.isEmpty() ? empty : String.join(", ", parts);
  }

  public String formatTokensInText(String text) {
    if (text == null || text.isEmpty()) {
      return text;
    }
    List<String> slots = new ArrayList<>();
    Matcher codeMatcher = CODE_SPAN.matcher(text);
    StringBuffer protectedBuf = new StringBuffer();
    while (codeMatcher.find()) {
      String slot = CODE_SLOT_PREFIX + slots.size() + CODE_SLOT_SUFFIX;
      slots.add(codeMatcher.group());
      codeMatcher.appendReplacement(protectedBuf, Matcher.quoteReplacement(slot));
    }
    codeMatcher.appendTail(protectedBuf);

    Matcher tokenMatcher = IDENTITY_TOKEN.matcher(protectedBuf.toString());
    StringBuffer wrapped = new StringBuffer();
    while (tokenMatcher.find()) {
      tokenMatcher.appendReplacement(
          wrapped, Matcher.quoteReplacement("`" + tokenMatcher.group() + "`"));
    }
    tokenMatcher.appendTail(wrapped);

    String out = wrapped.toString();
    for (int i = 0; i < slots.size(); i++) {
      out = out.replace(CODE_SLOT_PREFIX + i + CODE_SLOT_SUFFIX, slots.get(i));
    }
    return out;
  }
}
