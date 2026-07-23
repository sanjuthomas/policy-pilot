package com.sanjuthomas.policypilot.me;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.sanjuthomas.policypilot.TestFixtures;
import com.sanjuthomas.policypilot.auth.ChatUsersDirectory;
import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.eligibility.FakeEligibilityClient;
import com.sanjuthomas.policypilot.formatting.AnswerRenderer;
import com.sanjuthomas.policypilot.formatting.AnswerTemplateConfig;
import com.sanjuthomas.policypilot.formatting.IdentityTokenFormat;
import com.sanjuthomas.policypilot.formatting.MoneyFormat;
import com.sanjuthomas.policypilot.formatting.PolicyBasisFormat;
import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class MeIntentServiceTest {

  private MeIntentService service;
  private FakeEligibilityClient eligibilityClient;

  @BeforeEach
  void setUp() {
    AnswerRenderer renderer =
        new AnswerRenderer(
            new AnswerTemplateConfig().answerTemplateEngine(),
            new MoneyFormat(),
            new PolicyBasisFormat());
    IdentityTokenFormat tokens = new IdentityTokenFormat();
    ChatUsersDirectory directory = new ChatUsersDirectory(TestFixtures.properties());
    eligibilityClient = new FakeEligibilityClient();
    service =
        new MeIntentService(
            new MeIntentResolver(),
            new WhoAmIService(renderer, tokens),
            new MyPermissionsService(renderer, tokens),
            new CanActOnEntityService(renderer, tokens),
            new WhoCanCreateService(directory, renderer, tokens),
            new WhoCoversLobService(directory, renderer, tokens),
            new UsersLikeMeService(directory, renderer, tokens),
            new WaitingForMeService(eligibilityClient, renderer),
            new WhoElseCanActService(eligibilityClient, renderer));
  }

  @Test
  void myPermissionsForPay205() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("me");
    decision.setMeKind("my_permissions");
    MeIntentResult result = service.answer(decision, "What are my permissions?", pay205());
    assertEquals("me.my_permissions", result.intentId());
    assertTrue(result.answer().contains("**Roles:**"));
    assertTrue(result.answer().contains("`PAYMENT_CREATOR`"));
    assertTrue(result.answer().contains("**Derived capabilities:**"));
  }

  @Test
  void canCreatePaymentYes() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("me");
    decision.setMeKind("can_act_on_entity");
    decision.setMeAction("CREATE");
    decision.setMeEntityType("payment");
    MeIntentResult result = service.answer(decision, "Can I create a payment?", pay205());
    assertEquals("me.can_create_payment.yes", result.intentId());
    assertTrue(result.answer().contains("**Yes**"));
  }

  @Test
  void whoCoversFicc() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("me");
    decision.setMeKind("who_covers_lob");
    MeIntentResult result = service.answer(decision, "Who covers LOB FICC?", pay205());
    assertEquals("me.who_covers_lob", result.intentId());
    assertTrue(result.answer().contains("cover LOB FICC"));
    assertTrue(result.answer().contains("pay-"));
  }

  @Test
  void whoCanCreatePaymentsForFicc() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("me");
    decision.setMeKind("who_can_create");
    decision.setMeEntityType("payment");
    MeIntentResult result =
        service.answer(decision, "Who can create payments for FICC?", pay205());
    assertEquals("me.who_can_create.payment", result.intentId());
    assertTrue(result.answer().contains("PAYMENT_CREATOR"));
    assertTrue(result.answer().contains("FICC"));
  }

  @Test
  void usersLikeMe() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("me");
    decision.setMeKind("users_like_me");
    MeIntentResult result = service.answer(decision, "Who is like me?", pay205());
    assertEquals("me.users_like_me", result.intentId());
    assertTrue(result.answer().contains("Users similar to"));
  }

  @Test
  void waitingForMeNotApprover() {
    Subject fo =
        new Subject(
            "fo-fx-101",
            "A",
            "B",
            "Analyst",
            "FX",
            List.of("PAYMENT_CREATOR"),
            List.of(),
            null,
            List.of(),
            "tok",
            "sess");
    RouterDecision decision = new RouterDecision();
    decision.setPath("me");
    decision.setMeKind("waiting_for_me");
    MeIntentResult result =
        service.answer(decision, "What payments are waiting for my approval?", fo);
    assertEquals("me.waiting_for_me.not_approver", result.intentId());
  }

  @Test
  void waitingForMeFound() {
    eligibilityClient.returning(
        Map.of(
            "payments",
            List.of(
                Map.of(
                    "payment_id",
                    "20260705-FICC-P-1",
                    "amount",
                    1000,
                    "currency",
                    "USD",
                    "owning_lob",
                    "FICC",
                    "instruction_id",
                    "20260705-FICC-I-1")),
            "eligible",
            List.of(
                Map.of(
                    "user_id",
                    "pay-205",
                    "display_name",
                    "Al-Rashid, Fatima",
                    "title",
                    "Vice President",
                    "allow_basis",
                    List.of("role ok")))));
    RouterDecision decision = new RouterDecision();
    decision.setPath("me");
    decision.setMeKind("waiting_for_me");
    MeIntentResult result =
        service.answer(decision, "What payments are waiting for my approval?", pay205());
    assertEquals("me.waiting_for_me.found", result.intentId());
    assertTrue(result.answer().contains("20260705-FICC-P-1"));
  }

  @Test
  void whoElseWithoutPaymentIdIsUnresolved() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("me");
    decision.setMeKind("who_else_can_act");
    MeIntentResult result = service.answer(decision, "Who else can approve?", pay205());
    assertEquals("me.unresolved", result.intentId());
  }

  @Test
  void whoElseFoundExcludesSelf() {
    eligibilityClient.returning(
        Map.of(
            "eligible",
            List.of(
                Map.of(
                    "user_id",
                    "pay-205",
                    "display_name",
                    "Al-Rashid, Fatima",
                    "title",
                    "VP",
                    "allow_basis",
                    List.of()),
                Map.of(
                    "user_id",
                    "pay-300",
                    "display_name",
                    "Other, Approver",
                    "title",
                    "MD",
                    "allow_basis",
                    List.of("role ok")))));
    RouterDecision decision = new RouterDecision();
    decision.setPath("me");
    decision.setMeKind("who_else_can_act");
    MeIntentResult result =
        service.answer(decision, "Who else can approve payment 20260705-FX-P-534?", pay205());
    assertEquals("me.who_else_can_act.found", result.intentId());
    assertTrue(result.answer().contains("Other, Approver"));
    assertTrue(result.answer().contains("excluding you"));
    assertTrue(!result.answer().contains("Al-Rashid, Fatima"));
  }

  @Test
  void canApproveInstructionDoesNotReusePaymentAnswer() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("me");
    decision.setMeKind("can_act_on_entity");
    decision.setMeAction("APPROVE");
    decision.setMeEntityType("instruction");
    MeIntentResult result = service.answer(decision, "Can I approve an instruction?", pay205());
    assertEquals("me.can_approve_instruction.no", result.intentId());
    assertTrue(result.answer().contains("INSTRUCTION_APPROVER"));
    assertTrue(result.answer().contains("FUNDING_APPROVER"));
    assertTrue(!result.answer().contains("may **approve** payments"));
  }

  @Test
  void canApproveInstructionYesForDeskApprover() {
    Subject ficc300 =
        new Subject(
            "ficc-300",
            "Elena",
            "Vasquez",
            "Vice President",
            "FICC",
            List.of("INSTRUCTION_APPROVER"),
            List.of(),
            null,
            List.of(),
            "tok",
            "sess");
    RouterDecision decision = new RouterDecision();
    decision.setPath("me");
    decision.setMeKind("can_act_on_entity");
    decision.setMeAction("APPROVE");
    decision.setMeEntityType("instruction");
    MeIntentResult result = service.answer(decision, "Can I approve an instruction?", ficc300);
    assertEquals("me.can_approve_instruction.yes", result.intentId());
    assertTrue(result.answer().contains("FICC"));
    assertTrue(result.answer().contains("INSTRUCTION_APPROVER"));
  }

  @Test
  void canCreateInstructionNoForPay205() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("me");
    decision.setMeKind("can_act_on_entity");
    decision.setMeAction("CREATE");
    decision.setMeEntityType("instruction");
    MeIntentResult result = service.answer(decision, "Can I create an instruction?", pay205());
    assertEquals("me.can_create_instruction.no", result.intentId());
    assertTrue(result.answer().contains("INSTRUCTION_CREATOR"));
    assertTrue(result.answer().contains("PAYMENT_CREATOR"));
  }

  @Test
  void canApprovePaymentStillWorksForPay205() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("me");
    decision.setMeKind("can_act_on_entity");
    decision.setMeAction("APPROVE");
    decision.setMeEntityType("payment");
    MeIntentResult result = service.answer(decision, "Can I approve a payment?", pay205());
    assertEquals("me.can_approve_payment.yes", result.intentId());
    assertTrue(result.answer().toLowerCase().contains("approve") && result.answer().contains("payment"));
  }

  private static Subject pay205() {
    return new Subject(
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
  }
}
