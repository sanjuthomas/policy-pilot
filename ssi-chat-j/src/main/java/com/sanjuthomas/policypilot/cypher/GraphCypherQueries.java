package com.sanjuthomas.policypilot.cypher;

import com.sanjuthomas.policypilot.cypher.GraphPlanModels.PlannedQuery;
import java.util.List;
import java.util.Set;

/** Read-only Cypher templates for the remaining Java neo4j_direct graph intents. */
public final class GraphCypherQueries {

  private static final String SECURITY_EVENT_GRAPH_OPTIONAL_MATCHES =
      """
      OPTIONAL MATCH (actor:User)-[:ACTED_AS]->(e)
      OPTIONAL MATCH (e)-[:FOR]->(v:InstructionVersion)
      OPTIONAL MATCH (e)-[:FOR]->(pv:PaymentVersion)
      WITH e,
           head(collect(DISTINCT actor)) AS actor,
           head(collect(DISTINCT v)) AS v,
           head(collect(DISTINCT pv)) AS pv
      OPTIONAL MATCH (i:Instruction {instruction_id: coalesce(e.instruction_id, v.instruction_id)})
      OPTIONAL MATCH (pay:Payment {payment_id: coalesce(e.payment_id, pv.payment_id)})
      WITH e, actor, v, pv,
           head(collect(DISTINCT i)) AS i,
           head(collect(DISTINCT pay)) AS pay
      """;

  private static final String INSTRUCTION_ID_COALESCE =
      "coalesce(v.instruction_id, i.instruction_id, pv.instruction_id, pay.instruction_id, '')";

  private static final String ALERT_LIST_ENTITY_ID =
      """
      CASE
               WHEN e.payment_id IS NOT NULL THEN coalesce(e.payment_id, '')
               ELSE coalesce(e.instruction_id, v.instruction_id, i.instruction_id, '')
             END""";

  private GraphCypherQueries() {}

  public static List<PlannedQuery> alertRanking(
      String timeFilter, String domain, String question, Set<String> allowedLobs) {
    String domainFilter = domainFilter(domain);
    String lob = LobScope.owningLobAndClause("e", question, allowedLobs);
    return List.of(
        new PlannedQuery(
            "ranking",
            """
            MATCH (e:SecurityEvent {severity: 'ALERT'})
            WHERE true %s %s%s
            OPTIONAL MATCH (actor:User)-[:ACTED_AS]->(e)
            WITH actor.user_id AS user_id,
                 coalesce(actor.display_name, actor.user_id, '') AS actor_display,
                 count(e) AS alert_count,
                 sum(CASE WHEN e.payment_id IS NOT NULL THEN 1 ELSE 0 END) AS payment_alerts,
                 sum(CASE WHEN e.payment_id IS NULL THEN 1 ELSE 0 END) AS instruction_alerts
            WHERE user_id IS NOT NULL
            RETURN user_id, actor_display, alert_count, payment_alerts, instruction_alerts
            ORDER BY alert_count DESC
            LIMIT 20"""
                .formatted(domainFilter, timeFilter, lob)),
        new PlannedQuery(
            "details",
            """
            MATCH (e:SecurityEvent {severity: 'ALERT'})
            WHERE true %s %s%s%s
            RETURN e.event_id, e.timestamp, e.action, e.message, e.severity,
                   CASE WHEN e.payment_id IS NOT NULL THEN 'payment' ELSE 'instruction' END AS domain,
                   coalesce(e.payment_id, '') AS payment_id,
                   %s AS instruction_id,
                   coalesce(pv.amount, 0) AS amount,
                   coalesce(pv.currency, '') AS currency,
                   coalesce(pv.owning_lob, e.owning_lob, v.owning_lob, '') AS owning_lob,
                   coalesce(actor.display_name, actor.user_id, '') AS actor_display
            ORDER BY e.timestamp DESC
            LIMIT 200"""
                .formatted(
                    domainFilter,
                    timeFilter,
                    lob,
                    SECURITY_EVENT_GRAPH_OPTIONAL_MATCHES,
                    INSTRUCTION_ID_COALESCE)));
  }

