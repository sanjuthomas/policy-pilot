package com.sanjuthomas.policypilot.extraction;

import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import java.util.Locale;
import java.util.Optional;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.springframework.util.StringUtils;

/**
 * Stable-token helpers for {@code document_extraction}.
 *
 * <p>Open-vocabulary paraphrase → enum / facet mapping belongs on {@link RouterDecision} LLM slots.
 * This class may read <strong>stable tokens</strong> already in the question (ids, literal enums,
 * LOB codes, {@code single-use}) for inventory filters — not synonym/lemma tables or facet phrase
 * cues (versions / created-by).
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

  /**
   * Past-tense approval verb — not a lifecycle status filter.
   *
   * <p>Matches {@code approved by …} and {@code A approved B's …}. Does <em>not</em> match the
   * adjective form {@code approved instructions/payments} used for inventory filters.
   */
  private static final Pattern APPROVED_AS_VERB =
      Pattern.compile(
          "\\bapproved\\s+(?!instructions?\\b|payments?\\b)", Pattern.CASE_INSENSITIVE);

  /** Canonical type tokens, including the hyphenated product spelling {@code single-use}. */
  private static final Pattern TYPE_ENUM_TOKEN =
      Pattern.compile(
          "\\b(STANDING|SINGLE_USE|single[\\s_-]*use)\\b", Pattern.CASE_INSENSITIVE);

  private static final Pattern LOB_TOKEN =
      Pattern.compile("\\b(FICC|FX|RATES)\\b", Pattern.CASE_INSENSITIVE);

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
   * Fill blank document_extraction slots from LLM sibling fields and stable inventory tokens.
   * Does not map paraphrases (paused→SUSPENDED) or invent versions / created-by facets from phrases.
   */
  public static void enrichDecision(RouterDecision decision, String question) {
    if (decision == null) {
      return;
    }
    // "Who approved …" / "A approved B …" — verb, not a status filter.
    if (!StringUtils.hasText(decision.getEntityStatus())
        && !isWhoApprovedVerb(question)
        && !isApprovedAsVerb(question)) {
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

  /**
   * Facet inference for clamps from literal inventory enums only. Does <em>not</em> phrase-match
   * versions / created-by / who-approved / status-of / who-created — those facets come from {@code
   * RouterDecision.extractionFacet}.
   */
  static Facet inferFacet(String question, RouterDecision decision) {
    String status = normalizeStatusEnum(decision == null ? null : decision.getEntityStatus());
    if (status == null && !isWhoApprovedVerb(question) && !isApprovedAsVerb(question)) {
      status = statusEnumToken(question);
    }
    String type = normalizeTypeEnum(decision == null ? null : decision.getInstructionType());
    if (type == null) {
      type = instructionTypeEnumToken(question);
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

  /**
   * True when "approved" is the past-tense approval verb in a who-approved question — used only so
   * status-token fallback does not treat it as lifecycle {@code APPROVED}.
   */
  static boolean isWhoApprovedVerb(String question) {
    String q = lower(question);
    return q.contains("who approv") && !isCreatorAndApproverShape(question);
  }

  /**
   * True when {@code approved} is a past-tense verb ({@code approved by}, {@code A approved B}),
   * not the adjective in {@code approved instructions}.
   */
  static boolean isApprovedAsVerb(String question) {
    return question != null && APPROVED_AS_VERB.matcher(question).find();
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
