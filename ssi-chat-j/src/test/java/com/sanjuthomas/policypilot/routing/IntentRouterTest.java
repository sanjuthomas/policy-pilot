package com.sanjuthomas.policypilot.routing;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;

import com.sanjuthomas.policypilot.pipeline.RouterDecision;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.ai.chat.client.ChatClient;

@ExtendWith(MockitoExtension.class)
class IntentRouterTest {

  @Mock ChatClient.Builder chatClientBuilder;
  @Mock ChatClient chatClient;
  @Mock ChatClient.ChatClientRequestSpec requestSpec;
  @Mock ChatClient.CallResponseSpec callResponseSpec;

  private IntentRouter intentRouter;

  @BeforeEach
  void setUp() {
    when(chatClientBuilder.build()).thenReturn(chatClient);
    when(chatClient.prompt()).thenReturn(requestSpec);
    when(requestSpec.system(anyString())).thenReturn(requestSpec);
    when(requestSpec.user(anyString())).thenReturn(requestSpec);
    when(requestSpec.call()).thenReturn(callResponseSpec);
    intentRouter = new IntentRouter(chatClientBuilder);
  }

  @Test
  void routeReturnsStructuredDecision() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("eligibility");
    decision.setEligibilityTarget("payment");
    decision.setEligibilityAction("APPROVE");
    when(callResponseSpec.entity(eq(RouterDecision.class))).thenReturn(decision);

    RouterDecision result = intentRouter.route("Who can approve payment PAY-1?");

    assertEquals("eligibility", result.getPath());
    assertEquals("payment", result.getEligibilityTarget());
  }

  @Test
  void routeTreatsNullQuestionAsEmpty() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("skill");
    when(callResponseSpec.entity(eq(RouterDecision.class))).thenReturn(decision);

    assertEquals("skill", intentRouter.route(null).getPath());
  }

  @Test
  void routeFailsWhenModelReturnsNull() {
    when(callResponseSpec.entity(eq(RouterDecision.class))).thenReturn(null);

    assertThrows(IllegalStateException.class, () -> intentRouter.route("hello"));
  }

  @Test
  void routeDoesNotPhraseClampPastWhoApprovedWithoutLlmFacet() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("eligibility");
    decision.setEligibilityTarget("payment");
    decision.setEligibilityAction("APPROVE");
    when(callResponseSpec.entity(eq(RouterDecision.class))).thenReturn(decision);

    RouterDecision result = intentRouter.route("Who approved 20260720-FICC-P-19?");

    assertEquals("eligibility", result.getPath());
  }

  @Test
  void routeClampsWhenLlmSetApproverFacetOnWrongPath() {
    RouterDecision decision = new RouterDecision();
    decision.setPath("eligibility");
    decision.setEligibilityTarget("payment");
    decision.setEligibilityAction("APPROVE");
    decision.setExtractionFacet("approver");
    when(callResponseSpec.entity(eq(RouterDecision.class))).thenReturn(decision);

    RouterDecision result = intentRouter.route("Who approved 20260720-FICC-P-19?");

    assertEquals("document_extraction", result.getPath());
    assertEquals("approver", result.getExtractionFacet());
  }

  @Test
  void routePropagatesRuntimeFailures() {
    when(callResponseSpec.entity(eq(RouterDecision.class)))
        .thenThrow(new IllegalStateException("model down"));

    assertThrows(IllegalStateException.class, () -> intentRouter.route("hello"));
  }
}
