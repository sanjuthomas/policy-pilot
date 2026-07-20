package com.policypilot.chatj.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;

import com.policypilot.chatj.api.ApiModels.ChatRequest;
import com.policypilot.chatj.api.ApiModels.ChatResponse;
import com.policypilot.chatj.auth.Subject;
import com.policypilot.chatj.eligibility.EligibilityAnswerFormatter;
import com.policypilot.chatj.eligibility.FakeEligibilityClient;
import com.policypilot.chatj.formatting.AnswerRenderer;
import com.policypilot.chatj.formatting.AnswerTemplateConfig;
import com.policypilot.chatj.formatting.IdentityTokenFormat;
import com.policypilot.chatj.formatting.MoneyFormat;
import com.policypilot.chatj.formatting.PolicyBasisFormat;
import com.policypilot.chatj.me.WhoAmIService;
import com.policypilot.chatj.observability.ChatAnswerFinalizer;
import com.policypilot.chatj.observability.RoutingDistributionTracker;
import com.policypilot.chatj.observability.RoutingMetrics;
import com.policypilot.chatj.observability.SkillMetrics;
import com.policypilot.chatj.pipeline.RouterDecision;
import com.policypilot.chatj.policydirectory.PolicyDirectoryAnswerFormatter;
import com.policypilot.chatj.policydirectory.PolicyDirectoryService;
import com.policypilot.chatj.policysummary.PolicySummaryAnswerFormatter;
import com.policypilot.chatj.routing.IntentRouter;
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

  private EligibilityAnswerFormatter eligibilityAnswerFormatter;
  private PolicyDirectoryAnswerFormatter policyDirectoryAnswerFormatter;
  private PolicySummaryAnswerFormatter policySummaryAnswerFormatter;
  private WhoAmIService whoAmIService;
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
    policyDirectoryAnswerFormatter = new PolicyDirectoryAnswerFormatter(renderer);
    policySummaryAnswerFormatter =
        new PolicySummaryAnswerFormatter(renderer, identityTokenFormat);
    whoAmIService = new WhoAmIService(identityTokenFormat);
  }

  private ChatService chatService(FakeEligibilityClient eligibilityClient) {
    SimpleMeterRegistry registry = new SimpleMeterRegistry();
    ChatAnswerFinalizer finalizer =
        new ChatAnswerFinalizer(
            new RoutingMetrics(registry, new RoutingDistributionTracker()),
            new SkillMetrics(registry));
    return new ChatService(
        intentRouter,
        eligibilityClient,
        eligibilityAnswerFormatter,
        new PolicyDirectoryService(eligibilityClient, policyDirectoryAnswerFormatter),
        policySummaryAnswerFormatter,
        whoAmIService,
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
    decision.setPath("neo4j_direct");
    when(callResponseSpec.entity(eq(RouterDecision.class))).thenReturn(decision);

    ChatResponse response =
        chatService(new FakeEligibilityClient())
            .ask(new ChatRequest("How many alerts?", List.of(), "events"), subject());

    assertTrue(response.answer().contains("payment/instruction eligibility"));
    assertEquals("stub", response.routing().answer_synthesis());
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
