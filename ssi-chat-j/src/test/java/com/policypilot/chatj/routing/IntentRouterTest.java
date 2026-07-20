package com.policypilot.chatj.routing;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.policypilot.chatj.pipeline.RouterDecision;
import java.util.Optional;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.ObjectProvider;

class IntentRouterTest {

  private final IntentRouter router = new IntentRouter(new EmptyProvider<>());

  @Test
  void routesWhoCanApprovePayment() {
    RouterDecision decision =
        router.route("Who can approve payment PAY-abc123?");
    assertEquals("eligibility", decision.getPath());
    assertEquals("payment", decision.getEligibilityTarget());
    assertEquals("APPROVE", decision.getEligibilityAction());
    assertEquals(Optional.of("PAY-abc123"), router.extractPaymentId("Who can approve payment PAY-abc123?"));
  }

  @Test
  void heuristicOptionalPresent() {
    assertTrue(router.heuristicEligibility("Who can approve payment PAY-1?").isPresent());
  }

  private static final class EmptyProvider<T> implements ObjectProvider<T> {
    @Override
    public T getObject() {
      return null;
    }

    @Override
    public T getObject(Object... args) {
      return null;
    }

    @Override
    public T getIfAvailable() {
      return null;
    }

    @Override
    public T getIfUnique() {
      return null;
    }
  }
}
