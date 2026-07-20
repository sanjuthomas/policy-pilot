package com.sanjuthomas.policypilot.eligibility;

import com.sanjuthomas.policypilot.TestFixtures;
import com.sanjuthomas.policypilot.auth.ServiceIdentity;
import java.util.HashMap;
import java.util.Map;
import org.springframework.web.client.RestTemplate;

/** Test double for {@link EligibilityClient}. */
public class FakeEligibilityClient extends EligibilityClient {

  private Map<String, Object> response = Map.of();
  private Map<String, Object> limitsResponse;
  private Map<String, Object> groupMembersResponse;
  private RuntimeException error;

  public FakeEligibilityClient() {
    super(
        new RestTemplate(),
        TestFixtures.properties(),
        new ServiceIdentity(
            new com.sanjuthomas.policypilot.auth.FakeZitadelAuthClient(), TestFixtures.properties()));
  }

  public FakeEligibilityClient returning(Map<String, Object> response) {
    this.response = response;
    return this;
  }

  public FakeEligibilityClient returningLimits(Map<String, Object> limitsResponse) {
    this.limitsResponse = limitsResponse;
    return this;
  }

  public FakeEligibilityClient returningGroupMembers(Map<String, Object> groupMembersResponse) {
    this.groupMembersResponse = groupMembersResponse;
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

  @Override
  public Map<String, Object> eligibleApproversForInstruction(
      String instructionId, String userBearerToken, String userSessionId) {
    if (error != null) {
      throw error;
    }
    return new HashMap<>(response);
  }

  @Override
  public Map<String, Object> paymentAmountLimits(String userBearerToken, String userSessionId) {
    if (error != null) {
      throw error;
    }
    if (limitsResponse != null) {
      return new HashMap<>(limitsResponse);
    }
    return new HashMap<>(response);
  }

  @Override
  public Map<String, Object> groupMembers(
      String group,
      String userBearerToken,
      String userSessionId,
      String role,
      String coveringLob) {
    if (error != null) {
      throw error;
    }
    if (groupMembersResponse != null) {
      return new HashMap<>(groupMembersResponse);
    }
    return new HashMap<>(response);
  }

  @Override
  public Map<String, Object> policySummary(
      String domain, String action, String userBearerToken, String userSessionId) {
    if (error != null) {
      throw error;
    }
    return new HashMap<>(response);
  }

  @Override
  public java.util.List<Map<String, Object>> listPayments(
      String status, int limit, String userBearerToken, String userSessionId) {
    if (error != null) {
      throw error;
    }
    Object list = response.get("payments");
    if (list instanceof java.util.List<?> rows) {
      java.util.List<Map<String, Object>> out = new java.util.ArrayList<>();
      for (Object row : rows) {
        if (row instanceof Map<?, ?> map) {
          @SuppressWarnings("unchecked")
          Map<String, Object> cast = (Map<String, Object>) map;
          out.add(cast);
        }
      }
      return out;
    }
    return java.util.List.of();
  }
}
