package com.sanjuthomas.policypilot.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;

import com.sanjuthomas.policypilot.api.ApiModels.ChatRequest;
import com.sanjuthomas.policypilot.api.ApiModels.ChatResponse;
import com.sanjuthomas.policypilot.TestFixtures;
import com.sanjuthomas.policypilot.auth.ChatUsersDirectory;
import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.extraction.DocumentExtractionService;
import com.sanjuthomas.policypilot.extraction.PaymentDetailAnswerFormatter;
import com.sanjuthomas.policypilot.eligibility.EligibilityAnswerFormatter;
import com.sanjuthomas.policypilot.eligibility.EligibilityLaneService;
import com.sanjuthomas.policypilot.eligibility.FakeEligibilityClient;
import com.sanjuthomas.policypilot.formatting.AnswerRenderer;
import com.sanjuthomas.policypilot.formatting.AnswerTemplateConfig;
import com.sanjuthomas.policypilot.formatting.IdentityTokenFormat;
import com.sanjuthomas.policypilot.formatting.MoneyFormat;
import com.sanjuthomas.policypilot.formatting.PolicyBasisFormat;
import com.sanjuthomas.policypilot.formatting.TimestampFormat;
import com.sanjuthomas.policypilot.instruction.InstructionDetailAnswerFormatter;
import com.sanjuthomas.policypilot.me.CanActOnEntityService;
import com.sanjuthomas.policypilot.me.MeIntentResolver;
import com.sanjuthomas.policypilot.me.MeIntentService;
import com.sanjuthomas.policypilot.me.MyPermissionsService;
import com.sanjuthomas.policypilot.me.UsersLikeMeService;
import com.sanjuthomas.policypilot.me.WaitingForMeService;
import com.sanjuthomas.policypilot.me.WhoAmIService;
import com.sanjuthomas.policypilot.me.WhoCanCreateService;
import com.sanjuthomas.policypilot.me.WhoCoversLobService;
import com.sanjuthomas.policypilot.me.WhoElseCanActService;
import com.sanjuthomas.policypilot.neo4j.Neo4jDirectAnswerFormatter;
import com.sanjuthomas.policypilot.neo4j.Neo4jDirectService;
import com.sanjuthomas.policypilot.observability.ChatAnswerFinalizer;
import com.sanjuthomas.policypilot.observability.RoutingDistributionTracker;
import com.sanjuthomas.policypilot.observability.RoutingMetrics;
import com.sanjuthomas.policypilot.observability.SkillMetrics;
import com.sanjuthomas.policypilot.pipeline.LaneAnswer;
import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import com.sanjuthomas.policypilot.policydirectory.PolicyDirectoryAnswerFormatter;
import com.sanjuthomas.policypilot.policydirectory.PolicyDirectoryService;
import com.sanjuthomas.policypilot.policysummary.PolicySummaryAnswerFormatter;
import com.sanjuthomas.policypilot.policysummary.PolicySummaryService;
import com.sanjuthomas.policypilot.routing.IntentRouter;
import com.sanjuthomas.policypilot.vector.FullRagLaneService;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.ai.chat.client.ChatClient;

@ExtendWith(MockitoExtension.class)
class ChatServiceTest {

  @Mock ChatClient.Builder chatClientBuilder;
  @Mock ChatClient chatClient;
  @Mock ChatClient.ChatClientRequestSpec requestSpec;
  @Mock ChatClient.CallResponseSpec callResponseSpec;
  @Mock FullRagLaneService fullRagLaneService;

  private EligibilityAnswerFormatter eligibilityAnswerFormatter;
  private InstructionDetailAnswerFormatter instructionDetailAnswerFormatter;
  private PaymentDetailAnswerFormatter paymentDetailAnswerFormatter;
  private PolicyDirectoryAnswerFormatter policyDirectoryAnswerFormatter;
  private PolicySummaryAnswerFormatter policySummaryAnswerFormatter;
  private MeIntentService meIntentService;
  private IntentRouter intentRouter;

