package com.sanjuthomas.policypilot.observability;

import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.spi.LoggingEventBuilder;

/**
 * Structured log helper — event name as message, fields as SLF4J key-value pairs (captured by the
 * OpenTelemetry Logback appender → Loki) and as a compact key=value suffix for plain consoles.
 */
public final class StructuredLog {

  private StructuredLog() {}

  public static void info(Logger log, String event, Map<String, ?> fields) {
    emit(log.atInfo(), event, fields);
  }

  public static void warn(Logger log, String event, Map<String, ?> fields) {
    emit(log.atWarn(), event, fields);
  }

  public static void debug(Logger log, String event, Map<String, ?> fields) {
    if (!log.isDebugEnabled()) {
      return;
    }
    emit(log.atDebug(), event, fields);
  }

  private static void emit(LoggingEventBuilder builder, String event, Map<String, ?> fields) {
    StringBuilder message = new StringBuilder(event == null ? "event" : event);
    if (fields != null) {
      for (Map.Entry<String, ?> entry : fields.entrySet()) {
        if (entry.getKey() == null || entry.getValue() == null) {
          continue;
        }
        String key = entry.getKey();
        Object value = entry.getValue();
        builder = builder.addKeyValue(key, value);
        if (!"chat.event".equals(key)) {
          message.append(' ').append(key).append('=').append(value);
        }
      }
    }
    builder.log(message.toString());
  }
}