  public static List<PlannedQuery> alertList(
      String timeFilter,
      String domain,
      boolean approvalOnly,
      String question,
      Set<String> allowedLobs) {
    String domainFilter = domainFilter(domain);
    String actionFilter =
        approvalOnly ? "AND e.action IN ['APPROVE', 'APPROVE_PAYMENT']" : "";
    String lob = LobScope.owningLobAndClause("e", question, allowedLobs);
    return List.of(
        new PlannedQuery(
            "security_event_alert_list",
            """
            MATCH (e:SecurityEvent {severity: 'ALERT'})
            WHERE true %s %s %s%s%s
            RETURN e.event_id AS event_id,
                   e.timestamp AS timestamp,
                   e.action AS action,
                   CASE WHEN e.payment_id IS NOT NULL THEN 'payment' ELSE 'instruction' END AS entity_type,
                   %s AS entity_id,
                   coalesce(actor.display_name, actor.user_id, '') AS actor_display
            ORDER BY e.timestamp DESC
            LIMIT 200"""
                .formatted(
                    domainFilter,
                    timeFilter,
                    actionFilter,
                    lob,
                    SECURITY_EVENT_GRAPH_OPTIONAL_MATCHES,
                    ALERT_LIST_ENTITY_ID)));
  }

  public static List<PlannedQuery> alertCount(
      String timeFilter, String domain, String question, Set<String> allowedLobs) {
    String lob = LobScope.owningLobAndClause("e", question, allowedLobs);
    String countWhere;
    String countMatch;
    String detailOptional;
    String detailReturn;
    if ("payments".equals(domain)) {
      countWhere =
          "e.payment_id IS NOT NULL AND e.severity = 'ALERT' " + timeFilter + lob;
      countMatch = "MATCH (e:SecurityEvent)";
      detailOptional =
          """
          OPTIONAL MATCH (actor:User)-[:ACTED_AS]->(e)
          OPTIONAL MATCH (e)-[:FOR]->(pv:PaymentVersion)
          OPTIONAL MATCH (pay:Payment {payment_id: pv.payment_id})""";
      detailReturn =
          """
          RETURN e.event_id, e.timestamp, e.action, e.message, e.severity,
                 e.payment_id AS payment_id,
                 coalesce(pv.instruction_id, pay.instruction_id, '') AS instruction_id,
                 coalesce(pv.amount, 0) AS amount,
                 coalesce(pv.currency, '') AS currency,
                 coalesce(pv.owning_lob, e.owning_lob, '') AS owning_lob,
                 coalesce(actor.display_name, actor.user_id, '') AS actor_display""";
    } else if ("instructions".equals(domain)) {
      countWhere = "e.payment_id IS NULL AND e.severity = 'ALERT' " + timeFilter + lob;
      countMatch = "MATCH (e:SecurityEvent)";
      detailOptional =
          """
          OPTIONAL MATCH (e)-[:FOR]->(v:InstructionVersion)
          OPTIONAL MATCH (i:Instruction {instruction_id: v.instruction_id})
          OPTIONAL MATCH (actor:User)-[:ACTED_AS]->(e)""";
      detailReturn =
          """
          RETURN e.event_id, e.timestamp, e.action, e.message, e.severity,
                 coalesce(v.instruction_id, i.instruction_id, '') AS instruction_id,
                 coalesce(e.owning_lob, v.owning_lob, '') AS lob,
                 coalesce(actor.display_name, actor.user_id, '') AS actor_display""";
    } else {
      countWhere = "true " + timeFilter + lob;
      countMatch = "MATCH (e:SecurityEvent {severity: 'ALERT'})";
      detailOptional = SECURITY_EVENT_GRAPH_OPTIONAL_MATCHES;
      detailReturn =
          """
          RETURN e.event_id, e.timestamp, e.action, e.message, e.severity,
                 CASE WHEN e.payment_id IS NOT NULL THEN 'payment' ELSE 'instruction' END AS domain,
                 coalesce(e.payment_id, '') AS payment_id,
                 %s AS instruction_id,
                 coalesce(actor.display_name, actor.user_id, '') AS actor_display"""
              .formatted(INSTRUCTION_ID_COALESCE);
    }
    return List.of(
        new PlannedQuery(
            "count",
            """
            %s
            WHERE %s
            RETURN count(e) AS total LIMIT 1"""
                .formatted(countMatch, countWhere)),
        new PlannedQuery(
            "details",
            """
            %s
            WHERE %s%s
            %s
            ORDER BY e.timestamp DESC
            LIMIT 200"""
                .formatted(countMatch, countWhere, detailOptional, detailReturn)));
  }

