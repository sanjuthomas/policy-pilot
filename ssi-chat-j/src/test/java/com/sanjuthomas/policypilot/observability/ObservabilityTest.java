package com.sanjuthomas.policypilot.observability;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.sanjuthomas.policypilot.api.ApiModels.ChatResponse;
import com.sanjuthomas.policypilot.api.ApiModels.SourceHit;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class ObservabilityTest {

  private MeterRegistry registry;
  private RoutingDistributionTracker routingTracker;
  private FeedbackDistributionTracker feedbackTracker;
  private RoutingMetrics routingMetrics;
  private FeedbackMetrics feedbackMetrics;
  private SkillMetrics skillMetrics;
  private ChatAnswerFinalizer finalizer;

  @BeforeEach
  void setUp() {
    registry = new SimpleMeterRegistry();
    routingTracker = new RoutingDistributionTracker();
    feedbackTracker = new FeedbackDistributionTracker();
    routingMetrics = new RoutingMetrics(registry, routingTracker);
    feedbackMetrics = new FeedbackMetrics(registry, feedbackTracker);
    skillMetrics = new SkillMetrics(registry);
    finalizer = new ChatAnswerFinalizer(routingMetrics, skillMetrics);
  }

  @Test
  void classifyEligibilityAndDirectory() {
    assertEquals(
        "eligibility",
        ChatObservability.classifyRetrievalStrategy(
            "eligibility", "none", "eligibility_api", Map.of(), 0));
    assertEquals(
        "policy_directory",
        ChatObservability.classifyRetrievalStrategy(
            "policy_directory", "none", "policy_directory_api", Map.of(), 0));
    assertEquals(
        "deterministic",
        ChatObservability.classifyRetrievalStrategy("me", "none", "formatter", Map.of(), 0));
  }

  @Test
  void cypherClassMapping() {
    assertEquals("deterministic", ChatObservability.cypherClassForProvenance("predefined_yaml"));
    assertEquals("llm", ChatObservability.cypherClassForProvenance("llm_graph_plan"));
    assertEquals("none", ChatObservability.cypherClassForProvenance("none"));
  }

  @Test
  void finalizeIncrementsAnswerCountAndStats() {
    ChatResponse response =
        finalizer.of(
            "Who can approve payment X?",
            "events",
            "ok",
            "eligibility",
            "eligibility_api",
            "eligibility",
            12.3,
            45.6);

    assertEquals("eligibility", response.routing().path());
    assertEquals("eligibility", response.routing().retrieval_strategy());
    assertEquals(
        1.0,
        registry.find("chat.answer.count").counters().stream()
            .mapToDouble(c -> c.count())
            .sum(),
        0.001);
    assertEquals(1L, routingTracker.snapshot().get("total"));
    assertNotNull(response.retrieval_ms());
    assertNotNull(response.generation_ms());
  }

  @Test
  void pathOverrideIsRecorded() {
    AnswerRouting routing =
        new AnswerRouting(
            "neo4j_direct",
            "predefined_yaml",
            "formatter",
            "events",
            "deterministic",
            null,
            1.0,
            2.0,
            0,
            0,
            Map.of(),
            10,
            "deadbeef",
            "full_rag");
    routingMetrics.record(routing);

    Map<String, Object> snap = routingTracker.snapshot();
    assertEquals(1L, snap.get("route_override_total"));
    assertEquals(0L, snap.get("route_honored_total"));
    assertTrue(routing.routeOverridden());
    assertEquals("true", routing.pathDecisionLabels().get("chat.route_override"));
  }

  @Test
  void feedbackCounterAndSatisfaction() {
    feedbackMetrics.record(
        ChatFeedbackContext.fromPayload(
            "up",
            "events",
            "eligibility",
            "none",
            "eligibility_api",
            "eligibility",
            "u1",
            null,
            "hash"));
    feedbackMetrics.record(
        ChatFeedbackContext.fromPayload(
            "down",
            "events",
            "eligibility",
            "none",
            "eligibility_api",
            null,
            "u1",
            null,
            "hash"));

    assertEquals(
        2.0,
        registry.find("chat.feedback.count").counters().stream()
            .mapToDouble(c -> c.count())
            .sum(),
        0.001);
    Map<String, Object> snap = feedbackTracker.snapshot();
    assertEquals(1L, snap.get("up"));
    assertEquals(1L, snap.get("down"));
    assertEquals(0.5, snap.get("satisfaction_rate"));
  }

  @Test
  void skillOutcomeParsesErrorSuffix() {
    assertNull(SkillMetrics.parseSkillIntent(null));
    assertNull(SkillMetrics.parseSkillIntent("eligibility"));
    SkillMetrics.ParsedSkill ok = SkillMetrics.parseSkillIntent("skill.approve_payment.confirmed");
    assertEquals("approve_payment", ok.skill());
    assertEquals("ok", ok.status());
    SkillMetrics.ParsedSkill err =
        SkillMetrics.parseSkillIntent("skill.approve_payment.authz_error");
    assertEquals("error", err.status());

    skillMetrics.recordSkillOutcome("skill.create_payment.created");
    assertEquals(
        1.0,
        registry.find("chat.skill.outcome.count").counters().stream()
            .mapToDouble(c -> c.count())
            .sum(),
        0.001);
  }

  @Test
  void sourceChannelsCounted() {
    Map<String, Integer> counts =
        ChatAnswerFinalizer.countSourceChannels(
            List.of(
                new SourceHit("e1", null, 1.0, List.of("vector", "neo4j"), "s", null, null),
                new SourceHit("e2", null, 0.5, List.of("vector"), "s", null, null)));
    assertEquals(2, counts.get("vector"));
    assertEquals(1, counts.get("neo4j"));
    assertEquals(0, counts.get("exact"));
  }

  @Test
  void fingerprintIsStable() {
    AnswerRouting.QuestionFingerprint a = AnswerRouting.fingerprint(" hello ");
    AnswerRouting.QuestionFingerprint b = AnswerRouting.fingerprint("hello");
    assertEquals(a.hash(), b.hash());
    assertEquals(5, a.length());
  }

  @Test
  void resetClearsTrackers() {
    routingMetrics.record(
        new AnswerRouting(
            "eligibility",
            "none",
            "eligibility_api",
            "events",
            "eligibility",
            null,
            null,
            null,
            0,
            0,
            Map.of("vector", 1),
            1,
            "h",
            null));
    feedbackMetrics.record(
        ChatFeedbackContext.fromPayload(
            "up", "events", "eligibility", "none", "eligibility_api", "eligibility", null, null, null));
    routingTracker.reset();
    feedbackTracker.reset();
    assertEquals(0L, routingTracker.snapshot().get("total"));
    assertEquals(0L, feedbackTracker.snapshot().get("total"));
    assertFalse(routingTracker.snapshot().containsKey("bogus"));
  }

  @Test
  void otelEnvPostProcessorHonorsDisabled() {
    // Smoke: processor constructs without throwing when env unset.
    new OtelEnvironmentPostProcessor();
  }
}