  @BeforeEach
  void setUp() {
    when(chatClientBuilder.build()).thenReturn(chatClient);
    when(chatClient.prompt()).thenReturn(requestSpec);
    when(requestSpec.system(anyString())).thenReturn(requestSpec);
    when(requestSpec.user(anyString())).thenReturn(requestSpec);
    when(requestSpec.call()).thenReturn(callResponseSpec);
    intentRouter = new IntentRouter(chatClientBuilder);
    AnswerRenderer renderer =
        new AnswerRenderer(
            new AnswerTemplateConfig().answerTemplateEngine(),
            new MoneyFormat(),
            new PolicyBasisFormat());
    IdentityTokenFormat identityTokenFormat = new IdentityTokenFormat();
    eligibilityAnswerFormatter = new EligibilityAnswerFormatter(renderer);
    instructionDetailAnswerFormatter =
        new InstructionDetailAnswerFormatter(renderer, new TimestampFormat());
    paymentDetailAnswerFormatter =
        new PaymentDetailAnswerFormatter(renderer, new MoneyFormat(), new TimestampFormat());
    policyDirectoryAnswerFormatter = new PolicyDirectoryAnswerFormatter(renderer);
    policySummaryAnswerFormatter =
        new PolicySummaryAnswerFormatter(renderer, identityTokenFormat);
    ChatUsersDirectory directory = new ChatUsersDirectory(TestFixtures.properties());
    WhoAmIService whoAmIService = new WhoAmIService(renderer, identityTokenFormat);
    FakeEligibilityClient eligibilityForMe = new FakeEligibilityClient();
    meIntentService =
        new MeIntentService(
            new MeIntentResolver(),
            whoAmIService,
            new MyPermissionsService(renderer, identityTokenFormat),
            new CanActOnEntityService(renderer, identityTokenFormat),
            new WhoCanCreateService(directory, renderer, identityTokenFormat),
            new WhoCoversLobService(directory, renderer, identityTokenFormat),
            new UsersLikeMeService(directory, renderer, identityTokenFormat),
            new WaitingForMeService(eligibilityForMe, renderer),
            new WhoElseCanActService(eligibilityForMe, renderer));
  }

  private ChatService chatService(FakeEligibilityClient eligibilityClient) {
    SimpleMeterRegistry registry = new SimpleMeterRegistry();
    ChatAnswerFinalizer finalizer =
        new ChatAnswerFinalizer(
            new RoutingMetrics(registry, new RoutingDistributionTracker()),
            new SkillMetrics(registry));
    return new ChatService(
        intentRouter,
        new ChatPathDispatcher(
            meIntentService,
            new EligibilityLaneService(eligibilityClient, eligibilityAnswerFormatter),
            new PolicySummaryService(eligibilityClient, policySummaryAnswerFormatter),
            new PolicyDirectoryService(eligibilityClient, policyDirectoryAnswerFormatter),
            new DocumentExtractionService(
                eligibilityClient,
                instructionDetailAnswerFormatter,
                paymentDetailAnswerFormatter),
            new Neo4jDirectService(
                null,
                null,
                new Neo4jDirectAnswerFormatter(
                    new AnswerRenderer(
                        new AnswerTemplateConfig().answerTemplateEngine(),
                        new MoneyFormat(),
                        new PolicyBasisFormat()),
                    new PolicyBasisFormat())),
            fullRagLaneService),
        finalizer);
  }

  private static Subject subject() {
    return new Subject(
        "comp-001",
        "Comp",
        "One",
        "Analyst",
        "FICC",
        List.of("COMPLIANCE_ANALYST"),
        List.of(),
        null,
        List.of(),
        "tok",
        "sess");
  }

  @Test
  void eligibilityLaneFormatsAnswer() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("eligibility");
    decision.setEligibilityTarget("payment");
    decision.setEligibilityAction("APPROVE");
    when(callResponseSpec.entity(eq(RouterDecision.class))).thenReturn(decision);

