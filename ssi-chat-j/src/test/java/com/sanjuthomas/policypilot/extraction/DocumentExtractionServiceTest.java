package com.sanjuthomas.policypilot.extraction;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.eligibility.FakeEligibilityClient;
import com.sanjuthomas.policypilot.formatting.AnswerRenderer;
import com.sanjuthomas.policypilot.formatting.AnswerTemplateConfig;
import com.sanjuthomas.policypilot.formatting.MoneyFormat;
import com.sanjuthomas.policypilot.formatting.PolicyBasisFormat;
import com.sanjuthomas.policypilot.formatting.TimestampFormat;
import com.sanjuthomas.policypilot.instruction.InstructionDetailAnswerFormatter;
import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class DocumentExtractionServiceTest {

  private DocumentExtractionService service;
  private FakeEligibilityClient client;

  @BeforeEach
  void setUp() {
    AnswerRenderer renderer =
        new AnswerRenderer(
            new AnswerTemplateConfig().answerTemplateEngine(),
            new MoneyFormat(),
            new PolicyBasisFormat());
    client = new FakeEligibilityClient();
    service =
        new DocumentExtractionService(
            client,
            new InstructionDetailAnswerFormatter(renderer, new TimestampFormat()),
            new PaymentDetailAnswerFormatter(renderer, new MoneyFormat(), new TimestampFormat()),
            new EntityApiAnswerFormatter(renderer, new PolicyBasisFormat()));
  }

  @Test
  void formatsPaymentStatusFromApi() {
    client.returning(
        Map.of(
            "payment_id",
            "20260720-FICC-P-1",
            "status",
            "APPROVED",
            "owning_lob",
            "FICC",
            "created_by",
            Map.of("user_id", "mo-050", "given_name", "David", "family_name", "Okonkwo")));
    RouterDecision decision = new RouterDecision();
    decision.setPath("document_extraction");
    decision.setExtractionTarget("payment");
    decision.setExtractionFacet("status");

    DocumentExtractionResult result =
        service.answer(
            "What is the status of payment 20260720-FICC-P-1?", subject(), decision);

    assertEquals("payment.status_by_id", result.intentId());
    assertTrue(result.answer().contains("APPROVED"));
    assertTrue(result.answer().contains("20260720-FICC-P-1"));
  }

  @Test
  void listsApprovedInstructionsFromApi() {
    client.returning(
        Map.of(
            "instructions",
            List.of(
                Map.of(
                    "instruction_id",
                    "20260720-FICC-I-1",
                    "status",
                    "APPROVED",
                    "owning_lob",
                    "FICC",
                    "currency",
                    "USD",
                    "created_by",
                    Map.of("user_id", "mo-050", "given_name", "David", "family_name", "Okonkwo"),
                    "approved_by",
                    Map.of(
                        "user_id",
                        "ficc-500",
                        "given_name",
                        "Caroline",
                        "family_name",
                        "Nguyen")))));

    RouterDecision decision = new RouterDecision();
    decision.setExtractionFacet("list_by_status");
    decision.setEntityStatus("APPROVED");
    DocumentExtractionResult result =
        service.answer("Can you list all paused instructions?", subject(), decision);

    assertEquals("instruction.list_by_status", result.intentId());
    assertTrue(result.answer().contains("Found 1 instruction"));
    assertTrue(result.answer().contains("20260720-FICC-I-1"));
  }

  @Test
  void listsInstructionVersionsFromApi() {
    client.returning(
        Map.of(
            "versions",
            List.of(
                Map.of(
                    "version_number",
                    1,
                    "status",
                    "APPROVED",
                    "created_at",
                    "2026-07-01T00:00:00",
                    "created_by",
                    Map.of("user_id", "mo-050"),
                    "approved_by",
                    Map.of("user_id", "ficc-500")))));

    RouterDecision decision = new RouterDecision();
    decision.setExtractionTarget("instruction");
    decision.setExtractionFacet("versions");
    DocumentExtractionResult result =
        service.answer(
            "List all versions of instruction 20260720-FICC-I-1", subject(), decision);

    assertEquals("instruction.versions_by_id", result.intentId());
    assertTrue(result.answer().contains("versions (1)"));
    assertTrue(result.answer().contains("APPROVED"));
  }

  @Test
  void formatsPaymentApproverFromApiLifecycle() {
    client.returning(
        Map.of(
            "payment_id",
            "20260720-FICC-P-1",
            "status",
            "APPROVED",
            "approved_by",
            Map.of(
                "user_id",
                "pay-201",
                "given_name",
                "Sophie",
                "family_name",
                "Laurent",
                "roles",
                List.of("FUNDING_APPROVER")),
            "approved_at",
            "2026-07-20T01:19:04.508813Z",
            "lifecycle_events",
            List.of(
                Map.of(
                    "action",
                    "APPROVE",
                    "details",
                    Map.of(
                        "authorization",
                        Map.of(
                            "summary",
                            "Laurent, Sophie (pay-201) was allowed to APPROVE because role FUNDING_APPROVER",
                            "allow_basis",
                            List.of("role FUNDING_APPROVER")))))));

    RouterDecision decision = new RouterDecision();
    decision.setExtractionTarget("payment");
    decision.setExtractionFacet("approver");
    DocumentExtractionResult result =
        service.answer(
            "Who approved payment 20260720-FICC-P-1 and why?", subject(), decision);

    assertEquals("payment.approver_by_id", result.intentId());
    assertTrue(result.answer().contains("Payment: 20260720-FICC-P-1"));
    assertTrue(result.answer().contains("WHO: Laurent, Sophie (pay-201)"));
    assertTrue(result.answer().contains("FUNDING_APPROVER"));
    assertTrue(result.answer().contains("allowed"));
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
}
