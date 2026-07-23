package com.sanjuthomas.policypilot.extraction;

import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import com.sanjuthomas.policypilot.routing.InstructionIdParser;
import com.sanjuthomas.policypilot.routing.PaymentIdParser;
import java.util.Locale;
import java.util.Optional;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.springframework.util.StringUtils;

/**
 * Stable-token helpers for {@code document_extraction}.
 *
 * <p>Open-vocabulary paraphrase → enum mapping belongs on {@link RouterDecision} LLM slots. This
 * class may read <strong>stable tokens</strong> already in the question (ids, literal enums, LOB
 * codes, {@code single-use}) and apply narrow by-id structural facet cues used by {@code
 * RouteClamps} — not synonym/lemma tables.
 */
public final class EntityApiQuestion {

  /** Stable subject user ids (e.g. {@code mo-050}). */
  private static final Pattern USER_ID =
      Pattern.compile("\\b(mo|ficc|fx|rates|pay|fo|comp|admin|svc)-\\d+\\b", Pattern.CASE_INSENSITIVE);

  /** Literal domain enum already present in the question (stable token fallback only). */
  private static final Pattern STATUS_ENUM_TOKEN =
      Pattern.compile(
          "\\b(SUBMITTED|APPROVED|REJECTED|SUSPENDED|EXPIRED|CANCELLED|DRAFT|USED)\\b",
          Pattern.CASE_INSENSITIVE);

  /** Canonical type tokens, including the hyphenated product spelling {@code single-use}. */
  private static final Pattern TYPE_ENUM_TOKEN =
      Pattern.compile(
          "\\b(STANDING|SINGLE_USE|single[\\s_-]*use)\\b", Pattern.CASE_INSENSITIVE);

  private static final Pattern LOB_TOKEN =
      Pattern.compile("\\b(FICC|FX|RATES)\\b", Pattern.CASE_INSENSITIVE);

  /** By-id versions cue (product vocabulary — not open-vocab status paraphrases). */
  private static final Pattern VERSIONS_CUE =
      Pattern.compile(
          "\\bversions?\\b|\\bversion\\s+history\\b", Pattern.CASE_INSENSITIVE);

  private EntityApiQuestion() {}

  public enum Facet {
    SHOW,
    STATUS,
    CREATOR,
    CREATOR_AND_APPROVER,
    APPROVER,
    VERSIONS,
    LIST_BY_STATUS,
    LIST_STANDING,
    LIST_SINGLE_USE,
    CREATED_BY_USER
  }

  public static Optional<String> extractUserId(String question) {
    if (question == null || question.isBlank()) {
      return Optional.empty();
    }
    Matcher matcher = USER_ID.matcher(question);
    if (matcher.find()) {
      return Optional.of(matcher.group().toLowerCase(Locale.ROOT));
    }
    return Optional.empty();
  }

  public static boolean isInventoryFacet(Facet facet) {
    return facet == Facet.LIST_BY_STATUS
        || facet == Facet.LIST_STANDING
        || facet == Facet.LIST_SINGLE_USE
        || facet == Facet.CREATED_BY_USER;
  }

  /**
   * Fill blank document_extraction slots from LLM sibling fields, stable tokens, and narrow by-id
   * structural cues. Does not map paraphrases (paused→SUSPENDED).
   */
  public static void enrichDecision(RouterDecision decision, String question) {
    if (decision == null) {
      return;
    }
    // "Who approved …" contains the word approved — that is the verb, not a status filter.
    if (!StringUtils.hasText(decision.getEntityStatus()) && !isWhoApprovedVerb(question)) {
      String status = statusEnumToken(question);
      if (status != null) {
        decision.setEntityStatus(status);
      }
    }
    if (!StringUtils.hasText(decision.getInstructionType())) {
      String type = instructionTypeEnumToken(question);
      if (type != null) {
        decision.setInstructionType(type);
      }
    }
    if (facetFromSlot(decision.getExtractionFacet()) != null) {
      return;
    }
    Facet inferred = inferFacet(question, decision);
    if (inferred != null) {
      decision.setExtractionFacet(facetSlotName(inferred));
    }
  }

