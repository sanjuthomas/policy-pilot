package com.sanjuthomas.policypilot.formatting;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;
import org.springframework.stereotype.Component;

/** Humanize OPA allow_basis / authorization text — called from Thymeleaf and formatters. */
@Component
public class PolicyBasisFormat {

  private static final Pattern AMOUNT_IN_BASIS =
      Pattern.compile("(?i)amount\\s+([\\d.eE+-]+)\\s+(within subject and absolute limits)");
  private static final ObjectMapper JSON = new ObjectMapper();

  public String humanizePoint(String point) {
    if (point == null || point.isBlank()) {
      return point;
    }
    Matcher matcher = AMOUNT_IN_BASIS.matcher(point);
    StringBuffer out = new StringBuffer();
    while (matcher.find()) {
      try {
        double amount = Double.parseDouble(matcher.group(1));
        String replacement = "amount " + formatUsdCompact(amount) + " " + matcher.group(2);
        matcher.appendReplacement(out, Matcher.quoteReplacement(replacement));
      } catch (NumberFormatException ex) {
        matcher.appendReplacement(out, Matcher.quoteReplacement(matcher.group(0)));
      }
    }
    matcher.appendTail(out);
    return out.toString();
  }

  /** Same amount humanization applied to a full authorization_summary string. */
  public String humanizeText(String text) {
    return humanizePoint(text);
  }

  public List<String> parseBasis(Object value) {
    if (value instanceof List<?> list) {
      List<String> out = new ArrayList<>();
      for (Object item : list) {
        if (item != null && !item.toString().isBlank()) {
          out.add(item.toString());
        }
      }
      return out;
    }
    if (value instanceof String text && !text.isBlank()) {
      try {
        List<String> parsed = JSON.readValue(text, new TypeReference<>() {});
        return parsed == null
            ? List.of()
            : parsed.stream().filter(s -> s != null && !s.isBlank()).toList();
      } catch (Exception ignored) {
        return List.of();
      }
    }
    return List.of();
  }

  public String formatBasisLine(List<String> basis) {
    if (basis == null || basis.isEmpty()) {
      return null;
    }
    String joined =
        basis.stream().map(this::humanizePoint).collect(Collectors.joining(" | "));
    return "BASIS: " + joined;
  }

  public boolean basisRedundantWithSummary(String summary, List<String> basis) {
    if (summary == null || summary.isBlank() || basis == null || basis.isEmpty()) {
      return false;
    }
    String summaryLower = summary.toLowerCase(Locale.ROOT);
    return basis.stream()
        .map(this::humanizePoint)
        .allMatch(point -> summaryLower.contains(point.toLowerCase(Locale.ROOT)));
  }

  /**
   * Build BASIS line(s) without repeating OPA checks already present in the summary (parity with
   * Python {@code format_approval_auth_lines}).
   */
  public List<String> formatApprovalAuthLines(String summary, Object basisRaw) {
    List<String> basis = parseBasis(basisRaw);
    String readableSummary =
        summary == null || summary.isBlank() ? null : humanizeText(summary.strip());
    boolean redundant = basisRedundantWithSummary(readableSummary, basis);
    List<String> lines = new ArrayList<>();
    if (readableSummary != null) {
      lines.add("BASIS: " + readableSummary);
    } else {
      String basisLine = formatBasisLine(basis);
      if (basisLine != null) {
        lines.add(basisLine);
      }
    }
    if (readableSummary != null && !basis.isEmpty() && !redundant) {
      String basisLine = formatBasisLine(basis);
      if (basisLine != null) {
        lines.add(basisLine);
      }
    }
    return lines;
  }

  static String formatUsdCompact(double amount) {
    double abs = Math.abs(amount);
    if (abs >= 1_000_000_000d) {
      double value = abs / 1_000_000_000d;
      if (value == Math.rint(value)) {
        return "$" + ((long) value) + " billion";
      }
      return "$" + trimOneDecimal(value) + " billion";
    }
    if (abs >= 1_000_000d) {
      double value = abs / 1_000_000d;
      if (value == Math.rint(value)) {
        return "$" + ((long) value) + " million";
      }
      return "$" + trimOneDecimal(value) + " million";
    }
    if (abs >= 1_000d) {
      return String.format("$%,.0f", abs);
    }
    if (abs == Math.rint(abs)) {
      return "$" + ((long) abs);
    }
    return String.format("$%.2f", abs);
  }

  private static String trimOneDecimal(double value) {
    String text = String.format("%.1f", value);
    if (text.endsWith(".0")) {
      return text.substring(0, text.length() - 2);
    }
    return text;
  }
}
