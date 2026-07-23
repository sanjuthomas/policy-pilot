package com.sanjuthomas.policypilot.cypher;

import java.util.Locale;
import java.util.regex.Pattern;

/** Lightweight question flags for deterministic graph planning (not primary path routing). */
public final class GraphQuestionFlags {

  private static final Pattern COUNT =
      Pattern.compile("\\b(how many|number of|count of|total number)\\b", Pattern.CASE_INSENSITIVE);
  private static final Pattern RANKING =
      Pattern.compile(
          "\\b(most|top|highest|greatest|largest|biggest|who triggered|which user|which users)\\b",
          Pattern.CASE_INSENSITIVE);
  private static final Pattern DENIAL =
      Pattern.compile("\\b(policy denial|denials?|denied|alert|alerts)\\b", Pattern.CASE_INSENSITIVE);
  private static final Pattern WEEK =
      Pattern.compile(
          "\\b(this week|past week|last week|last 7 days|past 7 days)\\b", Pattern.CASE_INSENSITIVE);
  private static final Pattern LIST_ALERT =
      Pattern.compile(
          "\\b(list|show|summarize|summarise|summary|enumerate|display)\\b.*\\b(alerts?|policy\\s+denials?|denials?|denied)\\b|"
              + "\\b(alerts?|policy\\s+denials?|denials?)\\b.*\\b(list|show|summarize|summarise|summary|enumerate|display|all|events?)\\b|"
              + "\\b(all|every)\\b.*\\b(alerts?|policy\\s+denials?|denials?)\\b|"
              + "\\b(list|show|enumerate|display|all)\\b.*\\b(denial|denied)\\b.*\\bevents?\\b|"
              + "\\b(denial|denied)\\b.*\\bevents?\\b.*\\b(list|show|enumerate|display|all)\\b",
          Pattern.CASE_INSENSITIVE);
  private static final Pattern APPROVAL_DENIAL =
      Pattern.compile(
          "\\bapproval\\b.{0,40}\\bdenial|\\bdenial\\b.{0,40}\\bapprov", Pattern.CASE_INSENSITIVE);
  private static final Pattern MUTUAL =
      Pattern.compile("\\bmutual\\s+approv|\\bapprov\\w*\\b.*\\beach\\s+other", Pattern.CASE_INSENSITIVE);
  private static final Pattern CROSS_ENTITY =
      Pattern.compile("\\b(cross[- ]entity|across\\s+entit(?:y|ies))\\b", Pattern.CASE_INSENSITIVE);
  private static final Pattern SELF_APPROVAL =
      Pattern.compile(
          "\\bself[- ]?approv|\\bcreator\\s+and\\s+approver\\s+are\\s+the\\s+same\\b|"
              + "\\bsame\\s+person\\b.*\\bapprov",
          Pattern.CASE_INSENSITIVE);
  private static final Pattern DUPLICATE_ROUTES =
      Pattern.compile(
          "\\bduplicate\\b.*\\b(route|instruction)|\\bCONFLICTS_WITH\\b|"
              + "\\bsame\\s+creditor\\s+account\\b.*\\bcurrency\\b",
          Pattern.CASE_INSENSITIVE);
  private static final Pattern HIERARCHY =
      Pattern.compile(
          "\\b(reports?\\s+to|reporting\\s+to|directly\\s+reports?|subordinate|supervisor|"
              + "inversion\\s+of\\s+control|reporting\\s+chain|hierarchy)\\b",
          Pattern.CASE_INSENSITIVE);
  private static final Pattern SUBORDINATE =
      Pattern.compile(
          "\\b(reports?\\s+to|reporting\\s+to|directly\\s+reports?)\\b.*\\bcreator\\b|"
              + "\\bapprov.*\\b(reports?\\s+to|subordinate)\\b.*\\bcreator\\b",
          Pattern.CASE_INSENSITIVE);
  private static final Pattern TIMELINE =
      Pattern.compile(
          "\\b(full\\s+)?(security\\s+event\\s+)?timeline\\b|\\bfrom\\s+creation\\b.*\\bapprov",
          Pattern.CASE_INSENSITIVE);