  /** True when slots (after enrich) prefer domain APIs over Neo4j. */
  public static boolean isEntityApiQuestion(RouterDecision decision, String question) {
    if (decision == null) {
      return false;
    }
    enrichDecision(decision, question);
    if (facetFromSlot(decision.getExtractionFacet()) != null) {
      return true;
    }
    if (normalizeStatusEnum(decision.getEntityStatus()) != null) {
      return true;
    }
    return normalizeTypeEnum(decision.getInstructionType()) != null;
  }

  /** Prefer {@link RouterDecision#getExtractionFacet()}; infer from slots/tokens; else SHOW. */
  public static Facet resolveFacet(String question, RouterDecision decision) {
    if (decision != null) {
      enrichDecision(decision, question);
    }
    Facet fromSlot = facetFromSlot(decision == null ? null : decision.getExtractionFacet());
    if (fromSlot != null) {
      return fromSlot;
    }
    Facet inferred = inferFacet(question, decision);
    return inferred != null ? inferred : Facet.SHOW;
  }

  /**
   * Domain lifecycle status from the router slot, else a literal enum token already in the
   * question. No synonym/lemma mapping.
   */
  public static String resolveEntityStatus(String question, RouterDecision decision) {
    String fromSlot = normalizeStatusEnum(decision == null ? null : decision.getEntityStatus());
    if (fromSlot != null) {
      return fromSlot;
    }
    return statusEnumToken(question);
  }

  /**
   * Instruction type from the router slot, else a literal type token already in the question. No
   * synonym/lemma mapping (evergreen / one-time stay LLM-only).
   */
  public static String resolveInstructionType(String question, RouterDecision decision) {
    String fromSlot = normalizeTypeEnum(decision == null ? null : decision.getInstructionType());
    if (fromSlot != null) {
      return fromSlot;
    }
    return instructionTypeEnumToken(question);
  }

  public static String statusEnumToken(String question) {
    if (question == null || question.isBlank()) {
      return null;
    }
    Matcher enumMatch = STATUS_ENUM_TOKEN.matcher(question);
    if (enumMatch.find()) {
      return enumMatch.group(1).toUpperCase(Locale.ROOT);
    }
    return null;
  }

  public static String instructionTypeEnumToken(String question) {
    if (question == null || question.isBlank()) {
      return null;
    }
    Matcher enumMatch = TYPE_ENUM_TOKEN.matcher(question);
    if (enumMatch.find()) {
      return normalizeTypeEnum(enumMatch.group(1));
    }
    return null;
  }

  public static String lobFilter(String question) {
    if (question == null) {
      return null;
    }
    Matcher matcher = LOB_TOKEN.matcher(question);
    if (matcher.find()) {
      return matcher.group().toUpperCase(Locale.ROOT);
    }
    return null;
  }

  public static Facet facetFromSlot(String raw) {
    if (raw == null || raw.isBlank()) {
      return null;
    }
    String key = raw.strip().toLowerCase(Locale.ROOT).replace('-', '_');
    return switch (key) {
      case "show" -> Facet.SHOW;
      case "status" -> Facet.STATUS;
      case "creator" -> Facet.CREATOR;
      case "creator_and_approver" -> Facet.CREATOR_AND_APPROVER;
      case "approver" -> Facet.APPROVER;
      case "versions", "version" -> Facet.VERSIONS;
      case "list_by_status", "list" -> Facet.LIST_BY_STATUS;
      case "list_standing", "standing" -> Facet.LIST_STANDING;
      case "list_single_use", "single_use" -> Facet.LIST_SINGLE_USE;
      case "created_by_user" -> Facet.CREATED_BY_USER;
      default -> null;
    };
  }

  static String normalizeStatusEnum(String raw) {
    if (raw == null || raw.isBlank()) {
      return null;
    }
    String upper = raw.strip().toUpperCase(Locale.ROOT);
    return switch (upper) {
      case "SUBMITTED",
          "APPROVED",
          "REJECTED",
          "SUSPENDED",
          "EXPIRED",
          "CANCELLED",
          "DRAFT",
          "USED" -> upper;
      default -> null;
    };
  }