    FakeEligibilityClient eligibilityClient =
        new FakeEligibilityClient().returning(Map.of("payment_id", "20260720-FICC-P-8"));
    ChatService chatService = chatService(eligibilityClient);

    ChatResponse response =
        chatService.ask(
            new ChatRequest("Who can approve 20260720-FICC-P-8?", List.of(), "policies"),
            subject());

    assertTrue(response.answer().contains("Live OPA"));
    assertEquals("eligibility", response.routing().path());
    assertEquals("eligibility_api", response.routing().answer_synthesis());
  }

  @Test
  void instructionShowLaneFormatsAnswer() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("document_extraction");
    decision.setExtractionTarget("instruction");
    when(callResponseSpec.entity(eq(RouterDecision.class))).thenReturn(decision);

    java.util.Map<String, Object> payload = new java.util.HashMap<>();
    payload.put("instruction_id", "20260720-FICC-I-1");
    payload.put("status", "APPROVED");
    payload.put("instruction_type", "STANDING");
    payload.put("owning_lob", "FICC");
    payload.put("currency", "USD");
    payload.put("wire_scope", "DOMESTIC");
    payload.put("version_number", 2);
    payload.put("effective_date", "2026-07-20");
    payload.put("end_date", "2027-07-20");
    payload.put(
        "created_by",
        Map.of(
            "user_id",
            "mo-050",
            "given_name",
            "David",
            "family_name",
            "Okonkwo",
            "title",
            "Analyst"));
    payload.put(
        "approved_by",
        Map.of(
            "user_id",
            "ficc-500",
            "given_name",
            "Caroline",
            "family_name",
            "Nguyen",
            "title",
            "Approver"));
    payload.put("approved_at", "2026-07-20T10:00:00");
    payload.put("creditor", Map.of("name", "Acme Corp"));
    payload.put("creditor_account", Map.of("identification", "123456"));

    FakeEligibilityClient eligibilityClient = new FakeEligibilityClient().returning(payload);
    ChatResponse response =
        chatService(eligibilityClient)
            .ask(
                new ChatRequest(
                    "Show me instruction 20260720-FICC-I-1", List.of(), "instructions"),
                subject());

    assertTrue(response.answer().contains("### Instruction `20260720-FICC-I-1`"));
    assertTrue(response.answer().contains("**APPROVED**"));
    assertTrue(response.answer().contains("Okonkwo, David (mo-050)"));
    assertTrue(response.answer().contains("Nguyen, Caroline (ficc-500)"));
    assertEquals("document_extraction", response.routing().path());
    assertEquals("formatter", response.routing().answer_synthesis());
    assertEquals("instruction.show_by_id", response.routing().intent_id());
    assertEquals("document_extraction", response.routing().retrieval_strategy());
  }

  @Test
  void paymentShowLaneFormatsAnswer() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("document_extraction");
    decision.setExtractionTarget("payment");
    when(callResponseSpec.entity(eq(RouterDecision.class))).thenReturn(decision);

    java.util.Map<String, Object> payload = new java.util.HashMap<>();
    payload.put("payment_id", "20260720-FICC-P-8");
    payload.put("instruction_id", "20260720-FICC-I-1");
    payload.put("status", "APPROVED");
    payload.put("amount", 15_000_000);
    payload.put("currency", "USD");
    payload.put("value_date", "2026-07-21");
    payload.put("owning_lob", "FICC");
    payload.put(
        "created_by",
        Map.of("user_id", "pay-101", "given_name", "Emily", "family_name", "Rodriguez"));
    payload.put(
        "approved_by",
        Map.of("user_id", "ficc-500", "given_name", "Caroline", "family_name", "Nguyen"));
    payload.put("approved_at", "2026-07-20T12:00:00");

    ChatResponse response =
        chatService(new FakeEligibilityClient().returning(payload))
            .ask(
                new ChatRequest("Show me payment 20260720-FICC-P-8", List.of(), "payments"),
                subject());

    assertTrue(response.answer().contains("### Payment `20260720-FICC-P-8`"));
    assertTrue(response.answer().contains("**APPROVED**"));
    assertTrue(response.answer().contains("USD 15,000,000"));
    assertTrue(response.answer().contains("Rodriguez, Emily (pay-101)"));
    assertEquals("document_extraction", response.routing().path());
    assertEquals("payment.show_by_id", response.routing().intent_id());
    assertEquals("document_extraction", response.routing().retrieval_strategy());
  }

  @Test
  void instructionShowLaneNotFoundReturnsProse() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("document_extraction");
    decision.setExtractionTarget("instruction");
    when(callResponseSpec.entity(eq(RouterDecision.class))).thenReturn(decision);

    FakeEligibilityClient eligibilityClient =
        new FakeEligibilityClient()
            .failing(
                new org.springframework.web.server.ResponseStatusException(
                    org.springframework.http.HttpStatus.NOT_FOUND, "missing"));
    ChatResponse response =
        chatService(eligibilityClient)
            .ask(
                new ChatRequest(
                    "Show me instruction 20260720-FICC-I-99", List.of(), "instructions"),
                subject());

    assertEquals("No instruction with that ID was found.", response.answer());
    assertEquals("document_extraction", response.routing().path());
    assertEquals("instruction.show_by_id", response.routing().intent_id());
  }

  @Test
  void instructionShowLaneForbiddenReturnsFriendlyProse() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("document_extraction");
    decision.setExtractionTarget("instruction");
    when(callResponseSpec.entity(eq(RouterDecision.class))).thenReturn(decision);

    FakeEligibilityClient eligibilityClient =
        new FakeEligibilityClient()
            .failing(
                new org.springframework.web.server.ResponseStatusException(
                    org.springframework.http.HttpStatus.FORBIDDEN,
                    "{\"detail\":\"subject LOB/covering_lobs does not entitle read\"}"));
    ChatResponse response =
        chatService(eligibilityClient)
            .ask(
                new ChatRequest(
                    "Show me instruction 20260720-FICC-I-1", List.of(), "instructions"),
                subject());

    assertEquals("You are not authorized to view this instruction.", response.answer());
    assertTrue(!response.answer().contains("{"));
    assertEquals("instruction.show_by_id", response.routing().intent_id());
  }

  @Test
  void paymentShowLaneForbiddenReturnsFriendlyProse() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("document_extraction");
    decision.setExtractionTarget("payment");
    when(callResponseSpec.entity(eq(RouterDecision.class))).thenReturn(decision);

    ChatResponse response =
        chatService(
                new FakeEligibilityClient()
                    .failing(
                        new org.springframework.web.server.ResponseStatusException(
                            org.springframework.http.HttpStatus.FORBIDDEN,
                            "not authorized to view payment")))
            .ask(
                new ChatRequest("Show me payment 20260720-FICC-P-8", List.of(), "payments"),
                subject());

    assertEquals("You are not authorized to view this payment.", response.answer());
    assertEquals("payment.show_by_id", response.routing().intent_id());
  }

  @Test
  void eligibilitySubmittersLaneFormatsAnswer() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("eligibility");
    decision.setEligibilityTarget("payment");
    decision.setEligibilityAction("SUBMIT");
    when(callResponseSpec.entity(eq(RouterDecision.class))).thenReturn(decision);

    FakeEligibilityClient eligibilityClient =
        new FakeEligibilityClient()
            .returning(
                Map.of(
                    "payment_id",
                    "20260720-FICC-P-8",
                    "payment_status",
                    "DRAFT",
                    "amount",
                    100,
                    "currency",
                    "USD",
                    "owning_lob",
                    "FICC",
                    "eligible",
                    List.of(
                        Map.of(
                            "display_name",
                            "Chen, Sarah",
                            "user_id",
                            "mo-100",
                            "title",
                            "Analyst",
                            "allow_basis",
                            List.of("role PAYMENT_CREATOR"))),
                    "candidates_evaluated",
                    2));
    ChatResponse response =
        chatService(eligibilityClient)
            .ask(
                new ChatRequest(
                    "Who can submit 20260720-FICC-P-8 for approval?", List.of(), "policies"),
                subject());

    assertTrue(response.answer().contains("Live OPA evaluation for submitting"));
    assertTrue(response.answer().contains("Chen, Sarah"));
    assertEquals("eligibility", response.routing().path());
    assertEquals("eligibility_api", response.routing().answer_synthesis());
  }

  @Test
  void eligibilityInstructionLaneFormatsAnswer() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("eligibility");
    decision.setEligibilityTarget("instruction");
    decision.setEligibilityAction("APPROVE");
    when(callResponseSpec.entity(eq(RouterDecision.class))).thenReturn(decision);

    FakeEligibilityClient eligibilityClient =
        new FakeEligibilityClient()
            .returning(
                Map.of(
                    "instruction_id",
                    "20260720-FICC-I-1",
                    "instruction_status",
                    "SUBMITTED",
                    "instruction_type",
                    "SSI",
                    "owning_lob",
                    "FICC",
                    "created_by_user_id",
                    "mo-100",
                    "created_by_title",
                    "Analyst",
                    "eligible",
                    List.of(
                        Map.of(
                            "display_name",
                            "Lee, Kim",
                            "user_id",
                            "mo-050",
                            "title",
                            "Director",
                            "allow_basis",
                            List.of("role INSTRUCTION_APPROVER"))),
                    "candidates_evaluated",
                    2));
    ChatResponse response =
        chatService(eligibilityClient)
            .ask(
                new ChatRequest(
                    "Who can approve instruction 20260720-FICC-I-1?", List.of(), "policies"),
                subject());

    assertTrue(response.answer().contains("Live OPA evaluation for instruction"));
    assertTrue(response.answer().contains("Lee, Kim"));
    assertEquals("eligibility", response.routing().path());
  }

  @Test
  void eligibilityWithoutPaymentIdAsksForId() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("eligibility");
    decision.setEligibilityTarget("payment");
    decision.setEligibilityAction("APPROVE");
    when(callResponseSpec.entity(eq(RouterDecision.class))).thenReturn(decision);

    ChatResponse response =
        chatService(new FakeEligibilityClient())
            .ask(new ChatRequest("Who can approve?", List.of(), null), subject());

    assertTrue(response.answer().toLowerCase().contains("payment id"));
    assertEquals("eligibility", response.routing().path());
  }

  @Test
  void otherPathsReturnStub() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("skill");
    when(callResponseSpec.entity(eq(RouterDecision.class))).thenReturn(decision);

    ChatResponse response =
        chatService(new FakeEligibilityClient())
            .ask(new ChatRequest("Please create a payment", List.of(), "events"), subject());

    assertTrue(response.answer().contains("vector/full_rag"));
    assertEquals("stub", response.routing().answer_synthesis());
  }

  @Test
  void vectorLaneRecordsFullRagWithSources() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("vector");
    when(callResponseSpec.entity(eq(RouterDecision.class))).thenReturn(decision);
    when(fullRagLaneService.answer(anyString(), anyString(), org.mockito.ArgumentMatchers.any()))
        .thenReturn(
            LaneAnswer.fullRag(
                "Recent policy denial activity includes an ALERT for a VIEW denial.",
                List.of(
                    new com.sanjuthomas.policypilot.api.ApiModels.SourceHit(
                        "evt-1",
                        "20260720-FICC-I-1",
                        0.9,
                        List.of("vector"),
                        "Policy denial",
                        Map.of(),
                        Map.of()))));

    ChatResponse response =
        chatService(new FakeEligibilityClient())
            .ask(
                new ChatRequest(
                    "Write a brief narrative about recent policy denial activity in the audit log.",
                    List.of(),
                    "events"),
                subject());

    assertEquals("full_rag", response.routing().path());
    assertEquals("gemini_full", response.routing().answer_synthesis());
    assertEquals(1, response.sources().size());
    assertTrue(response.answer().toLowerCase().contains("denial"));
  }

  @Test
  void neo4jDirectLaneFormatsAlertCount() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("neo4j_direct");
    when(callResponseSpec.entity(eq(RouterDecision.class))).thenReturn(decision);

    Neo4jDirectService neo4j =
        org.mockito.Mockito.mock(Neo4jDirectService.class);
    when(neo4j.answer(anyString(), anyString(), org.mockito.ArgumentMatchers.any()))
        .thenReturn(
            new Neo4jDirectService.Neo4jDirectResult(
                "There were 2 ALERT events today.",
                "planned_graph",
                "MATCH (e) RETURN count(e) AS total",
                List.of(Map.of("total", 2L)),
                "predefined_planned"));

    SimpleMeterRegistry registry = new SimpleMeterRegistry();
    ChatAnswerFinalizer finalizer =
        new ChatAnswerFinalizer(
            new RoutingMetrics(registry, new RoutingDistributionTracker()),
            new SkillMetrics(registry));
    ChatService chatService =
        new ChatService(
            intentRouter,
            new ChatPathDispatcher(
                meIntentService,
                new EligibilityLaneService(
                    new FakeEligibilityClient(), eligibilityAnswerFormatter),
                new PolicySummaryService(
                    new FakeEligibilityClient(), policySummaryAnswerFormatter),
                new PolicyDirectoryService(
                    new FakeEligibilityClient(), policyDirectoryAnswerFormatter),
                new DocumentExtractionService(
                    new FakeEligibilityClient(),
                    instructionDetailAnswerFormatter,
                    paymentDetailAnswerFormatter),
                neo4j,
                fullRagLaneService),
            finalizer);

    ChatResponse response =
        chatService.ask(
            new ChatRequest("How many ALERT events happened today?", List.of(), "events"),
            subject());

    assertTrue(response.answer().contains("2 ALERT events"));
    assertEquals("neo4j_direct", response.routing().path());
    assertEquals("formatter", response.routing().answer_synthesis());
    assertEquals("planned_graph", response.routing().intent_id());
    // Parity with Python neo4j_direct: formatter answers report generation_ms=0.
    assertEquals(0.0, response.generation_ms());
  }

  @Test
  void policyDirectoryLaneFormatsAmountClubAnswer() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("policy_directory");
    decision.setDirectoryAmount(25_000_000_000.0);
    decision.setDirectoryAmountStrict(true);
    when(callResponseSpec.entity(eq(RouterDecision.class))).thenReturn(decision);

    FakeEligibilityClient eligibilityClient =
        new FakeEligibilityClient()
            .returningLimits(
                Map.of(
                    "absolute_limit",
                    100_000_000_000.0,
                    "club_limits",
                    Map.of(
                        "UP_TO_100_MILLION_CLUB",
                        100_000_000.0,
                        "UP_TO_1_BILLION_CLUB",
                        1_000_000_000.0,
                        "UP_TO_100_BILLION_CLUB",
                        100_000_000_000.0)))
            .returningGroupMembers(
                Map.of(
                    "group",
                    "UP_TO_100_BILLION_CLUB",
                    "members",
                    List.of(
                        Map.of(
                            "user_id",
                            "pay-204",
                            "display_name",
                            "Chen, Wei",
                            "title",
                            "Managing Director",
                            "groups",
                            List.of("MIDDLE_OFFICE", "UP_TO_100_BILLION_CLUB"),
                            "covering_lobs",
                            List.of("FICC", "FX")))));

    ChatResponse response =
        chatService(eligibilityClient)
            .ask(
                new ChatRequest(
                    "Who has permission to approve payments worth more than $25 billion?",
                    List.of(),
                    "policies"),
                subject());

    assertTrue(response.answer().contains("UP_TO_100_BILLION_CLUB"));
    assertTrue(response.answer().contains("exceeding $25 billion"));
    assertTrue(response.answer().contains("pay-204"));
    assertTrue(response.answer().contains("Covering LOBs"));
    assertEquals("policy_directory", response.routing().path());
    assertEquals("policy_directory_api", response.routing().answer_synthesis());
    assertEquals("policy_directory", response.routing().retrieval_strategy());
  }

  @Test
  void policyDirectoryLaneUsesLlmSlotsForWordedBillion() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("policy_directory");
    decision.setDirectoryAmount(1_000_000_000.0);
    decision.setDirectoryAmountStrict(false);
    when(callResponseSpec.entity(eq(RouterDecision.class))).thenReturn(decision);

    FakeEligibilityClient eligibilityClient =
        new FakeEligibilityClient()
            .returningLimits(
                Map.of(
                    "absolute_limit",
                    100_000_000_000.0,
                    "club_limits",
                    Map.of(
                        "UP_TO_1_BILLION_CLUB",
                        1_000_000_000.0,
                        "UP_TO_100_BILLION_CLUB",
                        100_000_000_000.0)))
            .returningGroupMembers(
                Map.of(
                    "members",
                    List.of(
                        Map.of(
                            "user_id",
                            "pay-201",
                            "display_name",
                            "Laurent, Sophie",
                            "title",
                            "VP",
                            "groups",
                            List.of("UP_TO_1_BILLION_CLUB"),
                            "covering_lobs",
                            List.of("FICC")))));

    ChatResponse response =
        chatService(eligibilityClient)
            .ask(
                new ChatRequest("Who can approve a billion dollar payment?", List.of(), "policies"),
                subject());

    assertTrue(response.answer().contains("of at least $1 billion"));
    assertTrue(response.answer().contains("pay-201"));
    assertEquals("policy_directory", response.routing().path());
  }

  @Test
  void policyDirectoryLaneFormatsCoveringLobAnswer() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("policy_directory");
    decision.setDirectoryCoveringLob("FICC");
    when(callResponseSpec.entity(eq(RouterDecision.class))).thenReturn(decision);

    FakeEligibilityClient eligibilityClient =
        new FakeEligibilityClient()
            .returningGroupMembers(
                Map.of(
                    "group",
                    "MIDDLE_OFFICE",
                    "members",
                    List.of(
                        Map.of(
                            "user_id",
                            "pay-201",
                            "display_name",
                            "Laurent, Sophie",
                            "title",
                            "Vice President",
                            "groups",
                            List.of("MIDDLE_OFFICE", "UP_TO_1_BILLION_CLUB"),
                            "covering_lobs",
                            List.of("FICC", "FX")))));

    ChatResponse response =
        chatService(eligibilityClient)
            .ask(
                new ChatRequest(
                    "Which users have permission to approve payments covering FICC?",
                    List.of(),
                    "policies"),
                subject());

    assertTrue(response.answer().contains("policy directory"));
    assertTrue(response.answer().contains("FUNDING_APPROVER covering desk FICC"));
    assertTrue(response.answer().contains("pay-201"));
    assertTrue(response.answer().contains("User ID"));
    assertEquals("policy_directory", response.routing().path());
    assertEquals("policy_directory_api", response.routing().answer_synthesis());
  }

  @Test
  void policySummaryLaneFormatsInstructionApproval() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("policy_summary");
    decision.setPolicyDomain("instruction");
    decision.setPolicyAction("APPROVE");
    when(callResponseSpec.entity(eq(RouterDecision.class))).thenReturn(decision);

    FakeEligibilityClient eligibilityClient =
        new FakeEligibilityClient()
            .returning(
                Map.of(
                    "domain",
                    "instruction",
                    "action",
                    "APPROVE",
                    "title",
                    "Instruction approval",
                    "narrative",
                    "Someone with the INSTRUCTION_APPROVER role may approve — subject to "
                        + "four-eyes and reporting-line checks and the approval matrix.",
                    "requires",
                    List.of(
                        Map.of("kind", "role", "value", "INSTRUCTION_APPROVER"),
                        Map.of("kind", "sod", "value", "approver is not the instruction creator")),
                    "source",
                    "opa"));

    ChatResponse response =
        chatService(eligibilityClient)
            .ask(
                new ChatRequest("What is the instruction approval policy?", List.of(), "policies"),
                subject());

    assertTrue(response.answer().contains("Instruction approval"));
    assertTrue(response.answer().contains("INSTRUCTION_APPROVER"));
    assertTrue(response.answer().contains("authorization-service"));
    assertTrue(response.answer().contains("`INSTRUCTION_APPROVER`"));
    assertEquals("policy_summary", response.routing().path());
    assertEquals("eligibility_api", response.routing().answer_synthesis());
    assertEquals("eligibility", response.routing().retrieval_strategy());
  }

  @Test
  void policySummaryLaneFormatsPaymentFundingApproval() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("policy_summary");
    decision.setPolicyDomain("payment");
    decision.setPolicyAction("APPROVE");
    when(callResponseSpec.entity(eq(RouterDecision.class))).thenReturn(decision);

    FakeEligibilityClient eligibilityClient =
        new FakeEligibilityClient()
            .returning(
                Map.of(
                    "domain",
                    "payment",
                    "action",
                    "APPROVE",
                    "title",
                    "Funding approval",
                    "narrative",
                    "Someone with the FUNDING_APPROVER role in MIDDLE_OFFICE may approve — "
                        + "subject to four-eyes and reporting-line checks.",
                    "requires",
                    List.of(
                        Map.of("kind", "role", "value", "FUNDING_APPROVER"),
                        Map.of("kind", "sod", "value", "approver is not the payment creator")),
                    "source",
                    "opa"));

    ChatResponse response =
        chatService(eligibilityClient)
            .ask(
                new ChatRequest("What is the funding approval policy?", List.of(), "policies"),
                subject());

    assertTrue(response.answer().contains("Funding approval"));
    assertTrue(response.answer().contains("FUNDING_APPROVER"));
    assertTrue(response.answer().contains("authorization-service"));
    assertEquals("policy_summary", response.routing().path());
    assertEquals("eligibility_api", response.routing().answer_synthesis());
  }

  @Test
  void whoAmILaneFormatsIdentityTokens() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("me");
    decision.setMeKind("who_am_i");
    when(callResponseSpec.entity(eq(RouterDecision.class))).thenReturn(decision);

    Subject pay205 =
        new Subject(
            "pay-205",
            "Fatima",
            "Al-Rashid",
            "Vice President",
            null,
            List.of("PAYMENT_CREATOR", "FUNDING_APPROVER"),
            List.of("MIDDLE_OFFICE", "UP_TO_1_BILLION_CLUB"),
            "pay-300",
            List.of("FICC"),
            "tok",
            "sess");

    ChatResponse response =
        chatService(new FakeEligibilityClient())
            .ask(new ChatRequest("Who am I?", List.of(), "all"), pay205);

    assertTrue(response.answer().contains("pay-205"));
    assertTrue(response.answer().contains("**Roles:**"));
    assertTrue(response.answer().contains("`PAYMENT_CREATOR`"));
    assertTrue(response.answer().contains("`FUNDING_APPROVER`"));
    assertTrue(response.answer().contains("**Amount clubs:**"));
    assertTrue(response.answer().contains("`UP_TO_1_BILLION_CLUB`"));
    assertTrue(response.answer().contains("`MIDDLE_OFFICE`"));
    assertTrue(!response.answer().contains("PAYMENTCREATOR"));
    assertEquals("eligibility", response.routing().path());
    assertEquals("formatter", response.routing().answer_synthesis());
    assertEquals("me.who_am_i", response.routing().intent_id());
  }
}
