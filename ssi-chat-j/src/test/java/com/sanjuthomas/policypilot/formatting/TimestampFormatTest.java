package com.sanjuthomas.policypilot.formatting;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;

import java.time.Instant;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.time.format.FormatStyle;
import java.util.Locale;
import org.junit.jupiter.api.Test;

class TimestampFormatTest {

  private final TimestampFormat timestamps = new TimestampFormat();

  @Test
  void formatsUtcZToSystemLocal() {
    String expected =
        DateTimeFormatter.ofLocalizedDateTime(FormatStyle.MEDIUM)
            .withLocale(Locale.getDefault())
            .withZone(ZoneId.systemDefault())
            .format(Instant.parse("2026-07-17T10:00:00Z"));
    assertEquals(expected, timestamps.formatLocal("2026-07-17T10:00:00Z"));
    assertFalse(expected.contains("T10:00:00"));
  }

  @Test
  void formatsPaymentAwareIsoWithRedundantZ() {
    // payment-service: datetime.now(UTC).isoformat() + "Z"
    String raw = "2026-07-17T10:00:00.123456+00:00Z";
    String expected =
        DateTimeFormatter.ofLocalizedDateTime(FormatStyle.MEDIUM)
            .withLocale(Locale.getDefault())
            .withZone(ZoneId.systemDefault())
            .format(Instant.parse("2026-07-17T10:00:00.123456Z"));
    assertEquals(expected, timestamps.formatLocal(raw));
    assertFalse(timestamps.formatLocal(raw).contains("+00:00"));
  }

  @Test
  void treatsNaiveIsoAsUtc() {
    String withZ = timestamps.formatLocal("2026-07-17T10:00:00Z");
    String naive = timestamps.formatLocal("2026-07-17T10:00:00");
    assertEquals(withZ, naive);
  }

  @Test
  void blankReturnsNull() {
    assertNull(timestamps.formatLocal(null));
    assertNull(timestamps.formatLocal(""));
    assertNull(timestamps.formatLocal("   "));
  }

  @Test
  void unparseableReturnsOriginal() {
    assertEquals("not-a-date", timestamps.formatLocal("not-a-date"));
  }
}