  static String normalizeTypeEnum(String raw) {
    if (raw == null || raw.isBlank()) {
      return null;
    }
    String upper = raw.strip().toUpperCase(Locale.ROOT).replace('-', '_').replace(' ', '_');
    if ("STANDING".equals(upper)) {
      return "STANDING";
    }
    if ("SINGLE_USE".equals(upper) || "SINGLEUSE".equals(upper.replace("_", ""))) {
      return "SINGLE_USE";
    }
    return null;
  }

  /** Stable id presence for clamps / extractors — not NLU. */
  public static boolean hasEntityId(String question) {
    return PaymentIdParser.extract(question).isPresent()
        || InstructionIdParser.extract(question).isPresent();
  }

  /**
   * Narrow by-id / inventory facet inference for clamps. Not paraphrase NLU: uses entity id +
   * fixed shapes, or sibling slots / literal enums already in the question.
   */
  static Facet inferFacet(String question, RouterDecision decision) {
    String status = normalizeStatusEnum(decision == null ? null : decision.getEntityStatus());
    if (status == null) {
      status = statusEnumToken(question);
    }
    String type = normalizeTypeEnum(decision == null ? null : decision.getInstructionType());
    if (type == null) {
      type = instructionTypeEnumToken(question);
    }

    if (hasEntityId(question)) {
      if (VERSIONS_CUE.matcher(question == null ? "" : question).find()) {
        return Facet.VERSIONS;
      }
      if (isCreatorAndApproverShape(question)) {
        return Facet.CREATOR_AND_APPROVER;
      }
      if (isPastWhoApprovedOnly(question)) {
        return Facet.APPROVER;
      }
      if (isStatusShape(question)) {
        return Facet.STATUS;
      }
      if (isCreatorShape(question)) {
        return Facet.CREATOR;
      }
      return null;
    }

    if (extractUserId(question).isPresent() && isCreatedByShape(question)) {
      return Facet.CREATED_BY_USER;
    }
    if ("STANDING".equals(type)) {
      return Facet.LIST_STANDING;
    }
    if ("SINGLE_USE".equals(type)) {
      return Facet.LIST_SINGLE_USE;
    }
    if (status != null) {
      return Facet.LIST_BY_STATUS;
    }
    return null;
  }

  public static boolean isCreatorAndApproverShape(String question) {
    String q = lower(question);
    return q.contains("who created") && q.contains("who approv");
  }

  public static boolean isCreatorShape(String question) {
    String q = lower(question);
    if (q.contains("approv")) {
      return false;
    }
    return q.contains("who created") || q.contains("which user created");
  }

  public static boolean isStatusShape(String question) {
    String q = lower(question);
    return q.contains("status of")
        || q.contains("what is the status")
        || q.contains("what's the status");
  }

  public static boolean isCreatedByShape(String question) {
    String q = lower(question);
    return q.contains("created by") || q.contains("were created by") || q.contains("was created by");
  }

  static boolean isPastWhoApprovedOnly(String question) {
    String q = lower(question);
    if (!q.contains("who approv")) {
      return false;
    }
    if (q.contains("who can approv")) {
      return false;
    }
    return !isCreatorAndApproverShape(question);
  }

  /** True when "approved" is the past-tense approval verb, not a lifecycle status filter. */
  static boolean isWhoApprovedVerb(String question) {
    String q = lower(question);
    return q.contains("who approv") && !isCreatorAndApproverShape(question);
  }

  private static String facetSlotName(Facet facet) {
    return switch (facet) {
      case SHOW -> "show";
      case STATUS -> "status";
      case CREATOR -> "creator";
      case CREATOR_AND_APPROVER -> "creator_and_approver";
      case APPROVER -> "approver";
      case VERSIONS -> "versions";
      case LIST_BY_STATUS -> "list_by_status";
      case LIST_STANDING -> "list_standing";
      case LIST_SINGLE_USE -> "list_single_use";
      case CREATED_BY_USER -> "created_by_user";
    };
  }

  private static String lower(String question) {
    return question == null ? "" : question.toLowerCase(Locale.ROOT);
  }
}