  public static List<PlannedQuery> selfApproval() {
    return List.of(
        new PlannedQuery(
            "self_approval",
            """
            MATCH (i:Instruction)-[:CURRENT]->(v:InstructionVersion)
            WHERE v.creator_user_id IS NOT NULL
              AND v.approver_user_id IS NOT NULL
              AND v.creator_user_id = v.approver_user_id
            OPTIONAL MATCH (creator:User {user_id: v.creator_user_id})
            RETURN v.instruction_id AS instruction_id,
                   v.status AS status,
                   v.owning_lob AS owning_lob,
                   coalesce(creator.display_name, v.creator_user_id, '') AS creator_display,
                   v.approved_at AS approved_at
            ORDER BY v.instruction_id
            LIMIT 50"""));
  }

  public static List<PlannedQuery> subordinateApprover() {
    return List.of(
        new PlannedQuery(
            "hierarchy_violations",
            """
            MATCH (i:Instruction)-[:CURRENT]->(v:InstructionVersion)
            WHERE v.approver_user_id IS NOT NULL AND v.creator_user_id IS NOT NULL
            MATCH (creator:User {user_id: v.creator_user_id})
            MATCH (approver:User {user_id: v.approver_user_id})-[:REPORTS_TO]->(creator)
            RETURN v.instruction_id, v.owning_lob, v.status, v.instruction_type,
                   v.currency, v.wire_scope,
                   v.creditor_name, v.creditor_account,
                   v.effective_date, v.end_date, v.is_expired,
                   creator.user_id AS creator_user_id,
                   coalesce(creator.display_name, creator.user_id, '') AS creator_display,
                   approver.user_id AS approver_user_id,
                   coalesce(approver.display_name, approver.user_id, '') AS approver_display,
                   approver.supervisor_id AS approver_supervisor_id
            ORDER BY v.instruction_id
            LIMIT 50"""));
  }

  public static List<PlannedQuery> mutualApproval() {
    return List.of(
        new PlannedQuery(
            "mutual_approval",
            """
            MATCH (a:User)-[:APPROVED_IV]->(va:InstructionVersion)<-[:CREATED_IV]-(b:User)
            MATCH (b)-[:APPROVED_IV]->(vb:InstructionVersion)<-[:CREATED_IV]-(a)
            WHERE a.user_id < b.user_id
            RETURN coalesce(a.display_name, a.user_id, '') AS user_a_display,
                   a.user_id AS user_a_id,
                   coalesce(b.display_name, b.user_id, '') AS user_b_display,
                   b.user_id AS user_b_id,
                   va.instruction_id AS approved_by_a,
                   vb.instruction_id AS approved_by_b,
                   va.owning_lob AS lob_a,
                   vb.owning_lob AS lob_b
            ORDER BY user_a_id, user_b_id
            LIMIT 50"""));
  }

