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
import com.policypilot.chatj.pipeline.RouterDecision;
import com.policypilot.chatj.routing.IntentRouter;
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
  private IntentRouter intentRouter;

  @BeforeEach
  void setUp() {
    when(chatClientBuilder.build()).thenReturn(chatClient);
    when(chatClient.prompt()).thenReturn(requestSpec);
    when(requestSpec.system(anyString())).thenReturn(requestSpec);
    when(requestSpec.user(anyString())).thenReturn(requestSpec);
    when(requestSpec.call()).thenReturn(callResponseSpec);
    intentRouter = new IntentRouter(chatClientBuilder);
    AnswerRenderer renderer = new AnswerRenderer(new AnswerTemplateConfig().answerTemplateEngine());
    eligibilityAnswerFormatter = new EligibilityAnswerFormatter(renderer);
  }

  private ChatService chatService(FakeEligibilityClient eligibilityClient) {
    return new ChatService(intentRouter, eligibilityClient, eligibilityAnswerFormatter);
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
        new FakeEligibilityClient().returning(Map.of("payment_id", "PAY-1"));
    ChatService chatService = chatService(eligibilityClient);

    ChatResponse response =
        chatService.ask(new ChatRequest("Who can approve payment PAY-1?", List.of(), "policies"), subject());

    assertTrue(response.answer().contains("Live OPA"));
    assertEquals("eligibility", response.routing().path());
    assertEquals("eligibility_api", response.routing().answer_synthesis());
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

    assertTrue(response.answer().contains("M1 only"));
    assertEquals("stub", response.routing().answer_synthesis());
  }
}
