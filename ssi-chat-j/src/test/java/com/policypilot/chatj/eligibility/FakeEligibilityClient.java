package com.policypilot.chatj.eligibility;

import com.policypilot.chatj.TestFixtures;
import com.policypilot.chatj.auth.ServiceIdentity;
import java.util.HashMap;
import java.util.Map;
import org.springframework.web.client.RestTemplate;

/** Test double for {@link EligibilityClient}. */
public class FakeEligibilityClient extends EligibilityClient {

  private Map<String, Object> response = Map.of();
  private RuntimeException error;

  public FakeEligibilityClient() {
    super(
        new RestTemplate(),
        TestFixtures.properties(),
        new ServiceIdentity(
            new com.policypilot.chatj.auth.FakeZitadelAuthClient(), TestFixtures.properties()));
  }

  public FakeEligibilityClient returning(Map<String, Object> response) {
    this.response = response;
    return this;
  }

  public FakeEligibilityClient failing(RuntimeException error) {
    this.error = error;
    return this;
  }

  @Override
  public Map<String, Object> eligibleApproversForPayment(
      String paymentId, String userBearerToken, String userSessionId) {
    if (error != null) {
      throw error;
    }
    return new HashMap<>(response);
  }

  @Override
  public Map<String, Object> eligibleSubmittersForPayment(
      String paymentId, String userBearerToken, String userSessionId) {
    if (error != null) {
      throw error;
    }
    return new HashMap<>(response);
  }
}
