package com.sanjuthomas.policypilot.formatting;

import java.time.DateTimeException;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.time.format.FormatStyle;
import java.util.Locale;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

/**
 * Formats API timestamps (UTC ISO-8601) for chat prose in the JVM default timezone / locale.
 *
 * <p>Payment-service appends {@code Z} even when {@code isoformat()} already includes {@code
 * +00:00} (aware UTC), producing {@code ...+00:00Z} — that form is normalized here.
 */
@Component
public class TimestampFormat {

  /**
   * Human-readable local datetime, e.g. {@code Jul 17, 2026, 6:00:00 AM EDT}. Returns null when
   * input is blank; returns the original string when parsing fails.
   */
  public String formatLocal(Object value) {
    if (value == null) {
      return null;
    }
    if (value instanceof Instant instant) {
      return formatInstant(instant);
    }
    String raw = String.valueOf(value).strip();
    if (!StringUtils.hasText(raw)) {
      return null;
    }
    try {
      return formatInstant(toInstant(raw));
    } catch (DateTimeException ex) {
      return raw;
    }
  }

  private static String formatInstant(Instant instant) {
    ZoneId zone = ZoneId.systemDefault();
    ZonedDateTime local = instant.atZone(zone);
    return DateTimeFormatter.ofLocalizedDateTime(FormatStyle.MEDIUM)
        .withLocale(Locale.getDefault())
        .withZone(zone)
        .format(local);
  }

  static Instant toInstant(String raw) {
    String text = normalizeApiTimestamp(raw.strip());
    try {
      return Instant.parse(text);
    } catch (DateTimeParseException ignored) {
      // fall through
    }
    try {
      return OffsetDateTime.parse(text).toInstant();
    } catch (DateTimeParseException ignored) {
      // fall through
    }
    // Naive ISO — treat as UTC (instruction-service utcnow path).
    LocalDateTime local = LocalDateTime.parse(text);
    return local.toInstant(ZoneOffset.UTC);
  }

  /**
   * Normalize quirky API forms: {@code 2026-07-17T10:00:00+00:00Z} → {@code
   * 2026-07-17T10:00:00+00:00}.
   */
  static String normalizeApiTimestamp(String text) {
    // Offset already present; trailing Z is redundant / invalid.
    if (text.endsWith("Z") && text.length() > 1) {
      String withoutZ = text.substring(0, text.length() - 1);
      if (withoutZ.indexOf('+', 10) >= 0
          || withoutZ.lastIndexOf('-') > withoutZ.indexOf('T')) {
        return withoutZ;
      }
    }
    return text;
  }
}