  public static List<PlannedQuery> crossEntityReciprocalApproval() {
    return List.of(
        new PlannedQuery(
            "cross_entity_reciprocal_approval",
            """
            MATCH (i:Instruction)-[:CURRENT]->(iv:InstructionVersion)
            MATCH (i)-[:HAS_PAYMENT]->(pay:Payment)-[:CURRENT]->(pv:PaymentVersion)
            WHERE iv.creator_user_id IS NOT NULL
              AND iv.approver_user_id IS NOT NULL
              AND pv.creator_user_id IS NOT NULL
              AND pv.approver_user_id IS NOT NULL
              AND iv.creator_user_id = pv.approver_user_id
              AND iv.approver_user_id = pv.creator_user_id
              AND iv.creator_user_id <> iv.approver_user_id
            OPTIONAL MATCH (instr_creator:User {user_id: iv.creator_user_id})
            OPTIONAL MATCH (instr_approver:User {user_id: iv.approver_user_id})
            OPTIONAL MATCH (pay_creator:User {user_id: pv.creator_user_id})
            OPTIONAL MATCH (pay_approver:User {user_id: pv.approver_user_id})
            RETURN coalesce(instr_creator.display_name, iv.creator_user_id, '') AS instruction_creator_display,
                   iv.creator_user_id AS instruction_creator_id,
                   coalesce(instr_approver.display_name, iv.approver_user_id, '') AS instruction_approver_display,
                   iv.approver_user_id AS instruction_approver_id,
                   coalesce(pay_approver.display_name, pv.approver_user_id, '') AS payment_approver_display,
                   pv.approver_user_id AS payment_approver_id,
                   coalesce(pay_creator.display_name, pv.creator_user_id, '') AS payment_creator_display,
                   pv.creator_user_id AS payment_creator_id,
                   i.instruction_id AS instruction_id,
                   pay.payment_id AS payment_id,
                   coalesce(iv.owning_lob, '') AS owning_lob,
                   iv.status AS instruction_status,
                   pv.status AS payment_status
            ORDER BY instruction_id, payment_id
            LIMIT 50"""));
  }

  public static List<PlannedQuery> duplicateRoutes(String question, Set<String> allowedLobs) {
    String lob = LobScope.owningLobAndClause("v1", question, allowedLobs);
    return List.of(
        new PlannedQuery(
            "duplicate_routes",
            """
            MATCH (i1:Instruction)-[:CONFLICTS_WITH]-(i2:Instruction)
            WHERE elementId(i1) < elementId(i2)
            MATCH (i1)-[:CURRENT]->(v1:InstructionVersion)
            MATCH (i2)-[:CURRENT]->(v2:InstructionVersion)
            WHERE v1.status IN ['APPROVED', 'SUBMITTED']
              AND v2.status IN ['APPROVED', 'SUBMITTED']
              %s
            RETURN i1.instruction_id AS instruction_id_a,
                   i2.instruction_id AS instruction_id_b,
                   v1.owning_lob AS owning_lob,
                   v1.currency AS currency,
                   v1.creditor_account AS creditor_account,
                   v1.creditor_name AS creditor_name
            ORDER BY v1.creditor_account, v1.currency
            LIMIT 50"""
                .formatted(lob)));
  }

  public static List<PlannedQuery> instructionTimeline(String instructionId) {
    String safeId = LobScope.escape(instructionId);
    return List.of(
        new PlannedQuery(
            "instruction_timeline_targets",
            """
            MATCH (i:Instruction {instruction_id: '%s'})-[:HAS_VERSION]->(v:InstructionVersion)
            MATCH (event:SecurityEvent)-[:FOR]->(v)
            OPTIONAL MATCH (actor:User)-[:ACTED_AS]->(event)
            RETURN event.event_id AS event_id,
                   event.timestamp AS timestamp,
                   event.action AS action,
                   event.severity AS severity,
                   event.outcome AS outcome,
                   event.message AS message,
                   coalesce(actor.display_name, actor.user_id, '') AS actor_display
            ORDER BY timestamp ASC
            LIMIT 200"""
                .formatted(safeId)));
  }

  private static String domainFilter(String domain) {
    if ("payments".equals(domain)) {
      return "AND e.payment_id IS NOT NULL";
    }
    if ("instructions".equals(domain)) {
      return "AND e.payment_id IS NULL";
    }
    return "";
  }
}
