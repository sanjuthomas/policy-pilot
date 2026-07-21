package com.sanjuthomas.policypilot.formatting;

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
 * Formats API timestamps (UTC ISO-8601, often with trailing {@code Z}) for chat prose in the JVM
 * default timezone / locale.
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
    String raw = String.valueOf(value).strip();
    if (!StringUtils.hasText(raw)) {
      return null;
    }
    try {
      Instant instant = toInstant(raw);
      ZonedDateTime local = instant.atZone(ZoneId.systemDefault());
      return DateTimeFormatter.ofLocalizedDateTime(FormatStyle.MEDIUM)
          .withLocale(Locale.getDefault())
          .withZone(ZoneId.systemDefault())
          .format(local);
    } catch (DateTimeParseException ex) {
      return raw;
    }
  }

  static Instant toInstant(String raw) {
    String text = raw.strip();
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
    // API sometimes omits zone; timestamps are UTC (isoformat + "Z" path may drop Z in tests).
    LocalDateTime local = LocalDateTime.parse(text);
    return local.toInstant(ZoneOffset.UTC);
  }
}