  public final boolean count;
  public final boolean ranking;
  public final boolean denial;
  public final boolean today;
  public final boolean week;
  public final boolean alerts;
  public final boolean payments;
  public final boolean instructions;

  private GraphQuestionFlags(
      boolean count,
      boolean ranking,
      boolean denial,
      boolean today,
      boolean week,
      boolean alerts,
      boolean payments,
      boolean instructions) {
    this.count = count;
    this.ranking = ranking;
    this.denial = denial;
    this.today = today;
    this.week = week;
    this.alerts = alerts;
    this.payments = payments;
    this.instructions = instructions;
  }

  public static GraphQuestionFlags from(String question) {
    String q = question == null ? "" : question.toLowerCase(Locale.ROOT);
    boolean payments = q.contains("payment");
    boolean instructions = q.contains("instruction") && !payments;
    return new GraphQuestionFlags(
        COUNT.matcher(question == null ? "" : question).find(),
        RANKING.matcher(question == null ? "" : question).find(),
        DENIAL.matcher(question == null ? "" : question).find(),
        q.contains("today"),
        WEEK.matcher(question == null ? "" : question).find(),
        q.contains("alert"),
        payments,
        instructions);
  }

  public String timeFilter() {
    if (today) {
      return "AND date(datetime(e.timestamp)) = date()";
    }
    if (week) {
      return "AND date(datetime(e.timestamp)) >= date() - duration('P7D')";
    }
    return "";
  }

  public String domain() {
    if (payments) {
      return "payments";
    }
    if (instructions) {
      return "instructions";
    }
    return "all";
  }

  public static boolean isAlertList(String question) {
    return LIST_ALERT.matcher(question == null ? "" : question).find();
  }

  public static boolean isApprovalDenialList(String question) {
    return APPROVAL_DENIAL.matcher(question == null ? "" : question).find();
  }

  public static boolean isMutualApproval(String question) {
    if (isCrossEntityReciprocal(question)) {
      return false;
    }
    return MUTUAL.matcher(question == null ? "" : question).find();
  }

  public static boolean isCrossEntityReciprocal(String question) {
    String q = question == null ? "" : question.toLowerCase(Locale.ROOT);
    if (!q.contains("instruction") || !q.contains("payment")) {
      return false;
    }
    if (!q.contains("approv")) {
      return false;
    }
    if (CROSS_ENTITY.matcher(question).find()) {
      return true;
    }
    if (Pattern.compile("\\bsame\\s+instruction\\b").matcher(q).find()
        && Pattern.compile("\\bother\\b").matcher(q).find()) {
      return true;
    }
    if (MUTUAL.matcher(question).find()) {
      return true;
    }
    boolean reciprocalCue =
        Pattern.compile(
                "\\bother\\s+user\\b|\\banother\\s+user\\b|\\bsame\\s+other\\b|\\breciprocal\\b|"
                    + "\\bone\\s+user\\b.{0,80}\\banother\\b")
            .matcher(q)
            .find();
    if (!reciprocalCue) {
      return false;
    }
    return Pattern.compile(
            "\\binstruction\\b.{0,120}\\bpayment\\b|\\bpayment\\b.{0,120}\\binstruction\\b")
        .matcher(q)
        .find();
  }

  public static boolean isSelfApproval(String question) {
    return SELF_APPROVAL.matcher(question == null ? "" : question).find();
  }

  public static boolean isDuplicateRoutes(String question) {
    return DUPLICATE_ROUTES.matcher(question == null ? "" : question).find();
  }

  public static boolean isSubordinateApprover(String question) {
    String q = question == null ? "" : question.toLowerCase(Locale.ROOT);
    if (!q.contains("approv")) {
      return false;
    }
    if (!HIERARCHY.matcher(question).find() && !SUBORDINATE.matcher(question).find()) {
      return false;
    }
    return q.contains("creator")
        || q.contains("created")
        || q.contains("supervisor")
        || q.contains("subordinate")
        || q.contains("reports to")
        || q.contains("reporting to")
        || q.contains("directly report")
        || SUBORDINATE.matcher(question).find();
  }

  public static boolean isTimeline(String question) {
    return TIMELINE.matcher(question == null ? "" : question).find();
  }
}
